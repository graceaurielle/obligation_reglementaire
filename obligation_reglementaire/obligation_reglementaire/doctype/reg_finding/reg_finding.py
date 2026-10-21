# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from obligation_reglementaire.engine.common import check_transition, require_text, today_date

FINDING_TRANSITIONS = {
	"Ouvert": {"Qualifié", "Transformé en non-conformité", "Clos sans suite"},
	"Qualifié": {"Transformé en non-conformité", "Clos sans suite"},
	"Transformé en non-conformité": set(),
	"Clos sans suite": set(),
}


class RegFinding(Document):
	def validate(self):
		check_transition(self, FINDING_TRANSITIONS)
		self.date_constat = self.date_constat or today_date()
		self.constate_par = self.constate_par or frappe.session.user
		if self.has_value_changed("statut") and self.statut == "Clos sans suite":
			require_text(self.motif_classement, _("Le motif de classement sans suite"))
		if self.statut == "Transformé en non-conformité" and not self.non_conformite and not self.flags.reg_converting:
			frappe.throw(_("Utilisez le bouton « Créer la non-conformité »."))

	def to_non_conformity(self):
		from obligation_reglementaire.engine.action_plan import create_nc
		if self.non_conformite:
			return self.non_conformite
		resp = None
		if self.obligation:
			resp = frappe.db.get_value("Reg Obligation", self.obligation, "responsable_operationnel") or \
				frappe.db.get_value("Reg Obligation", self.obligation, "proprietaire")
		nc = create_nc(origine=self.origine or "Détection manuelle", intitule=self.intitule, description=self.description or self.intitule,
			organisation=self.organisation, responsable=resp or frappe.session.user, gravite=self.criticite,
			obligation=self.obligation, echeance=self.echeance, justificatif=self.justificatif, constat=self.name, event=self)
		self.non_conformite = nc.name
		self.statut = "Transformé en non-conformité"
		self.flags.reg_converting = True
		self.save(ignore_permissions=True)
		return nc.name
