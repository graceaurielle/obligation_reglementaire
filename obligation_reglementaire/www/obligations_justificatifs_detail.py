"""Page de détail d'un justificatif — /obligations-justificatifs-detail?name=…"""

import frappe

from obligation_reglementaire.portal_actions import evidence_buttons
from obligation_reglementaire.portal_common import (
	base_context, detail_url, est_operationnel_seul, resoudre_noms,
)

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-justificatifs", title="Justificatif")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Evidence", name):
		frappe.local.flags.redirect_location = "/obligations-justificatifs"
		raise frappe.Redirect

	ev = frappe.get_doc("Reg Evidence", name)
	try:
		ev.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-justificatifs"
		raise frappe.Redirect

	if est_operationnel_seul(user) and ev.responsable != user:
		frappe.local.flags.redirect_location = "/obligations-justificatifs"
		raise frappe.Redirect

	versions = frappe.get_all("Reg Evidence Version", filters={"justificatif": ev.name},
		fields=["name", "numero", "statut", "fichier", "auteur", "date_depot", "commentaire", "motif_rejet"],
		order_by="numero desc")
	resoudre_noms(versions, "auteur")

	review = None
	if ev.dernier_controle:
		review = frappe.db.get_value("Reg Evidence Review", ev.dernier_controle,
			["name", "resultat", "commentaire", "corrections_attendues", "complements_attendus",
				"date_limite_resoumission", "reserve_nature", "reserve_justification", "controleur"],
			as_dict=True)
		if review:
			review.motifs = frappe.get_all("Reg Evidence Review Reason", filters={"parent": review.name},
				fields=["libelle", "commentaire"])

	roles = set(frappe.get_roles(user))
	buttons = [b for b in evidence_buttons(ev.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	context.title = f"{ev.name} — Justificatif"
	context.ev = ev
	context.versions = versions
	context.review = review
	context.buttons = buttons
	context.echeance_url = detail_url("Reg Deadline", ev.echeance)
	context.max_mo = round((frappe.db.get_value("Reg Evidence Type", ev.type_justificatif, "taille_max_mo") or 0), 1) \
		if ev.type_justificatif else 0
