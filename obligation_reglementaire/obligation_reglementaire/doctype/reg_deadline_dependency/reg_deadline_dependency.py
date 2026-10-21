# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RegDeadlineDependency(Document):
	def validate(self):
		if self.echeance_source == self.echeance_dependante:
			frappe.throw(_("Une échéance ne peut pas dépendre d'elle-même."))
		# détection de cycle
		seen, stack = set(), [self.echeance_source]
		while stack:
			cur = stack.pop()
			if cur == self.echeance_dependante:
				frappe.throw(_("Cette dépendance créerait un cycle."))
			if cur in seen:
				continue
			seen.add(cur)
			stack += frappe.get_all("Reg Deadline Dependency", filters={"echeance_dependante": cur, "actif": 1,
				"name": ("!=", self.name or "")}, pluck="echeance_source")
