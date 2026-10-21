"""Applicabilité (Ch4) : évaluation du profil réglementaire contre les règles du catalogue, propositions avec niveau de
confiance, décisions motivées, génération des obligations depuis les modèles, notices de mise à jour des modèles."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from obligation_reglementaire.engine.common import SystemAction, assert_sod, log_audit, require_text

TEMPLATE_ACTIVE = ("Validé", "Actif")


def _profile_value(profile, criterion):
	"""Valeur d'un critère : réponse explicite au questionnaire, sinon champ du profil portant le code du critère."""
	for a in profile.reponses or []:
		if a.critere == criterion:
			return a.reponse, True
	code = (frappe.db.get_value("Reg Applicability Criterion", criterion, "code") or criterion).lower()
	if code in ("activite", "activites"):
		return [r.activite for r in profile.activites or []], True
	if code in ("pays", "pays_implantation"):
		return [r.pays for r in profile.pays_implantation or []], True
	if profile.meta.has_field(code):
		val = profile.get(code)
		return val, val not in (None, "")
	return None, False


def _truthy(v):
	return str(v).strip().lower() in ("1", "oui", "yes", "true", "vrai", "o")


def _compare(value, op, expected):
	if op == "est renseigné":
		return value not in (None, "", [], 0)
	if isinstance(value, list):
		if op in ("=", "contient"):
			return expected in value
		if op == "!=":
			return expected not in value
		value = len(value)
	if op == "contient":
		return (expected or "").lower() in str(value or "").lower()
	if expected is not None and str(expected).strip().lower() in ("oui", "non", "true", "false", "1", "0"):
		eq = _truthy(value) == _truthy(expected)
		return eq if op == "=" else (not eq if op == "!=" else False)
	try:
		v, e = flt(value), flt(expected)
		numeric = True
	except Exception:
		numeric = False
	if op in (">", ">=", "<", "<=") and numeric:
		return {">": v > e, ">=": v >= e, "<": v < e, "<=": v <= e}[op]
	if op == "=":
		return str(value or "").strip().lower() == str(expected or "").strip().lower()
	if op == "!=":
		return str(value or "").strip().lower() != str(expected or "").strip().lower()
	return False


def evaluate_template(profile, tpl):
	"""Retourne (état proposé, confiance, critères satisfaits, critères non satisfaits)."""
	ok, ko, unknown = [], [], []
	sectors = {tpl.secteur_principal} | {s.secteur for s in tpl.secteurs or []}
	sectors.discard(None)
	if sectors:
		label = _("Secteur {0}").format(", ".join(sorted(sectors)))
		(ok if profile.secteur in sectors else ko).append(label)
	blocking = False
	for r in tpl.regles or []:
		label = r.description or f"{r.critere or r.agrement} {r.operateur or ''} {r.valeur or ''}".strip()
		if r.type_condition == "Agrément requis":
			held = any(_truthy(a.reponse) and (a.libelle or "").lower() == (r.agrement or "").lower() for a in profile.reponses or []) \
				or any((frappe.db.get_value("Reg Activity", a.activite, "agrement_requis") or "").lower() == (r.agrement or "").lower()
					for a in profile.activites or [])
			(ok if held else ko).append(_("Agrément « {0} »").format(r.agrement))
			blocking = blocking or not held
			continue
		value, known = _profile_value(profile, r.critere)
		if not known:
			unknown.append(label)
			continue
		res = _compare(value, r.operateur or "=", r.valeur)
		if r.type_condition == "Négative":
			res = not res
		(ok if res else ko).append(label)
		if not res and r.type_condition in ("Positive", "Négative", "Seuil"):
			blocking = True
	if sectors and profile.secteur not in sectors:
		blocking = True
	if blocking:
		etat = "Non applicable" if not unknown else "Potentiellement applicable"
	elif unknown:
		etat = "Potentiellement applicable"
	else:
		etat = "Applicable"
	total = len(ok) + len(ko) + len(unknown)
	ratio = (len(ok) + len(ko)) / total if total else 0
	confiance = "Élevé" if ratio >= 0.9 and total else ("Moyen" if ratio >= 0.5 else "Faible")
	if not tpl.regles and not sectors:
		etat, confiance = "Potentiellement applicable", "Faible"
	return etat, confiance, ok, ko + [_("Non renseigné : {0}").format(u) for u in unknown]


