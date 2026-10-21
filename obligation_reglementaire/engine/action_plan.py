"""Non-conformités et plans d'action (Ch8) : création automatique, progression pondérée, prérequis de clôture,
prolongations, réouverture, annulation, vérification d'efficacité."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, now_datetime

from obligation_reglementaire.engine.common import (
	SystemAction, assert_sod, criticality_weight, get_settings, require_text, today_date)

PLAN_TRANSITIONS = {
	"Brouillon": {"Ouvert", "Annulé"},
	"Ouvert": {"En cours", "Bloqué", "En attente de preuves", "En attente de validation", "Annulé"},
	"En cours": {"Bloqué", "En attente de preuves", "En attente de validation", "Annulé"},
	"Bloqué": {"En cours", "Annulé"},
	"En attente de preuves": {"En cours", "En attente de validation", "Annulé"},
	"En attente de validation": {"En cours", "Vérification d'efficacité", "Clôturé"},
	"Vérification d'efficacité": {"Clôturé", "Réouvert", "En cours"},
	"Clôturé": {"Réouvert"},
	"Réouvert": {"En cours", "Bloqué", "En attente de preuves", "En attente de validation", "Annulé"},
	"Annulé": set(),
}

ACTION_TRANSITIONS = {
	"Non commencée": {"Planifiée", "En cours", "Bloquée", "Annulée"},
	"Planifiée": {"En cours", "Bloquée", "Annulée"},
	"En cours": {"Bloquée", "Soumise à contrôle", "Annulée"},
	"Bloquée": {"En cours", "Planifiée", "Annulée"},
	"Soumise à contrôle": {"Validée", "Retour pour correction"},
	"Retour pour correction": {"En cours", "Soumise à contrôle", "Annulée"},
	"Validée": {"En cours"},
	"Annulée": set(),
}

NC_TRANSITIONS = {
	"Ouverte": {"En analyse", "En traitement", "Mesure compensatoire en place", "Annulée", "Clôturée"},
	"En analyse": {"En traitement", "Mesure compensatoire en place", "Annulée", "Clôturée"},
	"En traitement": {"Mesure compensatoire en place", "En attente de vérification", "Clôturée", "Annulée"},
	"Mesure compensatoire en place": {"En traitement", "En attente de vérification", "Clôturée"},
	"En attente de vérification": {"Clôturée", "En traitement"},
	"Clôturée": {"En traitement"},
	"Annulée": set(),
}

OPEN_PLAN = ("Brouillon", "Ouvert", "En cours", "Bloqué", "En attente de preuves", "En attente de validation",
	"Vérification d'efficacité", "Réouvert")
OPEN_ACTION = ("Non commencée", "Planifiée", "En cours", "Bloquée", "Soumise à contrôle", "Retour pour correction")


# ------------------------------------------------------------------ non-conformités
def create_nc(origine, intitule, description, organisation, responsable=None, gravite=None, obligation=None,
		echeance=None, justificatif=None, constat=None, event=None):
	"""Crée une NC (anti-doublon : une NC ouverte par objet et origine) puis un plan si la criticité l'exige."""
	filters = {"origine": origine, "statut": ("not in", ("Clôturée", "Annulée"))}
	for k, v in (("justificatif", justificatif), ("echeance", echeance), ("constat", constat)):
		if v:
			filters[k] = v
	if justificatif or echeance or constat:
		existing = frappe.db.get_value("Reg Non Conformity", filters, "name")
		if existing:
			return frappe.get_doc("Reg Non Conformity", existing)
	gravite = gravite or frappe.db.get_value("Reg Criticality Level", {"actif": 1}, "name", order_by="poids asc")
	responsable = responsable or frappe.db.get_value("Reg Obligation", obligation, "proprietaire") if obligation else responsable
	recurrent = bool(obligation and frappe.db.exists("Reg Non Conformity", {"obligation": obligation, "origine": origine,
		"statut": "Clôturée"}))
	with SystemAction():
		nc = frappe.get_doc({
			"doctype": "Reg Non Conformity",
			"organisation": organisation,
			"intitule": intitule[:140],
			"origine": origine,
			"gravite": gravite,
			"responsable": responsable or "Administrator",
			"direction": frappe.db.get_value("Reg Obligation", obligation, "direction") if obligation else None,
			"date_detection": today_date(),
			"obligation": obligation,
			"echeance": echeance,
			"justificatif": justificatif,
			"constat": constat,
			"description": description,
			"recurrente": 1 if recurrent else 0,
			"creee_automatiquement": 1 if event is not None else 0,
			"evenement_doctype": event.doctype if event is not None else None,
			"evenement_name": event.name if event is not None else None,
		})
		nc.insert(ignore_permissions=True, ignore_mandatory=True)
	return nc


