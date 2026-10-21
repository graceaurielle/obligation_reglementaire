# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from obligation_reglementaire.engine import source as engine
from obligation_reglementaire.engine.common import assert_sod, check_transition


class RegSource(Document):
	def onload(self):
		self.set_onload("relations_inverses", engine.inverse_relations_html(self))

	def validate(self):
		check_transition(self, engine.SOURCE_TRANSITIONS)
		engine.validate_source(self)
		if self.has_value_changed("statut") and self.statut == "Validée" and not frappe.flags.reg_system:
			assert_sod(frappe.session.user, self.owner if self.owner != "Administrator" else None,
				message=_("Séparation des tâches : l'auteur de la fiche ne peut pas la valider."))
			self.valide_par, self.date_validation = frappe.session.user, today()

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.statut != self.statut:
			engine.on_source_status_change(self, before.statut)
			if self.statut == "En vigueur":
				from obligation_reglementaire.engine import notification
				notification.emit("source_entree_vigueur", self)
