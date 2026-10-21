"""Indicateurs (Ch9) : taux de conformité (non calculable ≠ 0 %), taux pondéré par criticité, horizons,
retards, justificatifs, ancienneté NC, plans, prolongations, qualité des données ; historisation quotidienne."""

import json

import frappe
from frappe.utils import add_days, cint, date_diff, flt, getdate, now_datetime

from obligation_reglementaire.engine.common import criticality_weight, get_settings, today_date

ACTIVE_OBL = ("Active", "Validée")
OPEN_DL = ("À venir", "À traiter", "En cours", "En attente", "Soumise pour validation", "En retard", "Non conforme", "Reportée")
OPEN_NC = ("Ouverte", "En analyse", "En traitement", "Mesure compensatoire en place", "En attente de vérification")
OPEN_PA = ("Ouvert", "En cours", "Bloqué", "En attente de preuves", "En attente de validation", "Vérification d'efficacité", "Réouvert")


def _f(org, extra=None, field="organisation"):
	f = dict(extra or {})
	if org:
		f[field] = org
	return f


def _res(num, den, pct=True, motif=None, details=None):
	if den in (0, None) and pct:
		return {"valeur": None, "calculable": 0, "motif": motif or "Aucune donnée évaluée", "num": num, "den": den, "details": details}
	val = round(100.0 * num / den, 1) if pct else num
	return {"valeur": val, "calculable": 1, "motif": None, "num": num, "den": den, "details": details}


def _count(dt, org, extra=None):
	return frappe.db.count(dt, _f(org, extra))


def compliance_rate(org=None, filters=None):
	"""Conformes / évaluées — les obligations non évaluées sont exclues et comptées à part (Ch9.6)."""
	base = _f(org, {"statut": ("in", ACTIVE_OBL), "applicabilite": ("in", ("Applicable", "Applicable sous condition")), **(filters or {})})
	rows = frappe.get_all("Reg Obligation", filters=base, fields=["etat_conformite", "criticite"])
	evaluated = [r for r in rows if r.etat_conformite and r.etat_conformite != "Non évalué"]
	conf = [r for r in evaluated if r.etat_conformite == "Conforme"]
	res = _res(len(conf), len(evaluated), details={"non_evaluees": len(rows) - len(evaluated), "total": len(rows),
		"partielles": len([r for r in evaluated if r.etat_conformite == "Partiellement conforme"]),
		"non_conformes": len([r for r in evaluated if r.etat_conformite == "Non conforme"])})
	return res


def weighted_compliance_rate(org=None, filters=None):
	base = _f(org, {"statut": ("in", ACTIVE_OBL), "applicabilite": ("in", ("Applicable", "Applicable sous condition")), **(filters or {})})
	rows = frappe.get_all("Reg Obligation", filters=base, fields=["etat_conformite", "criticite"])
	evaluated = [r for r in rows if r.etat_conformite and r.etat_conformite != "Non évalué"]
	den = sum(criticality_weight(r.criticite) or 1 for r in evaluated)
	num = sum((criticality_weight(r.criticite) or 1) for r in evaluated if r.etat_conformite == "Conforme")
	return _res(num, den)


def deadline_horizons(org=None, filters=None):
	"""Répartition des échéances ouvertes : échues, aujourd'hui, ≤7, 8–15, 16–30, 31–60, 61–90, >90 (Ch9.9)."""
	t = today_date()
	rows = frappe.get_all("Reg Deadline", filters=_f(org, {"statut": ("in", OPEN_DL), **(filters or {})}), fields=["date_limite"])
	buckets = {"Échues": 0, "Aujourd'hui": 0, "1–7 j": 0, "8–15 j": 0, "16–30 j": 0, "31–60 j": 0, "61–90 j": 0, "> 90 j": 0}
	for r in rows:
		d = date_diff(r.date_limite, t)
		key = ("Échues" if d < 0 else "Aujourd'hui" if d == 0 else "1–7 j" if d <= 7 else "8–15 j" if d <= 15
			else "16–30 j" if d <= 30 else "31–60 j" if d <= 60 else "61–90 j" if d <= 90 else "> 90 j")
		buckets[key] += 1
	return buckets


