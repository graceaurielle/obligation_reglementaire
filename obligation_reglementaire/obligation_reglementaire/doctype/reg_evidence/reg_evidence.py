# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from obligation_reglementaire.engine.common import check_transition, require_text
from obligation_reglementaire.engine.deadline import refresh_doc_state
from obligation_reglementaire.engine.evidence import EVIDENCE_TRANSITIONS, LOCKED, _copy_type_metadata

# Champs figés une fois le justificatif validé (l'historique probant ne se réécrit pas)
FROZEN_FIELDS = ("type_justificatif", "libelle", "obligation", "echeance", "periode_du", "periode_au", "date_emission",
	"reference_externe", "version_courante", "organisation")


class RegEvidence(Document):
	def validate(self):
		check_transition(self, EVIDENCE_TRANSITIONS)
		if self.echeance:
			dl = frappe.db.get_value("Reg Deadline", self.echeance, ["obligation", "organisation"], as_dict=True)
			if dl and self.obligation and dl.obligation != self.obligation:
				frappe.throw(_("L'échéance n'appartient pas à l'obligation indiquée."))
			if dl:
				self.obligation = self.obligation or dl.obligation
				self.organisation = self.organisation or dl.organisation
		if self.periode_du and self.periode_au and getdate(self.periode_au) < getdate(self.periode_du):
			frappe.throw(_("La période couverte est incohérente."))
		if self.date_fin_validite and self.date_debut_validite and getdate(self.date_fin_validite) < getdate(self.date_debut_validite):
			frappe.throw(_("La fin de validité précède le début de validité."))
		if self.has_value_changed("statut") and self.statut == "Annulé":
			require_text(self.motif_annulation, _("Le motif d'annulation"))
		before = self.get_doc_before_save()
		if before and before.statut in LOCKED and not frappe.flags.reg_system and not frappe.flags.reg_force_transition:
			changed = [f for f in FROZEN_FIELDS if str(before.get(f) or "") != str(self.get(f) or "")]
			if changed:
				frappe.throw(_("Justificatif {0} : champs non modifiables ({1}).").format(before.statut.lower(), ", ".join(changed)))
		if self.is_new():
			_copy_type_metadata(self)
			if not self.confidentialite and self.obligation:
				self.confidentialite = "Interne"

	def after_insert(self):
		if self.statut in ("Attendu", "À fournir", "Demandé"):
			from obligation_reglementaire.engine import notification
			notification.emit("justificatif_attendu", self)

	def on_update(self):
		if self.has_value_changed("statut"):
			refresh_doc_state(self.echeance)
