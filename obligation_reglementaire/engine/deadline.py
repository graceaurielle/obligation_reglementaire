"""Moteur d'échéances (Ch6) : génération périodique / événementielle idempotente, statuts quotidiens,
état documentaire, suspension, report, clôture."""

from datetime import timedelta

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.utils import add_days, cint, date_diff, get_datetime, getdate, now_datetime

from obligation_reglementaire.engine.calendar import add_delay, describe_delay, get_calendar
from obligation_reglementaire.engine.common import SystemAction, get_settings, log_audit, today_date

OPEN_STATUSES = ("À venir", "À traiter", "En cours", "En attente", "Soumise pour validation", "En retard", "Non conforme", "Reportée")
FINAL_STATUSES = ("Réalisée", "Réalisée en retard", "Clôturée", "Annulée")
DONE_STATUSES = ("Réalisée", "Réalisée en retard", "Clôturée")

DEADLINE_TRANSITIONS = {
	"À venir": {"À traiter", "En cours", "En attente", "Soumise pour validation", "En retard", "Suspendue", "Annulée", "Reportée"},
	"À traiter": {"En cours", "En attente", "Soumise pour validation", "En retard", "Suspendue", "Annulée", "Reportée", "À venir"},
	"En cours": {"En attente", "Soumise pour validation", "En retard", "Suspendue", "Annulée", "Reportée"},
	"En attente": {"En cours", "Soumise pour validation", "En retard", "Suspendue", "Annulée", "Reportée"},
	"Soumise pour validation": {"Réalisée", "Réalisée en retard", "En cours", "Non conforme", "En retard"},
	"En retard": {"En cours", "Soumise pour validation", "Non conforme", "Suspendue", "Annulée", "Reportée"},
	"Non conforme": {"En cours", "Soumise pour validation", "Clôturée", "Annulée", "Reportée"},
	"Reportée": {"À venir", "À traiter", "En cours", "En retard", "Soumise pour validation", "Suspendue", "Annulée"},
	"Suspendue": {"À venir", "À traiter", "En cours", "En retard", "Annulée"},
	"Réalisée": {"Clôturée", "En cours"},
	"Réalisée en retard": {"Clôturée", "En cours"},
	"Clôturée": {"En cours"},
	"Annulée": set(),
}

_STEPS = {
	"Quotidienne": relativedelta(days=1),
	"Hebdomadaire": relativedelta(weeks=1),
	"Mensuelle": relativedelta(months=1),
	"Trimestrielle": relativedelta(months=3),
	"Semestrielle": relativedelta(months=6),
	"Annuelle": relativedelta(years=1),
	"Pluriannuelle": relativedelta(years=2),
}

_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


def period_step(obl):
	if obl.frequence == "Personnalisée":
		n = max(cint(obl.intervalle), 1)
		unit = obl.intervalle_unite or "Mois"
		return {"Jours calendaires": relativedelta(days=n), "Semaines": relativedelta(weeks=n),
			"Mois": relativedelta(months=n), "Années": relativedelta(years=n)}.get(unit, relativedelta(months=n))
	if obl.frequence == "Pluriannuelle" and cint(obl.intervalle):
		return relativedelta(years=cint(obl.intervalle))
	return _STEPS.get(obl.frequence)


