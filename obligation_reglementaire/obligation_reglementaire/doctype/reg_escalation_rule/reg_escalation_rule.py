# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RegEscalationRule(Document):
	def validate(self):
		levels = [s.niveau for s in self.paliers]
		if len(levels) != len(set(levels)):
			frappe.throw(_("Chaque palier doit avoir un niveau unique."))
		days = [s.jours_relatifs for s in sorted(self.paliers, key=lambda s: s.niveau)]
		if days != sorted(days):
			frappe.throw(_("Les délais des paliers doivent croître avec le niveau."))
