"""Points d'entrée whitelistés du module Obligations réglementaires.

Chaque action contrôle le droit d'écriture sur l'objet (cloisonnement par organisation via User Permission),
puis délègue au moteur métier (obligation_reglementaire.engine.*) qui porte les règles de gestion."""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, today

from obligation_reglementaire.engine import action_plan, applicability, config, deadline, evidence, ged, indicators, reporting
from obligation_reglementaire.engine import notification, source
from obligation_reglementaire.engine.common import (
	SystemAction, has_any_role, log_audit, require_roles, require_text, today_date, user_organisation)

COMPLIANCE_ROLES = ("OR Administrateur", "OR Responsable Conformité")


def _doc(doctype, name, ptype="write"):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission(ptype)
	return doc


def _json(value):
	if isinstance(value, str):
		return json.loads(value) if value else {}
	return value or {}


# ================================================================== obligations
@frappe.whitelist()
def obligation_transition(obligation, statut, motif=None):
	doc = _doc("Reg Obligation", obligation)
	if statut in ("Validée", "Archivée", "Obsolète") and not has_any_role(*COMPLIANCE_ROLES, "OR Validateur"):
		frappe.throw(_("Action réservée à la fonction conformité ou au valideur."), frappe.PermissionError)
	doc.statut = statut
	if motif:
		doc.flags.reg_justification = motif
	doc.save()
	if motif:
		log_audit(f"Obligation → {statut}", doc, justification=motif)
	return doc.statut


@frappe.whitelist()
def obligation_update_with_justification(obligation, values, justification):
	"""Modification d'un champ sensible d'une obligation active : justification obligatoire, historisée."""
	require_text(justification, _("La justification"))
	doc = _doc("Reg Obligation", obligation)
	values = _json(values)
	before_crit = doc.criticite
	doc.update({k: v for k, v in values.items() if doc.meta.has_field(k) and k not in ("statut", "organisation", "name")})
	doc.flags.reg_justification = justification
	doc.save()
	if before_crit != doc.criticite:
		log_audit("Changement de criticité", doc, champ="criticite", ancienne=before_crit, nouvelle=doc.criticite,
			justification=justification)
	return doc.name


@frappe.whitelist()
def generate_deadlines(obligation):
	doc = _doc("Reg Obligation", obligation)
	if doc.statut != "Active":
		frappe.throw(_("Seule une obligation active génère des échéances."))
	created = deadline.generate_for_obligation(doc)
	return {"creees": created}


@frappe.whitelist()
def deadline_preview(obligation, nombre=6):
	"""Aperçu des prochaines dates calculées (sans création) pour l'écran de paramétrage."""
	doc = _doc("Reg Obligation", obligation, "read")
	return {"regle": deadline.calc_rule_text(doc), "dates": _preview_dates(doc, cint(nombre) or 6)}


def _preview_dates(obl, n):
	from frappe.utils import add_days

	from obligation_reglementaire.engine.calendar import add_delay, get_calendar

	cal = get_calendar(obl.calendrier)
	if obl.nature_temporelle != "Périodique" or not obl.frequence:
		d = obl.date_fixe or (obl.date_debut if obl.nature_temporelle != "Permanente" else None)
		return [{"periode": "", "date_limite": str(d)}] if d else []
	step = deadline.period_step(obl)
	if not step:
		return []
	cur = deadline.period_start(obl, obl.date_reference or obl.date_debut or today_date())
	out = []
	for _i in range(n):
		end = add_days(cur + step, -1)
		due = add_delay(end, obl.delai_valeur, obl.delai_unite, cal) if obl.delai_valeur else end
		out.append({"periode": deadline.period_label(obl, cur, end), "date_limite": str(cal.adjust(getdate(due), obl.regle_jour_non_ouvre))})
		cur = add_days(end, 1)
	return out


@frappe.whitelist()
def create_obligation_from_template(template, organisation, applicabilite="Applicable", justification=None):
	require_roles(*COMPLIANCE_ROLES, "OR Analyste Réglementaire")
	return applicability.create_obligation_from_template(template, organisation, applicabilite, justification=justification)


