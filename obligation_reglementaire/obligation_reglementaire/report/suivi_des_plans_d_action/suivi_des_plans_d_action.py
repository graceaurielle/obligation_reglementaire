# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today


def execute(filters=None):
	f = frappe._dict(filters or {})
	cond = {}
	for k in ("organisation", "responsable", "criticite", "statut", "direction"):
		if f.get(k):
			cond[k] = f.get(k)
	if f.get("ouverts_seulement"):
		cond["statut"] = ("not in", ("Clôturé", "Annulé"))
	if f.get("en_retard"):
		cond["en_retard"] = 1
	data = frappe.get_all("Reg Action Plan", filters=cond, fields=["name", "intitule", "origine", "statut", "criticite", "responsable",
		"direction", "date_cible", "taux_realisation", "nb_actions", "nb_actions_validees", "nb_actions_retard", "en_retard",
		"nb_prolongations", "non_conformite", "obligation"], order_by="date_cible asc", limit_page_length=0)
	t = getdate(today())
	for r in data:
		r.jours = date_diff(r.date_cible, t) if r.date_cible else None
	columns = [
		{"fieldname": "name", "label": _("Plan"), "fieldtype": "Link", "options": "Reg Action Plan", "width": 140},
		{"fieldname": "intitule", "label": _("Intitulé"), "fieldtype": "Data", "width": 240},
		{"fieldname": "statut", "label": _("Statut"), "fieldtype": "Data", "width": 140},
		{"fieldname": "criticite", "label": _("Criticité"), "fieldtype": "Link", "options": "Reg Criticality Level", "width": 90},
		{"fieldname": "responsable", "label": _("Responsable"), "fieldtype": "Link", "options": "User", "width": 160},
		{"fieldname": "date_cible", "label": _("Date cible"), "fieldtype": "Date", "width": 100},
		{"fieldname": "jours", "label": _("Jours restants"), "fieldtype": "Int", "width": 90},
		{"fieldname": "taux_realisation", "label": _("Réalisation (%)"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "nb_actions", "label": _("Actions"), "fieldtype": "Int", "width": 70},
		{"fieldname": "nb_actions_validees", "label": _("Validées"), "fieldtype": "Int", "width": 70},
		{"fieldname": "nb_actions_retard", "label": _("En retard"), "fieldtype": "Int", "width": 80},
		{"fieldname": "nb_prolongations", "label": _("Prolongations"), "fieldtype": "Int", "width": 100},
		{"fieldname": "non_conformite", "label": _("NC"), "fieldtype": "Link", "options": "Reg Non Conformity", "width": 120},
		{"fieldname": "obligation", "label": _("Obligation"), "fieldtype": "Link", "options": "Reg Obligation", "width": 130},
	]
	by_status = {}
	for r in data:
		by_status[r.statut] = by_status.get(r.statut, 0) + 1
	chart = {"data": {"labels": list(by_status), "datasets": [{"name": _("Plans"), "values": list(by_status.values())}]}, "type": "pie"}
	summary = [{"label": _("Plans"), "value": len(data), "indicator": "blue"},
		{"label": _("En retard"), "value": sum(1 for r in data if r.en_retard), "indicator": "red"},
		{"label": _("Réalisation moyenne"), "value": f"{round(sum(r.taux_realisation or 0 for r in data) / len(data), 1) if data else 0} %",
			"indicator": "green"}]
	return columns, data, None, chart, summary