def after_nc_insert(nc):
	from obligation_reglementaire.engine import notification

	notification.emit("nc_creee", nc)
	if criticality_weight(nc.gravite) >= cint(get_settings().pa_auto_poids_min or 3) and not nc.plan_action:
		plan = create_plan_from_nc(nc)
		frappe.db.set_value("Reg Non Conformity", nc.name, {"plan_action": plan.name, "statut": "En traitement"})


def create_plan_from_nc(nc):
	obl = frappe.db.get_value("Reg Obligation", nc.obligation, ["domaine", "direction", "source", "disposition_principale",
		"autorite", "controleur", "validateur", "referent_conformite"], as_dict=True) if nc.obligation else frappe._dict()
	direction = nc.direction or obl.get("direction") or frappe.db.get_value("Reg Org Unit", {"organisation": nc.organisation}, "name")
	domaine = obl.get("domaine") or frappe.db.get_value("Reg Domain", {"actif": 1}, "name")
	settings = get_settings()
	with SystemAction():
		plan = frappe.get_doc({
			"doctype": "Reg Action Plan",
			"organisation": nc.organisation,
			"intitule": _("Remédiation de la non-conformité « {0} »").format(nc.intitule)[:140],
			"origine": "Non-conformité réglementaire",
			"type_plan": "Réglementaire",
			"criticite": nc.gravite,
			"domaine": domaine,
			"statut": "Brouillon",
			"direction": direction,
			"responsable": nc.responsable,
			"controleur": obl.get("controleur") or obl.get("referent_conformite"),
			"valideur": obl.get("validateur") or obl.get("referent_conformite"),
			"date_cible": nc.date_cible or add_days(today_date(), 90),
			"description": nc.description,
			"constat_texte": nc.intitule,
			"obligation": nc.obligation,
			"source": obl.get("source"),
			"disposition": obl.get("disposition_principale"),
			"autorite": obl.get("autorite"),
			"echeance": nc.echeance,
			"justificatif": nc.justificatif,
			"constat": nc.constat,
			"non_conformite": nc.name,
			"cree_automatiquement": 1,
			"evenement_doctype": "Reg Non Conformity",
			"evenement_name": nc.name,
			"efficacite_requise": 1 if criticality_weight(nc.gravite) >= cint(settings.efficacite_requise_poids_min or 3) else 0,
		})
		plan.insert(ignore_permissions=True, ignore_mandatory=True)
	return plan


def nc_close_blockers(nc):
	blockers = []
	if nc.plan_action:
		st = frappe.db.get_value("Reg Action Plan", nc.plan_action, "statut")
		if st not in ("Clôturé", "Annulé"):
			blockers.append(_("Plan d'action {0} non clôturé ({1}).").format(nc.plan_action, st))
	if not nc.decision_cloture and not nc.risque_residuel_accepte:
		blockers.append(_("Décision de clôture non renseignée."))
	return blockers


# ------------------------------------------------------------------ plans
def recompute_plan(plan_name):
	"""Progression pondérée : actions validées = 100 %, autres = avancement déclaré (plafonné à 90 %)."""
	if not plan_name:
		return
	acts = frappe.get_all("Reg Corrective Action", filters={"plan": plan_name, "statut": ("!=", "Annulée")},
		fields=["statut", "poids", "avancement", "en_retard"])
	total = sum(flt(a.poids) or 1 for a in acts)
	done = sum((flt(a.poids) or 1) * (100 if a.statut == "Validée" else min(flt(a.avancement), 90)) for a in acts)
	values = {
		"taux_realisation": round(done / total, 1) if total else 0,
		"nb_actions": len(acts),
		"nb_actions_validees": len([a for a in acts if a.statut == "Validée"]),
		"nb_actions_retard": len([a for a in acts if cint(a.en_retard)]),
	}
	plan = frappe.db.get_value("Reg Action Plan", plan_name, ["date_cible", "statut"], as_dict=True)
	values["en_retard"] = 1 if (plan.statut in OPEN_PLAN and plan.date_cible and getdate(plan.date_cible) < today_date()) \
		or values["nb_actions_retard"] else 0
	frappe.db.set_value("Reg Action Plan", plan_name, values, update_modified=False)
	return values