# ================================================================== échéances
DEADLINE_ACTIONS = ("demarrer", "attente", "soumettre", "valider", "rejeter", "non_conforme", "cloturer", "rouvrir", "annuler",
	"suspendre", "reprendre")


@frappe.whitelist()
def deadline_action(name, action, motif=None, commentaire=None, date_realisation=None, cause_retard=None,
		derogation=0, date_fin_prevue=None, autorite=None, justificatif=None):
	if action not in DEADLINE_ACTIONS:
		frappe.throw(_("Action inconnue : {0}").format(action))
	dl = _doc("Reg Deadline", name)
	if action == "suspendre":
		require_text(motif, _("Le motif de suspension"))
		deadline.suspend(dl, motif, date_fin_prevue, autorite, justificatif)
		return dl.statut
	if action == "reprendre":
		deadline.resume(dl)
		return dl.statut
	if action == "demarrer":
		dl.statut = "En cours"
	elif action == "attente":
		dl.statut, dl.motif_attente = "En attente", motif
	elif action == "soumettre":
		dl.statut = "Soumise pour validation"
		if date_realisation:
			dl.date_realisation = date_realisation
		if cint(derogation):
			require_roles(*COMPLIANCE_ROLES)
			dl.derogation_justificatif = 1
			dl.justification_derogation = motif
			dl.flags.reg_force = True
	elif action == "valider":
		if not has_any_role(*COMPLIANCE_ROLES, "OR Validateur", "OR Contrôleur") and dl.validateur != frappe.session.user:
			frappe.throw(_("Vous n'êtes pas valideur de cette échéance."), frappe.PermissionError)
		dl.statut = "Réalisée"
		if cause_retard:
			dl.cause_retard = cause_retard
		if commentaire:
			dl.commentaire_retard = commentaire
	elif action == "rejeter":
		dl.statut, dl.motif_rejet = "En cours", motif
	elif action == "non_conforme":
		require_text(motif, _("Le motif de non-conformité"))
		dl.statut, dl.motif_rejet = "Non conforme", motif
	elif action == "cloturer":
		dl.statut, dl.commentaire_cloture = "Clôturée", commentaire or motif
	elif action == "rouvrir":
		require_roles(*COMPLIANCE_ROLES)
		dl.statut, dl.motif_reouverture = "En cours", motif
		dl.flags.reg_justification = motif
	elif action == "annuler":
		require_roles(*COMPLIANCE_ROLES)
		dl.statut, dl.motif_annulation = "Annulée", motif
		dl.flags.reg_justification = motif
	dl.save()
	return dl.statut


@frappe.whitelist()
def request_deadline_change(echeance, nouvelle_date, motif, justification=None, type_modification="Report métier",
		piece=None, autorite=None):
	_doc("Reg Deadline", echeance, "read")
	ch = frappe.get_doc({"doctype": "Reg Deadline Change", "echeance": echeance, "nouvelle_date": nouvelle_date,
		"motif": motif, "justification": justification, "type_modification": type_modification, "piece": piece,
		"autorite_autorisant": autorite, "statut": "Demandée"})
	ch.insert()
	return ch.name


@frappe.whitelist()
def decide_deadline_change(name, decision, commentaire=None):
	if decision not in ("Approuvée", "Refusée"):
		frappe.throw(_("Décision invalide."))
	require_roles(*COMPLIANCE_ROLES, "OR Validateur")
	ch = frappe.get_doc("Reg Deadline Change", name)
	ch.statut, ch.commentaire_decision = decision, commentaire
	ch.save(ignore_permissions=True)
	return ch.statut


# ================================================================== justificatifs
@frappe.whitelist()
def deposit_evidence(evidence_name, file_url, commentaire=None, confirmer_doublon=0, motif_remplacement=None):
	_doc("Reg Evidence", evidence_name)
	return evidence.deposit_version(evidence_name, file_url, commentaire, confirmer_doublon, motif_remplacement)


