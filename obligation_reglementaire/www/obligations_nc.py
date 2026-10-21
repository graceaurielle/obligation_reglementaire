import frappe

from obligation_reglementaire.portal_common import base_context, resoudre_noms, user_org_filter

login_required = True
no_cache = 1

_CLOSED = ("Clôturée", "Annulée")


def get_context(context):
	user, role = base_context(context, active_page="obligations-nc",
							  title="Non-conformités réglementaires")
	org = user_org_filter(user)

	rows = frappe.get_all("Reg Non Conformity", filters={**org,
		"statut": ("not in", _CLOSED)},
		fields=["name", "intitule", "origine", "gravite", "statut", "responsable",
				"date_detection", "date_cible", "anciennete_jours", "obligation",
				"plan_action"],
		order_by="date_detection desc", limit_page_length=500)

	resoudre_noms(rows, "responsable")

	critiques = sum(1 for r in rows if r.gravite in ("Critique", "Élevée"))
	sans_plan = sum(1 for r in rows if not r.plan_action)

	context.page_title = "Non-conformités"
	context.columns = [
		{"label": "NC", "key": "name", "link_prefix": "/obligations-nc-detail?name="},
		{"label": "Intitulé", "key": "intitule"},
		{"label": "Gravité", "key": "gravite", "badge": True},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Détection", "key": "date_detection", "date": True},
		{"label": "Date cible", "key": "date_cible", "date": True},
		{"label": "Ancienneté (j)", "key": "anciennete_jours"},
		{"label": "Responsable", "key": "responsable"},
		{"label": "Plan d'action", "key": "plan_action", "link_prefix": "/obligations-plans-detail?name="},
		{"label": "Obligation", "key": "obligation", "link_prefix": "/obligations-obligation-detail?name="},
	]
	context.rows = rows
	context.empty_message = "Aucune non-conformité ouverte ✓"
	context.stats = [
		{"label": "NC ouvertes", "value": len(rows), "color": "#dc2626"},
		{"label": "Critiques / Élevées", "value": critiques, "color": "#b91c1c"},
		{"label": "Sans plan d'action", "value": sans_plan, "color": "#d97706"},
	]
