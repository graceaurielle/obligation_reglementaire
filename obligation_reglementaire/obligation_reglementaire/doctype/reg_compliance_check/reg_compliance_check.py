# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from obligation_reglementaire.engine.common import assert_sod, check_transition, today_date

CHECK_TRANSITIONS = {
	"Planifié": {"En cours", "Réalisé", "Annulé"},
	"En cours": {"Réalisé", "Annulé"},
	"Réalisé": {"Validé", "En cours"},
	"Validé": set(),
	"Annulé": set(),
}


class RegComplianceCheck(Document):
	def validate(self):
		check_transition(self, CHECK_TRANSITIONS)
		if self.echeance and not self.obligation:
			self.obligation = frappe.db.get_value("Reg Deadline", self.echeance, "obligation")
		if self.obligation and not self.organisation:
			self.organisation = frappe.db.get_value("Reg Obligation", self.obligation, "organisation")
		if self.statut in ("Réalisé", "Validé"):
			if not self.resultat or not self.conclusion:
				frappe.throw(_("Le résultat et la conclusion du contrôle sont obligatoires."))
			self.date_controle = self.date_controle or today_date()
			self.controleur = self.controleur or frappe.session.user
		if self.has_value_changed("statut") and self.statut == "Validé":
			assert_sod(frappe.session.user, self.controleur,
				message=_("Séparation des tâches : le contrôleur ne peut pas valider son propre contrôle."))
			self.valide_par = frappe.session.user

	def on_update(self):
		if not self.has_value_changed("statut") or self.statut not in ("Réalisé", "Validé"):
			return
		if self.echeance and self.resultat:
			frappe.db.set_value("Reg Deadline", self.echeance, "resultat_controle", self.resultat)
		if self.resultat in ("Non conforme", "Justificatif insuffisant") and self.creer_non_conformite and not self.non_conformite:
			from obligation_reglementaire.engine.action_plan import create_nc
			obl = frappe.db.get_value("Reg Obligation", self.obligation, ["criticite", "proprietaire", "responsable_operationnel"],
				as_dict=True) if self.obligation else frappe._dict()
			nc = create_nc(origine="Contrôle de conformité", intitule=_("Contrôle non conforme : {0}").format(self.intitule),
				description="\n".join(filter(None, [self.anomalies, self.conclusion])) or self.intitule,
				organisation=self.organisation, responsable=obl.get("responsable_operationnel") or obl.get("proprietaire"),
				gravite=obl.get("criticite"), obligation=self.obligation, echeance=self.echeance, event=self)
			self.db_set("non_conformite", nc.name)
