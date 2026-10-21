"""Page de détail d'une échéance réglementaire — /obligations-echeances-detail?name=…"""

import frappe

from obligation_reglementaire.portal_actions import deadline_buttons
from obligation_reglementaire.portal_common import (
	base_context, detail_url, est_operationnel_seul, resoudre_noms,
)

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-echeances", title="Échéance")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Deadline", name):
		frappe.local.flags.redirect_location = "/obligations-echeances"
		raise frappe.Redirect

	dl = frappe.get_doc("Reg Deadline", name)
	try:
		dl.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-echeances"
		raise frappe.Redirect

	if est_operationnel_seul(user) and dl.responsable != user:
		frappe.local.flags.redirect_location = "/obligations-echeances"
		raise frappe.Redirect

	obl = frappe.db.get_value("Reg Obligation", dl.obligation,
		["titre", "criticite", "statut"], as_dict=True) if dl.obligation else None

	evidences = frappe.get_all("Reg Evidence", filters={"echeance": dl.name},
		fields=["name", "libelle", "type_justificatif", "statut", "obligatoire"],
		order_by="creation desc")
	for e in evidences:
		e["detail_url"] = detail_url("Reg Evidence", e.name)

	changements = frappe.get_all("Reg Deadline Change", filters={"echeance": dl.name, "statut": "Demandée"},
		fields=["name", "nouvelle_date", "motif", "demandeur", "date_demande"])
	resoudre_noms(changements, "demandeur")

	roles = set(frappe.get_roles(user))
	buttons = [b for b in deadline_buttons(dl.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	context.title = f"{dl.name} — Échéance"
	context.dl = dl
	context.obligation = obl
	context.evidences = evidences
	context.changements_en_attente = changements
	context.buttons = buttons
	context.nc_detail_url = detail_url("Reg Non Conformity", dl.non_conformite) if dl.non_conformite else None
	context.plan_detail_url = detail_url("Reg Action Plan", dl.plan_action) if dl.plan_action else None
