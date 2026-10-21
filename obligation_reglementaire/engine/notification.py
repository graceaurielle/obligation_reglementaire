"""Moteur de notifications (Ch11) : règles administrables, destinataires par rôle métier, anti-doublon,
canaux application / e-mail, relances temporelles, escalade, résumé quotidien, journal distinct de l'audit."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, get_url_to_form, getdate, now_datetime

from obligation_reglementaire.engine.common import SystemAction, criticality_weight, get_settings, today_date

PRIORITY_BY_WEIGHT = {4: "Critique", 3: "Élevée", 2: "Normale", 1: "Faible"}
CONFIDENTIAL = ("Strictement confidentiel", "Sensible")

# événements temporels génériques : (doctype, champ date, statuts ouverts)
TEMPORAL = {
	"echeance_approche": ("Reg Deadline", "date_limite", ("À venir", "À traiter", "En cours", "En attente", "Reportée")),
	"echeance_depassee": ("Reg Deadline", "date_limite", ("En retard",)),
	"justificatif_manquant": ("Reg Deadline", "date_limite", ("À venir", "À traiter", "En cours", "En retard")),
	"action_approche": ("Reg Corrective Action", "date_fin_prevue", ("Non commencée", "Planifiée", "En cours", "Bloquée", "Retour pour correction")),
	"action_retard": ("Reg Corrective Action", "date_fin_prevue", ("Non commencée", "Planifiée", "En cours", "Bloquée", "Retour pour correction")),
	"justificatif_expiration_proche": ("Reg Evidence", "date_fin_validite", ("Validé", "Validé avec réserve")),
	"licence_expiration_proche": ("Reg License", "date_expiration", ("Active", "En renouvellement")),
	"efficacite_a_controler": ("Reg Effectiveness Check", "date_prevue", ("Planifiée",)),
}

# objets considérés « résolus » : relances annulées (RG-NOT : une relance s'arrête quand l'action est faite)
RESOLVED = {
	"Reg Deadline": ("Réalisée", "Réalisée en retard", "Clôturée", "Annulée", "Suspendue"),
	"Reg Evidence": ("Validé", "Validé avec réserve", "Archivé", "Annulé", "Remplacé"),
	"Reg Corrective Action": ("Validée", "Annulée"),
	"Reg Action Plan": ("Clôturé", "Annulé"),
	"Reg Non Conformity": ("Clôturée", "Annulée"),
	"Reg Report Instance": ("Clôturé", "Archivé"),
}

ESCALATION_OBJECTS = {
	"Échéance": ("Reg Deadline", "date_limite", ("À venir", "À traiter", "En cours", "En attente", "En retard", "Reportée", "Non conforme"), "criticite", "unite"),
	"Action corrective": ("Reg Corrective Action", "date_fin_prevue", ("Non commencée", "Planifiée", "En cours", "Bloquée", "Retour pour correction"), None, None),
	"Plan d'action": ("Reg Action Plan", "date_cible", ("Ouvert", "En cours", "Bloqué", "En attente de preuves", "Réouvert"), "criticite", "direction"),
	"Non-conformité": ("Reg Non Conformity", "date_cible", ("Ouverte", "En analyse", "En traitement", "Mesure compensatoire en place"), "gravite", "direction"),
	"Justificatif": ("Reg Evidence", "date_limite_resoumission", ("Rejeté", "À compléter"), None, None),
}


# ------------------------------------------------------------------ résolution des destinataires
def _obligation_of(doc):
	if doc.doctype == "Reg Obligation":
		return doc
	name = doc.get("obligation")
	if not name and doc.get("plan"):
		name = frappe.db.get_value("Reg Action Plan", doc.plan, "obligation")
	return frappe.get_cached_doc("Reg Obligation", name) if name else None


def _org_users_with_role(role, org):
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	users = [u for u in users if u not in ("Administrator", "Guest")
		and frappe.db.get_value("User", u, "enabled")]
	if org:
		members = set(frappe.get_all("Reg Member", filters={"organisation": org, "statut": "Actif"}, pluck="utilisateur"))
		users = [u for u in users if u in members]
	return users


def resolve_target(doc, cible, role=None, utilisateur=None):
	org = doc.get("organisation")
	obl = _obligation_of(doc)
	direction = doc.get("direction") or doc.get("unite") or (obl.direction if obl else None)
	owner_field = doc.get("responsable") or doc.get("proprietaire") or doc.get("demandeur") or doc.owner
	if cible == "Responsable de l'objet":
		return [owner_field]
	if cible == "Responsable de l'obligation":
		return [obl.responsable_operationnel or obl.proprietaire] if obl else []
	if cible == "Propriétaire de l'obligation":
		return [obl.proprietaire] if obl else []
	if cible == "Responsable de l'échéance":
		dl = doc.get("echeance") if doc.doctype != "Reg Deadline" else doc.name
		return [frappe.db.get_value("Reg Deadline", dl, "responsable")] if dl else []
	if cible == "Propriétaire du justificatif":
		return [doc.get("responsable"), doc.get("deposant")] if doc.doctype == "Reg Evidence" else []
	if cible == "Contrôleur":
		return [doc.get("controleur") or (obl.controleur if obl else None)]
	if cible == "Validateur":
		return [doc.get("validateur") or doc.get("valideur") or (obl.validateur if obl else None)]
	if cible == "Manager":
		return [frappe.db.get_value("Reg Member", owner_field, "manager")] if owner_field else []
	if cible == "Responsable de la direction":
		return [frappe.db.get_value("Reg Org Unit", direction, "responsable")] if direction else []
	if cible in ("Fonction conformité", "Responsable des risques"):
		return _org_users_with_role("OR Responsable Conformité", org)
	if cible == "Direction Générale":
		return _org_users_with_role("OR Direction Générale", org)
	if cible == "Rôle" and role:
		return _org_users_with_role(role, org)
	if cible == "Utilisateur" and utilisateur:
		return [utilisateur]
	return []


def _with_substitute(users):
	"""Les suppléants des membres désactivés reçoivent les alertes (continuité de service)."""
	out = []
	for u in users:
		if not u:
			continue
		m = frappe.db.get_value("Reg Member", u, ["statut", "suppleant"], as_dict=True)
		if m and m.statut == "Désactivé":
			if m.suppleant:
				out.append(m.suppleant)
			continue
		out.append(u)
	return list(dict.fromkeys(out))


# ------------------------------------------------------------------ rendu
def _title(doc):
	return doc.get(doc.meta.title_field) if doc.meta.title_field else doc.name


def context(doc, extra=None):
	obl = _obligation_of(doc)
	due = doc.get("date_limite") or doc.get("date_fin_prevue") or doc.get("date_cible") or doc.get("date_fin_validite") \
		or doc.get("date_expiration") or doc.get("date_prevue")
	ctx = {
		"doc": doc,
		"reference": doc.name,
		"intitule": _title(doc),
		"responsable": frappe.utils.get_fullname(doc.get("responsable") or doc.get("proprietaire") or doc.owner),
		"date_echeance": frappe.utils.formatdate(due) if due else "",
		"jours_restants": date_diff(due, today_date()) if due else "",
		"direction": doc.get("direction") or doc.get("unite") or (obl.direction if obl else ""),
		"criticite": doc.get("criticite") or doc.get("gravite") or (obl.criticite if obl else ""),
		"statut": doc.get("statut") or "",
		"obligation": obl.titre if obl else "",
		"motif": doc.get("motif_rejet") or doc.get("motif") or doc.get("motif_retour") or "",
		"lien": get_url_to_form(doc.doctype, doc.name),
	}
	ctx.update(extra or {})
	return ctx


def render(template, doc, extra=None):
	ctx = context(doc, extra)
	if not template:
		return _("{0} — {1}").format(_(doc.doctype), ctx["intitule"]), _("<p>Objet : {0}</p>").format(ctx["lien"]), ctx
	try:
		subject = frappe.render_template(template.sujet, ctx)
		body = frappe.render_template(template.corps, ctx)
	except Exception:
		frappe.log_error(title=f"Rendu notification {template.name}")
		subject, body = _("{0} — {1}").format(_(doc.doctype), ctx["intitule"]), ctx["lien"]
	return subject[:140], body, ctx


# ------------------------------------------------------------------ émission
def _rules(event, doc):
	rules = frappe.get_all("Reg Notification Rule", filters={"evenement": event, "statut": "Active"}, pluck="name")
	out = []
	t = today_date()
	for r in rules:
		rule = frappe.get_cached_doc("Reg Notification Rule", r)
		if rule.organisation and doc.get("organisation") and rule.organisation != doc.get("organisation"):
			continue
		if rule.valide_du and getdate(rule.valide_du) > t or rule.valide_au and getdate(rule.valide_au) < t:
			continue
		if rule.criticite_min:
			lvl = doc.get("criticite") or doc.get("gravite") or ((_obligation_of(doc) or frappe._dict()).get("criticite"))
			if criticality_weight(lvl) < criticality_weight(rule.criticite_min):
				continue
		if rule.condition:
			try:
				if not frappe.safe_eval(rule.condition, None, {"doc": doc, "jours": None}):
					continue
			except Exception:
				frappe.log_error(title=f"Condition de notification {rule.name}")
				continue
		out.append(rule)
	return out


def emit(event, doc, extra=None, period=None):
	"""Point d'entrée unique : déclenche toutes les règles actives de l'événement."""
	settings = get_settings()
	if not cint(settings.notifications_actives) or frappe.flags.in_install or frappe.flags.in_migrate:
		return []
	sent = []
	try:
		for rule in _rules(event, doc):
			sent += dispatch(rule, doc, event, extra=extra, period=period)
	except Exception:
		frappe.log_error(title=f"Notification {event} {doc.doctype} {doc.name}")
	return sent


def _priority(rule, doc):
	if cint(rule.priorite_selon_criticite):
		lvl = doc.get("criticite") or doc.get("gravite") or ((_obligation_of(doc) or frappe._dict()).get("criticite"))
		w = criticality_weight(lvl)
		if w:
			return PRIORITY_BY_WEIGHT.get(min(w, 4), rule.priorite)
	return rule.priorite or "Normale"


def dispatch(rule, doc, event, extra=None, period=None, niveau=0, users=None):
	users = users if users is not None else [u for r in rule.destinataires for u in resolve_target(doc, r.cible, r.role, r.utilisateur)]
	users = _with_substitute(users)
	template = frappe.get_cached_doc("Reg Notification Template", rule.modele) if rule.modele else None
	subject, body, ctx = render(template, doc, extra)
	priority = _priority(rule, doc)
	period = period or str(today_date())
	created = []
	for user in users:
		if not frappe.db.get_value("User", user, "enabled"):
			continue
		# RG-NOT : aucune notification ne révèle un objet non autorisé
		if not frappe.has_permission(doc.doctype, "read", doc, user=user):
			continue
		channels = []
		if cint(rule.canal_application):
			channels.append("Application")
		if cint(rule.canal_email) and cint(get_settings().email_actif):
			channels.append("E-mail")
		pref = frappe.db.get_value("Reg Member", user, ["notif_email_informatives", "notif_groupees", "desactiver_categories"], as_dict=True) or {}
		for canal in channels:
			mandatory = cint(rule.obligatoire) or priority in ("Critique", "Élevée")
			if canal == "E-mail" and not mandatory and pref and not cint(pref.get("notif_email_informatives")) \
					and priority in ("Information", "Faible"):
				continue
			if not mandatory and pref and pref.get("desactiver_categories") and \
					any(c.strip().lower() and c.strip().lower() in event for c in pref.get("desactiver_categories").lower().split(",")):
				continue
			key = f"{doc.doctype}|{doc.name}|{event}|{rule.name}|{user}|{canal}|{period}|{niveau}"[:140]
			if frappe.db.exists("Reg Notification Log", {"cle_unicite": key}):
				continue
			grouped = canal == "E-mail" and not mandatory and cint(rule.groupable) and pref and cint(pref.get("notif_groupees"))
			log = frappe.get_doc({
				"doctype": "Reg Notification Log",
				"titre": subject,
				"evenement": event,
				"regle": None if str(rule.name).startswith("ESC:") else rule.name,
				"version_regle": rule.version,
				"modele": rule.modele,
				"organisation": doc.get("organisation"),
				"destinataire": user,
				"canal": canal,
				"priorite": priority,
				"statut": "En attente" if grouped else "Générée",
				"niveau_escalade": niveau,
				"reference_doctype": doc.doctype,
				"reference_name": doc.name,
				"action_attendue": template.action_attendue if template else None,
				"lien": ctx["lien"],
				"cle_unicite": key,
				"date_generation": now_datetime(),
				"message": body,
				"accuse_requis": rule.accuse_requis,
			})
			log.flags.ignore_permissions = True
			log.flags.ignore_links = True
			log.insert()
			if not grouped:
				deliver(log, confidential=(template and cint(template.contenu_confidentiel_email))
					or doc.get("confidentialite") in CONFIDENTIAL)
			created.append(log.name)
	return created


def deliver(log, confidential=False):
	settings = get_settings()
	try:
		if log.canal == "Application":
			frappe.get_doc({
				"doctype": "Notification Log",
				"subject": log.titre,
				"for_user": log.destinataire,
				"type": "Alert",
				"document_type": log.reference_doctype,
				"document_name": log.reference_name,
				"email_content": log.message,
				"from_user": "Administrator",
			}).insert(ignore_permissions=True)
		else:
			email = frappe.db.get_value("User", log.destinataire, "email")
			body = log.message
			if confidential:
				body = _("<p>Une action est attendue de votre part sur un objet confidentiel.</p><p><a href='{0}'>Consulter dans la plateforme</a></p>").format(log.lien)
			frappe.sendmail(recipients=[email], subject=log.titre, message=body,
				reference_doctype=log.reference_doctype, reference_name=log.reference_name, delayed=True)
		_log_update(log.name, statut="Envoyée", date_envoi=now_datetime(), tentatives=cint(log.tentatives) + 1, erreur=None)
	except Exception as e:
		tries = cint(log.tentatives) + 1
		_log_update(log.name, statut="Échouée", tentatives=tries, erreur=str(e)[:500],
			prochaine_tentative=frappe.utils.add_to_date(now_datetime(), hours=1) if tries < cint(settings.max_tentatives_envoi or 3) else None)


def _log_update(name, **values):
	frappe.db.set_value("Reg Notification Log", name, values, update_modified=False)


# ------------------------------------------------------------------ actions utilisateur
@frappe.whitelist()
def accuser_reception(name):
	log = frappe.get_doc("Reg Notification Log", name)
	if log.destinataire != frappe.session.user:
		frappe.throw(_("Seul le destinataire peut accuser réception."), frappe.PermissionError)
	_log_update(name, accuse=1, date_accuse=now_datetime(), lu=1, date_lecture=log.date_lecture or now_datetime(),
		adresse_ip_accuse=getattr(frappe.local, "request_ip", None))
	return True


@frappe.whitelist()
def marquer_lue(name):
	log = frappe.get_doc("Reg Notification Log", name)
	if log.destinataire != frappe.session.user:
		frappe.throw(_("Accès refusé."), frappe.PermissionError)
	_log_update(name, lu=1, date_lecture=now_datetime(), statut="Délivrée" if log.statut == "Envoyée" else log.statut)
	return True


def simulate(rule_name, doctype, name):
	"""Mode simulation (Ch13) : calcule destinataires et message sans rien envoyer."""
	rule = frappe.get_doc("Reg Notification Rule", rule_name)
	doc = frappe.get_doc(doctype, name)
	users = _with_substitute([u for r in rule.destinataires for u in resolve_target(doc, r.cible, r.role, r.utilisateur)])
	template = frappe.get_doc("Reg Notification Template", rule.modele) if rule.modele else None
	subject, body, _ctx = render(template, doc)
	allowed = [u for u in users if frappe.has_permission(doctype, "read", doc, user=u)]
	return {"destinataires": allowed, "exclus_sans_droit": [u for u in users if u not in allowed],
		"sujet": subject, "message": body, "priorite": _priority(rule, doc)}


# ------------------------------------------------------------------ traitements planifiés
def deadline_alerts():
	"""Alertes J-n par échéance selon la liste de l'obligation (ou le paramètre général)."""
	settings = get_settings()
	default = settings.jours_alerte_defaut or "30,15,7,3,1,0"
	t = today_date()
	with SystemAction():
		for d in frappe.get_all("Reg Deadline", filters={"statut": ("in", TEMPORAL["echeance_approche"][2]),
				"date_limite": ("between", (t, add_days(t, 120)))}, fields=["name", "obligation", "date_limite", "dernier_seuil_alerte"]):
			days = date_diff(d.date_limite, t)
			spec = frappe.db.get_value("Reg Obligation", d.obligation, "jours_alerte") or default
			thresholds = sorted({cint(x) for x in spec.replace(";", ",").split(",") if x.strip() != ""}, reverse=True)
			if days not in thresholds:
				continue
			doc = frappe.get_doc("Reg Deadline", d.name)
			emit("echeance_approche", doc, extra={"seuil": days}, period=f"J-{days}")
			if doc.etat_documentaire in ("Aucun justificatif", "Partiellement fourni", "À compléter", "Rejetés"):
				emit("justificatif_manquant", doc, extra={"seuil": days}, period=f"J-{days}")
			frappe.db.set_value("Reg Deadline", d.name, "dernier_seuil_alerte", days, update_modified=False)