@frappe.whitelist()
def start_evidence_review(evidence_name):
	require_roles(*COMPLIANCE_ROLES, "OR Contrôleur", "OR Validateur")
	_doc("Reg Evidence", evidence_name, "read")
	return evidence.start_review(evidence_name)


@frappe.whitelist()
def replace_evidence(evidence_name, motif):
	require_text(motif, _("Le motif de remplacement"))
	_doc("Reg Evidence", evidence_name)
	return evidence.replace_evidence(evidence_name, motif)


@frappe.whitelist()
def add_evidence(echeance, type_justificatif, libelle, obligatoire=0):
	"""Ajout manuel d'un justificatif complémentaire sur une échéance."""
	dl = _doc("Reg Deadline", echeance)
	ev = frappe.get_doc({"doctype": "Reg Evidence", "echeance": dl.name, "obligation": dl.obligation, "organisation": dl.organisation,
		"type_justificatif": type_justificatif, "libelle": libelle, "obligatoire": cint(obligatoire), "statut": "À fournir",
		"responsable": dl.responsable, "nature": "Complémentaire"})
	ev.insert(ignore_mandatory=True)
	deadline.refresh_doc_state(dl.name)
	return ev.name


@frappe.whitelist()
def cancel_evidence(evidence_name, motif):
	require_roles(*COMPLIANCE_ROLES)
	ev = _doc("Reg Evidence", evidence_name)
	ev.statut, ev.motif_annulation = "Annulé", motif
	ev.save()
	return ev.statut


@frappe.whitelist()
def reuse_evidence(evidence_name, echeance, contexte=None):
	u = frappe.get_doc({"doctype": "Reg Evidence Usage", "justificatif": evidence_name, "echeance": echeance,
		"contexte": contexte, "statut_validation": "En attente"})
	u.insert()
	return u.name


@frappe.whitelist()
def submit_evidence_review(review_name, resultat, items=None, motifs=None, commentaire=None,
		corrections_attendues=None, complements_attendus=None, date_limite_resoumission=None,
		reserve_nature=None, reserve_justification=None, reserve_statut=None):
	"""Soumission d'un contrôle de justificatif depuis le portail. La soumission (doc.submit())
	déclenche automatiquement validate_review() puis apply_review() (déjà portées par le
	contrôleur Reg Evidence Review) : aucune logique métier n'est dupliquée ici."""
	doc = _doc("Reg Evidence Review", review_name)
	if doc.docstatus != 0:
		frappe.throw(_("Ce contrôle a déjà été soumis."))
	doc.resultat = resultat
	doc.commentaire = commentaire
	doc.corrections_attendues = corrections_attendues
	doc.complements_attendus = complements_attendus
	doc.date_limite_resoumission = date_limite_resoumission
	doc.reserve_nature = reserve_nature
	doc.reserve_justification = reserve_justification
	doc.reserve_statut = reserve_statut

	for row in _json(items) if items else []:
		critere = row.get("critere")
		match = next((i for i in doc.items if i.critere == critere), None)
		if match:
			match.resultat = row.get("resultat")
			match.commentaire = row.get("commentaire")

	if resultat == "Rejeté":
		doc.set("motifs", [])
		for row in _json(motifs) if motifs else []:
			if row.get("motif"):
				doc.append("motifs", {"motif": row.get("motif"), "commentaire": row.get("commentaire")})

	try:
		doc.submit()
	except (frappe.ValidationError, frappe.PermissionError) as e:
		frappe.throw(str(e))
	non_conformite = frappe.db.get_value("Reg Evidence Review", doc.name, "non_conformite")
	return {"statut": doc.resultat, "justificatif": doc.justificatif, "non_conformite": non_conformite}


# ================================================================== non-conformités / constats
@frappe.whitelist()
def finding_to_nc(finding):
	doc = _doc("Reg Finding", finding)
	return doc.to_non_conformity()


@frappe.whitelist()
def create_plan_from_nc(nc):
	doc = _doc("Reg Non Conformity", nc)
	if doc.plan_action:
		return doc.plan_action
	plan = action_plan.create_plan_from_nc(doc)
	doc.db_set({"plan_action": plan.name, "statut": "En traitement" if doc.statut in ("Ouverte", "En analyse") else doc.statut})
	return plan.name


