"""Traitements planifiés : chaque étape est isolée (une erreur est journalisée sans bloquer les suivantes)."""

import frappe
from frappe.utils import getdate

from obligation_reglementaire.engine import action_plan, deadline, evidence, ged, indicators, notification, reporting
from obligation_reglementaire.engine.common import SystemAction, log_audit, today_date


def _run(label, fn, *args):
	try:
		with SystemAction():
			fn(*args)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Obligations réglementaires — {label}")


def daily():
	_run("Génération des échéances", deadline.regenerate_all)
	_run("Statuts des échéances", deadline.update_statuses)
	_run("NC sur retard", deadline.create_overdue_nc)
	_run("Expiration des justificatifs", evidence.expire_evidences)
	_run("Contrôles en retard", evidence.late_review_alerts)
	_run("Plans d'action", action_plan.daily_update)
	_run("Licences et mandats", expire_licenses_and_mandates)
	_run("Sources entrées en vigueur", activate_sources)
	_run("GED", ged.daily)
	_run("Alertes d'échéance", notification.deadline_alerts)
	_run("Relances temporelles", notification.temporal_rules)
	_run("Escalades", notification.escalate)
	_run("Annulation des relances résolues", notification.cancel_resolved)
	_run("Rapports planifiés", reporting.scheduled_generation)
	_run("Historique des indicateurs", indicators.snapshot)


def daily_digest():
	_run("Résumé quotidien", notification.daily_digest)


def hourly():
	_run("Renvoi des notifications en échec", notification.retry_failed)


def expire_licenses_and_mandates():
	t = today_date()
	for name in frappe.get_all("Reg License", filters={"statut": ("in", ("Active", "En renouvellement")),
			"date_expiration": ("<", t)}, pluck="name"):
		frappe.db.set_value("Reg License", name, "statut", "Expirée")
		log_audit("Expiration automatique de licence", doctype="Reg License", name=name)
	for name in frappe.get_all("Reg Governance Mandate", filters={"statut": "Actif", "date_fin_mandat": ("<", t)}, pluck="name"):
		frappe.db.set_value("Reg Governance Mandate", name, "statut", "Terminé")
		log_audit("Fin automatique de mandat", doctype="Reg Governance Mandate", name=name)


def activate_sources():
	"""Une source validée dont la date d'entrée en vigueur est atteinte passe « En vigueur » et déclenche la notification."""
	t = today_date()
	for name in frappe.get_all("Reg Source", filters={"statut": "Validée", "date_entree_vigueur": ("<=", t)}, pluck="name"):
		src = frappe.get_doc("Reg Source", name)
		if src.date_entree_vigueur and getdate(src.date_entree_vigueur) <= t:
			src.statut = "En vigueur"
			src.flags.ignore_permissions = True
			src.save()
