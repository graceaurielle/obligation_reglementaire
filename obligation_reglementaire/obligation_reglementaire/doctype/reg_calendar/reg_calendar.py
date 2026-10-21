# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RegCalendar(Document):
	def validate(self):
		if not any(self.get(d) for d in ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")):
			frappe.throw(_("Au moins un jour ouvré doit être coché."))
		seen = set()
		for h in self.jours_feries:
			if h.date in seen:
				frappe.throw(_("Jour férié en double : {0}").format(h.date))
			seen.add(h.date)