@frappe.whitelist()
def close_nc(nc, decision, risque_residuel_accepte=0, justification_acceptation=None):
	require_roles(*COMPLIANCE_ROLES, "OR Validateur")
	doc = _doc("Reg Non Conformity", nc)
	doc.decision_cloture = decision
	doc.risque_residuel_accepte = cint(risque_residuel_accepte)
	doc.justification_acceptation = justification_acceptation
	doc.statut = "Clôturée"
	doc.save()
	return doc.statut


NC_ACTIONS_STATUT = {
	"analyser": "En analyse",
	"traiter": "En traitement",
	"mesure_compensatoire": "Mesure compensatoire en place",
	"verifier": "En attente de vérification",
}


@frappe.whitelist()
def nc_action(name, action, motif=None):
	"""Transitions mécaniques de non-conformité non couvertes par close_nc()/create_plan_from_nc().
	check_transition(self, NC_TRANSITIONS) (engine/action_plan.py) reste le seul garde-fou réel :
	un statut non atteignable depuis le statut courant est rejeté par le save()."""
	doc = _doc("Reg Non Conformity", name)
	if action == "annuler":
		require_roles(*COMPLIANCE_ROLES)
		require_text(motif, _("Le motif d'annulation"))
		doc.motif_annulation = motif
		doc.flags.reg_justification = motif
		doc.statut = "Annulée"
	elif action in NC_ACTIONS_STATUT:
		doc.statut = NC_ACTIONS_STATUT[action]
	else:
		frappe.throw(_("Action inconnue : {0}").format(action))
	doc.save()
	return doc.statut


# ================================================================== plans d'action
@frappe.whitelist()
def plan_action(plan, action, motif=None, commentaire=None, categorie=None, nouveau_constat=None):
	doc = _doc("Reg Action Plan", plan)
	if action == "ouvrir":
		doc.statut = "Ouvert"
		doc.save()
	elif action == "demander_cloture":
		action_plan.request_closure(doc)
	elif action == "valider_cloture":
		if not has_any_role(*COMPLIANCE_ROLES, "OR Validateur") and doc.valideur != frappe.session.user:
			frappe.throw(_("Vous n'êtes pas valideur de ce plan."), frappe.PermissionError)
		action_plan.validate_closure(doc, commentaire)
	elif action == "refuser_cloture":
		require_text(motif, _("Le motif du refus"))
		doc.statut, doc.commentaire_validation = "En cours", motif
		doc.save()
	elif action == "rouvrir":
		require_roles(*COMPLIANCE_ROLES, "OR Validateur")
		action_plan.reopen_plan(doc, motif, nouveau_constat)
	elif action == "annuler":
		require_roles(*COMPLIANCE_ROLES)
		action_plan.cancel_plan(doc, categorie, motif)
	elif action == "bloquer":
		doc.statut, doc.commentaires = "Bloqué", motif
		doc.save()
	elif action == "debloquer":
		doc.statut = "En cours"
		doc.save()
	elif action == "blocages":
		return action_plan.plan_close_blockers(doc)
	else:
		frappe.throw(_("Action inconnue : {0}").format(action))
	return frappe.db.get_value("Reg Action Plan", plan, "statut")


@frappe.whitelist()
def corrective_action(name, action, motif=None):
	doc = _doc("Reg Corrective Action", name)
	if action == "soumettre":
		action_plan.submit_action(doc)
	elif action == "valider":
		if not has_any_role(*COMPLIANCE_ROLES, "OR Contrôleur", "OR Validateur") and doc.controleur != frappe.session.user:
			frappe.throw(_("Vous n'êtes pas contrôleur de cette action."), frappe.PermissionError)
		action_plan.validate_action(doc)
	elif action == "retourner":
		action_plan.return_action(doc, motif)
	elif action == "demarrer":
		doc.statut = "En cours"
		doc.save()
	elif action == "bloquer":
		doc.statut, doc.motif_blocage = "Bloquée", motif
		doc.save()
	elif action == "annuler":
		doc.statut, doc.motif_annulation = "Annulée", motif
		doc.flags.reg_justification = motif
		doc.save()
	else:
		frappe.throw(_("Action inconnue : {0}").format(action))
	return doc.statut


