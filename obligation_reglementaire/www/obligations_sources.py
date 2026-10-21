import frappe

from obligation_reglementaire.portal_common import base_context, user_org_filter

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-sources",
							  title="Sources réglementaires")

	rows = frappe.get_all("Reg Source", filters={
		"statut": ("not in", ("Archivée",))},
		fields=["name", "reference_officielle", "titre_officiel", "titre_court",
				"type_source", "autorite", "statut", "date_publication",
				"date_entree_vigueur", "pays"],
		order_by="date_publication desc", limit_page_length=500)

	en_vigueur = sum(1 for r in rows if r.statut == "En vigueur")
	en_analyse = sum(1 for r in rows if r.statut in ("Brouillon", "En analyse", "Vérifiée"))

	context.page_title = "Sources réglementaires"
	context.columns = [
		{"label": "Référence", "key": "name", "link_prefix": "/obligations-sources-detail?name="},
		{"label": "Titre", "key": "titre_court"},
		{"label": "Type", "key": "type_source"},
		{"label": "Autorité", "key": "autorite", "link_prefix": "/app/reg-authority/"},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Publication", "key": "date_publication", "date": True},
		{"label": "Entrée en vigueur", "key": "date_entree_vigueur", "date": True},
		{"label": "Pays", "key": "pays"},
	]
	context.rows = rows
	context.empty_message = "Aucune source réglementaire enregistrée."
	context.stats = [
		{"label": "Total", "value": len(rows), "color": "#2563eb"},
		{"label": "En vigueur", "value": en_vigueur, "color": "#16a34a"},
		{"label": "En analyse / validation", "value": en_analyse, "color": "#d97706"},
	]