def temporal_rules():
	"""Règles en mode « Temporel » : J±n par rapport à une date, avec relances tant que l'objet n'est pas résolu."""
	t = today_date()
	with SystemAction():
		for r in frappe.get_all("Reg Notification Rule", filters={"statut": "Active", "mode": "Temporel"}, pluck="name"):
			rule = frappe.get_cached_doc("Reg Notification Rule", r)
			spec = TEMPORAL.get(rule.evenement)
			if not spec:
				continue
			doctype, field, statuses = spec
			offsets = [0]
			if cint(rule.frequence_relance_jours):
				offsets += [k * cint(rule.frequence_relance_jours) for k in range(1, cint(rule.max_relances or 3) + 1)]
			for k, off in enumerate(offsets):
				target = add_days(t, -(cint(rule.jours_relatifs) + off))
				filters = {field: target, "statut": ("in", statuses)}
				if rule.organisation:
					filters["organisation"] = rule.organisation
				for name in frappe.get_all(doctype, filters=filters, pluck="name"):
					doc = frappe.get_doc(doctype, name)
					if rule.condition:
						try:
							if not frappe.safe_eval(rule.condition, None, {"doc": doc, "jours": date_diff(doc.get(field), t)}):
								continue
						except Exception:
							continue
					dispatch(rule, doc, rule.evenement, period=f"{target}|R{k}")


