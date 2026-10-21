# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, today


def execute(filters=None):
	f = frappe._dict(filters or {})
	user = f.get("utilisateur") or frappe.session.user
	horizon = add_days(today(), int(f.get("horizon") or 7))
	org = {"organisation": f.organisation} if f.get("organisation") else {}
	data = []

	def add(kind, doctype, rows, title_field, date_field, role):
		for r in rows:
			data.append(frappe._dict(type=_(kind), doctype_ref=doctype, document=r.name, libelle=r.get(title_field), date=r.get(date_field),
				statut=r.statut, role=_(role)))

	mine = lambda field: {field: user} if not f.get("tous") else {}
	add("Échéance", "Reg Deadline", frappe.get_all("Reg Deadline", filters={**org, **mine("responsable"), "date_limite": ("<=", horizon),
		"statut": ("in", ("À venir", "À traiter", "En cours", "En attente", "En retard"))},
		fields=["name", "libelle", "date_limite", "statut"]), "libelle", "date_limite", "Responsable")
	add("Échéance à valider", "Reg Deadline", frappe.get_all("Reg Deadline", filters={**org, **mine("validateur"),
		"statut": "Soumise pour validation"}, fields=["name", "libelle", "date_limite", "statut"]), "libelle", "date_limite", "Valideur")
	add("Justificatif à contrôler", "Reg Evidence", frappe.get_all("Reg Evidence", filters={**org, **mine("controleur"),
		"statut": ("in", ("Déposé", "Soumis à nouveau", "En cours de contrôle"))},
		fields=["name", "libelle", "date_limite_controle", "statut"]), "libelle", "date_limite_controle", "Contrôleur")
	add("Justificatif à compléter", "Reg Evidence", frappe.get_all("Reg Evidence", filters={**org, **mine("responsable"),
		"statut": ("in", ("À compléter", "Rejeté"))}, fields=["name", "libelle", "date_limite_resoumission", "statut"]),
		"libelle", "date_limite_resoumission", "Responsable")
	add("Action corrective", "Reg Corrective Action", frappe.get_all("Reg Corrective Action", filters={**org, **mine("responsable"),
		"date_fin_prevue": ("<=", horizon), "statut": ("in", ("Non commencée", "Planifiée", "En cours", "Bloquée", "Retour pour correction"))},
		fields=["name", "intitule", "date_fin_prevue", "statut"]), "intitule", "date_fin_prevue", "Responsable")
	add("Action à contrôler", "Reg Corrective Action", frappe.get_all("Reg Corrective Action", filters={**org, **mine("controleur"),
		"statut": "Soumise à contrôle"}, fields=["name", "intitule", "date_fin_prevue", "statut"]), "intitule", "date_fin_prevue", "Contrôleur")
	add("Clôture de plan à valider", "Reg Action Plan", frappe.get_all("Reg Action Plan", filters={**org, **mine("valideur"),
		"statut": ("in", ("En attente de validation", "Vérification d'efficacité"))}, fields=["name", "intitule", "date_cible", "statut"]),
		"intitule", "date_cible", "Valideur")
	add("Prolongation à décider", "Reg Extension Request", frappe.get_all("Reg Extension Request", filters={**org, **mine("valideur"),
		"statut": "Demandée"}, fields=["name", "motif", "nouvelle_date", "statut"]), "motif", "nouvelle_date", "Valideur")
	data.sort(key=lambda r: str(r.date or "9999"))
	columns = [
		{"fieldname": "type", "label": _("Type"), "fieldtype": "Data", "width": 170},
		{"fieldname": "doctype_ref", "label": _("Type de document"), "fieldtype": "Data", "hidden": 1},
		{"fieldname": "document", "label": _("Document"), "fieldtype": "Dynamic Link", "options": "doctype_ref", "width": 150},
		{"fieldname": "libelle", "label": _("Libellé"), "fieldtype": "Data", "width": 300},
		{"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "statut", "label": _("Statut"), "fieldtype": "Data", "width": 140},
		{"fieldname": "role", "label": _("Mon rôle"), "fieldtype": "Data", "width": 110},
	]
	return columns, data