def period_start(obl, d):
	"""Aligne le début de période sur la période civile (mois, trimestre, semestre, année, semaine ISO)."""
	d = getdate(d)
	f = obl.frequence
	if f == "Mensuelle":
		return d.replace(day=1)
	if f == "Trimestrielle":
		return d.replace(day=1, month=3 * ((d.month - 1) // 3) + 1)
	if f == "Semestrielle":
		return d.replace(day=1, month=1 if d.month <= 6 else 7)
	if f == "Annuelle":
		return d.replace(day=1, month=1)
	if f == "Hebdomadaire":
		return d - timedelta(days=d.weekday())
	return d


def period_label(obl, start, end):
	f = obl.frequence
	if f == "Mensuelle":
		return f"{_MOIS[start.month - 1].capitalize()} {start.year}"
	if f == "Trimestrielle":
		return f"T{(start.month - 1) // 3 + 1} {start.year}"
	if f == "Semestrielle":
		return f"S{1 if start.month <= 6 else 2} {start.year}"
	if f == "Annuelle":
		return f"Exercice {start.year}" if start.month == 1 else f"{start.year}-{end.year}"
	if f == "Hebdomadaire":
		return f"Semaine {start.isocalendar()[1]} {start.year}"
	if f == "Quotidienne":
		return start.strftime("%d/%m/%Y")
	return f"{start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"


def calc_rule_text(obl):
	cal = obl.calendrier or "calendrier par défaut"
	rule = obl.regle_jour_non_ouvre or "Aucun report"
	if obl.nature_temporelle == "Périodique":
		base = f"Échéance {obl.frequence.lower() if obl.frequence else ''} : fin de période + {describe_delay(obl.delai_valeur, obl.delai_unite)}"
	elif obl.nature_temporelle == "Événementielle":
		base = f"Événement « {obl.evenement_declencheur or '?'} » + {describe_delay(obl.delai_valeur, obl.delai_unite)}"
	elif obl.nature_temporelle in ("Ponctuelle", "Date fixe", "Relative à une date réglementaire"):
		base = f"Date fixe {obl.date_fixe or '?'} + {describe_delay(obl.delai_valeur, obl.delai_unite)}"
	elif obl.nature_temporelle == "Permanente":
		base = "Obligation permanente : pas d'échéance datée, suivie par contrôles de conformité"
	else:
		base = "Échéance conditionnelle : créée manuellement lorsque la condition est remplie"
	return f"{base} — {cal} — jour non ouvré : {rule}"


def obligation_generates(obl):
	return obl.statut == "Active" and obl.applicabilite in ("Applicable", "Applicable sous condition")


def _snapshot(obl, cal):
	return {
		"calendrier": obl.calendrier,
		"fuseau_horaire": cal.fuseau or get_settings().fuseau_horaire,
		"regle_calcul": obl.regle_calcul or calc_rule_text(obl),
		"delai_valeur": obl.delai_valeur,
		"delai_unite": obl.delai_unite,
	}


def create_deadline(obl, key, libelle, date_limite, type_echeance, periode=None, debut=None, fin=None,
		evenement=None, date_reference=None, source_date=None, auto=1):
	if frappe.db.exists("Reg Deadline", {"cle_unicite": key}):
		return None
	cal = get_calendar(obl.calendrier)
	settings = get_settings()
	date_limite = cal.adjust(date_limite, obl.regle_jour_non_ouvre or settings.regle_jour_non_ouvre)
	doc = frappe.get_doc({
		"doctype": "Reg Deadline",
		"organisation": obl.organisation,
		"obligation": obl.name,
		"libelle": libelle,
		"periode": periode,
		"debut_periode": debut,
		"fin_periode": fin,
		"statut": "À venir",
		"date_limite": date_limite,
		"date_limite_initiale": date_limite,
		"heure_limite": obl.heure_limite or cal.heure_limite or settings.heure_limite_defaut,
		"responsable": obl.responsable_operationnel or obl.proprietaire,
		"unite": obl.direction,
		"controleur": obl.controleur,
		"validateur": obl.validateur,
		"type_echeance": type_echeance,
		"evenement": evenement,
		"date_reference": date_reference,
		"source_date": source_date,
		"generee_automatiquement": auto,
		"cle_unicite": key,
		"etat_documentaire": "Aucun justificatif" if obl.justificatif_requis else "Sans justificatif requis",
		**_snapshot(obl, cal),
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_mandatory=True)
	return doc


def generate_for_obligation(obl, horizon_days=None):
	"""Génère les échéances futures d'une obligation jusqu'à l'horizon. Idempotent (clé d'unicité)."""
	if isinstance(obl, str):
		obl = frappe.get_doc("Reg Obligation", obl)
	if not obligation_generates(obl):
		return []
	settings = get_settings()
	horizon = add_days(today_date(), cint(horizon_days or settings.horizon_generation_jours or 400))
	max_n = cint(settings.max_occurrences_generation) or 60
	created = []
	with SystemAction():
		if obl.nature_temporelle == "Périodique":
			step = period_step(obl)
			if not step:
				return []
			start = period_start(obl, obl.date_reference or obl.date_debut)
			end_validity = getdate(obl.date_fin) if obl.date_fin else None
			cal = get_calendar(obl.calendrier)
			for _i in range(2000):
				if len(created) >= max_n:
					break
				fin = start + step - timedelta(days=1)
				if end_validity and start > end_validity:
					break
				date_limite = add_delay(fin, obl.delai_valeur, obl.delai_unite, cal)
				if date_limite > horizon:
					break
				# n'engendre pas d'échéances antérieures au début d'application
				if date_limite >= getdate(obl.date_debut):
					label = period_label(obl, start, fin)
					d = create_deadline(obl, f"{obl.name}|{start}", f"{obl.titre} — {label}", date_limite,
						"Périodique", periode=label, debut=start, fin=fin, date_reference=get_datetime(fin),
						source_date="Fin de période")
					if d:
						created.append(d.name)
				start = start + step
		elif obl.nature_temporelle in ("Ponctuelle", "Date fixe", "Relative à une date réglementaire"):
			ref = obl.date_fixe or obl.date_debut
			if ref:
				date_limite = add_delay(ref, obl.delai_valeur, obl.delai_unite, get_calendar(obl.calendrier))
				d = create_deadline(obl, f"{obl.name}|{ref}", obl.titre, date_limite,
					obl.nature_temporelle, date_reference=get_datetime(ref),
					source_date="Date réglementaire" if obl.nature_temporelle == "Relative à une date réglementaire" else "Date fixe")
				if d:
					created.append(d.name)
		frappe.db.set_value("Reg Obligation", obl.name, "derniere_generation", now_datetime(), update_modified=False)
	if created:
		log_audit("Génération d'échéances", obl, details={"echeances": created})
	return created


def generate_from_event(event):
	"""Crée les échéances des obligations événementielles rattachées au type d'événement (Ch6)."""
	if isinstance(event, str):
		event = frappe.get_doc("Reg Event Occurrence", event)
	if event.statut == "Annulé":
		return []
	ref = event.date_connaissance or event.date_evenement
	obligations = frappe.get_all("Reg Obligation", filters={
		"organisation": event.organisation, "evenement_declencheur": event.type_evenement,
		"nature_temporelle": "Événementielle", "statut": "Active",
		"applicabilite": ("in", ("Applicable", "Applicable sous condition"))}, pluck="name")
	created = []
	with SystemAction():
		for name in obligations:
			obl = frappe.get_doc("Reg Obligation", name)
			date_limite = add_delay(ref, obl.delai_valeur, obl.delai_unite, get_calendar(obl.calendrier))
			d = create_deadline(obl, f"{obl.name}|{event.name}", f"{obl.titre} — {event.libelle}", date_limite,
				"Événementielle", evenement=event.name, date_reference=get_datetime(ref),
				source_date=event.source_date or ("Date de connaissance" if event.date_connaissance else "Date de l'événement"))
			if d:
				created.append(d.name)
		if created:
			frappe.db.set_value("Reg Event Occurrence", event.name, {"nb_echeances": len(created), "statut": "Traité"})
	return created


def cancel_event_deadlines(event, motif):
	for name in frappe.get_all("Reg Deadline", filters={"evenement": event.name, "statut": ("in", OPEN_STATUSES)}, pluck="name"):
		d = frappe.get_doc("Reg Deadline", name)
		d.flags.reg_justification = motif
		d.statut = "Annulée"
		d.motif_annulation = _("Événement annulé : {0}").format(motif)
		d.flags.ignore_permissions = True
		d.save()


# ------------------------------------------------------------------ état documentaire
def compute_doc_state(deadline):
	if isinstance(deadline, str):
		deadline = frappe.get_doc("Reg Deadline", deadline)
	required = frappe.db.get_value("Reg Obligation", deadline.obligation, "justificatif_requis")
	evs = frappe.get_all("Reg Evidence", filters={"echeance": deadline.name, "statut": ("not in", ("Annulé", "Remplacé", "Archivé"))},
		fields=["statut", "obligatoire"])
	if not evs:
		return "Aucun justificatif" if cint(required) else "Sans justificatif requis"
	mandatory = [e for e in evs if cint(e.obligatoire)] or evs
	st = [e.statut for e in mandatory]
	if all(s in ("Validé", "Validé avec réserve") for s in st):
		return "Validés"
	if any(s == "Expiré" for s in st):
		return "Expirés"
	if any(s == "Rejeté" for s in st):
		return "Rejetés"
	if any(s == "À compléter" for s in st):
		return "À compléter"
	if any(s == "En cours de contrôle" for s in st):
		return "Contrôle en cours"
	deposited = [s for s in st if s in ("Déposé", "Soumis à nouveau", "Validé", "Validé avec réserve")]
	if len(deposited) == len(st):
		return "Tous déposés"
	if deposited:
		return "Partiellement fourni"
	return "Aucun justificatif"


def refresh_doc_state(deadline_name):
	if not deadline_name:
		return
	state = compute_doc_state(deadline_name)
	frappe.db.set_value("Reg Deadline", deadline_name, "etat_documentaire", state, update_modified=False)
	return state


def evidence_blockers(deadline):
	"""Éléments documentaires empêchant la soumission / validation de l'échéance."""
	obl = frappe.get_cached_doc("Reg Obligation", deadline.obligation)
	if not cint(obl.justificatif_requis) or cint(deadline.derogation_justificatif):
		return []
	evs = frappe.get_all("Reg Evidence", filters={"echeance": deadline.name, "obligatoire": 1,
		"statut": ("not in", ("Annulé", "Remplacé", "Archivé"))}, fields=["name", "libelle", "statut"])
	if not evs:
		return [_("Aucun justificatif obligatoire n'est rattaché à l'échéance.")]
	return [f"{e.libelle} ({e.statut})" for e in evs
		if e.statut not in ("Déposé", "Soumis à nouveau", "En cours de contrôle", "Validé", "Validé avec réserve")]


def validation_blockers(deadline):
	obl = frappe.get_cached_doc("Reg Obligation", deadline.obligation)
	if not cint(obl.justificatif_requis) or not cint(obl.validation_justificatif_requise) or cint(deadline.derogation_justificatif):
		return []
	evs = frappe.get_all("Reg Evidence", filters={"echeance": deadline.name, "obligatoire": 1,
		"statut": ("not in", ("Annulé", "Remplacé", "Archivé"))}, fields=["libelle", "statut"])
	return [f"{e.libelle} ({e.statut})" for e in evs if e.statut not in ("Validé", "Validé avec réserve")]


# ------------------------------------------------------------------ traitements quotidiens
def update_statuses():
	"""À traiter à J-n, En retard après la date limite, calcul des jours de retard (Ch6)."""
	settings = get_settings()
	t = today_date()
	a_traiter = add_days(t, cint(settings.jours_a_traiter or 30))
	changed = []
	with SystemAction():
		for d in frappe.get_all("Reg Deadline", filters={"statut": ("in", ("À venir", "Reportée")), "date_limite": ("<=", a_traiter)},
				fields=["name", "date_limite"]):
			if getdate(d.date_limite) >= t:
				_set(d.name, "À traiter")
				changed.append(d.name)
		for d in frappe.get_all("Reg Deadline", filters={"statut": ("in", ("À venir", "À traiter", "En cours", "En attente", "Reportée")),
				"date_limite": ("<", t)}, fields=["name"]):
			_set(d.name, "En retard")
			changed.append(d.name)
		# jours de retard (y compris échéances soumises / non conformes non encore clôturées)
		for d in frappe.get_all("Reg Deadline", filters={"statut": ("in", ("En retard", "Soumise pour validation", "Non conforme")),
				"date_limite": ("<", t)}, fields=["name", "date_limite"]):
			frappe.db.set_value("Reg Deadline", d.name, {"en_retard": 1, "jours_retard": date_diff(t, d.date_limite)},
				update_modified=False)
	return changed


def _set(name, statut):
	from obligation_reglementaire.engine import notification

	doc = frappe.get_doc("Reg Deadline", name)
	doc.statut = statut
	if statut == "En retard":
		doc.en_retard = 1
		doc.jours_retard = date_diff(today_date(), doc.date_limite)
	doc.flags.ignore_permissions = True
	doc.save()
	if statut == "En retard":
		notification.emit("echeance_depassee", doc)


def create_overdue_nc():
	"""Proposition automatique de non-conformité pour les échéances en retard au-delà du seuil (Ch6/Ch8)."""
	from obligation_reglementaire.engine.action_plan import create_nc

	settings = get_settings()
	if not cint(settings.nc_auto_sur_retard):
		return
	limit = add_days(today_date(), -cint(settings.jours_retard_nc or 5))
	for d in frappe.get_all("Reg Deadline", filters={"statut": "En retard", "date_limite": ("<", limit),
			"non_conformite": ("is", "not set")}, fields=["name"]):
		dl = frappe.get_doc("Reg Deadline", d.name)
		nc = create_nc(origine="Retard d'échéance", intitule=_("Retard : {0}").format(dl.libelle),
			description=_("L'échéance {0} est en retard de {1} jour(s) (date limite {2}).").format(
				dl.name, dl.jours_retard, frappe.utils.formatdate(dl.date_limite)),
			obligation=dl.obligation, echeance=dl.name, organisation=dl.organisation,
			responsable=dl.responsable, gravite=dl.criticite, event=dl)
		frappe.db.set_value("Reg Deadline", dl.name, "non_conformite", nc.name, update_modified=False)


def regenerate_all():
	for name in frappe.get_all("Reg Obligation", filters={"statut": "Active", "nature_temporelle": ("in",
			("Périodique", "Ponctuelle", "Date fixe", "Relative à une date réglementaire"))}, pluck="name"):
		try:
			generate_for_obligation(name)
		except Exception:
			frappe.log_error(title=f"Génération d'échéances {name}")


# ------------------------------------------------------------------ actions métier
def update_obligation_compliance(obligation):
	"""Dernière échéance clôturée = état de conformité de l'obligation (non évalué tant qu'aucune n'est évaluée)."""
	last = frappe.get_all("Reg Deadline", filters={"obligation": obligation, "statut": ("in", DONE_STATUSES + ("Non conforme",))},
		fields=["statut", "resultat_controle"], order_by="date_limite desc", limit=1)
	if not last:
		return
	l = last[0]
	if l.statut == "Non conforme" or l.resultat_controle in ("Non conforme", "Justificatif insuffisant"):
		state = "Non conforme"
	elif l.statut == "Réalisée en retard" or l.resultat_controle in ("Conforme avec observation", "Incomplet"):
		state = "Partiellement conforme"
	else:
		state = "Conforme"
	frappe.db.set_value("Reg Obligation", obligation, "etat_conformite", state)


def suspend(deadline, motif, date_fin_prevue=None, autorite=None, justificatif=None):
	if deadline.statut in FINAL_STATUSES or deadline.statut == "Suspendue":
		frappe.throw(_("Cette échéance ne peut pas être suspendue dans son état actuel."))
	remaining = date_diff(deadline.date_limite, today_date())
	sus = frappe.get_doc({"doctype": "Reg Deadline Suspension", "echeance": deadline.name, "motif": motif,
		"date_debut": today_date(), "date_fin_prevue": date_fin_prevue, "jours_restants": remaining,
		"responsable": frappe.session.user, "autorite_autorisant": autorite, "justificatif": justificatif})
	sus.insert(ignore_permissions=True)
	deadline.statut_avant_suspension = deadline.statut
	deadline.jours_restants_suspension = remaining
	deadline.suspendue = 1
	deadline.statut = "Suspendue"
	deadline.flags.reg_justification = motif
	deadline.flags.ignore_permissions = True
	deadline.save()
	return sus


def resume(deadline):
	"""Levée de suspension : la date limite est recalculée avec le temps restant conservé (Ch6)."""
	if deadline.statut != "Suspendue":
		frappe.throw(_("L'échéance n'est pas suspendue."))
	sus_name = frappe.db.get_value("Reg Deadline Suspension", {"echeance": deadline.name, "statut": "Active"}, "name")
	remaining = max(cint(deadline.jours_restants_suspension), 0)
	new_date = get_calendar(deadline.calendrier).adjust(add_days(today_date(), remaining),
		frappe.db.get_value("Reg Obligation", deadline.obligation, "regle_jour_non_ouvre"))
	if sus_name:
		frappe.db.set_value("Reg Deadline Suspension", sus_name, {"statut": "Levée", "date_fin_effective": today_date(),
			"nouvelle_date_limite": new_date})
	old = deadline.date_limite
	deadline.date_limite = new_date
	deadline.suspendue = 0
	prev = deadline.statut_avant_suspension or "À venir"
	deadline.statut = prev if prev in DEADLINE_TRANSITIONS["Suspendue"] else "À venir"
	deadline.flags.reg_justification = _("Levée de suspension")
	deadline.flags.ignore_permissions = True
	deadline.save()
	log_audit("Levée de suspension", deadline, champ="date_limite", ancienne=old, nouvelle=new_date)
	return deadline


def apply_change(change):
	"""Applique un report métier / une correction technique approuvé(e) — l'ancienne date reste historisée."""
	dl = frappe.get_doc("Reg Deadline", change.echeance)
	old = dl.date_limite
	dl.date_limite = change.nouvelle_date
	if change.type_modification == "Report métier" and dl.statut not in FINAL_STATUSES:
		dl.statut = "Reportée"
		dl.en_retard = 0
		dl.jours_retard = 0
	dl.flags.reg_justification = change.motif
	dl.flags.reg_force_transition = True
	dl.flags.ignore_permissions = True
	frappe.flags.reg_force_transition = True
	try:
		dl.save()
	finally:
		frappe.flags.reg_force_transition = False
	log_audit(change.type_modification, dl, champ="date_limite", ancienne=old, nouvelle=change.nouvelle_date,
		justification=change.motif)
	return dl
