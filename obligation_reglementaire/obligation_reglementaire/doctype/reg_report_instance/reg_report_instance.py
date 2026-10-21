# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from obligation_reglementaire.engine.common import check_transition
from obligation_reglementaire.engine.reporting import FROZEN, REPORT_TRANSITIONS

FROZEN_FIELDS = ("donnees", "filtres_appliques", "resultat_html", "date_debut", "date_fin", "date_arrete", "modele", "organisation",
	"fichier_pdf", "fichier_excel", "synthese")


class RegReportInstance(Document):
	def validate(self):
		check_transition(self, REPORT_TRANSITIONS)
		if self.date_debut and self.date_fin and getdate(self.date_fin) < getdate(self.date_debut):
			frappe.throw(_("La période du rapport est incohérente."))
		if self.is_new():
			self.version = cint(self.version) or 1
			self.officiel = self.officiel or (1 if frappe.db.get_value("Reg Report Template", self.modele, "categorie") == "Réglementaire" else 0)
			self.intitule = self.intitule or frappe.db.get_value("Reg Report Template", self.modele, "intitule")
		before = self.get_doc_before_save()
		if before and (before.statut in FROZEN or cint(before.fige)) and not frappe.flags.reg_system and not self.flags.reg_exporting:
			changed = [f for f in FROZEN_FIELDS if str(before.get(f) or "") != str(self.get(f) or "")]
			if changed:
				frappe.throw(_("Rapport figé : les données ne peuvent plus être modifiées ({0}). Créez une nouvelle version.")
					.format(", ".join(changed)))