@frappe.whitelist()
def review_action_proof(proof, decision, motif=None, commentaire=None):
	if decision not in ("Acceptée", "Rejetée", "Complément demandé"):
		frappe.throw(_("Décision invalide."))
	doc = _doc("Reg Action Proof", proof)
	action_plan.review_proof(doc, decision, motif, commentaire)
	return doc.statut


@frappe.whitelist()
def decide_extension(name, decision, commentaire=None):
	if decision not in ("Acceptée", "Refusée", "Informations demandées"):
		frappe.throw(_("Décision invalide."))
	require_roles(*COMPLIANCE_ROLES, "OR Validateur")
	doc = frappe.get_doc("Reg Extension Request", name)
	action_plan.decide_extension(doc, decision, commentaire)
	return doc.statut


@frappe.whitelist()
def add_action_proof(action, type_preuve, libelle, file_url):
	"""Dépôt d'une preuve de réalisation depuis le portail. Le contrôleur Reg Action Proof
	(validate()) dérive déjà plan/organisation/deposant/empreinte/numero_version : rien n'est
	dupliqué ici, seul le champ d'action est contrôlé en écriture."""
	_doc("Reg Corrective Action", action)
	proof = frappe.get_doc({"doctype": "Reg Action Proof", "action": action, "type_preuve": type_preuve,
		"libelle": libelle, "fichier": file_url})
	proof.insert(ignore_mandatory=True)
	return proof.name


@frappe.whitelist()
def request_extension(type_objet, nouvelle_date, motif, justification, plan=None, action=None,
		etat_avancement=None, difficultes=None, risques=None, mesures_compensatoires=None):
	"""Demande de prolongation depuis le portail (plan ou action). Le contrôleur Reg Extension
	Request dérive plan/organisation/demandeur/jours_ajoutes et refuse les doublons en cours :
	rien n'est dupliqué ici, seul l'objet visé est contrôlé en écriture."""
	if type_objet == "Action":
		act = _doc("Reg Corrective Action", action)
		plan = act.plan
	else:
		_doc("Reg Action Plan", plan)
	ext = frappe.get_doc({"doctype": "Reg Extension Request", "type_objet": type_objet, "plan": plan, "action": action,
		"nouvelle_date": nouvelle_date, "motif": motif, "justification": justification,
		"etat_avancement": etat_avancement, "difficultes": difficultes, "risques": risques,
		"mesures_compensatoires": mesures_compensatoires})
	ext.insert(ignore_mandatory=True)
	return ext.name


# ================================================================== applicabilité
@frappe.whitelist()
def evaluate_profile(profile):
	_doc("Reg Profile", profile, "read")
	require_roles(*COMPLIANCE_ROLES, "OR Analyste Réglementaire")
	return applicability.evaluate_profile(profile)


@frappe.whitelist()
def decide_proposal(proposal, decision, justification=None):
	require_roles(*COMPLIANCE_ROLES, "OR Analyste Réglementaire")
	_doc("Reg Applicability Proposal", proposal)
	return applicability.decide_proposal(proposal, decision, justification)


@frappe.whitelist()
def decide_template_notice(notice, decision, justification=None):
	require_roles(*COMPLIANCE_ROLES, "OR Analyste Réglementaire")
	n = _doc("Reg Template Update Notice", notice)
	n.decision, n.justification = decision, justification
	applicability.apply_template_notice(n)
	return n.statut


# ================================================================== référentiel
@frappe.whitelist()
def compare_source_versions(version_a, version_b):
	_doc("Reg Source Version", version_b, "read")
	return source.compare_versions(version_a, version_b)


