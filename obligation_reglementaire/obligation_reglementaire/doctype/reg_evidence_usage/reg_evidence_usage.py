# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from obligation_reglementaire.engine.common import assert_sod


class RegEvidenceUsage(Document):
	"""Réutilisation d'un justificatif existant pour une autre obligation / échéance (Ch7) : validation propre au contexte."""

	def validate(self):
		ev = frappe.db.get_value("Reg Evidence", self.justificatif, ["organisation", "statut", "version_courante", "confidentialite"],
			as_dict=True)
		if ev.statut not in ("Validé", "Validé avec réserve"):
			frappe.throw(_("Seul un justificatif validé peut être réutilisé."))
		if self.echeance:
			dl = frappe.db.get_value("Reg Deadline", self.echeance, ["organisation", "obligation"], as_dict=True)
			if dl.organisation != ev.organisation:
				frappe.throw(_("Réutilisation impossible entre organisations différentes."))
			self.obligation = self.obligation or dl.obligation
		self.organisation = ev.organisation
		self.version = self.version or ev.version_courante
		if self.has_value_changed("statut_validation") and self.statut_validation in ("Validé", "Rejeté"):
			assert_sod(frappe.session.user, self.owner, message=_("Séparation des tâches : l'auteur de la réutilisation ne peut pas la valider."))
			self.validateur, self.date_validation = frappe.session.user, today()

	def on_update(self):
		from obligation_reglementaire.engine.deadline import refresh_doc_state
		if self.echeance and self.has_value_changed("statut_validation"):
			refresh_doc_state(self.echeance)
