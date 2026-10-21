# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today


def execute(filters=None):
	f = frappe._dict(filters or {})
	cond = {}
	for k in ("organisation", "statut", "responsable", "controleur", "type_justificatif", "obligation"):
		if f.get(k):
			cond[k] = f.get(k)
	if f.get("en_souffrance"):
		cond["statut"] = ("in", ("Attendu", "Demandé", "À fournir", "À compléter", "Rejeté", "Déposé", "Soumis à nouveau", "En cours de contrôle"))
	rows = frappe.get_all("Reg Evidence", filters=cond, fields=["name", "libelle", "type_justificatif", "statut", "obligatoire", "obligation",
		"echeance", "responsable", "controleur", "date_depot", "depose_apres_echeance", "date_limite_controle", "date_validation",
		"date_fin_validite", "numero_version_courante"], order_by="modified desc", limit_page_length=0)
	dl = dict(frappe.get_all("Reg Deadline", filters={"name": ("in", [r.echeance for r in rows if r.echeance] or [""])},
		fields=["name", "date_limite"], as_list=True))
	t = getdate(today())
	data = []
	for r in rows:
		r.date_limite = dl.get(r.echeance)
		if f.get("horizon") and r.date_limite and date_diff(r.date_limite, t) > int(f.horizon):
			continue
		r.controle_en_retard = 1 if (r.date_limite_controle and r.statut in ("Déposé", "Soumis à nouveau", "En cours de contrôle")
			and getdate(r.date_limite_controle) < t) else 0
		r.expire_bientot = 1 if (r.date_fin_validite and 0 <= date_diff(r.date_fin_validite, t) <= 30) else 0
		data.append(r)
	columns = [
		{"fieldname": "name", "label": _("Justificatif"), "fieldtype": "Link", "options": "Reg Evidence", "width": 140},
		{"fieldname": "libelle", "label": _("Libellé"), "fieldtype": "Data", "width": 220},
		{"fieldname": "type_justificatif", "label": _("Type"), "fieldtype": "Link", "options": "Reg Evidence Type", "width": 150},
		{"fieldname": "statut", "label": _("Statut"), "fieldtype": "Data", "width": 120},
		{"fieldname": "obligatoire", "label": _("Obligatoire"), "fieldtype": "Check", "width": 80},
		{"fieldname": "echeance", "label": _("Échéance"), "fieldtype": "Link", "options": "Reg Deadline", "width": 140},
		{"fieldname": "date_limite", "label": _("Date limite"), "fieldtype": "Date", "width": 100},
		{"fieldname": "date_depot", "label": _("Déposé le"), "fieldtype": "Datetime", "width": 140},
		{"fieldname": "depose_apres_echeance", "label": _("Dépôt tardif"), "fieldtype": "Check", "width": 90},
		{"fieldname": "controle_en_retard", "label": _("Contrôle en retard"), "fieldtype": "Check", "width": 110},
		{"fieldname": "date_fin_validite", "label": _("Fin de validité"), "fieldtype": "Date", "width": 100},
		{"fieldname": "expire_bientot", "label": _("Expire < 30 j"), "fieldtype": "Check", "width": 90},
		{"fieldname": "numero_version_courante", "label": _("Version"), "fieldtype": "Int", "width": 70},
		{"fieldname": "responsable", "label": _("Responsable"), "fieldtype": "Link", "options": "User", "width": 150},
		{"fieldname": "controleur", "label": _("Contrôleur"), "fieldtype": "Link", "options": "User", "width": 150},
	]
	by_status = {}
	for r in data:
		by_status[r.statut] = by_status.get(r.statut, 0) + 1
	chart = {"data": {"labels": list(by_status), "datasets": [{"name": _("Justificatifs"), "values": list(by_status.values())}]}, "type": "bar"}
	summary = [{"label": _("Justificatifs"), "value": len(data), "indicator": "blue"},
		{"label": _("Validés"), "value": sum(1 for r in data if r.statut in ("Validé", "Validé avec réserve")), "indicator": "green"},
		{"label": _("Dépôts tardifs"), "value": sum(1 for r in data if r.depose_apres_echeance), "indicator": "orange"},
		{"label": _("Contrôles en retard"), "value": sum(r.controle_en_retard for r in data), "indicator": "red"}]
	return columns, data, None, chart, summary
