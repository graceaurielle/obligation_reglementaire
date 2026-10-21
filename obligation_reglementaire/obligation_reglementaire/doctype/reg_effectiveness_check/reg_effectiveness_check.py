# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from obligation_reglementaire.engine.common import assert_sod, check_transition, today_date

EFF_TRANSITIONS = {"Planifiée": {"En cours", "Réalisée", "Annulée"}, "En cours": {"Réalisée", "Annulée"},
	"Réalisée": set(), "Annulée": set()}


class RegEffectivenessCheck(Document):
	def validate(self):
		check_transition(self, EFF_TRANSITIONS)
		plan = frappe.db.get_value("Reg Action Plan", self.plan, ["organisation", "non_conformite", "responsable"], as_dict=True)
		self.organisation = plan.organisation
		self.non_conformite = self.non_conformite or plan.non_conformite
		if self.statut == "Réalisée":
			missing = [_(self.meta.get_label(f)) for f in ("methode", "resultats", "conclusion", "resultat") if not self.get(f)]
			if missing:
				frappe.throw(_("Champs requis pour conclure la vérification : {0}").format(", ".join(missing)))
			if self.resultat != "Efficace" and not self.suite_donnee:
				frappe.throw(_("Précisez la suite donnée à une vérification non concluante."))
			self.date_realisation = self.date_realisation or today_date()
			if self.has_value_changed("statut"):
				assert_sod(frappe.session.user, plan.responsable,
					message=_("Séparation des tâches : le responsable du plan ne peut pas juger de son efficacité."))

	def on_update(self):
		from obligation_reglementaire.engine.action_plan import apply_effectiveness
		if self.has_value_changed("statut") and self.statut == "Réalisée":
			apply_effectiveness(self)
