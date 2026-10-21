import frappe
from frappe.utils import getdate, nowdate

from obligation_reglementaire.portal_common import (
	base_context, est_operationnel_seul, resoudre_noms, user_org_filter,
)

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-justificatifs",
							  title="Justificatifs réglementaires")
	org = user_org_filter(user)
	oper = est_operationnel_seul(user)

	# Justificatifs en souffrance
	flt = {**org, "statut": ("in", ("Attendu", "Demandé", "À fournir", "À compléter", "Rejeté",
									"Déposé", "Soumis à nouveau", "En cours de contrôle"))}
	if oper:
		flt["responsable"] = user

	rows = frappe.get_all("Reg Evidence", filters=flt,
		fields=["name", "libelle", "type_justificatif", "statut", "obligatoire",
				"echeance", "responsable", "controleur", "date_depot",
				"depose_apres_echeance", "date_limite_controle"],
		order_by="modified desc", limit_page_length=500)

	resoudre_noms(rows, "responsable", "controleur")

	aujourd = getdate(nowdate())
	a_fournir = 0
	a_controler = 0
	controle_retard = 0
	for r in rows:
		if r.statut in ("Attendu", "Demandé", "À fournir", "À compléter", "Rejeté"):
			a_fournir += 1
		if r.statut in ("Déposé", "Soumis à nouveau", "En cours de contrôle"):
			a_controler += 1
			if r.date_limite_controle and getdate(r.date_limite_controle) < aujourd:
				controle_retard += 1
				r["controle_retard"] = "Oui"
			else:
				r["controle_retard"] = ""
		else:
			r["controle_retard"] = ""

	context.page_title = "Justificatifs"
	context.columns = [
		{"label": "Justificatif", "key": "name", "link_prefix": "/obligations-justificatifs-detail?name="},
		{"label": "Libellé", "key": "libelle"},
		{"label": "Type", "key": "type_justificatif"},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Obligatoire", "key": "obligatoire"},
		{"label": "Échéance", "key": "echeance", "link_prefix": "/obligations-echeances-detail?name="},
		{"label": "Déposé le", "key": "date_depot", "date": True},
		{"label": "Dépôt tardif", "key": "depose_apres_echeance"},
		{"label": "Contrôle en retard", "key": "controle_retard"},
		{"label": "Responsable", "key": "responsable"},
	]
	context.rows = rows
	context.empty_message = "Aucun justificatif en souffrance."
	context.stats = [
		{"label": "À fournir", "value": a_fournir, "color": "#d97706"},
		{"label": "À contrôler", "value": a_controler, "color": "#4338ca"},
		{"label": "Contrôles en retard", "value": controle_retard, "color": "#dc2626"},
	]