def nc_aging(org=None):
	t = today_date()
	limits = [cint(x) for x in (get_settings().tranches_anciennete_nc or "30,60,90,180").split(",") if x.strip()]
	labels = []
	prev = 0
	for lim in limits:
		labels.append((prev, lim, f"{prev}–{lim} j" if prev else f"< {lim} j"))
		prev = lim + 1
	labels.append((prev, 10 ** 6, f"> {limits[-1]} j" if limits else "Toutes"))
	out = {lab: 0 for _a, _b, lab in labels}
	for r in frappe.get_all("Reg Non Conformity", filters=_f(org, {"statut": ("in", OPEN_NC)}), fields=["date_detection"]):
		age = date_diff(t, r.date_detection)
		for a, b, lab in labels:
			if a <= age <= b:
				out[lab] += 1
				break
	return out


def compute(method, org=None):
	t = today_date()
	if method == "taux_conformite":
		return compliance_rate(org)
	if method == "taux_conformite_pondere":
		return weighted_compliance_rate(org)
	if method == "obligations_actives":
		return _res(_count("Reg Obligation", org, {"statut": "Active"}), None, pct=False)
	if method == "obligations_non_evaluees":
		return _res(_count("Reg Obligation", org, {"statut": "Active", "etat_conformite": "Non évalué"}), None, pct=False)
	if method == "echeances_en_retard":
		return _res(_count("Reg Deadline", org, {"statut": "En retard"}), None, pct=False)
	if method == "taux_retard_echeances":
		due = _count("Reg Deadline", org, {"date_limite": ("<", t), "statut": ("not in", ("Annulée", "Suspendue"))})
		late = _count("Reg Deadline", org, {"date_limite": ("<", t), "statut": ("in", ("En retard", "Réalisée en retard", "Non conforme"))})
		return _res(late, due, motif="Aucune échéance échue")
	if method == "echeances_7_jours":
		return _res(_count("Reg Deadline", org, {"statut": ("in", OPEN_DL), "date_limite": ("between", (t, add_days(t, 7)))}), None, pct=False)
	if method == "justificatifs_attendus":
		return _res(_count("Reg Evidence", org, {"statut": ("in", ("Attendu", "Demandé", "À fournir"))}), None, pct=False)
	if method == "justificatifs_en_controle":
		return _res(_count("Reg Evidence", org, {"statut": ("in", ("Déposé", "Soumis à nouveau", "En cours de contrôle"))}), None, pct=False)
	if method == "taux_rejet_justificatifs":
		reviews = frappe.get_all("Reg Evidence Review", filters=_f(org, {"docstatus": 1}), fields=["resultat"])
		return _res(len([r for r in reviews if r.resultat == "Rejeté"]), len(reviews), motif="Aucun contrôle réalisé")
	if method == "delai_moyen_validation_justificatifs":
		rows = frappe.get_all("Reg Evidence", filters=_f(org, {"date_validation": ("is", "set"), "date_depot": ("is", "set")}),
			fields=["date_depot", "date_validation"])
		if not rows:
			return _res(0, 0, motif="Aucun justificatif validé")
		avg = sum(date_diff(r.date_validation, r.date_depot) for r in rows) / len(rows)
		return {"valeur": round(avg, 1), "calculable": 1, "motif": None, "num": avg, "den": len(rows), "details": None}
	if method == "justificatifs_expires":
		return _res(_count("Reg Evidence", org, {"statut": "Expiré"}), None, pct=False)
	if method == "nc_ouvertes":
		return _res(_count("Reg Non Conformity", org, {"statut": ("in", OPEN_NC)}), None, pct=False, details=nc_aging(org))
	if method == "nc_critiques_ouvertes":
		crit = [c.name for c in frappe.get_all("Reg Criticality Level", fields=["name", "poids"]) if cint(c.poids) >= 4]
		return _res(_count("Reg Non Conformity", org, {"statut": ("in", OPEN_NC), "gravite": ("in", crit or [""])}), None, pct=False)
	if method == "nc_anciennete_moyenne":
		rows = frappe.get_all("Reg Non Conformity", filters=_f(org, {"statut": ("in", OPEN_NC)}), fields=["date_detection"])
		if not rows:
			return _res(0, 0, motif="Aucune non-conformité ouverte")
		avg = sum(date_diff(t, r.date_detection) for r in rows) / len(rows)
		return {"valeur": round(avg, 1), "calculable": 1, "motif": None, "num": avg, "den": len(rows), "details": None}
	if method == "pa_ouverts":
		return _res(_count("Reg Action Plan", org, {"statut": ("in", OPEN_PA)}), None, pct=False)
	if method == "pa_critiques_ouverts":
		crit = [c.name for c in frappe.get_all("Reg Criticality Level", fields=["name", "poids"]) if cint(c.poids) >= 4]
		return _res(_count("Reg Action Plan", org, {"statut": ("in", OPEN_PA), "criticite": ("in", crit or [""])}), None, pct=False)
	if method == "pa_en_retard":
		return _res(_count("Reg Action Plan", org, {"statut": ("in", OPEN_PA), "en_retard": 1}), None, pct=False)
	if method == "taux_realisation_pa":
		rows = frappe.get_all("Reg Action Plan", filters=_f(org, {"statut": ("in", OPEN_PA)}), fields=["taux_realisation", "criticite"])
		den = sum(criticality_weight(r.criticite) or 1 for r in rows)
		num = sum((criticality_weight(r.criticite) or 1) * flt(r.taux_realisation) / 100 for r in rows)
		return _res(num, den, motif="Aucun plan ouvert")
	if method == "actions_en_retard":
		return _res(_count("Reg Corrective Action", org, {"en_retard": 1, "statut": ("not in", ("Validée", "Annulée"))}), None, pct=False)
	if method == "actions_bloquees":
		return _res(_count("Reg Corrective Action", org, {"statut": "Bloquée"}), None, pct=False)
	if method == "prolongations_en_attente":
		return _res(_count("Reg Extension Request", org, {"statut": ("in", ("Demandée", "Informations demandées"))}), None, pct=False)
	if method == "pa_prolonges_plusieurs_fois":
		return _res(_count("Reg Action Plan", org, {"nb_prolongations": (">=", cint(get_settings().max_prolongations_alerte or 3))}), None, pct=False)
	if method == "taux_reouverture_pa":
		closed = _count("Reg Action Plan", org, {"statut": ("in", ("Clôturé", "Réouvert"))})
		reopened = _count("Reg Action Plan", org, {"nb_reouvertures": (">", 0)})
		return _res(reopened, closed, motif="Aucun plan clôturé")
	if method == "obligations_sans_responsable":
		return _res(len(frappe.get_all("Reg Obligation", filters=_f(org, {"statut": ("in", ACTIVE_OBL)}),
			or_filters={"responsable_operationnel": ("is", "not set"), "controleur": ("is", "not set")}, pluck="name")), None, pct=False)
	if method == "sources_sans_obligation":
		used = set(frappe.get_all("Reg Obligation", filters=_f(org), pluck="source"))
		srcs = frappe.get_all("Reg Source", filters={"statut": ("in", ("Validée", "En vigueur"))}, pluck="name")
		return _res(len([s for s in srcs if s not in used]), None, pct=False)
	return {"valeur": None, "calculable": 0, "motif": f"Méthode inconnue : {method}", "num": None, "den": None, "details": None}


