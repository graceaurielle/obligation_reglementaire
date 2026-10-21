# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from obligation_reglementaire.engine.common import require_text


class RegDeadlineSuspension(Document):
	def validate(self):
		require_text(self.motif, _("Le motif de suspension"))
		self.organisation = self.organisation or frappe.db.get_value("Reg Deadline", self.echeance, "organisation")
		if self.date_fin_prevue and self.date_debut and getdate(self.date_fin_prevue) < getdate(self.date_debut):
			frappe.throw(_("La fin prévue précède le début de la suspension."))
		before = self.get_doc_before_save()
		if before and before.statut != "Active" and not frappe.flags.reg_system:
			frappe.throw(_("Une suspension levée ou annulée n'est plus modifiable."))
