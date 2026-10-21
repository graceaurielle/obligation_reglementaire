# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today

from obligation_reglementaire.engine import source as engine
from obligation_reglementaire.engine.common import check_transition


class RegSourceVersion(Document):
	def validate(self):
		check_transition(self, engine.VERSION_TRANSITIONS)
		if self.is_new() and not self.version_precedente:
			self.version_precedente = frappe.db.get_value("Reg Source Version", {"source": self.source,
				"statut": ("in", ("En vigueur", "Validée"))}, "name", order_by="creation desc")
		engine.validate_version(self)
		if self.has_value_changed("statut") and self.statut in ("Validée", "En vigueur") and not self.valide_par:
			self.valide_par, self.date_validation = frappe.session.user, today()

	def on_update(self):
		if self.has_value_changed("statut") and self.statut == "En vigueur":
			engine.activate_version(self)
			from obligation_reglementaire.engine import notification
			notification.emit("source_nouvelle_version", self)
