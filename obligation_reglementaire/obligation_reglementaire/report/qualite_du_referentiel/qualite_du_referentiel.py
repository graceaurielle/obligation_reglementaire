# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _

CHECKS = [
	("source", "Source réglementaire absente"),
	("proprietaire", "Propriétaire non désigné"),
	("responsable_operationnel", "Responsable opérationnel non désigné"),
	("validateur", "Valideur non désigné"),
	("criticite", "Criticité non qualifiée"),
	("domaine", "Domaine non renseigné"),
	("direction", "Direction non renseignée"),
]


def execute(filters=None):
	f = frappe._dict(filters or {})
	cond = {"statut": ("not in", ("Archivée", "Obsolète"))}
	if f.get("organisation"):
		cond["organisation"] = f.organisation
	obls = frappe.get_all("Reg Obligation", filters=cond, fields=["name", "titre", "statut", "nature_temporelle", "frequence",
		"justificatif_requis", "a_revoir", "motif_revue", "controleur", "applicabilite"] + [c[0] for c in CHECKS], limit_page_length=0)
	with_evidence = set(frappe.get_all("Reg Obligation Evidence", filters={"parenttype": "Reg Obligation"}, pluck="parent"))
	with_deadlines = set(frappe.get_all("Reg Deadline", distinct=True, pluck="obligation"))
	data = []
	for o in obls:
		anomalies = [_(label) for fn, label in CHECKS if not o.get(fn)]
		if o.nature_temporelle == "Périodique" and not o.frequence:
			anomalies.append(_("Fréquence absente pour une obligation périodique"))
		if o.justificatif_requis and o.name not in with_evidence:
			anomalies.append(_("Justificatif requis mais aucun type attendu"))
		if o.statut == "Active" and o.nature_temporelle in ("Périodique", "Ponctuelle") and o.name not in with_deadlines:
			anomalies.append(_("Obligation active sans échéance"))
		if o.a_revoir:
			anomalies.append(_("À revoir : {0}").format(o.motif_revue or ""))
		if o.responsable_operationnel and o.validateur and o.responsable_operationnel == o.validateur:
			anomalies.append(_("Séparation des tâches : responsable = valideur"))
		if not anomalies and not f.get("tout_afficher"):
			continue
		data.append(frappe._dict(name=o.name, titre=o.titre, statut=o.statut, nb=len(anomalies),
			score=round(100 * (1 - len(anomalies) / (len(CHECKS) + 5)), 0), anomalies=" ; ".join(anomalies)))
	data.sort(key=lambda r: -r.nb)
	columns = [
		{"fieldname": "name", "label": _("Obligation"), "fieldtype": "Link", "options": "Reg Obligation", "width": 140},
		{"fieldname": "titre", "label": _("Titre"), "fieldtype": "Data", "width": 260},
		{"fieldname": "statut", "label": _("Statut"), "fieldtype": "Data", "width": 110},
		{"fieldname": "nb", "label": _("Anomalies"), "fieldtype": "Int", "width": 90},
		{"fieldname": "score", "label": _("Score qualité"), "fieldtype": "Percent", "width": 110},
		{"fieldname": "anomalies", "label": _("Détail"), "fieldtype": "Small Text", "width": 500},
	]
	complete = len(obls) - sum(1 for r in data if r.nb)
	summary = [{"label": _("Obligations analysées"), "value": len(obls), "indicator": "blue"},
		{"label": _("Fiches complètes"), "value": complete, "indicator": "green"},
		{"label": _("Fiches avec anomalies"), "value": len(obls) - complete, "indicator": "orange"},
		{"label": _("Taux de complétude"), "value": f"{round(100 * complete / len(obls), 1) if obls else 0} %", "indicator": "blue"}]
	return columns, data, None, None, summary