def evaluate_profile(profile_name):
	"""Évalue le profil validé contre tous les modèles actifs et crée / actualise les propositions."""
	profile = frappe.get_doc("Reg Profile", profile_name)
	if profile.statut != "Validé":
		frappe.throw(_("Le profil réglementaire doit être validé avant l'évaluation."))
	created = updated = 0
	for tname in frappe.get_all("Reg Template Obligation", filters={"statut": ("in", TEMPLATE_ACTIVE)}, pluck="name"):
		tpl = frappe.get_cached_doc("Reg Template Obligation", tname)
		if tpl.date_fin and getdate(tpl.date_fin) < getdate(today()):
			continue
		etat, conf, ok, ko = evaluate_template(profile, tpl)
		existing = frappe.db.get_value("Reg Applicability Proposal", {"profil": profile.name, "modele": tname,
			"statut": ("in", ("Proposée", "En analyse"))}, "name")
		if existing:
			frappe.db.set_value("Reg Applicability Proposal", existing, {"etat_propose": etat, "score_confiance": conf,
				"criteres_satisfaits": "\n".join(ok), "criteres_non_satisfaits": "\n".join(ko)})
			updated += 1
			continue
		if frappe.db.exists("Reg Applicability Proposal", {"profil": profile.name, "modele": tname,
				"statut": ("in", ("Validée", "Générée", "Rejetée"))}):
			continue
		if etat == "Non applicable" and conf == "Élevé":
			continue
		frappe.get_doc({"doctype": "Reg Applicability Proposal", "organisation": profile.organisation, "profil": profile.name,
			"modele": tname, "intitule_modele": tpl.intitule, "etat_propose": etat, "score_confiance": conf, "statut": "Proposée",
			"criteres_satisfaits": "\n".join(ok), "criteres_non_satisfaits": "\n".join(ko)}).insert(ignore_permissions=True)
		created += 1
	frappe.db.set_value("Reg Profile", profile.name, "derniere_evaluation", today())
	log_audit("Évaluation d'applicabilité", profile, details={"creees": created, "actualisees": updated})
	return {"creees": created, "actualisees": updated}


def decide_proposal(proposal, decision, justification):
	"""Décision humaine motivée ; une décision « Applicable » génère l'obligation et la décision d'applicabilité."""
	p = frappe.get_doc("Reg Applicability Proposal", proposal) if isinstance(proposal, str) else proposal
	if p.statut in ("Générée", "Rejetée"):
		frappe.throw(_("Cette proposition est déjà traitée."))
	if decision in ("Non applicable", "Applicable sous condition") or decision != p.etat_propose:
		require_text(justification, _("La justification de la décision"))
	p.decision, p.justification = decision, justification
	p.decideur, p.date_decision = frappe.session.user, today()
	if decision == "À analyser":
		p.statut = "En analyse"
	elif decision == "Non applicable":
		p.statut = "Rejetée"
	else:
		p.statut = "Validée"
	p.flags.ignore_permissions = True
	p.save()
	if decision in ("Applicable", "Applicable sous condition"):
		obl = create_obligation_from_template(p.modele, p.organisation, applicabilite=decision, proposition=p.name,
			justification=justification)
		p.db_set({"obligation": obl, "statut": "Générée"})
		return obl
	if decision == "Non applicable":
		frappe.get_doc({"doctype": "Reg Applicability Decision", "organisation": p.organisation, "decision": decision,
			"statut": "Validée", "date_decision": today(), "decideur": frappe.session.user, "justification": justification,
			"criteres_examines": "\n".join(filter(None, (p.criteres_satisfaits, p.criteres_non_satisfaits))),
			"proposition": p.name}).insert(ignore_permissions=True)


def create_obligation_from_template(template, organisation, applicabilite="Applicable", proposition=None, justification=None):
	tpl = frappe.get_doc("Reg Template Obligation", template)
	if tpl.statut not in TEMPLATE_ACTIVE:
		frappe.throw(_("Le modèle {0} n'est pas actif.").format(template))
	if frappe.db.exists("Reg Obligation", {"organisation": organisation, "modele": template,
			"statut": ("not in", ("Archivée", "Obsolète", "Clôturée"))}):
		frappe.throw(_("Une obligation issue du modèle {0} existe déjà pour cette organisation.").format(template))
	obl = frappe.get_doc({
		"doctype": "Reg Obligation", "organisation": organisation, "modele": template, "titre": tpl.intitule,
		"description": tpl.description, "statut": "Brouillon", "applicabilite": applicabilite,
		"source": tpl.source, "version_source": tpl.version_source, "disposition_principale": tpl.disposition,
		"autorite": tpl.autorite, "domaine": tpl.domaine, "sous_domaine": tpl.sous_domaine, "type_obligation": tpl.type_obligation,
		"criticite": tpl.criticite, "nature_temporelle": tpl.nature_temporelle, "frequence": tpl.frequence,
		"evenement_declencheur": tpl.evenement_declencheur, "delai_valeur": tpl.delai_valeur, "delai_unite": tpl.delai_unite,
		"regle_calcul": tpl.regle_calcul, "consequence_nc": tpl.consequence_nc, "exigence_operationnelle": tpl.controle_attendu,
		"justificatif_requis": 1 if tpl.justificatifs else 0, "validation_justificatif_requise": 1 if tpl.justificatifs else 0,
		"justificatifs": [{"type_justificatif": j.type_justificatif, "libelle": j.libelle, "obligatoire": j.obligatoire,
			"nature": j.nature or "Principal", "actif": 1} for j in tpl.justificatifs or []],
	})
	if tpl.disposition:
		obl.append("dispositions", {"disposition": tpl.disposition, "source": tpl.source, "role_lien": "Principal",
			"nature_lien": "Fondement", "ajoute_par": frappe.session.user, "date_ajout": today()})
	obl.flags.ignore_mandatory = True
	obl.insert(ignore_permissions=True)
	frappe.get_doc({"doctype": "Reg Applicability Decision", "obligation": obl.name, "organisation": organisation,
		"decision": applicabilite, "statut": "Proposée", "date_decision": today(), "decideur": frappe.session.user,
		"justification": justification, "proposition": proposition}).insert(ignore_permissions=True)
	log_audit("Génération depuis modèle", obl, details={"modele": template, "version_modele": tpl.version})
	return obl.name


