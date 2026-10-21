import frappe

from obligation_reglementaire.portal_common import base_context, user_org_filter

login_required = True
no_cache = 1

_CLOSED = ("Archivé", "Supprimé logiquement")


def get_context(context):
	user, role = base_context(context, active_page="obligations-documents",
							  title="Documents réglementaires")
	org = user_org_filter(user)

	rows = frappe.get_all("Reg Document", filters={**org,
		"statut": ("not in", _CLOSED)},
		fields=["name", "titre", "reference_documentaire", "type_document", "categorie",
				"statut", "confidentialite", "numero_version", "gel",
				"date_depot", "date_expiration"],
		order_by="modified desc", limit_page_length=500)

	publies = sum(1 for r in rows if r.statut == "Publié")
	geles = sum(1 for r in rows if r.gel)

	context.page_title = "Documents"
	context.columns = [
		{"label": "Document", "key": "name", "link_prefix": "/obligations-documents-detail?name="},
		{"label": "Titre", "key": "titre"},
		{"label": "Référence", "key": "reference_documentaire"},
		{"label": "Type", "key": "type_document"},
		{"label": "Catégorie", "key": "categorie"},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Confidentialité", "key": "confidentialite"},
		{"label": "Version", "key": "numero_version"},
		{"label": "Dépôt", "key": "date_depot", "date": True},
		{"label": "Expiration", "key": "date_expiration", "date": True},
	]
	context.rows = rows
	context.empty_message = "Aucun document réglementaire enregistré."
	context.stats = [
		{"label": "Total", "value": len(rows), "color": "#2563eb"},
		{"label": "Publiés", "value": publies, "color": "#16a34a"},
		{"label": "Sous gel", "value": geles, "color": "#dc2626"},
	]
