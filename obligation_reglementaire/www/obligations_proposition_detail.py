"""Page de détail d'une proposition d'applicabilité — /obligations-proposition-detail?name=…"""

import frappe

from obligation_reglementaire.portal_common import base_context, detail_url, resoudre_noms

login_required = True
no_cache = 1

_DECISION_ROLES = ("OR Administrateur", "OR Responsable Conformité", "OR Analyste Réglementaire")
_FINAL = ("Générée", "Rejetée")


def get_context(context):
	user, role = base_context(context, active_page="obligations-proposition", title="Proposition d'applicabilité")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Applicability Proposal", name):
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	doc = frappe.get_doc("Reg Applicability Proposal", name)
	try:
		doc.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	roles = set(frappe.get_roles(user))
	rows = [{"decideur": doc.decideur}]
	resoudre_noms(rows, "decideur")

	context.title = f"{doc.name} — Proposition d'applicabilité"
	context.doc = doc
	context.decideur_nom = rows[0]["decideur"]
	context.peut_decider = doc.statut not in _FINAL and bool(roles.intersection(_DECISION_ROLES))
	context.obligation_url = detail_url("Reg Obligation", doc.obligation) if doc.obligation else None