def plan_close_blockers(plan):
	"""Prérequis de clôture (Ch8.21) — retourne la liste explicite des éléments bloquants."""
	b = []
	acts = frappe.get_all("Reg Corrective Action", filters={"plan": plan.name}, fields=["name", "intitule", "statut", "obligatoire", "motif_annulation"])
	if not acts:
		b.append(_("Aucune action corrective n'est définie."))
	for a in acts:
		if a.statut == "Annulée" and not a.motif_annulation:
			b.append(_("Action {0} annulée sans justification.").format(a.name))
		elif cint(a.obligatoire) and a.statut not in ("Validée", "Annulée"):
			b.append(_("Action obligatoire « {0} » non validée ({1}).").format(a.intitule, a.statut))
	pending = frappe.get_all("Reg Action Proof", filters={"plan": plan.name, "statut": ("in", ("À contrôler", "Complément demandé"))},
		pluck="name")
	if pending:
		b.append(_("Preuves non contrôlées : {0}.").format(", ".join(pending)))
	if not plan.causes and criticality_weight(plan.criticite) >= 3:
		b.append(_("Analyse des causes non renseignée (obligatoire pour un plan critique ou élevé)."))
	for m in plan.mesures_compensatoires:
		if m.statut == "Active" and m.date_fin and getdate(m.date_fin) < today_date():
			b.append(_("Mesure compensatoire expirée non traitée : {0}.").format(m.description[:60]))
	if plan.nb_prolongations and cint(plan.nb_prolongations) >= cint(get_settings().max_prolongations_alerte or 3) \
			and not plan.commentaire_validation:
		b.append(_("Plan prolongé {0} fois : un commentaire de validation est requis.").format(plan.nb_prolongations))
	return b


def request_closure(plan):
	b = plan_close_blockers(plan)
	plan.blocages_cloture = "\n".join(b) if b else None
	if b:
		plan.db_set("blocages_cloture", plan.blocages_cloture)
		frappe.throw("<br>".join(b), title=_("Clôture impossible"))
	plan.statut = "En attente de validation"
	plan.demande_cloture_par = frappe.session.user
	plan.date_demande_cloture = now_datetime()
	plan.flags.ignore_permissions = True
	plan.save()
	from obligation_reglementaire.engine import notification
	notification.emit("pa_cloture_demandee", plan)


def validate_closure(plan, commentaire=None):
	if plan.statut != "En attente de validation":
		frappe.throw(_("Le plan n'est pas en attente de validation."))
	assert_sod(frappe.session.user, plan.responsable, plan.demande_cloture_par,
		message=_("Séparation des tâches : le propriétaire du plan ne peut pas valider sa clôture."))
	b = plan_close_blockers(plan)
	if b:
		frappe.throw("<br>".join(b), title=_("Clôture impossible"))
	plan.valide_par = frappe.session.user
	plan.date_validation = now_datetime()
	plan.commentaire_validation = commentaire or plan.commentaire_validation
	if cint(plan.efficacite_requise) and not frappe.db.exists("Reg Effectiveness Check",
			{"plan": plan.name, "statut": "Réalisée", "resultat": "Efficace"}):
		plan.statut = "Vérification d'efficacité"
		plan.flags.ignore_permissions = True
		plan.save()
		if not frappe.db.exists("Reg Effectiveness Check", {"plan": plan.name, "statut": ("in", ("Planifiée", "En cours"))}):
			frappe.get_doc({"doctype": "Reg Effectiveness Check", "plan": plan.name, "statut": "Planifiée",
				"date_prevue": add_days(today_date(), 90), "responsable": plan.controleur or plan.valideur or frappe.session.user,
				"criteres_efficacite": _("Absence de récurrence du constat ; contrôles concluants sur la période.")
			}).insert(ignore_permissions=True)
		from obligation_reglementaire.engine import notification
		notification.emit("efficacite_a_controler", plan)
		return plan
	close_plan(plan)
	return plan


def close_plan(plan):
	plan.statut = "Clôturé"
	plan.date_cloture = now_datetime()
	plan.blocages_cloture = None
	plan.flags.ignore_permissions = True
	plan.save()
	if plan.non_conformite:
		nc = frappe.get_doc("Reg Non Conformity", plan.non_conformite)
		if nc.statut not in ("Clôturée", "Annulée"):
			nc.decision_cloture = nc.decision_cloture or _("Plan d'action {0} clôturé.").format(plan.name)
			nc.flags.ignore_permissions = True
			nc.statut = "Clôturée"
			nc.cloture_par = frappe.session.user
			nc.date_cloture = now_datetime()
			nc.save()
	from obligation_reglementaire.engine import notification
	notification.emit("pa_cloture", plan)