@frappe.whitelist()
def create_impact_analysis(version, organisation=None):
	require_roles(*COMPLIANCE_ROLES, "OR Analyste Réglementaire")
	v = _doc("Reg Source Version", version, "read")
	return source.create_impact_analysis(v, organisation)


@frappe.whitelist()
def source_duplicates(source_name):
	src = _doc("Reg Source", source_name, "read")
	return source.find_duplicates(src)


# ================================================================== GED
@frappe.whitelist()
def add_document_version(document, file_url, commentaire=None, type_version="Mineure"):
	_doc("Reg Document", document)
	return ged.add_version(document, file_url, commentaire, type_version)


@frappe.whitelist()
def validate_document_version(version, accepter=1, motif_rejet=None, commentaire=None):
	require_roles(*COMPLIANCE_ROLES, "OR Contrôleur", "OR Validateur", "OR Gestionnaire Documentaire")
	ged.validate_version(version, cint(accepter), motif_rejet, commentaire)
	return frappe.db.get_value("Reg Document Version", version, "statut")


@frappe.whitelist()
def document_action(document, action, motif=None):
	doc = _doc("Reg Document", document)
	if action == "publier":
		ged.publish(doc)
	elif action == "geler":
		require_roles(*COMPLIANCE_ROLES, "OR Gestionnaire Documentaire", "OR Auditeur")
		ged.freeze(doc, motif, True)
	elif action == "degeler":
		require_roles(*COMPLIANCE_ROLES, "OR Gestionnaire Documentaire")
		ged.freeze(doc, motif, False)
	elif action == "supprimer":
		require_roles(*COMPLIANCE_ROLES, "OR Gestionnaire Documentaire")
		ged.logical_delete(doc, motif)
	elif action == "soumettre":
		doc.statut = "Soumis"
		doc.save()
	elif action == "archiver":
		doc.statut = "Archivé"
		doc.date_archivage = today_date()
		doc.save()
	else:
		frappe.throw(_("Action inconnue : {0}").format(action))
	return frappe.db.get_value("Reg Document", document, "statut")


@frappe.whitelist()
def share_document(document, destinataire, date_expiration, motif=None):
	_doc("Reg Document", document, "share")
	s = ged.create_share(document, destinataire, date_expiration, motif)
	return {"name": s.name, "lien": s.lien}


@frappe.whitelist()
def revoke_share(share):
	s = frappe.get_doc("Reg Document Share", share)
	_doc("Reg Document", s.document, "share")
	ged.revoke_share(share)
	log_audit("Révocation de partage", s)
	return "Révoqué"


@frappe.whitelist(allow_guest=True)
def shared_document(token=None):
	"""Lien de partage sécurisé : jeton aléatoire, expiration, révocation, compteur d'accès."""
	doc = ged.resolve_share(token)
	f = frappe.get_doc("File", {"file_url": doc.fichier})
	log_audit("Accès par lien de partage", doc, details={"jeton": token[:6] + "…"})
	frappe.db.commit()
	frappe.local.response.filename = f.file_name
	frappe.local.response.filecontent = f.get_content()
	frappe.local.response.type = "download"


# ================================================================== paramétrage sensible
@frappe.whitelist()
def config_action(name, action, motif=None):
	req = frappe.get_doc("Reg Config Change Request", name)
	if action == "controler":
		config.control(req)
	elif action == "valider":
		config.approve(req)
	elif action == "activer":
		config.activate(req)
	elif action == "rejeter":
		require_roles(*COMPLIANCE_ROLES, "OR Contrôleur")
		config.reject(req, motif)
	else:
		frappe.throw(_("Action inconnue : {0}").format(action))
	return req.statut


