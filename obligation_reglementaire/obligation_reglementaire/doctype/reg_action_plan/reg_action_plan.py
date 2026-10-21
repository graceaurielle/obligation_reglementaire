# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from obligation_reglementaire.engine.action_plan import PLAN_TRANSITIONS, plan_close_blockers, recompute_plan
from obligation_reglementaire.engine.common import check_transition, criticality_weight, require_text, today_date


class RegActionPlan(Document):
	def validate(self):
		check_transition(self, PLAN_TRANSITIONS)
		self.date_creation = self.date_creation or today_date()
		if self.is_new():
			self.date_cible_initiale = self.date_cible_initiale or self.date_cible
		if self.date_cible and getdate(self.date_cible) < getdate(self.date_creation) and self.is_new():
			frappe.throw(_("La date cible ne peut pas précéder la date de création du plan."))
		if self.obligation and not self.source:
			self.source = frappe.db.get_value("Reg Obligation", self.obligation, "source")
		if self.non_conformite and not self.obligation:
			self.obligation = frappe.db.get_value("Reg Non Conformity", self.non_conformite, "obligation")
		if self.origine in ("Non-conformité réglementaire",) and not self.non_conformite and not self.constat and not frappe.flags.reg_system:
			frappe.throw(_("Un plan issu d'une non-conformité doit être rattaché à la non-conformité."))
		before = self.get_doc_before_save()
		if before:
			if before.date_cible != self.date_cible and not self.flags.reg_justification and not frappe.flags.reg_system \
					and self.statut not in ("Brouillon",):
				frappe.throw(_("La date cible ne se modifie que par une demande de prolongation validée."))
			if before.criticite != self.criticite:
				require_text(self.justification_criticite or self.flags.reg_justification,
					_("La justification du changement de criticité"))
				self.append("historique_criticite", {"ancienne_valeur": before.criticite, "nouvelle_valeur": self.criticite,
					"utilisateur": frappe.session.user, "date": today_date(),
					"justification": self.justification_criticite or self.flags.reg_justification})
				self.justification_criticite = None
		if criticality_weight(self.criticite) >= 3 and self.statut not in ("Brouillon", "Annulé") and not self.causes \
				and self.statut in ("En attente de validation", "Clôturé"):
			frappe.throw(_("L'analyse des causes est obligatoire pour un plan critique ou élevé."))
		for m in self.mesures_compensatoires:
			if m.date_fin and m.date_debut and getdate(m.date_fin) < getdate(m.date_debut):
				frappe.throw(_("Mesure compensatoire : la fin précède le début."))
		if self.has_value_changed("statut"):
			self._on_status_change(before)

	def _on_status_change(self, before):
		st = self.statut
		if st == "Ouvert":
			if not (self.responsable and self.date_cible):
				frappe.throw(_("Responsable et date cible sont obligatoires pour ouvrir le plan."))
		elif st == "En attente de validation":
			blockers = plan_close_blockers(self)
			if blockers:
				self.blocages_cloture = "\n".join(blockers)
				frappe.throw("<br>".join(blockers), title=_("Clôture impossible"))
		elif st == "Clôturé" and not self.valide_par:
			frappe.throw(_("La clôture passe par la validation du valideur (bouton « Valider la clôture »)."))
		elif st == "Annulé":
			require_text(self.motif_annulation, _("Le motif d'annulation"))
		elif st == "Bloqué":
			require_text(self.commentaires or self.flags.reg_justification, _("Le motif de blocage (commentaires)"))
		elif st == "Réouvert":
			require_text(self.motif_reouverture, _("Le motif de réouverture"))

	def after_insert(self):
		from obligation_reglementaire.engine import notification
		notification.emit("pa_cree", self)

	def on_update(self):
		recompute_plan(self.name)
		if self.non_conformite and not frappe.db.get_value("Reg Non Conformity", self.non_conformite, "plan_action"):
			frappe.db.set_value("Reg Non Conformity", self.non_conformite, "plan_action", self.name)
