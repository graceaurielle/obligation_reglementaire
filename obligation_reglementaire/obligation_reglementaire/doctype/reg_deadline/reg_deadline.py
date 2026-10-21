# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from obligation_reglementaire.engine import deadline as engine
from obligation_reglementaire.engine.common import assert_sod, check_transition, require_text, today_date


class RegDeadline(Document):
	def validate(self):
		check_transition(self, engine.DEADLINE_TRANSITIONS)
		obl = frappe.get_cached_doc("Reg Obligation", self.obligation) if self.obligation else None
		if obl:
			self.organisation = self.organisation or obl.organisation
			self.criticite = self.criticite or obl.criticite
			self.domaine = self.domaine or obl.domaine
			self.responsable = self.responsable or obl.responsable_operationnel or obl.proprietaire
			self.unite = self.unite or obl.direction
			self.controleur = self.controleur or obl.controleur
			self.validateur = self.validateur or obl.validateur
		if self.is_new():
			self.date_limite_initiale = self.date_limite_initiale or self.date_limite
			self.type_echeance = self.type_echeance or "Manuelle"
			if not self.cle_unicite:
				self.cle_unicite = f"{self.obligation}|M|{frappe.generate_hash(length=8)}"
		elif self.has_value_changed("date_limite") and not frappe.flags.reg_force_transition and not frappe.flags.reg_system \
				and not self.flags.reg_justification:
			frappe.throw(_("La date limite ne se modifie que par une demande de report ou de correction (historisée)."))
		if self.has_value_changed("statut"):
			self._on_status_change()

	def _on_status_change(self):
		st = self.statut
		if st == "En attente":
			require_text(self.motif_attente, _("Le motif de mise en attente"))
		elif st == "Annulée":
			require_text(self.motif_annulation, _("Le motif d'annulation"))
		elif st == "Soumise pour validation":
			blockers = engine.evidence_blockers(self)
			if blockers and not self.flags.reg_force:
				frappe.throw(_("Justificatifs obligatoires manquants :<br>{0}").format("<br>".join(blockers)),
					title=_("Soumission impossible"))
			if self.derogation_justificatif:
				require_text(self.justification_derogation, _("La justification de la dérogation"))
			self.date_soumission = now_datetime()
			self.date_realisation = self.date_realisation or today_date()
		elif st in ("Réalisée", "Réalisée en retard"):
			blockers = engine.validation_blockers(self)
			if blockers:
				frappe.throw(_("Justificatifs non validés :<br>{0}").format("<br>".join(blockers)), title=_("Validation impossible"))
			if not frappe.flags.reg_system:
				assert_sod(frappe.session.user, self.responsable,
					message=_("Séparation des tâches : le responsable de l'échéance ne peut pas la valider."))
			self.valide_par = self.valide_par or frappe.session.user
			self.date_validation = now_datetime()
			done = getdate(self.date_realisation or today_date())
			late = done > getdate(self.date_limite)
			self.statut = "Réalisée en retard" if late else "Réalisée"
			self.delai_respecte = 0 if late else 1
			if late and not self.cause_retard and not frappe.flags.reg_system:
				frappe.throw(_("Échéance réalisée en retard : la cause du retard est obligatoire."))
			self.resultat_controle = self.resultat_controle or "Conforme"
			self.en_retard = 1 if late else 0
		elif st == "Non conforme":
			self.resultat_controle = self.resultat_controle or "Non conforme"
		elif st == "Clôturée":
			if self.get_doc_before_save() and self.get_doc_before_save().statut == "Non conforme":
				require_text(self.commentaire_cloture, _("Le commentaire de clôture"))
		elif st == "En cours" and self.get_doc_before_save():
			prev = self.get_doc_before_save().statut
			if prev == "Soumise pour validation":
				require_text(self.motif_rejet, _("Le motif de rejet de la soumission"))
			elif prev in engine.DONE_STATUSES:
				require_text(self.motif_reouverture, _("Le motif de réouverture"))
				self.valide_par = self.date_validation = None

	def after_insert(self):
		from obligation_reglementaire.engine import evidence, notification
		evidence.create_expected(self)
		notification.emit("echeance_creee", self)

	def on_update(self):
		from obligation_reglementaire.engine import notification
		before = self.get_doc_before_save()
		if before and before.responsable != self.responsable:
			notification.emit("responsable_modifie", self)
		if not before or before.statut == self.statut:
			return
		event = {"Soumise pour validation": "echeance_soumise", "Suspendue": "echeance_suspendue",
			"Reportée": "echeance_reportee", "Clôturée": "echeance_cloturee", "Réalisée": "echeance_cloturee",
			"Réalisée en retard": "echeance_cloturee"}.get(self.statut)
		if before.statut == "Suspendue" and self.statut != "Annulée":
			event = "echeance_reactivee"
		if before.statut == "Soumise pour validation" and self.statut == "En cours":
			event = "echeance_rejetee"
		if event:
			notification.emit(event, self)
		if self.statut in engine.DONE_STATUSES + ("Non conforme",) or before.statut in engine.DONE_STATUSES:
			engine.update_obligation_compliance(self.obligation)
		if self.statut == "Non conforme" and not self.non_conformite:
			from obligation_reglementaire.engine.action_plan import create_nc
			nc = create_nc(origine="Contrôle de conformité", intitule=_("Échéance non conforme : {0}").format(self.libelle),
				description=self.motif_rejet or _("Échéance {0} déclarée non conforme.").format(self.name),
				organisation=self.organisation, responsable=self.responsable, gravite=self.criticite,
				obligation=self.obligation, echeance=self.name, event=self)
			self.db_set("non_conformite", nc.name)
