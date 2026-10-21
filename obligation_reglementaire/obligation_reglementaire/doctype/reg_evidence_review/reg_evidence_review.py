# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from obligation_reglementaire.engine.evidence import apply_review, validate_review


class RegEvidenceReview(Document):
	def validate(self):
		ev = frappe.db.get_value("Reg Evidence", self.justificatif, ["organisation", "obligation", "echeance", "version_courante"],
			as_dict=True)
		if not ev:
			frappe.throw(_("Justificatif introuvable."))
		self.organisation, self.obligation, self.echeance = ev.organisation, ev.obligation, ev.echeance
		self.version = self.version or ev.version_courante
		self.controleur = self.controleur or frappe.session.user
		if self.resultat:
			validate_review(self)

	def before_submit(self):
		if not self.resultat:
			frappe.throw(_("Choisissez le résultat du contrôle avant de le soumettre."))
		if self.resultat in ("Rejeté", "À compléter") and not (self.motifs or self.complements_attendus or self.corrections_attendues):
			frappe.throw(_("Précisez les motifs ou compléments attendus."))
		if self.resultat == "Validé avec réserve" and not (self.reserve_nature and self.reserve_justification):
			frappe.throw(_("Une validation avec réserve exige la nature et la justification de la réserve."))
		validate_review(self)

	def on_submit(self):
		apply_review(self)

	def on_cancel(self):
		frappe.throw(_("Une décision de contrôle ne s'annule pas : redéposez une version et effectuez un nouveau contrôle."))
