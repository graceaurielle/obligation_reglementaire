# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from obligation_reglementaire.engine.common import assert_sod, check_transition, has_any_role, require_text
from obligation_reglementaire.engine.deadline import FINAL_STATUSES

CHANGE_TRANSITIONS = {"Demandée": {"Approuvée", "Refusée"}, "Approuvée": set(), "Refusée": set()}


class RegDeadlineChange(Document):
	def validate(self):
		check_transition(self, CHANGE_TRANSITIONS)
		dl = frappe.db.get_value("Reg Deadline", self.echeance, ["obligation", "organisation", "date_limite", "statut"], as_dict=True)
		if not dl:
			frappe.throw(_("Échéance introuvable."))
		self.obligation, self.organisation = dl.obligation, dl.organisation
		if self.is_new():
			if dl.statut in FINAL_STATUSES and self.type_modification == "Report métier":
				frappe.throw(_("Une échéance {0} ne peut pas être reportée.").format(dl.statut.lower()))
			if frappe.db.exists("Reg Deadline Change", {"echeance": self.echeance, "statut": "Demandée"}):
				frappe.throw(_("Une demande de modification est déjà en attente pour cette échéance."))
			self.ancienne_date = dl.date_limite
			self.demandeur = self.demandeur or frappe.session.user
			self.date_demande = today()
		require_text(self.motif, _("Le motif"))
		if not self.nouvelle_date:
			frappe.throw(_("La nouvelle date est obligatoire."))
		if getdate(self.nouvelle_date) == getdate(self.ancienne_date):
			frappe.throw(_("La nouvelle date est identique à la date actuelle."))
		if self.type_modification == "Correction technique" and not has_any_role("OR Administrateur", "OR Responsable Conformité"):
			frappe.throw(_("Seul un administrateur ou le responsable conformité peut corriger techniquement une date."))
		if self.has_value_changed("statut") and self.statut in ("Approuvée", "Refusée"):
			if self.statut == "Refusée":
				require_text(self.commentaire_decision, _("Le commentaire de refus"))
			assert_sod(frappe.session.user, self.demandeur,
				message=_("Séparation des tâches : le demandeur ne peut pas approuver son propre report."))
			self.approbateur, self.date_approbation = frappe.session.user, today()

	def after_insert(self):
		from obligation_reglementaire.engine import notification
		notification.emit("echeance_reportee", frappe.get_doc("Reg Deadline", self.echeance), extra={"demande": self.name})

	def on_update(self):
		from obligation_reglementaire.engine import notification
		from obligation_reglementaire.engine.deadline import apply_change
		if not self.has_value_changed("statut") or self.is_new():
			return
		if self.statut == "Approuvée":
			apply_change(self)
		elif self.statut == "Refusée":
			notification.emit("report_refuse", frappe.get_doc("Reg Deadline", self.echeance), extra={"motif": self.commentaire_decision})