# ================================================================== reporting
@frappe.whitelist()
def report_action(name, action, motif=None, elements=None, reserves=None, users=None, canal=None, values=None):
	inst = _doc("Reg Report Instance", name)
	if action == "generer":
		reporting.generate(inst)
	elif action == "soumettre":
		reporting.submit_for_control(inst)
	elif action == "controler":
		require_roles(*COMPLIANCE_ROLES, "OR Contrôleur", "OR Auditeur")
		reporting.control(inst)
	elif action == "valider":
		require_roles(*COMPLIANCE_ROLES, "OR Validateur", "OR Direction Générale")
		reporting.approve(inst, reserves)
	elif action == "rejeter":
		reporting.reject(inst, motif, elements)
	elif action == "diffuser":
		reporting.distribute(inst, _json(users) if isinstance(users, str) and users.startswith("[") else
			[u.strip() for u in (users or "").split(",") if u.strip()], canal or "Plateforme")
	elif action == "transmettre":
		reporting.transmit(inst, _json(values))
	elif action == "accuse":
		v = _json(values)
		inst.accuse_reception = v.get("accuse_reception")
		if not inst.accuse_reception:
			frappe.throw(_("Joignez l'accusé de réception."))
		inst.statut = "Accusé réception obtenu"
		inst.save()
	elif action == "rejet_autorite":
		v = _json(values)
		require_text(v.get("motif_rejet_autorite"), _("Le motif de rejet de l'autorité"))
		inst.update({k: v.get(k) for k in ("motif_rejet_autorite", "courrier_autorite", "date_rejet_autorite", "nouvelle_echeance",
			"responsable_correction")})
		inst.statut = "Rejeté par le destinataire"
		inst.save()
		inst.statut = "À corriger après transmission"
		inst.save()
		return reporting.new_version(inst)
	elif action == "nouvelle_version":
		return reporting.new_version(inst)
	elif action == "exporter":
		inst.flags.reg_exporting = True
		reporting.export_files(inst)
	elif action == "cloturer":
		inst.statut = "Clôturé"
		inst.save()
	else:
		frappe.throw(_("Action inconnue : {0}").format(action))
	return frappe.db.get_value("Reg Report Instance", name, "statut")


# ================================================================== notifications
@frappe.whitelist()
def simulate_notification(rule, doctype, name):
	require_roles(*COMPLIANCE_ROLES)
	return notification.simulate(rule, doctype, name)


@frappe.whitelist()
def acknowledge(name):
	return notification.accuser_reception(name)


@frappe.whitelist()
def mark_read(name):
	return notification.marquer_lue(name)


# ================================================================== tableaux de bord
DASHBOARD_METHODS = ("taux_conformite", "taux_conformite_pondere", "obligations_actives", "echeances_en_retard", "echeances_7_jours",
	"justificatifs_en_controle", "nc_ouvertes", "nc_critiques_ouvertes", "pa_ouverts", "pa_en_retard", "taux_realisation_pa",
	"actions_en_retard", "prolongations_en_attente")


@frappe.whitelist()
def dashboard(organisation=None):
	"""Synthèse pour la page d'accueil : indicateurs clés, horizons d'échéances, ancienneté des NC, qualité des données."""
	org = organisation or user_organisation()
	if org:
		frappe.get_doc("Reg Organization", org).check_permission("read")
	inds = {}
	for m in DASHBOARD_METHODS:
		ind = frappe.db.get_value("Reg Indicator", {"methode": m, "actif": 1}, ["name", "libelle", "seuil_vigilance", "seuil_alerte",
			"sens", "unite"], as_dict=True)
		r = indicators.compute(m, org)
		r["libelle"] = ind.libelle if ind else m
		r["niveau"] = indicators.level(ind, r["valeur"] if r["calculable"] else None) if ind else None
		r["unite"] = ind.unite if ind else None
		inds[m] = r
	return {"organisation": org, "indicateurs": inds, "horizons": indicators.deadline_horizons(org),
		"anciennete_nc": indicators.nc_aging(org), "qualite": indicators.data_quality(org), "calcule_le": str(now_datetime())}


@frappe.whitelist()
def indicator_value(code, organisation=None):
	ind = frappe.get_doc("Reg Indicator", code)
	r = indicators.compute(ind.methode, organisation or user_organisation())
	r["niveau"] = indicators.level(ind, r["valeur"] if r["calculable"] else None)
	return r


