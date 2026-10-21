# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RegTemplateUpdateNotice(Document):
	def validate(self):
		before = self.get_doc_before_save()
		if before and before.statut == "Décidée" and not self.flags.ignore_permissions:
			frappe.throw(frappe._("Cette mise à jour a déjà été décidée."))
