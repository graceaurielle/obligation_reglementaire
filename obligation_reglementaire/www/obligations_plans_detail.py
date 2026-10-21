"""Page de détail d'un plan d'action — /obligations-plans-detail?name=…"""

import frappe

from obligation_reglementaire.engine.action_plan import plan_close_blockers
from obligation_reglementaire.portal_actions import COMPLIANCE_ROLES, plan_buttons
from obligation_reglementaire.portal_common import (
	base_context, detail_url, est_operationnel_seul, resoudre_noms,
)

login_required = True
no_cache = 1

PLAN_CLOTURABLE = ("Ouvert", "En cours", "Bloqué", "Réouvert")
PLAN_PROLONGATION_BLOQUEE = ("Clôturé", "Annulé")


def get_context(context):
	user, role = base_context(context, active_page="obligations-plans", title="Plan d'action")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Action Plan", name):
		frappe.local.flags.redirect_location = "/obligations-plans"
		raise frappe.Redirect

	plan = frappe.get_doc("Reg Action Plan", name)
	try:
		plan.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-plans"
		raise frappe.Redirect

	if est_operationnel_seul(user) and plan.responsable != user:
		frappe.local.flags.redirect_location = "/obligations-plans"
		raise frappe.Redirect

	actions = frappe.get_all("Reg Corrective Action", filters={"plan": plan.name},
		fields=["name", "intitule", "statut", "priorite", "responsable", "date_fin_prevue",
				"avancement", "en_retard", "obligatoire"],
		order_by="creation asc")
	resoudre_noms(actions, "responsable")
	for a in actions:
		a["detail_url"] = detail_url("Reg Corrective Action", a.name)

	effectiveness_checks = frappe.get_all("Reg Effectiveness Check", filters={"plan": plan.name},
		fields=["name", "statut", "date_prevue", "date_realisation", "responsable", "resultat", "conclusion"],
		order_by="creation desc") if plan.efficacite_requise else []
	resoudre_noms(effectiveness_checks, "responsable")

	extensions = frappe.get_all("Reg Extension Request",
		filters={"plan": plan.name, "statut": ("in", ("Demandée", "Informations demandées"))},
		fields=["name", "type_objet", "action", "nouvelle_date", "date_initiale", "motif", "justification",
				"demandeur", "date_demande", "statut"],
		order_by="date_demande desc")
	resoudre_noms(extensions, "demandeur")

	roles = set(frappe.get_roles(user))
	buttons = [b for b in plan_buttons(plan.statut) if not b.get("roles") or roles.intersection(b["roles"])]

	context.title = f"{plan.name} — Plan d'action"
	context.plan = plan
	context.actions = actions
	context.causes = plan.causes
	context.mesures = plan.mesures_compensatoires
	context.effectiveness_checks = effectiveness_checks
	context.extensions = extensions
	context.peut_decider_extension = bool(roles.intersection(COMPLIANCE_ROLES + ("OR Validateur",)))
	context.peut_prolonger = plan.statut not in PLAN_PROLONGATION_BLOQUEE
	context.buttons = buttons
	context.blockers = plan_close_blockers(plan) if plan.statut in PLAN_CLOTURABLE else []
	context.obligation_url = detail_url("Reg Obligation", plan.obligation) if plan.obligation else None
	context.nc_url = detail_url("Reg Non Conformity", plan.non_conformite) if plan.non_conformite else None