def level(ind, value):
	if value is None:
		return "Non calculable"
	vig, alert = ind.seuil_vigilance, ind.seuil_alerte
	if ind.sens == "Plus haut est mieux":
		if alert and value <= flt(alert):
			return "Alerte"
		if vig and value <= flt(vig):
			return "Vigilance"
	else:
		if alert and value >= flt(alert):
			return "Alerte"
		if vig and value >= flt(vig):
			return "Vigilance"
	return "Normal"


def snapshot(date=None):
	"""Historisation quotidienne des indicateurs actifs, par organisation (Ch9.45)."""
	date = getdate(date or today_date())
	orgs = frappe.get_all("Reg Organization", filters={"statut": "Active"}, pluck="name")
	for ind_name in frappe.get_all("Reg Indicator", filters={"actif": 1}, pluck="name"):
		ind = frappe.get_cached_doc("Reg Indicator", ind_name)
		for org in orgs:
			if frappe.db.exists("Reg Indicator Value", {"indicateur": ind.name, "organisation": org, "date_reference": date}):
				continue
			r = compute(ind.methode, org)
			v = frappe.get_doc({"doctype": "Reg Indicator Value", "indicateur": ind.name, "organisation": org,
				"date_reference": date, "valeur": r["valeur"] if r["valeur"] is not None else 0, "calculable": r["calculable"],
				"motif_non_calculable": r["motif"], "niveau": level(ind, r["valeur"] if r["calculable"] else None),
				"numerateur": r["num"], "denominateur": r["den"], "calcule_le": now_datetime(),
				"details": json.dumps(r["details"], default=str, ensure_ascii=False) if r["details"] else None})
			v.flags.ignore_permissions = True
			v.insert()


