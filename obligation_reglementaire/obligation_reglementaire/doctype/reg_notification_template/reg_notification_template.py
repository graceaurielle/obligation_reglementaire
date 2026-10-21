# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class RegNotificationTemplate(Document):
	def validate(self):
		from jinja2 import TemplateSyntaxError
		for f in ("sujet", "corps"):
			try:
				frappe.get_jenv().from_string(self.get(f) or "")
			except TemplateSyntaxError as e:
				frappe.throw(_("Erreur de syntaxe dans {0} : {1}").format(self.meta.get_label(f), e))
		before = self.get_doc_before_save()
		if before and (before.sujet != self.sujet or before.corps != self.corps):
			self.version = cint(before.version) + 1
		self.version = cint(self.version) or 1
