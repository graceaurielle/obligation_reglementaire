import frappe
from frappe.utils import add_days, getdate, nowdate

from obligation_reglementaire.portal_common import (
	base_context, est_operationnel_seul, resoudre_noms, user_org_filter,
)

login_required = True
no_cache = 1

_CLOSED = ("Réalisée", "Réalisée en retard", "Annulée", "Clôturée")


def get_context(context):
	user, role = base_context(context, active_page="obligations-echeances",
							  title="Échéances réglementaires")
	org = user_org_filter(user)
	user_filter = {"responsable": user} if est_operationnel_seul(user) else {}
	aujourd = getdate(nowdate())

	rows = frappe.get_all("Reg Deadline", filters={**org, **user_filter,
		"statut": ("not in", _CLOSED)},
		fields=["name", "libelle", "obligation", "periode", "date_limite", "statut",
				"criticite", "responsable", "etat_documentaire", "en_retard"],
		order_by="date_limite asc", limit_page_length=500)

	resoudre_noms(rows, "responsable")

	# Calcul des jours restants
	for r in rows:
		if r.date_limite:
			from frappe.utils import date_diff
			r["jours"] = date_diff(r.date_limite, aujourd)
		else:
			r["jours"] = ""

	en_retard = sum(1 for r in rows if r.statut in ("En retard", "Non conforme"))
	a_traiter = sum(1 for r in rows if r.statut in ("À traiter", "En cours", "En attente"))

	context.page_title = "Échéances"
	context.columns = [
		{"label": "Échéance", "key": "name", "link_prefix": "/obligations-echeances-detail?name="},
		{"label": "Libellé", "key": "libelle"},
		{"label": "Période", "key": "periode"},
		{"label": "Date limite", "key": "date_limite", "date": True},
		{"label": "Jours", "key": "jours"},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Criticité", "key": "criticite"},
		{"label": "Justificatifs", "key": "etat_documentaire", "badge": True},
		{"label": "Responsable", "key": "responsable"},
	]
	context.rows = rows
	context.empty_message = "Aucune échéance ouverte."
	context.stats = [
		{"label": "Total ouvertes", "value": len(rows), "color": "#2563eb"},
		{"label": "En retard", "value": en_retard, "color": "#dc2626"},
		{"label": "À traiter", "value": a_traiter, "color": "#d97706"},
	]
