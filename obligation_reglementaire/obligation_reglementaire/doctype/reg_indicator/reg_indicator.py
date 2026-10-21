# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RegIndicator(Document):
	def validate(self):
		if self.seuil_vigilance is not None and self.seuil_alerte is not None and self.seuil_vigilance != self.seuil_alerte:
			ok = self.seuil_alerte > self.seuil_vigilance if self.sens == "Plus bas est mieux" else self.seuil_alerte < self.seuil_vigilance
			if not ok:
				frappe.throw(_("Seuils incohérents avec le sens de l'indicateur ({0}).").format(self.sens))
