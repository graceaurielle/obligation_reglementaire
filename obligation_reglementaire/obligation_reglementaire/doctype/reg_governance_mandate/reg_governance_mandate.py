# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class RegGovernanceMandate(Document):
	def validate(self):
		if self.date_fin_mandat and self.date_nomination and getdate(self.date_fin_mandat) < getdate(self.date_nomination):
			frappe.throw(_("La fin de mandat précède la nomination."))
		if self.statut == "Actif" and self.agrement_autorite and not self.date_agrement:
			frappe.throw(_("Un mandat soumis à agrément ne peut être actif sans date d'agrément."))
