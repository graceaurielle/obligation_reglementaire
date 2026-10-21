# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today

from obligation_reglementaire.engine.common import criticality_weight

GROUPS = {"domaine": ("Reg Domain", "Domaine"), "unite": ("Reg Org Unit", "Unité"), "responsable": ("User", "Responsable"),
	"criticite": ("Reg Criticality Level", "Criticité"), "obligation": ("Reg Obligation", "Obligation")}


def execute(filters=None):
	f = frappe._dict(filters or {})
	group = f.get("regroupement") or "domaine"
	d_from = getdate(f.get("date_debut") or add_months(today(), -12))
	d_to = getdate(f.get("date_fin") or today())
	cond = {"date_limite": ("between", (d_from, d_to)), "statut": ("not in", ("Annulée", "Suspendue"))}
	if f.get("organisation"):
		cond["organisation"] = f.organisation
	rows = frappe.get_all("Reg Deadline", filters=cond, fields=["name", group, "statut", "criticite", "delai_respecte", "date_limite"],
		limit_page_length=0)
	t = getdate(today())
	agg = {}
	for r in rows:
		# Seules les échéances arrivées à terme ou traitées sont mesurées
		if getdate(r.date_limite) > t and r.statut not in ("Réalisée", "Réalisée en retard", "Non conforme", "Clôturée"):
			continue
		key = r.get(group) or _("(non renseigné)")
		a = agg.setdefault(key, frappe._dict(groupe=key, total=0, conformes=0, en_retard=0, non_conformes=0, poids_total=0, poids_conformes=0))
		w = criticality_weight(r.criticite) or 1
		ok = r.statut in ("Réalisée", "Clôturée") and r.delai_respecte
		a.total += 1
		a.poids_total += w
		if ok:
			a.conformes += 1
			a.poids_conformes += w
		elif r.statut == "Non conforme":
			a.non_conformes += 1
		else:
			a.en_retard += 1
	data = sorted(agg.values(), key=lambda a: a.groupe)
	for a in data:
		a.taux = flt(100.0 * a.conformes / a.total, 1) if a.total else 0
		a.taux_pondere = flt(100.0 * a.poids_conformes / a.poids_total, 1) if a.poids_total else 0
	dt, label = GROUPS[group]
	columns = [
		{"fieldname": "groupe", "label": _(label), "fieldtype": "Link" if dt else "Data", "options": dt, "width": 220},
		{"fieldname": "total", "label": _("Échéances mesurées"), "fieldtype": "Int", "width": 130},
		{"fieldname": "conformes", "label": _("Conformes"), "fieldtype": "Int", "width": 100},
		{"fieldname": "en_retard", "label": _("En retard / hors délai"), "fieldtype": "Int", "width": 140},
		{"fieldname": "non_conformes", "label": _("Non conformes"), "fieldtype": "Int", "width": 110},
		{"fieldname": "taux", "label": _("Taux de conformité (%)"), "fieldtype": "Percent", "width": 150},
		{"fieldname": "taux_pondere", "label": _("Taux pondéré criticité (%)"), "fieldtype": "Percent", "width": 170},
	]
	tot = sum(a.total for a in data)
	ok = sum(a.conformes for a in data)
	chart = {"data": {"labels": [str(a.groupe) for a in data], "datasets": [{"name": _("Taux (%)"), "values": [a.taux for a in data]}]},
		"type": "bar"}
	summary = [{"label": _("Échéances mesurées"), "value": tot, "indicator": "blue"},
		{"label": _("Taux global"), "value": f"{flt(100.0 * ok / tot, 1) if tot else 0} %", "indicator": "green" if tot and ok / tot >= 0.9 else "orange"}]
	return columns, data, None, chart, summary
