# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class RegLicense(Document):
	def validate(self):
		if self.date_expiration and self.date_delivrance and getdate(self.date_expiration) < getdate(self.date_delivrance):
			frappe.throw(_("La date d'expiration précède la date de délivrance."))
		if self.statut == "Active" and self.date_expiration and getdate(self.date_expiration) < getdate(today()):
			self.statut = "Expirée"
