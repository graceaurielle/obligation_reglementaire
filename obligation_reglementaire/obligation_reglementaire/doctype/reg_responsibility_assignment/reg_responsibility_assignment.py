# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from obligation_reglementaire.engine.common import SystemAction, require_text

ROLE_FIELD = {"Propriétaire": "proprietaire", "Responsable opérationnel": "responsable_operationnel",
	"Référent conformité": "referent_conformite", "Validateur": "validateur", "Contrôleur": "controleur", "Suppléant": "suppleant"}


class RegResponsibilityAssignment(Document):
	def validate(self):
		self.organisation = frappe.db.get_value("Reg Obligation", self.obligation, "organisation")
		self.assigne_par = self.assigne_par or frappe.session.user
		self.date_debut = self.date_debut or today()
		if self.date_fin and getdate(self.date_fin) < getdate(self.date_debut):
			frappe.throw(_("La date de fin précède la date de début."))
		if not self.is_new() and self.has_value_changed("utilisateur"):
			frappe.throw(_("Une affectation historisée ne change pas d'utilisateur : clôturez-la et créez-en une nouvelle."))
		if self.role_responsabilite in ROLE_FIELD:
			require_text(self.motif, _("Le motif de l'affectation"))

	def on_update(self):
		field = ROLE_FIELD.get(self.role_responsabilite)
		if not field or not self.actif or (self.date_fin and getdate(self.date_fin) < getdate(today())):
			return
		obl = frappe.get_doc("Reg Obligation", self.obligation)
		if obl.get(field) == self.utilisateur:
			return
		for other in frappe.get_all("Reg Responsibility Assignment", filters={"obligation": self.obligation, "actif": 1,
				"role_responsabilite": self.role_responsabilite, "name": ("!=", self.name)}, pluck="name"):
			frappe.db.set_value("Reg Responsibility Assignment", other, {"actif": 0, "date_fin": today()})
		obl.set(field, self.utilisateur)
		obl.flags.reg_justification = self.motif
		with SystemAction():
			obl.save(ignore_permissions=True)