def reopen_plan(plan, motif, nouveau_constat=None):
	require_text(motif, _("Le motif de réouverture"))
	if plan.statut not in ("Clôturé", "Vérification d'efficacité"):
		frappe.throw(_("Seul un plan clôturé ou en vérification d'efficacité peut être réouvert."))
	plan.statut = "Réouvert"
	plan.motif_reouverture = motif
	plan.nouveau_constat_reouverture = nouveau_constat
	plan.nb_reouvertures = cint(plan.nb_reouvertures) + 1
	plan.date_cloture = None
	plan.flags.reg_justification = motif
	plan.flags.ignore_permissions = True
	plan.save()
	from obligation_reglementaire.engine import notification
	notification.emit("pa_reouvert", plan)


def cancel_plan(plan, categorie, motif):
	require_text(motif, _("Le motif d'annulation"))
	if plan.statut in ("Clôturé", "Annulé"):
		frappe.throw(_("Un plan clôturé ou annulé ne peut pas être annulé."))
	plan.statut = "Annulé"
	plan.categorie_annulation = categorie
	plan.motif_annulation = motif
	plan.flags.reg_justification = motif
	plan.flags.ignore_permissions = True
	plan.save()
	for a in frappe.get_all("Reg Corrective Action", filters={"plan": plan.name, "statut": ("in", OPEN_ACTION)}, pluck="name"):
		frappe.db.set_value("Reg Corrective Action", a, {"statut": "Annulée", "motif_annulation": _("Plan annulé : {0}").format(motif)})


# ------------------------------------------------------------------ actions
def action_prerequisites_ok(action):
	missing = []
	for dep in action.dependances:
		if cint(dep.obligatoire) and frappe.db.get_value("Reg Corrective Action", dep.action_prerequise, "statut") != "Validée":
			missing.append(dep.intitule or dep.action_prerequise)
	return missing


def submit_action(action):
	if action.statut not in ("En cours", "Retour pour correction"):
		frappe.throw(_("Seule une action en cours peut être soumise à contrôle."))
	proofs = frappe.get_all("Reg Action Proof", filters={"action": action.name, "statut": ("not in", ("Rejetée", "Remplacée"))},
		pluck="name")
	if action.preuve_attendue and not proofs:
		frappe.throw(_("Une preuve de réalisation ({0}) doit être déposée avant la soumission.").format(action.preuve_attendue))
	action.statut = "Soumise à contrôle"
	action.date_realisation = action.date_realisation or today_date()
	action.avancement = 100
	action.flags.ignore_permissions = True
	action.save()
	from obligation_reglementaire.engine import notification
	notification.emit("action_soumise", action)


def validate_action(action):
	if action.statut != "Soumise à contrôle":
		frappe.throw(_("L'action n'est pas soumise à contrôle."))
	assert_sod(frappe.session.user, action.responsable,
		message=_("Séparation des tâches : le responsable d'une action ne peut pas la valider."))
	pending = frappe.get_all("Reg Action Proof", filters={"action": action.name, "statut": ("in", ("À contrôler", "Complément demandé"))},
		pluck="name")
	if pending:
		frappe.throw(_("Des preuves restent à contrôler : {0}.").format(", ".join(pending)))
	if action.preuve_attendue and not frappe.db.exists("Reg Action Proof", {"action": action.name, "statut": "Acceptée"}):
		frappe.throw(_("Aucune preuve acceptée : l'action ne peut pas être validée."))
	action.statut = "Validée"
	action.valide_par = frappe.session.user
	action.date_validation = now_datetime()
	action.flags.ignore_permissions = True
	action.save()
	from obligation_reglementaire.engine import notification
	notification.emit("action_validee", action)


def return_action(action, motif):
	require_text(motif, _("Le motif de retour"))
	action.statut = "Retour pour correction"
	action.motif_retour = motif
	action.flags.reg_justification = motif
	action.flags.ignore_permissions = True
	action.save()
	from obligation_reglementaire.engine import notification
	notification.emit("action_rejetee", action)


