# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RegAuditLog(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("Le journal d'audit est inaltérable."))

	def on_trash(self):
		frappe.throw(_("Le journal d'audit est inaltérable."))
