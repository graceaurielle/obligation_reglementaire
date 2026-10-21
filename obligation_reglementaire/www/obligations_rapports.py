import frappe

from obligation_reglementaire.portal_common import base_context, resoudre_noms, user_org_filter

login_required = True
no_cache = 1

_CLOSED = ("Clôturé", "Archivé")


def get_context(context):
	user, role = base_context(context, active_page="obligations-rapports",
							  title="Rapports réglementaires")
	org = user_org_filter(user)

	rows = frappe.get_all("Reg Report Instance", filters={**org,
		"statut": ("not in", _CLOSED)},
		fields=["name", "intitule", "modele", "statut", "type_periode",
				"date_debut", "date_fin", "preparateur", "controleur", "validateur",
				"date_generation", "version"],
		order_by="modified desc", limit_page_length=500)

	resoudre_noms(rows, "preparateur", "controleur", "validateur")

	en_circuit = sum(1 for r in rows if r.statut in ("À contrôler", "À valider", "Contrôlé"))
	a_corriger = sum(1 for r in rows if r.statut in ("Rejeté", "À corriger", "À corriger après transmission"))

	context.page_title = "Rapports"
	context.columns = [
		{"label": "Rapport", "key": "name", "link_prefix": "/obligations-rapports-detail?name="},
		{"label": "Intitulé", "key": "intitule"},
		{"label": "Modèle", "key": "modele"},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Période", "key": "type_periode"},
		{"label": "Du", "key": "date_debut", "date": True},
		{"label": "Au", "key": "date_fin", "date": True},
		{"label": "Version", "key": "version"},
		{"label": "Préparateur", "key": "preparateur"},
		{"label": "Contrôleur", "key": "controleur"},
		{"label": "Validateur", "key": "validateur"},
	]
	context.rows = rows
	context.empty_message = "Aucun rapport réglementaire en cours."
	context.stats = [
		{"label": "Total", "value": len(rows), "color": "#2563eb"},
		{"label": "En circuit de validation", "value": en_circuit, "color": "#d97706"},
		{"label": "À corriger", "value": a_corriger, "color": "#dc2626"},
	]