def cancel_resolved():
	"""Les notifications en attente (groupées) d'objets résolus sont annulées."""
	for log in frappe.get_all("Reg Notification Log", filters={"statut": ("in", ("En attente", "Échouée"))},
			fields=["name", "reference_doctype", "reference_name"]):
		final = RESOLVED.get(log.reference_doctype)
		if final and frappe.db.get_value(log.reference_doctype, log.reference_name, "statut") in final:
			_log_update(log.name, statut="Annulée")


def retry_failed():
	settings = get_settings()
	for name in frappe.get_all("Reg Notification Log", filters={"statut": "Échouée",
			"tentatives": ("<", cint(settings.max_tentatives_envoi or 3)), "prochaine_tentative": ("<=", now_datetime())}, pluck="name"):
		deliver(frappe.get_doc("Reg Notification Log", name))


def escalate():
	"""Escalade par paliers J-n / J+n selon criticité, domaine, direction… (Ch8.20, Ch11.16)."""
	t = today_date()
	with SystemAction():
		for r in frappe.get_all("Reg Escalation Rule", filters={"actif": 1}, pluck="name"):
			rule = frappe.get_cached_doc("Reg Escalation Rule", r)
			spec = ESCALATION_OBJECTS.get(rule.objet)
			if not spec:
				continue
			doctype, field, statuses, crit_field, dir_field = spec
			for step in rule.paliers:
				target = add_days(t, -cint(step.jours_relatifs))
				filters = {field: target, "statut": ("in", statuses)}
				if rule.organisation:
					filters["organisation"] = rule.organisation
				if rule.criticite and crit_field:
					filters[crit_field] = rule.criticite
				if rule.direction and dir_field:
					filters[dir_field] = rule.direction
				if rule.domaine and frappe.get_meta(doctype).has_field("domaine"):
					filters["domaine"] = rule.domaine
				for name in frappe.get_all(doctype, filters=filters, pluck="name"):
					doc = frappe.get_doc(doctype, name)
					if rule.type_obligation:
						obl = _obligation_of(doc)
						if not obl or obl.type_obligation != rule.type_obligation:
							continue
					_escalate_one(rule, step, doc)


