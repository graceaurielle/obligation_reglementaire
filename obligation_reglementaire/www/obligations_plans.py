import frappe

from obligation_reglementaire.portal_common import base_context, resoudre_noms, user_org_filter

login_required = True
no_cache = 1

_CLOSED = ("Clôturé", "Annulé")


def get_context(context):
	user, role = base_context(context, active_page="obligations-plans",
							  title="Plans d'action réglementaires")
	org = user_org_filter(user)

	rows = frappe.get_all("Reg Action Plan", filters={**org,
		"statut": ("not in", _CLOSED)},
		fields=["name", "intitule", "statut", "criticite", "responsable",
				"date_cible", "taux_realisation", "nb_actions", "nb_actions_validees",
				"nb_actions_retard", "en_retard", "non_conformite", "obligation"],
		order_by="date_cible asc", limit_page_length=500)

	resoudre_noms(rows, "responsable")

	en_retard = sum(1 for r in rows if r.en_retard)
	from frappe.utils import flt
	taux_moyen = round(sum(flt(r.taux_realisation) for r in rows) / len(rows), 1) if rows else 0

	for r in rows:
		r["avancement"] = f"{r.nb_actions_validees or 0}/{r.nb_actions or 0}"

	context.page_title = "Plans d'action"
	context.columns = [
		{"label": "Plan", "key": "name", "link_prefix": "/obligations-plans-detail?name="},
		{"label": "Intitulé", "key": "intitule"},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Criticité", "key": "criticite", "badge": True},
		{"label": "Date cible", "key": "date_cible", "date": True},
		{"label": "Réalisation", "key": "taux_realisation", "percent": True},
		{"label": "Actions", "key": "avancement"},
		{"label": "En retard", "key": "nb_actions_retard"},
		{"label": "Responsable", "key": "responsable"},
		{"label": "NC", "key": "non_conformite", "link_prefix": "/obligations-nc-detail?name="},
	]
	context.rows = rows
	context.empty_message = "Aucun plan d'action ouvert."
	context.stats = [
		{"label": "Plans ouverts", "value": len(rows), "color": "#7c3aed"},
		{"label": "En retard", "value": en_retard, "color": "#dc2626"},
		{"label": "Réalisation moyenne", "value": f"{taux_moyen}%", "color": "#16a34a"},
	]
