# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from obligation_reglementaire.engine.common import check_transition, require_text

ORG_TRANSITIONS = {"Active": {"Suspendue", "Inactive"}, "Suspendue": {"Active", "Inactive"}, "Inactive": {"Active"}}


class RegOrganization(Document):
	def validate(self):
		check_transition(self, ORG_TRANSITIONS)
		self.code = (self.code or "").strip().upper()
		if self.is_new():
			self.date_activation = self.date_activation or today()
		if self.has_value_changed("statut"):
			if self.statut == "Suspendue":
				require_text(self.motif_suspension, _("Le motif de suspension"))
			if self.statut == "Inactive":
				self.date_desactivation = today()
