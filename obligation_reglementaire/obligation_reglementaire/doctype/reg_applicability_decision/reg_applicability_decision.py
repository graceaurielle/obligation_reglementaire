# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from obligation_reglementaire.engine.applicability import apply_decision, validate_decision
from obligation_reglementaire.engine.common import check_transition

DECISION_TRANSITIONS = {"Proposée": {"Validée", "Rejetée"}, "Validée": {"Remplacée"}, "Rejetée": set(), "Remplacée": set()}


class RegApplicabilityDecision(Document):
	def validate(self):
		check_transition(self, DECISION_TRANSITIONS)
		self.decideur = self.decideur or frappe.session.user
		if self.obligation and not self.organisation:
			self.organisation = frappe.db.get_value("Reg Obligation", self.obligation, "organisation")
		validate_decision(self)

	def on_update(self):
		from obligation_reglementaire.engine import notification
		if self.has_value_changed("statut") and self.statut == "Validée":
			apply_decision(self)
			if self.obligation:
				obl = frappe.get_doc("Reg Obligation", self.obligation)
				notification.emit("obligation_non_applicable" if self.decision == "Non applicable" else "obligation_applicable", obl)