def _evidence_to_provide(user, horizon=30):
	"""Justificatifs à fournir : demandes hors échéance ou échéances dans l'horizon (évite d'afficher toute l'année)."""
	rows = frappe.get_all("Reg Evidence", filters={"responsable": user,
		"statut": ("in", ("Attendu", "Demandé", "À fournir", "À compléter", "Rejeté"))},
		fields=["name", "libelle", "statut", "echeance"], limit=500)
	limit = add_days(today(), horizon)
	due = dict(frappe.get_all("Reg Deadline", filters={"name": ("in", [r.echeance for r in rows if r.echeance] or [""])},
		fields=["name", "date_limite"], as_list=True))
	return [r for r in rows if not r.echeance or (due.get(r.echeance) and str(due[r.echeance]) <= limit)][:50]


@frappe.whitelist()
def my_tasks():
	"""« À traiter aujourd'hui » : tout ce qui attend une action de l'utilisateur connecté."""
	u, t = frappe.session.user, today_date()
	open_dl = list(deadline.OPEN_STATUSES)
	return {
		"echeances_retard": frappe.get_all("Reg Deadline", filters={"responsable": u, "statut": "En retard"},
			fields=["name", "libelle", "date_limite", "criticite"], order_by="date_limite asc", limit=50),
		"echeances_proches": frappe.get_all("Reg Deadline", filters={"responsable": u, "statut": ("in", open_dl),
			"date_limite": ("between", (t, frappe.utils.add_days(t, 7)))}, fields=["name", "libelle", "date_limite", "statut"],
			order_by="date_limite asc", limit=50),
		"echeances_a_valider": frappe.get_all("Reg Deadline", filters={"validateur": u, "statut": "Soumise pour validation"},
			fields=["name", "libelle", "date_limite"], limit=50),
		"justificatifs_a_fournir": _evidence_to_provide(u),
		"justificatifs_a_controler": frappe.get_all("Reg Evidence", filters={"controleur": u,
			"statut": ("in", ("Déposé", "Soumis à nouveau", "En cours de contrôle"))}, fields=["name", "libelle", "statut"], limit=50)
			if frappe.get_meta("Reg Evidence").has_field("controleur") else [],
		"actions": frappe.get_all("Reg Corrective Action", filters={"responsable": u, "statut": ("in", action_plan.OPEN_ACTION)},
			fields=["name", "intitule", "date_fin_prevue", "statut", "en_retard"], order_by="date_fin_prevue asc", limit=50),
		"actions_a_controler": frappe.get_all("Reg Corrective Action", filters={"controleur": u, "statut": "Soumise à contrôle"},
			fields=["name", "intitule", "plan"], limit=50),
		"prolongations": frappe.get_all("Reg Extension Request", filters={"statut": "Demandée", "demandeur": ("!=", u)},
			fields=["name", "plan", "action", "nouvelle_date"], limit=50) if has_any_role(*COMPLIANCE_ROLES, "OR Validateur") else [],
		"notifications": frappe.get_all("Reg Notification Log", filters={"destinataire": u, "lu": 0},
			fields=["name", "titre", "priorite", "creation"], order_by="creation desc", limit=20),
	}


# ================================================================== audit
@frappe.whitelist()
def export_audit_trail(doctype=None, name=None, date_from=None, date_to=None):
	require_roles(*COMPLIANCE_ROLES, "OR Auditeur")
	filters = {}
	if doctype:
		filters["reference_doctype"] = doctype
	if name:
		filters["reference_name"] = name
	if date_from:
		filters["creation"] = (">=", date_from)
	rows = frappe.get_all("Reg Audit Log", filters=filters, fields=["*"], order_by="creation asc", limit=10000)
	if date_to:
		rows = [r for r in rows if getdate(r.creation) <= getdate(date_to)]
	log_audit("Export de piste d'audit", doctype="Reg Audit Log", name=None, details={"filtres": filters, "lignes": len(rows)})
	return rows


@frappe.whitelist()
def run_daily_now():
	"""Exécution manuelle des traitements quotidiens (administrateur)."""
	require_roles("OR Administrateur")
	from obligation_reglementaire import tasks
	with SystemAction():
		tasks.daily()
	return True
