# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RegCriticalityLevel(Document):
	def validate(self):
		if not self.poids or self.poids < 1:
			frappe.throw(_("Le poids doit être un entier strictement positif."))
		if frappe.db.exists("Reg Criticality Level", {"poids": self.poids, "name": ("!=", self.name), "actif": 1}) and self.actif:
			frappe.throw(_("Un autre niveau actif a déjà le poids {0}.").format(self.poids))
