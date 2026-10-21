# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	f = frappe._dict(filters or {})
	org = {"organisation": f.organisation} if f.get("organisation") else {}
	period = {}
	if f.get("date_debut") and f.get("date_fin"):
		period = {"date_demande": ("between", (f.date_debut, f.date_fin))}
	data = []
	if f.get("type") in (None, "", "Prolongation"):
		for r in frappe.get_all("Reg Extension Request", filters={**org, **period}, fields=["name", "type_objet", "plan", "action",
				"statut", "date_initiale", "nouvelle_date", "jours_ajoutes", "motif", "demandeur", "date_demande", "valideur", "date_decision"],
				order_by="date_demande desc", limit_page_length=0):
			data.append(frappe._dict(nature=_("Prolongation"), doctype_ref="Reg Extension Request", document=r.name,
				objet=r.action or r.plan, ancienne=r.date_initiale, nouvelle=r.nouvelle_date, jours=r.jours_ajoutes, statut=r.statut,
				motif=r.motif, demandeur=r.demandeur, date_demande=r.date_demande, decideur=r.valideur, date_decision=r.date_decision))
	if f.get("type") in (None, "", "Report d'échéance"):
		from frappe.utils import date_diff
		for r in frappe.get_all("Reg Deadline Change", filters={**org, **period}, fields=["name", "echeance", "type_modification", "statut",
				"ancienne_date", "nouvelle_date", "motif", "demandeur", "date_demande", "approbateur", "date_approbation"],
				order_by="date_demande desc", limit_page_length=0):
			data.append(frappe._dict(nature=_("Report d'échéance") + f" ({r.type_modification})", doctype_ref="Reg Deadline Change",
				document=r.name, objet=r.echeance, ancienne=r.ancienne_date, nouvelle=r.nouvelle_date,
				jours=date_diff(r.nouvelle_date, r.ancienne_date) if r.ancienne_date and r.nouvelle_date else None, statut=r.statut,
				motif=r.motif, demandeur=r.demandeur, date_demande=r.date_demande, decideur=r.approbateur, date_decision=r.date_approbation))
	if f.get("statut"):
		data = [d for d in data if d.statut == f.statut]
	columns = [
		{"fieldname": "nature", "label": _("Nature"), "fieldtype": "Data", "width": 200},
		{"fieldname": "doctype_ref", "label": _("Type"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "document", "label": _("Demande"), "fieldtype": "Dynamic Link", "options": "doctype_ref", "width": 140},
		{"fieldname": "objet", "label": _("Objet"), "fieldtype": "Data", "width": 140},
		{"fieldname": "ancienne", "label": _("Date initiale"), "fieldtype": "Date", "width": 100},
		{"fieldname": "nouvelle", "label": _("Nouvelle date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "jours", "label": _("Jours ajoutés"), "fieldtype": "Int", "width": 90},
		{"fieldname": "statut", "label": _("Statut"), "fieldtype": "Data", "width": 110},
		{"fieldname": "motif", "label": _("Motif"), "fieldtype": "Small Text", "width": 250},
		{"fieldname": "demandeur", "label": _("Demandeur"), "fieldtype": "Link", "options": "User", "width": 150},
		{"fieldname": "date_demande", "label": _("Demandée le"), "fieldtype": "Date", "width": 100},
		{"fieldname": "decideur", "label": _("Décideur"), "fieldtype": "Link", "options": "User", "width": 150},
		{"fieldname": "date_decision", "label": _("Décidée le"), "fieldtype": "Date", "width": 100},
	]
	summary = [{"label": _("Demandes"), "value": len(data), "indicator": "blue"},
		{"label": _("En attente"), "value": sum(1 for d in data if d.statut in ("Demandée", "Informations demandées")), "indicator": "orange"},
		{"label": _("Accordées"), "value": sum(1 for d in data if d.statut in ("Acceptée", "Approuvée")), "indicator": "green"},
		{"label": _("Refusées"), "value": sum(1 for d in data if d.statut in ("Refusée",)), "indicator": "red"}]
	return columns, data, None, None, summary
