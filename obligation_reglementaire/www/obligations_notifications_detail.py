"""Page de détail d'une notification réglementaire — /obligations-notifications-detail?name=…"""

import frappe

from obligation_reglementaire.portal_common import base_context, detail_url

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-notifications", title="Notification")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Notification Log", name):
		frappe.local.flags.redirect_location = "/obligations-notifications"
		raise frappe.Redirect

	log = frappe.get_doc("Reg Notification Log", name)
	if log.destinataire != user:
		frappe.local.flags.redirect_location = "/obligations-notifications"
		raise frappe.Redirect

	context.title = f"{log.name} — Notification"
	context.log = log
	context.lien_href = detail_url(log.reference_doctype, log.reference_name) if (
		log.reference_doctype and log.reference_name) else None
	context.peut_marquer_lue = not log.lu
	context.peut_accuser = bool(log.accuse_requis) and not log.date_accuse
