# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, now_datetime

from obligation_reglementaire.engine.action_plan import NC_TRANSITIONS, nc_close_blockers
from obligation_reglementaire.engine.common import assert_sod, check_transition, require_text, today_date


class RegNonConformity(Document):
	def validate(self):
		check_transition(self, NC_TRANSITIONS)
		self.date_detection = self.date_detection or today_date()
		if getdate(self.date_detection) > getdate(today_date()):
			frappe.throw(_("La date de détection ne peut pas être future."))
		if self.date_cible and getdate(self.date_cible) < getdate(self.date_detection):
			frappe.throw(_("La date cible précède la date de détection."))
		if self.obligation:
			obl = frappe.db.get_value("Reg Obligation", self.obligation, ["organisation", "domaine", "source",
				"disposition_principale", "direction", "criticite"], as_dict=True)
			if obl.organisation != self.organisation:
				frappe.throw(_("L'obligation appartient à une autre organisation."))
			self.domaine = self.domaine or obl.domaine
			self.source = self.source or obl.source
			self.disposition = self.disposition or obl.disposition_principale
			self.direction = self.direction or obl.direction
			self.gravite = self.gravite or obl.criticite
		if self.statut not in ("Clôturée", "Annulée"):
			self.anciennete_jours = date_diff(today_date(), self.date_detection)
		if self.risque_residuel_accepte:
			require_text(self.justification_acceptation, _("La justification de l'acceptation du risque résiduel"))
		self.recurrente = 1 if self._is_recurrent() else self.recurrente
		if self.has_value_changed("statut"):
			if self.statut == "Annulée":
				require_text(self.motif_annulation, _("Le motif d'annulation"))
			elif self.statut == "Clôturée":
				blockers = nc_close_blockers(self)
				if blockers:
					frappe.throw("<br>".join(blockers), title=_("Clôture impossible"))
				if not frappe.flags.reg_system and not self.plan_action:
					assert_sod(frappe.session.user, self.responsable,
						message=_("Séparation des tâches : le responsable de la non-conformité ne peut pas la clôturer."))
				self.cloture_par = self.cloture_par or frappe.session.user
				self.date_cloture = now_datetime()
			elif self.get_doc_before_save() and self.get_doc_before_save().statut == "Clôturée":
				self.flags.reg_justification = self.flags.reg_justification or _("Réouverture")
				self.cloture_par = self.date_cloture = None

	def _is_recurrent(self):
		if not self.obligation:
			return False
		return bool(frappe.db.exists("Reg Non Conformity", {"obligation": self.obligation, "name": ("!=", self.name or ""),
			"statut": "Clôturée"}))

	def after_insert(self):
		from obligation_reglementaire.engine.action_plan import after_nc_insert
		after_nc_insert(self)

	def on_update(self):
		from obligation_reglementaire.engine import notification
		if self.has_value_changed("statut") and self.statut == "Clôturée" and not self.is_new():
			notification.emit("nc_cloturee", self)
		if self.obligation and self.has_value_changed("statut"):
			from obligation_reglementaire.engine.deadline import update_obligation_compliance
			update_obligation_compliance(self.obligation)