def _escalate_one(rule, step, doc):
	users = resolve_target(doc, step.cible, step.role, step.utilisateur)
	pseudo = frappe._dict({
		"name": f"ESC:{rule.name}", "version": 1, "modele": "ESCALADE" if frappe.db.exists("Reg Notification Template", "ESCALADE") else None,
		"canal_application": 1 if step.canal in ("Application + E-mail", "Application") else 0,
		"canal_email": 1 if step.canal in ("Application + E-mail", "E-mail") else 0,
		"priorite": step.priorite or "Élevée", "priorite_selon_criticite": 0, "obligatoire": 1, "groupable": 0,
		"accuse_requis": 1 if (step.priorite or "") == "Critique" else 0, "destinataires": [],
	})
	sign = "+" if cint(step.jours_relatifs) >= 0 else ""
	dispatch(pseudo, doc, "escalade", extra={"niveau": step.niveau, "palier": f"J{sign}{step.jours_relatifs}"},
		period=f"{rule.name}|{step.jours_relatifs}", niveau=cint(step.niveau), users=users)


def daily_digest():
	"""Résumé quotidien par utilisateur : à traiter, retards, contrôles attendus + notifications groupées."""
	settings = get_settings()
	if not cint(settings.resume_quotidien_actif) or not cint(settings.notifications_actives):
		return
	t = today_date()
	for m in frappe.get_all("Reg Member", filters={"statut": "Actif", "resume_quotidien": 1}, fields=["utilisateur"]):
		u = m.utilisateur
		lines = []
		n = frappe.db.count("Reg Deadline", {"responsable": u, "statut": "En retard"})
		if n:
			lines.append(_("{0} échéance(s) en retard").format(n))
		n = frappe.db.count("Reg Deadline", {"responsable": u, "statut": ("in", ("À traiter", "En cours")),
			"date_limite": ("between", (t, add_days(t, 7)))})
		if n:
			lines.append(_("{0} échéance(s) dans les 7 prochains jours").format(n))
		n = frappe.db.count("Reg Evidence", {"controleur": u, "statut": ("in", ("Déposé", "Soumis à nouveau", "En cours de contrôle"))})
		if n:
			lines.append(_("{0} justificatif(s) à contrôler").format(n))
		n = frappe.db.count("Reg Evidence", {"responsable": u, "statut": ("in", ("Rejeté", "À compléter"))})
		if n:
			lines.append(_("{0} justificatif(s) à corriger").format(n))
		n = frappe.db.count("Reg Corrective Action", {"responsable": u, "en_retard": 1, "statut": ("not in", ("Validée", "Annulée"))})
		if n:
			lines.append(_("{0} action(s) corrective(s) en retard").format(n))
		pending = frappe.get_all("Reg Notification Log", filters={"destinataire": u, "statut": "En attente"}, fields=["name", "titre", "lien"])
		if not lines and not pending:
			continue
		body = "<p>" + _("Bonjour,") + "</p><ul>" + "".join(f"<li>{line}</li>" for line in lines) + "</ul>"
		if pending:
			body += "<p>" + _("Notifications regroupées :") + "</p><ul>" + "".join(
				f"<li><a href='{p.lien}'>{frappe.utils.escape_html(p.titre)}</a></li>" for p in pending) + "</ul>"
		key = f"DIGEST|{u}|{t}"
		if frappe.db.exists("Reg Notification Log", {"cle_unicite": key}):
			continue
		log = frappe.get_doc({"doctype": "Reg Notification Log", "titre": _("Résumé quotidien — obligations réglementaires"),
			"evenement": "resume_quotidien", "destinataire": u, "canal": "E-mail", "priorite": "Information",
			"statut": "Générée", "cle_unicite": key, "date_generation": now_datetime(), "message": body,
			"lien": frappe.utils.get_url("/app/obligation-reglementaire")})
		log.flags.ignore_permissions = True
		log.insert()
		deliver(log)
		for p in pending:
			_log_update(p.name, statut="Envoyée", date_envoi=now_datetime())
