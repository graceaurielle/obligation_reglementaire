# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class RegReportTemplate(Document):
	def validate(self):
		self.version = cint(self.version) or 1
		if not self.sections:
			frappe.throw(_("Un modèle de rapport doit comporter au moins une section."))
		for s in self.sections:
			if s.source_donnees == "Indicateur" and not s.indicateur:
				frappe.throw(_("Section {0} : choisissez l'indicateur.").format(s.idx))
		before = self.get_doc_before_save()
		if before and before.statut in ("Validé", "Actif") and self.statut == before.statut:
			if [(s.titre, s.source_donnees) for s in before.sections] != [(s.titre, s.source_donnees) for s in self.sections]:
				frappe.throw(_("Un modèle publié ne se modifie pas : dupliquez-le pour créer une nouvelle version."))
		if self.generation_automatique and not self.frequence:
			frappe.throw(_("La génération automatique nécessite une fréquence."))