def data_quality(org=None):
	"""Tableau de bord qualité des données (Ch9.37)."""
	f = _f(org, {"statut": ("in", ACTIVE_OBL)})
	return {
		"Obligations sans responsable opérationnel": frappe.db.count("Reg Obligation", {**f, "responsable_operationnel": ("is", "not set")}),
		"Obligations sans contrôleur": frappe.db.count("Reg Obligation", {**f, "controleur": ("is", "not set")}),
		"Obligations sans disposition principale": frappe.db.count("Reg Obligation", {**f, "disposition_principale": ("is", "not set")}),
		"Obligations actives sans échéance": len([o for o in frappe.get_all("Reg Obligation", filters={**f, "statut": "Active",
			"nature_temporelle": ("not in", ("Permanente", "Conditionnelle", "Événementielle"))}, pluck="name")
			if not frappe.db.exists("Reg Deadline", {"obligation": o})]),
		"Obligations à revoir (évolution réglementaire)": frappe.db.count("Reg Obligation", {**f, "a_revoir": 1}),
		"Obligations rattachées à un texte abrogé": len(frappe.db.sql("""select o.name from `tabReg Obligation` o
			join `tabReg Source` s on s.name = o.source where s.statut = 'Abrogée' and o.statut in ('Active','Validée')
			{0}""".format("and o.organisation = %(org)s" if org else ""), {"org": org})),
		"Échéances sans responsable": frappe.db.count("Reg Deadline", _f(org, {"responsable": ("is", "not set"), "statut": ("in", OPEN_DL)})),
		"Justificatifs sans responsable de dépôt": frappe.db.count("Reg Evidence", _f(org, {"responsable": ("is", "not set"),
			"statut": ("in", ("Attendu", "Demandé", "À fournir"))})),
		"Non-conformités critiques sans plan": len(frappe.db.sql("""select n.name from `tabReg Non Conformity` n
			join `tabReg Criticality Level` c on c.name = n.gravite where c.poids >= 3 and ifnull(n.plan_action,'') = ''
			and n.statut not in ('Clôturée','Annulée') {0}""".format("and n.organisation = %(org)s" if org else ""), {"org": org})),
		"Actions sans date de fin": frappe.db.count("Reg Corrective Action", _f(org, {"date_fin_prevue": ("is", "not set")})),
		"Textes sans obligation rattachée": compute("sources_sans_obligation", org)["valeur"] or 0,
	}
