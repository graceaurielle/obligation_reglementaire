# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

HORIZONS = [("Échues", None, -1), ("Aujourd'hui", 0, 0), ("1–7 j", 1, 7), ("8–15 j", 8, 15), ("16–30 j", 16, 30),
	("31–60 j", 31, 60), ("61–90 j", 61, 90), ("> 90 j", 91, None)]
CLOSED = ("Réalisée", "Réalisée en retard", "Annulée", "Clôturée")


def horizon_of(days):
	for label, lo, hi in HORIZONS:
		if (lo is None or days >= lo) and (hi is None or days <= hi):
			return label


def execute(filters=None):
	f = frappe._dict(filters or {})
	cond = {"statut": ("not in", CLOSED)}
	for k in ("organisation", "responsable", "domaine", "criticite", "unite"):
		if f.get(k):
			cond[k] = f.get(k)
	rows = frappe.get_all("Reg Deadline", filters=cond, fields=["name", "libelle", "obligation", "periode", "date_limite", "statut",
		"criticite", "responsable", "unite", "etat_documentaire"], order_by="date_limite asc", limit_page_length=0)
	t = getdate(today())
	data = []
	for r in rows:
		r.jours = date_diff(r.date_limite, t)
		r.horizon = horizon_of(r.jours)
		if f.get("horizon") and r.horizon != f.horizon:
			continue
		data.append(r)
	columns = [
		{"fieldname": "horizon", "label": _("Horizon"), "fieldtype": "Data", "width": 100},
		{"fieldname": "name", "label": _("Échéance"), "fieldtype": "Link", "options": "Reg Deadline", "width": 140},
		{"fieldname": "libelle", "label": _("Libellé"), "fieldtype": "Data", "width": 260},
		{"fieldname": "obligation", "label": _("Obligation"), "fieldtype": "Link", "options": "Reg Obligation", "width": 130},
		{"fieldname": "periode", "label": _("Période"), "fieldtype": "Data", "width": 110},
		{"fieldname": "date_limite", "label": _("Date limite"), "fieldtype": "Date", "width": 100},
		{"fieldname": "jours", "label": _("Jours restants"), "fieldtype": "Int", "width": 90},
		{"fieldname": "statut", "label": _("Statut"), "fieldtype": "Data", "width": 120},
		{"fieldname": "criticite", "label": _("Criticité"), "fieldtype": "Link", "options": "Reg Criticality Level", "width": 90},
		{"fieldname": "responsable", "label": _("Responsable"), "fieldtype": "Link", "options": "User", "width": 160},
		{"fieldname": "unite", "label": _("Unité"), "fieldtype": "Link", "options": "Reg Org Unit", "width": 120},
		{"fieldname": "etat_documentaire", "label": _("Justificatifs"), "fieldtype": "Data", "width": 130},
	]
	counts = {h[0]: 0 for h in HORIZONS}
	for r in data:
		counts[r.horizon] += 1
	chart = {"data": {"labels": list(counts), "datasets": [{"name": _("Échéances"), "values": list(counts.values())}]},
		"type": "bar", "colors": ["#e24c4c"]}
	summary = [{"label": _(k), "value": v, "indicator": "red" if k == "Échues" else ("orange" if k in ("Aujourd'hui", "1–7 j") else "blue")}
		for k, v in counts.items()]
	return columns, data, None, chart, summary
