"""Page de détail d'une demande de modification de paramétrage sensible — /obligations-config-detail?name=…"""

import frappe

from obligation_reglementaire.portal_actions import config_buttons
from obligation_reglementaire.portal_common import base_context, detail_url, resoudre_noms

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-config", title="Demande de paramétrage")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Config Change Request", name):
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	doc = frappe.get_doc("Reg Config Change Request", name)
	try:
		doc.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations"
		raise frappe.Redirect

	roles = set(frappe.get_roles(user))
	buttons = [b for b in config_buttons(doc.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	rows = [{"propose_par": doc.propose_par, "controle_par": doc.controle_par, "valide_par": doc.valide_par}]
	resoudre_noms(rows, "propose_par", "controle_par", "valide_par")

	context.title = f"{doc.name} — Demande de paramétrage"
	context.doc = doc
	context.buttons = buttons
	context.propose_par_nom = rows[0]["propose_par"]
	context.controle_par_nom = rows[0]["controle_par"]
	context.valide_par_nom = rows[0]["valide_par"]
	context.cible_url = detail_url(doc.cible_doctype, doc.cible_nom)
	if not context.cible_url and doc.cible_doctype and doc.cible_nom and frappe.db.exists(doc.cible_doctype, doc.cible_nom):
		context.cible_url = frappe.utils.get_url_to_form(doc.cible_doctype, doc.cible_nom)