def validate_decision(dec):
	if dec.decision in ("Non applicable", "Applicable sous condition"):
		require_text(dec.justification, _("La justification"))
	if dec.statut == "Validée":
		if not dec.validateur:
			dec.validateur = frappe.session.user
		assert_sod(dec.validateur, dec.decideur, message=_("Séparation des tâches : le décideur ne peut pas valider sa propre décision."))
		dec.date_validation = dec.date_validation or today()


def apply_decision(dec):
	"""Une décision validée met à jour l'applicabilité de l'obligation et remplace la décision précédente."""
	if dec.statut != "Validée" or not dec.obligation:
		return
	with SystemAction():
		for old in frappe.get_all("Reg Applicability Decision", filters={"obligation": dec.obligation, "statut": "Validée",
				"name": ("!=", dec.name)}, pluck="name"):
			frappe.db.set_value("Reg Applicability Decision", old, {"statut": "Remplacée", "date_fin": dec.date_debut or today()})
		frappe.db.set_value("Reg Obligation", dec.obligation, "applicabilite", dec.decision)
		if dec.decision == "Non applicable":
			for name in frappe.get_all("Reg Deadline", filters={"obligation": dec.obligation,
					"statut": ("in", ("À venir", "À traiter"))}, pluck="name"):
				d = frappe.get_doc("Reg Deadline", name)
				d.statut, d.motif_annulation = "Annulée", _("Obligation déclarée non applicable ({0})").format(dec.name)
				frappe.flags.reg_force_transition = True
				try:
					d.save(ignore_permissions=True)
				finally:
					frappe.flags.reg_force_transition = False


def on_template_update(tpl):
	"""Nouvelle version validée d'un modèle → notice « à décider » pour chaque obligation qui en dérive (aucune écrasée)."""
	if tpl.statut not in TEMPLATE_ACTIVE:
		return
	for o in frappe.get_all("Reg Obligation", filters={"modele": tpl.name, "statut": ("not in", ("Archivée", "Obsolète", "Clôturée"))},
			fields=["name", "organisation"]):
		if frappe.db.exists("Reg Template Update Notice", {"obligation": o.name, "version_modele": tpl.version}):
			continue
		n = frappe.get_doc({"doctype": "Reg Template Update Notice", "organisation": o.organisation, "modele": tpl.name,
			"version_modele": tpl.version, "obligation": o.name, "statut": "À décider",
			"resume_changements": tpl.resume_derniere_modif}).insert(ignore_permissions=True)
		from obligation_reglementaire.engine import notification
		notification.emit("modele_mis_a_jour", n)


def apply_template_notice(notice):
	n = frappe.get_doc("Reg Template Update Notice", notice) if isinstance(notice, str) else notice
	if not n.decision:
		frappe.throw(_("Choisissez une décision."))
	if n.decision != "Accepter la mise à jour":
		require_text(n.justification, _("La justification"))
	if n.decision == "Accepter la mise à jour":
		tpl = frappe.get_doc("Reg Template Obligation", n.modele)
		obl = frappe.get_doc("Reg Obligation", n.obligation)
		for f in ("titre", "description", "criticite", "frequence", "delai_valeur", "delai_unite", "regle_calcul",
				"consequence_nc", "evenement_declencheur", "source", "version_source", "autorite", "domaine"):
			src_f = {"titre": "intitule", "disposition_principale": "disposition"}.get(f, f)
			if tpl.get(src_f) not in (None, ""):
				obl.set(f, tpl.get(src_f))
		obl.flags.reg_justification = _("Mise à jour du modèle {0} v{1}").format(tpl.name, tpl.version)
		obl.save(ignore_permissions=True)
	elif n.decision == "Non applicable":
		frappe.get_doc({"doctype": "Reg Applicability Decision", "obligation": n.obligation, "organisation": n.organisation,
			"decision": "Non applicable", "statut": "Proposée", "date_decision": today(), "decideur": frappe.session.user,
			"justification": n.justification}).insert(ignore_permissions=True)
	elif n.decision == "Créer une nouvelle obligation":
		frappe.db.set_value("Reg Obligation", n.obligation, {"a_revoir": 1, "motif_revue": _("Remplacement par une nouvelle obligation issue du modèle")})
	elif n.decision == "Modifier l'obligation existante":
		frappe.db.set_value("Reg Obligation", n.obligation, {"a_revoir": 1, "motif_revue": n.resume_changements or n.justification})
	n.statut, n.decide_par, n.date_decision = "Décidée", frappe.session.user, today()
	n.save(ignore_permissions=True)
