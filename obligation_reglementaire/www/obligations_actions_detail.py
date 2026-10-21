"""Page de détail d'une action corrective — /obligations-actions-detail?name=…"""

import frappe

from obligation_reglementaire.portal_actions import COMPLIANCE_ROLES, action_buttons
from obligation_reglementaire.portal_common import base_context, detail_url, est_operationnel_seul, resoudre_noms

login_required = True
no_cache = 1

PROOF_REVIEW_ROLES = COMPLIANCE_ROLES + ("OR Contrôleur", "OR Validateur")


def get_context(context):
	user, role = base_context(context, active_page="obligations-plans", title="Action corrective")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Corrective Action", name):
		frappe.local.flags.redirect_location = "/obligations-plans"
		raise frappe.Redirect

	action = frappe.get_doc("Reg Corrective Action", name)
	try:
		action.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-plans"
		raise frappe.Redirect

	if est_operationnel_seul(user) and action.responsable != user:
		frappe.local.flags.redirect_location = "/obligations-plans"
		raise frappe.Redirect

	plan = frappe.db.get_value("Reg Action Plan", action.plan, ["intitule", "statut"], as_dict=True)

	proofs = frappe.get_all("Reg Action Proof", filters={"action": action.name},
		fields=["name", "type_preuve", "libelle", "statut", "numero_version", "fichier",
				"deposant", "date_depot", "controleur", "motif_rejet", "commentaire_controle"],
		order_by="numero_version desc")
	resoudre_noms(proofs, "deposant", "controleur")

	roles = set(frappe.get_roles(user))
	peut_reviewer = bool(roles.intersection(PROOF_REVIEW_ROLES)) or action.controleur == user
	motifs_rejet = frappe.get_all("Reg Rejection Reason",
		filters={"actif": 1, "s_applique_a": ("in", ("Tous", "Preuve d'action"))},
		fields=["name", "libelle"], order_by="libelle")

	buttons = [b for b in action_buttons(action.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	context.title = f"{action.name} — Action corrective"
	context.action = action
	context.plan = plan
	context.plan_url = detail_url("Reg Action Plan", action.plan)
	context.proofs = proofs
	context.peut_reviewer = peut_reviewer
	context.motifs_rejet = motifs_rejet
	context.dependances = action.dependances
	context.buttons = buttons
