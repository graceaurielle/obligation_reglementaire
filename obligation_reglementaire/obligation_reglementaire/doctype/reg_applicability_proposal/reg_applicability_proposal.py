# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RegApplicabilityProposal(Document):
	def validate(self):
		if self.modele and not self.intitule_modele:
			self.intitule_modele = frappe.db.get_value("Reg Template Obligation", self.modele, "intitule")
		if self.profil and not self.organisation:
			self.organisation = frappe.db.get_value("Reg Profile", self.profil, "organisation")
