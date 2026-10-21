# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from obligation_reglementaire.engine.action_plan import ACTION_TRANSITIONS, action_prerequisites_ok, recompute_plan
from obligation_reglementaire.engine.common import check_transition, require_text, today_date


class RegCorrectiveAction(Document):
	def validate(self):
		check_transition(self, ACTION_TRANSITIONS)
		plan = frappe.db.get_value("Reg Action Plan", self.plan, ["organisation", "statut", "date_cible", "controleur"], as_dict=True)
		if not plan:
			frappe.throw(_("Plan d'action introuvable."))
		if plan.statut in ("Clôturé", "Annulé") and not frappe.flags.reg_system:
			frappe.throw(_("Le plan {0} est {1} : ses actions ne sont plus modifiables.").format(self.plan, plan.statut.lower()))
		self.organisation = plan.organisation
		self.controleur = self.controleur or plan.controleur
		if self.is_new():
			self.date_fin_prevue_initiale = self.date_fin_prevue_initiale or self.date_fin_prevue
		if self.date_fin_prevue and self.date_debut_prevue and getdate(self.date_fin_prevue) < getdate(self.date_debut_prevue):
			frappe.throw(_("La fin prévue précède le début prévu."))
		if self.date_fin_prevue and plan.date_cible and getdate(self.date_fin_prevue) > getdate(plan.date_cible):
			frappe.msgprint(_("Attention : l'échéance de l'action dépasse la date cible du plan."), indicator="orange", alert=True)
		for d in self.dependances:
			if d.action_prerequise == self.name:
				frappe.throw(_("Une action ne peut pas dépendre d'elle-même."))
		before = self.get_doc_before_save()
		if before and before.date_fin_prevue != self.date_fin_prevue and not self.flags.reg_justification \
				and not frappe.flags.reg_system and before.statut != "Non commencée":
			frappe.throw(_("L'échéance d'une action démarrée se modifie par une demande de prolongation."))
		if self.has_value_changed("statut"):
			self._on_status_change()

	def _on_status_change(self):
		st = self.statut
		if st == "En cours":
			missing = action_prerequisites_ok(self)
			if missing:
				frappe.throw(_("Actions prérequises non validées : {0}").format(", ".join(missing)))
			self.date_debut_reelle = self.date_debut_reelle or today_date()
			self.motif_blocage = None
		elif st == "Bloquée":
			require_text(self.motif_blocage, _("Le motif de blocage"))
			self.date_blocage = today_date()
		elif st == "Annulée":
			require_text(self.motif_annulation, _("Le motif d'annulation"))
		elif st == "Validée" and not self.valide_par:
			frappe.throw(_("La validation passe par le contrôleur (bouton « Valider l'action »)."))
		elif st == "Soumise à contrôle" and not self.flags.ignore_permissions and not frappe.flags.reg_system:
			frappe.throw(_("Utilisez le bouton « Soumettre à contrôle »."))

	def after_insert(self):
		from obligation_reglementaire.engine import notification
		if self.responsable:
			notification.emit("action_assignee", self)

	def on_update(self):
		from obligation_reglementaire.engine import notification
		recompute_plan(self.plan)
		before = self.get_doc_before_save()
		if before and before.responsable != self.responsable and self.responsable:
			notification.emit("action_assignee", self)
		if self.has_value_changed("statut") and self.statut == "Bloquée":
			notification.emit("action_bloquee", self)
		if self.has_value_changed("statut") and self.statut == "En cours":
			plan = frappe.get_doc("Reg Action Plan", self.plan)
			if plan.statut in ("Ouvert", "Réouvert"):
				plan.statut = "En cours"
				plan.flags.ignore_permissions = True
				plan.save()
