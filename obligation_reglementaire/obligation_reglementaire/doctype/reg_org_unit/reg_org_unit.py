# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.nestedset import NestedSet


class RegOrgUnit(NestedSet):
	def validate(self):
		if self.parent_reg_org_unit:
			org = frappe.db.get_value("Reg Org Unit", self.parent_reg_org_unit, "organisation")
			if org and self.organisation and org != self.organisation:
				frappe.throw(_("L'unité parente appartient à une autre organisation."))
			self.organisation = self.organisation or org
		if self.date_fin and self.date_debut and getdate(self.date_fin) < getdate(self.date_debut):
			frappe.throw(_("La date de fin précède la date de début."))
		if self.date_fin and getdate(self.date_fin) < getdate(frappe.utils.today()):
			self.statut = "Inactive"
