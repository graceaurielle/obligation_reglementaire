"""Page de détail d'un document réglementaire — /obligations-documents-detail?name=…"""

import frappe

from obligation_reglementaire.portal_actions import document_buttons
from obligation_reglementaire.portal_common import base_context, detail_url, resoudre_noms

login_required = True
no_cache = 1

_PARTAGE_INTERDIT = ("Strictement confidentiel", "Sensible")
_VERSION_EN_ATTENTE = ("Soumise", "En contrôle")


def get_context(context):
	user, role = base_context(context, active_page="obligations-documents", title="Document")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Document", name):
		frappe.local.flags.redirect_location = "/obligations-documents"
		raise frappe.Redirect

	doc = frappe.get_doc("Reg Document", name)
	try:
		doc.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-documents"
		raise frappe.Redirect

	roles = set(frappe.get_roles(user))
	buttons = [b for b in document_buttons(doc.statut, doc.gel) if not b.get("roles") or roles.intersection(b["roles"])]

	versions = frappe.get_all("Reg Document Version", filters={"document": name},
		fields=["name", "numero", "type_version", "statut", "deposant", "date_depot",
				"nom_fichier", "commentaire", "motif_rejet", "commentaire_rejet", "valide_par", "date_validation"],
		order_by="creation desc", limit_page_length=200)
	resoudre_noms(versions, "deposant", "valide_par")
	for v in versions:
		v["peut_valider"] = v.statut in _VERSION_EN_ATTENTE and v.deposant != user

	shares = frappe.get_all("Reg Document Share", filters={"document": name},
		fields=["name", "destinataire", "statut", "date_expiration", "nb_acces", "dernier_acces", "motif"],
		order_by="creation desc", limit_page_length=100)

	context.title = f"{doc.name} — Document"
	context.doc = doc
	context.buttons = buttons
	context.versions = versions
	context.shares = shares
	context.peut_deposer = not doc.gel and doc.statut != "Supprimé logiquement"
	context.peut_partager = doc.statut in ("Validé", "Publié") and doc.confidentialite not in _PARTAGE_INTERDIT
	context.obligation_url = detail_url("Reg Obligation", doc.obligation) if doc.obligation else None
	context.echeance_url = detail_url("Reg Deadline", doc.echeance) if doc.echeance else None
	context.justificatif_url = detail_url("Reg Evidence", doc.justificatif) if doc.justificatif else None
	context.nc_url = detail_url("Reg Non Conformity", doc.non_conformite) if doc.non_conformite else None
	context.plan_url = detail_url("Reg Action Plan", doc.plan_action) if doc.plan_action else None
	context.source_url = detail_url("Reg Source", doc.source) if doc.source else None
