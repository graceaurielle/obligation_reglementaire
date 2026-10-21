"""Page de détail d'une obligation réglementaire — /obligations-obligation-detail?name=…"""

import frappe

from obligation_reglementaire.engine.deadline import OPEN_STATUSES
from obligation_reglementaire.obligation_reglementaire.doctype.reg_obligation.reg_obligation import (
	OBLIGATION_TRANSITIONS, SENSITIVE,
)
from obligation_reglementaire.portal_actions import COMPLIANCE_ROLES, obligation_buttons
from obligation_reglementaire.portal_common import (
	base_context, detail_url, est_operationnel_seul, resoudre_noms,
)

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations", title="Obligation")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Obligation", name):
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	obligation = frappe.get_doc("Reg Obligation", name)
	try:
		obligation.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	if est_operationnel_seul(user) and obligation.proprietaire != user and obligation.responsable_operationnel != user:
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	echeances = frappe.get_all("Reg Deadline", filters={"obligation": name, "statut": ("in", OPEN_STATUSES)},
		fields=["name", "periode", "date_limite", "statut", "responsable"],
		order_by="date_limite asc")
	resoudre_noms(echeances, "responsable")
	for e in echeances:
		e["detail_url"] = detail_url("Reg Deadline", e.name)

	non_conformites = frappe.get_all("Reg Non Conformity", filters={"obligation": name,
			"statut": ("not in", ("Clôturée", "Annulée"))},
		fields=["name", "intitule", "gravite", "statut", "responsable"],
		order_by="date_detection desc")
	resoudre_noms(non_conformites, "responsable")
	for nc in non_conformites:
		nc["detail_url"] = detail_url("Reg Non Conformity", nc.name)

	roles = set(frappe.get_roles(user))
	buttons = [b for b in obligation_buttons(obligation.statut, OBLIGATION_TRANSITIONS)
		if not b.get("roles") or roles.intersection(b["roles"])]

	champs_sensibles = [{"field": f, "label": obligation.meta.get_label(f), "value": obligation.get(f)} for f in SENSITIVE]

	context.title = f"{obligation.name} — Obligation"
	context.obligation = obligation
	context.source_url = detail_url("Reg Source", obligation.source) if obligation.source else None
	context.echeances = echeances
	context.non_conformites = non_conformites
	context.buttons = buttons
	context.peut_generer_echeances = obligation.statut == "Active"
	context.peut_modifier_justifie = obligation.statut in ("Active", "Suspendue") and bool(
		roles.intersection(COMPLIANCE_ROLES + ("OR Validateur", "OR Analyste Réglementaire", "OR Responsable Obligation")))
	context.champs_sensibles = champs_sensibles
