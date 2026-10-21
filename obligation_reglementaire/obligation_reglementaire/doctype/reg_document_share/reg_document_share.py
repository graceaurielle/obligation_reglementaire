# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class RegDocumentShare(Document):
	def validate(self):
		if self.is_new() and (not self.date_expiration or getdate(self.date_expiration) <= getdate(today())):
			frappe.throw(_("La date d'expiration du partage doit être future."))
		before = self.get_doc_before_save()
		if before and before.jeton != self.jeton:
			frappe.throw(_("Le jeton d'un partage n'est pas modifiable."))
