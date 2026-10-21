import frappe
from frappe.utils import add_days, getdate, nowdate

from obligation_reglementaire.portal_common import (
	base_context, est_operationnel_seul, resoudre_noms, user_org_filter,
)

login_required = True
no_cache = 1

_CLOSED_DL = ("Réalisée", "Réalisée en retard", "Annulée", "Clôturée")
_CLOSED_NC = ("Clôturée", "Annulée")
_CLOSED_PA = ("Clôturé", "Annulé")


def get_context(context):
	user, role = base_context(context, active_page="obligations",
							  title="Obligations réglementaires — Tableau de bord")

	org = user_org_filter(user)
	aujourd = getdate(nowdate())
	horizon7 = add_days(aujourd, 7)
	horizon30 = add_days(aujourd, 30)

	# Filtres de périmètre pour les opérationnels « purs »
	user_filter = {}
	if est_operationnel_seul(user):
		user_filter = {"responsable": user}
		context.vue_restreinte = True
	else:
		context.vue_restreinte = False

	# KPIs
	obligations_actives = frappe.db.count("Reg Obligation", {**org, "statut": "Active"})
	echeances_retard = frappe.db.count("Reg Deadline", {**org, **user_filter,
		"statut": ("in", ("En retard", "Non conforme"))})
	echeances_7j = frappe.db.count("Reg Deadline", {**org, **user_filter,
		"statut": ("not in", _CLOSED_DL), "date_limite": ("between", (str(aujourd), str(horizon7)))})
	echeances_30j = frappe.db.count("Reg Deadline", {**org, **user_filter,
		"statut": ("not in", _CLOSED_DL), "date_limite": ("between", (str(aujourd), str(horizon30)))})
	nc_ouvertes = frappe.db.count("Reg Non Conformity", {**org,
		"statut": ("not in", _CLOSED_NC)})
	plans_ouverts = frappe.db.count("Reg Action Plan", {**org,
		"statut": ("not in", _CLOSED_PA)})
	plans_retard = frappe.db.count("Reg Action Plan", {**org,
		"statut": ("not in", _CLOSED_PA), "en_retard": 1})
	justificatifs_a_fournir = frappe.db.count("Reg Evidence", {**org, **user_filter,
		"statut": ("in", ("Attendu", "Demandé", "À fournir", "À compléter", "Rejeté"))})
	justificatifs_a_controler = frappe.db.count("Reg Evidence", {**org,
		"statut": ("in", ("Déposé", "Soumis à nouveau", "En cours de contrôle"))})
	notifs_non_lues = frappe.db.count("Reg Notification Log", {
		"destinataire": user, "lu": 0, "statut": ("in", ("Envoyée", "Délivrée"))})

	context.kpis = [
		{"label": "Obligations actives", "value": obligations_actives, "accent": "#2563eb"},
		{"label": "Échéances en retard", "value": echeances_retard, "accent": "#dc2626"},
		{"label": "Échéances < 7 j", "value": echeances_7j, "accent": "#d97706"},
		{"label": "Échéances < 30 j", "value": echeances_30j, "accent": "#0f766e"},
		{"label": "NC ouvertes", "value": nc_ouvertes, "accent": "#ba1a1a"},
		{"label": "Plans d'action", "value": plans_ouverts, "accent": "#7c3aed",
		 "sub": f"dont {plans_retard} en retard" if plans_retard else ""},
		{"label": "Justificatifs à fournir", "value": justificatifs_a_fournir, "accent": "#0369a1"},
		{"label": "Justificatifs à contrôler", "value": justificatifs_a_controler, "accent": "#4338ca"},
		{"label": "Notifications", "value": notifs_non_lues, "accent": "#be185d"},
	]

	# Horizons d'échéances
	horizons = []
	for label, lo, hi in [("Échues", None, -1), ("Aujourd'hui", 0, 0), ("1–7 j", 1, 7),
						   ("8–15 j", 8, 15), ("16–30 j", 16, 30), ("31–60 j", 31, 60), ("> 60 j", 61, None)]:
		flt = {**org, **user_filter, "statut": ("not in", _CLOSED_DL)}
		if lo is not None and hi is not None:
			flt["date_limite"] = ("between", (str(add_days(aujourd, lo)), str(add_days(aujourd, hi))))
		elif lo is not None:
			flt["date_limite"] = (">", str(add_days(aujourd, lo - 1)))
		else:
			flt["date_limite"] = ("<", str(aujourd))
		cnt = frappe.db.count("Reg Deadline", flt)
		color = "#dc2626" if label == "Échues" else "#d97706" if label in ("Aujourd'hui", "1–7 j") else "#2563eb"
		horizons.append({"label": label, "count": cnt, "color": color})
	context.horizons = horizons

	# Échéances urgentes (retard + 7 prochains jours)
	context.echeances_urgentes = frappe.get_all("Reg Deadline", filters={**org, **user_filter,
		"statut": ("in", ("En retard", "À traiter", "En cours", "En attente")),
		"date_limite": ("<=", str(horizon7))},
		fields=["name", "libelle", "date_limite", "statut", "responsable", "obligation"],
		order_by="date_limite asc", limit=10)
	resoudre_noms(context.echeances_urgentes, "responsable")

	# NC récentes
	context.nc_recentes = frappe.get_all("Reg Non Conformity", filters={**org,
		"statut": ("not in", _CLOSED_NC)},
		fields=["name", "intitule", "gravite", "statut", "responsable", "date_detection"],
		order_by="date_detection desc", limit=6)
	resoudre_noms(context.nc_recentes, "responsable")
