# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from obligation_reglementaire.engine.common import assert_sod, check_transition

PROFILE_TRANSITIONS = {"Brouillon": {"Validé"}, "Validé": {"À réviser"}, "À réviser": {"Validé", "Brouillon"}}


class RegProfile(Document):
	def validate(self):
		check_transition(self, PROFILE_TRANSITIONS)
		self.raison_sociale = self.raison_sociale or frappe.db.get_value("Reg Organization", self.organisation, "nom_legal")
		if self.is_new() and frappe.db.exists("Reg Profile", {"organisation": self.organisation, "statut": ("!=", "À réviser")}):
			frappe.throw(_("Un profil réglementaire existe déjà pour cette organisation."))
		before = self.get_doc_before_save()
		if before and before.statut == "Validé" and self.statut == "Validé" and self._content_changed(before):
			self.statut = "À réviser"
			frappe.msgprint(_("Le profil a été modifié : il repasse « À réviser » et devra être revalidé puis réévalué."))
		if self.has_value_changed("statut") and self.statut == "Validé":
			if not self.secteur or not self.activites:
				frappe.throw(_("Secteur et activités sont obligatoires pour valider le profil."))
			assert_sod(frappe.session.user, self.modified_by if before and before.modified_by != frappe.session.user else None,
				message=_("Séparation des tâches : le dernier contributeur ne peut pas valider le profil."))
			self.valide_par, self.date_validation = frappe.session.user, today()

	def _content_changed(self, before):
		ignore = {"modified", "modified_by", "statut", "valide_par", "date_validation", "derniere_evaluation"}
		return any(str(before.get(df.fieldname) or "") != str(self.get(df.fieldname) or "")
			for df in self.meta.fields if df.fieldname not in ignore and df.fieldtype not in ("Table", "Section Break", "Column Break", "Tab Break"))