def review_proof(proof, decision, motif=None, commentaire=None):
	if proof.statut != "À contrôler" and decision != "Complément demandé":
		frappe.throw(_("La preuve a déjà été contrôlée."))
	assert_sod(frappe.session.user, proof.deposant, message=_("Séparation des tâches : le déposant ne peut pas contrôler sa preuve."))
	if decision in ("Rejetée", "Complément demandé") and not (motif or commentaire):
		frappe.throw(_("Un motif est obligatoire."))
	proof.statut = decision
	proof.controleur = frappe.session.user
	proof.date_controle = now_datetime()
	proof.motif_rejet = motif
	proof.commentaire_controle = commentaire
	proof.flags.ignore_permissions = True
	proof.save()
	if decision == "Rejetée":
		from obligation_reglementaire.engine import notification
		notification.emit("preuve_rejetee", proof)


# ------------------------------------------------------------------ prolongations
def decide_extension(ext, decision, commentaire=None):
	if ext.statut not in ("Demandée", "Informations demandées"):
		frappe.throw(_("Demande déjà traitée."))
	assert_sod(frappe.session.user, ext.demandeur, message=_("Séparation des tâches : le demandeur ne peut pas valider sa prolongation."))
	if decision != "Acceptée" and not commentaire:
		frappe.throw(_("Un commentaire est obligatoire pour refuser ou demander des informations."))
	ext.statut = decision
	ext.valideur = frappe.session.user
	ext.date_decision = now_datetime()
	ext.commentaire_decision = commentaire
	ext.flags.ignore_permissions = True
	ext.save()
	from obligation_reglementaire.engine import notification
	if decision == "Acceptée":
		if ext.type_objet == "Action":
			a = frappe.get_doc("Reg Corrective Action", ext.action)
			a.date_fin_prevue = ext.nouvelle_date
			a.nb_prolongations = cint(a.nb_prolongations) + 1
			a.en_retard = 0
			a.jours_retard = 0
			a.flags.reg_justification = ext.justification
			a.flags.ignore_permissions = True
			a.save()
		plan = frappe.get_doc("Reg Action Plan", ext.plan)
		if ext.type_objet == "Plan" or getdate(ext.nouvelle_date) > getdate(plan.date_cible):
			plan.date_cible = max(getdate(plan.date_cible), getdate(ext.nouvelle_date))
		plan.nb_prolongations = cint(plan.nb_prolongations) + 1
		plan.flags.reg_justification = ext.justification
		plan.flags.ignore_permissions = True
		plan.save()
		notification.emit("prolongation_acceptee", ext)
	elif decision == "Refusée":
		notification.emit("prolongation_refusee", ext)


# ------------------------------------------------------------------ efficacité
def apply_effectiveness(check):
	plan = frappe.get_doc("Reg Action Plan", check.plan)
	plan.resultat_efficacite = check.resultat
	plan.flags.ignore_permissions = True
	if check.resultat == "Efficace":
		plan.save()
		if plan.statut == "Vérification d'efficacité":
			close_plan(plan)
	elif check.suite_donnee == "Réouverture du plan" or check.resultat == "Inefficace":
		plan.save()
		if plan.statut in ("Clôturé", "Vérification d'efficacité"):
			reopen_plan(plan, _("Vérification d'efficacité {0} : {1}").format(check.name, check.resultat), check.anomalies)
	else:
		plan.save()


# ------------------------------------------------------------------ quotidien
def daily_update():
	from obligation_reglementaire.engine import notification

	t = today_date()
	with SystemAction():
		for a in frappe.get_all("Reg Corrective Action", filters={"statut": ("in", OPEN_ACTION), "date_fin_prevue": ("<", t)},
				fields=["name", "date_fin_prevue", "en_retard", "plan"]):
			frappe.db.set_value("Reg Corrective Action", a.name, {"en_retard": 1, "jours_retard": date_diff(t, a.date_fin_prevue)},
				update_modified=False)
			if not cint(a.en_retard):
				notification.emit("action_retard", frappe.get_doc("Reg Corrective Action", a.name))
		for p in frappe.get_all("Reg Action Plan", filters={"statut": ("in", OPEN_PLAN)}, pluck="name"):
			recompute_plan(p)
		for nc in frappe.get_all("Reg Non Conformity", filters={"statut": ("not in", ("Clôturée", "Annulée"))},
				fields=["name", "date_detection"]):
			frappe.db.set_value("Reg Non Conformity", nc.name, "anciennete_jours", date_diff(t, nc.date_detection),
				update_modified=False)
		for m in frappe.get_all("Reg Effectiveness Check", filters={"statut": "Planifiée", "date_prevue": ("<=", t)}, pluck="name"):
			notification.emit("efficacite_a_controler", frappe.get_doc("Reg Effectiveness Check", m))
