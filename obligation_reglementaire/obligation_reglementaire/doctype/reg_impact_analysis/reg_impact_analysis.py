# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from obligation_reglementaire.engine import source as engine
from obligation_reglementaire.engine.common import assert_sod, check_transition

IMPACT_TRANSITIONS = {"À analyser": {"En cours", "Terminée"}, "En cours": {"Terminée", "À analyser"},
	"Terminée": {"Validée", "En cours"}, "Validée": set()}


class RegImpactAnalysis(Document):
	def validate(self):
		check_transition(self, IMPACT_TRANSITIONS)
		engine.validate_impact(self)
		if self.has_value_changed("statut") and self.statut == "Validée":
			assert_sod(frappe.session.user, self.analyste, message=frappe._("Séparation des tâches : l'analyste ne peut pas valider son analyse."))

	def after_insert(self):
		from obligation_reglementaire.engine import notification
		notification.emit("impact_a_analyser", self)

	def on_update(self):
		if self.has_value_changed("statut") and self.statut == "Validée":
			engine.apply_impact(self)
