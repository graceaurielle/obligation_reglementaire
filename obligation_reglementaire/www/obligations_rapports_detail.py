"""Page de détail d'un rapport réglementaire — /obligations-rapports-detail?name=…"""

import frappe

from obligation_reglementaire.portal_actions import report_simple_buttons
from obligation_reglementaire.portal_common import base_context, detail_url, resoudre_noms

login_required = True
no_cache = 1

_DIFFUSABLE = ("Validé", "Diffusé")
_TRANSMISSIBLE = ("Validé", "Diffusé", "Prêt à transmettre")


def get_context(context):
	user, role = base_context(context, active_page="obligations-rapports", title="Rapport")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Report Instance", name):
		frappe.local.flags.redirect_location = "/obligations-rapports"
		raise frappe.Redirect

	doc = frappe.get_doc("Reg Report Instance", name)
	try:
		doc.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-rapports"
		raise frappe.Redirect

	roles = set(frappe.get_roles(user))
	buttons = [b for b in report_simple_buttons(doc.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	diffusions = [d.as_dict() for d in doc.get("diffusions", [])]
	resoudre_noms(diffusions, "destinataire")

	commentaires = [c.as_dict() for c in doc.get("commentaires", [])]
	resoudre_noms(commentaires, "auteur")

	context.title = f"{doc.name} — Rapport"
	context.doc = doc
	context.buttons = buttons
	context.diffusions = diffusions
	context.commentaires = commentaires
	context.peut_diffuser = doc.statut in _DIFFUSABLE
	context.peut_transmettre = doc.statut in _TRANSMISSIBLE
	context.peut_accuser = doc.statut == "Transmis"
	context.peut_rejet_autorite = doc.statut == "Transmis"
	context.version_precedente_url = detail_url("Reg Report Instance", doc.version_precedente) if doc.version_precedente else None
