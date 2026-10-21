"""Demandes de modification de paramétrage sensible (Ch2 / Ch11) : Proposée → Contrôlée → Validée → Activée,
avec séparation des tâches entre proposant, contrôleur et valideur, et application tracée des valeurs."""

import json

import frappe
from frappe import _
from frappe.utils import today

from obligation_reglementaire.engine.common import assert_sod, log_audit, require_roles, require_text

CONFIG_TRANSITIONS = {
	"Proposée": {"Contrôlée", "Rejetée"},
	"Contrôlée": {"Validée", "Rejetée"},
	"Validée": {"Activée", "Rejetée"},
	"Activée": set(),
	"Rejetée": set(),
}

PROTECTED = {"name", "doctype", "owner", "creation", "modified", "modified_by", "docstatus", "idx"}


def _proposed(req):
	try:
		values = json.loads(req.valeurs_proposees or "{}")
	except ValueError:
		frappe.throw(_("Les valeurs proposées doivent être un objet JSON valide."))
	if not isinstance(values, dict) or not values:
		frappe.throw(_("Les valeurs proposées doivent être un objet JSON non vide : {\"champ\": valeur}."))
	meta = frappe.get_meta(req.cible_doctype)
	unknown = [k for k in values if k in PROTECTED or not meta.has_field(k)]
	if unknown:
		frappe.throw(_("Champs inconnus ou protégés : {0}").format(", ".join(unknown)))
	return values


def validate_request(req):
	if req.cible_doctype and frappe.get_meta(req.cible_doctype).module != "Obligation Reglementaire":
		frappe.throw(_("Seuls les paramétrages du module Obligations réglementaires peuvent être modifiés ainsi."))
	values = _proposed(req)
	if req.is_new():
		req.propose_par = req.propose_par or frappe.session.user
		req.date_proposition = today()
		if req.cible_nom and frappe.db.exists(req.cible_doctype, req.cible_nom):
			target = frappe.get_doc(req.cible_doctype, req.cible_nom)
			req.valeurs_actuelles = json.dumps({k: target.get(k) for k in values}, default=str, ensure_ascii=False, indent=1)


def control(req):
	require_roles("OR Responsable Conformité", "OR Contrôleur")
	assert_sod(frappe.session.user, req.propose_par, message=_("Séparation des tâches : le proposant ne peut pas contrôler sa demande."))
	req.statut, req.controle_par, req.date_controle = "Contrôlée", frappe.session.user, today()
	req.save(ignore_permissions=True)


def approve(req):
	require_roles("OR Administrateur", "OR Responsable Conformité")
	assert_sod(frappe.session.user, req.propose_par, req.controle_par,
		message=_("Séparation des tâches : le valideur doit être distinct du proposant et du contrôleur."))
	req.statut, req.valide_par, req.date_validation = "Validée", frappe.session.user, today()
	req.save(ignore_permissions=True)


def activate(req):
	require_roles("OR Administrateur")
	if req.statut != "Validée":
		frappe.throw(_("Seule une demande validée peut être activée."))
	values = _proposed(req)
	meta = frappe.get_meta(req.cible_doctype)
	target = frappe.get_doc(req.cible_doctype, req.cible_nom) if not meta.issingle else frappe.get_single(req.cible_doctype)
	target.update(values)
	target.flags.reg_justification = _("Demande de paramétrage {0} : {1}").format(req.name, req.justification)
	target.flags.reg_config_request = req.name
	target.save(ignore_permissions=True)
	req.statut, req.date_activation = "Activée", today()
	req.save(ignore_permissions=True)
	log_audit("Activation de paramétrage", target, justification=req.justification, details={"demande": req.name, "valeurs": values})


def reject(req, motif):
	require_text(motif, _("Le motif de rejet"))
	req.statut, req.motif_rejet = "Rejetée", motif
	req.save(ignore_permissions=True)
