"""Page de détail d'une non-conformité — /obligations-nc-detail?name=…"""

import frappe

from obligation_reglementaire.engine.action_plan import nc_close_blockers
from obligation_reglementaire.portal_actions import COMPLIANCE_ROLES, nc_buttons
from obligation_reglementaire.portal_common import base_context, detail_url, est_operationnel_seul

login_required = True
no_cache = 1

NC_CLOTURABLE = ("Ouverte", "En analyse", "En traitement", "Mesure compensatoire en place", "En attente de vérification")


def get_context(context):
	user, role = base_context(context, active_page="obligations-nc", title="Non-conformité")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Non Conformity", name):
		frappe.local.flags.redirect_location = "/obligations-nc"
		raise frappe.Redirect

	nc = frappe.get_doc("Reg Non Conformity", name)
	try:
		nc.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-nc"
		raise frappe.Redirect

	if est_operationnel_seul(user) and nc.responsable != user:
		frappe.local.flags.redirect_location = "/obligations-nc"
		raise frappe.Redirect

	obligation = frappe.db.get_value("Reg Obligation", nc.obligation, ["titre", "criticite"], as_dict=True) if nc.obligation else None
	plan = frappe.db.get_value("Reg Action Plan", nc.plan_action, ["statut"], as_dict=True) if nc.plan_action else None

	roles = set(frappe.get_roles(user))
	buttons = [b for b in nc_buttons(nc.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	context.title = f"{nc.name} — Non-conformité"
	context.nc = nc
	context.obligation = obligation
	context.plan = plan
	context.buttons = buttons
	context.echeance_url = detail_url("Reg Deadline", nc.echeance) if nc.echeance else None
	context.justificatif_url = detail_url("Reg Evidence", nc.justificatif) if nc.justificatif else None
	context.plan_url = detail_url("Reg Action Plan", nc.plan_action) if nc.plan_action else None
	context.peut_creer_plan = not nc.plan_action and nc.statut not in ("Clôturée", "Annulée")
	context.peut_cloturer = nc.statut in NC_CLOTURABLE and bool(roles.intersection(COMPLIANCE_ROLES + ("OR Validateur",)))
	context.blockers = nc_close_blockers(nc) if context.peut_cloturer else []
