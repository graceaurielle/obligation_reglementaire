"""Page de détail d'un contrôle de justificatif — /obligations-controle-detail?name=…"""

import frappe

from obligation_reglementaire.portal_common import (
	base_context, detail_url, est_operationnel_seul,
)

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-justificatifs", title="Contrôle")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Evidence Review", name):
		frappe.local.flags.redirect_location = "/obligations-justificatifs"
		raise frappe.Redirect

	ctl = frappe.get_doc("Reg Evidence Review", name)
	try:
		ctl.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-justificatifs"
		raise frappe.Redirect

	if est_operationnel_seul(user) and ctl.controleur != user:
		frappe.local.flags.redirect_location = "/obligations-justificatifs"
		raise frappe.Redirect

	ev = frappe.db.get_value("Reg Evidence", ctl.justificatif,
		["libelle", "type_justificatif", "statut"], as_dict=True)

	motifs_options = frappe.get_all("Reg Rejection Reason",
		filters={"actif": 1, "s_applique_a": ("in", ("Tous", "Justificatif"))},
		fields=["name", "libelle"], order_by="libelle")

	context.title = f"{ctl.name} — Contrôle"
	context.ctl = ctl
	context.ev = ev
	context.ev_url = detail_url("Reg Evidence", ctl.justificatif)
	context.motifs_options = motifs_options
	context.editable = ctl.docstatus == 0
