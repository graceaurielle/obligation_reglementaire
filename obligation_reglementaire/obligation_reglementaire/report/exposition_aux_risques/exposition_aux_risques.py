# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from obligation_reglementaire.engine.common import criticality_weight


def execute(filters=None):
	f = frappe._dict(filters or {})
	cond = {"statut": ("in", ("Active", "Suspendue")), "applicabilite": ("!=", "Non applicable")}
	if f.get("organisation"):
		cond["organisation"] = f.organisation
	obls = frappe.get_all("Reg Obligation", filters=cond, fields=["name", "titre", "criticite", "domaine", "proprietaire", "etat_conformite",
		"consequence_nc"], limit_page_length=0)

	def count(dt, field, filt):
		return {r[0]: r[1] for r in frappe.get_all(dt, filters=filt, fields=[field, "count(name) as n"], group_by=field, as_list=True)}

	late = count("Reg Deadline", "obligation", {"statut": ("in", ("En retard", "Non conforme"))})
	nc = count("Reg Non Conformity", "obligation", {"statut": ("not in", ("Clôturée", "Annulée"))})
	pa_late = count("Reg Action Plan", "obligation", {"en_retard": 1, "statut": ("not in", ("Clôturé", "Annulé"))})
	data = []
	for o in obls:
		w = criticality_weight(o.criticite) or 1
		r = frappe._dict(o, retards=late.get(o.name, 0), nc=nc.get(o.name, 0), pa_retard=pa_late.get(o.name, 0))
		# Score d'exposition : poids de criticité × (1 + retards + 2 × NC ouvertes + plans en retard)
		r.score = w * (r.retards + 2 * r.nc + r.pa_retard)
		r.niveau = _("Critique") if r.score >= 12 else _("Élevé") if r.score >= 6 else _("Modéré") if r.score > 0 else _("Maîtrisé")
		if r.score or f.get("tout_afficher"):
			data.append(r)
	data.sort(key=lambda r: -r.score)
	columns = [
		{"fieldname": "name", "label": _("Obligation"), "fieldtype": "Link", "options": "Reg Obligation", "width": 140},
		{"fieldname": "titre", "label": _("Titre"), "fieldtype": "Data", "width": 250},
		{"fieldname": "criticite", "label": _("Criticité"), "fieldtype": "Link", "options": "Reg Criticality Level", "width": 90},
		{"fieldname": "domaine", "label": _("Domaine"), "fieldtype": "Link", "options": "Reg Domain", "width": 110},
		{"fieldname": "retards", "label": _("Échéances en retard / NC"), "fieldtype": "Int", "width": 120},
		{"fieldname": "nc", "label": _("NC ouvertes"), "fieldtype": "Int", "width": 90},
		{"fieldname": "pa_retard", "label": _("Plans en retard"), "fieldtype": "Int", "width": 100},
		{"fieldname": "score", "label": _("Score d'exposition"), "fieldtype": "Int", "width": 120},
		{"fieldname": "niveau", "label": _("Niveau"), "fieldtype": "Data", "width": 90},
		{"fieldname": "etat_conformite", "label": _("État de conformité"), "fieldtype": "Data", "width": 140},
		{"fieldname": "proprietaire", "label": _("Propriétaire"), "fieldtype": "Link", "options": "User", "width": 160},
		{"fieldname": "consequence_nc", "label": _("Conséquence en cas de NC"), "fieldtype": "Small Text", "width": 250},
	]
	levels = {}
	for r in data:
		levels[r.niveau] = levels.get(r.niveau, 0) + 1
	chart = {"data": {"labels": list(levels), "datasets": [{"name": _("Obligations"), "values": list(levels.values())}]}, "type": "donut"}
	return columns, data, None, chart
