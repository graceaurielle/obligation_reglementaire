# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from obligation_reglementaire.engine.common import check_transition, require_text, today_date

EVENT_TRANSITIONS = {
	"Enregistré": {"Qualifié", "Traité", "Annulé"},
	"Qualifié": {"Traité", "Annulé"},
	"Traité": {"Clôturé", "Annulé"},
	"Clôturé": set(),
	"Annulé": set(),
}


class RegEventOccurrence(Document):
	def validate(self):
		check_transition(self, EVENT_TRANSITIONS)
		self.enregistre_par = self.enregistre_par or frappe.session.user
		self.date_evenement = self.date_evenement or today_date()
		if self.date_connaissance and getdate(self.date_connaissance) < getdate(self.date_evenement):
			frappe.throw(_("La date de connaissance ne peut pas précéder la date de l'événement."))
		if getdate(self.date_evenement) > getdate(today_date()):
			frappe.throw(_("Un événement déclencheur ne peut pas être daté dans le futur."))
		if self.has_value_changed("statut") and self.statut == "Annulé":
			require_text(self.motif_annulation, _("Le motif d'annulation"))
		if not self.is_new() and self.statut != "Annulé":
			before = self.get_doc_before_save()
			if before and before.nb_echeances and (before.date_evenement != self.date_evenement
					or before.date_connaissance != self.date_connaissance or before.type_evenement != self.type_evenement):
				frappe.throw(_("Des échéances ont été générées : annulez l'événement et enregistrez-en un nouveau pour le corriger."))

	def after_insert(self):
		from obligation_reglementaire.engine.deadline import generate_from_event
		if self.statut != "Annulé":
			generate_from_event(self)

	def on_update(self):
		from obligation_reglementaire.engine.deadline import cancel_event_deadlines
		if self.has_value_changed("statut") and self.statut == "Annulé" and not self.is_new():
			cancel_event_deadlines(self, self.motif_annulation)
