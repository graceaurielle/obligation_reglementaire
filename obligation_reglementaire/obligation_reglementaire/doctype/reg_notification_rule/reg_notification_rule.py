# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate


class RegNotificationRule(Document):
	def validate(self):
		if self.statut == "Active" and not self.destinataires:
			frappe.throw(_("Une règle active doit avoir au moins un destinataire."))
		if self.mode == "Temporel" and self.jours_relatifs is None:
			frappe.throw(_("Une règle temporelle doit préciser le nombre de jours relatifs."))
		if not (cint(self.canal_application) or cint(self.canal_email)):
			frappe.throw(_("Choisissez au moins un canal."))
		if self.valide_au and self.valide_du and getdate(self.valide_au) < getdate(self.valide_du):
			frappe.throw(_("Période de validité incohérente."))
		if self.condition:
			try:
				compile(self.condition, "<condition>", "eval")
			except SyntaxError as e:
				frappe.throw(_("Condition invalide : {0}").format(e))
		for r in self.destinataires:
			if r.cible == "Rôle" and not r.role:
				frappe.throw(_("Ligne {0} : précisez le rôle.").format(r.idx))
			if r.cible == "Utilisateur" and not r.utilisateur:
				frappe.throw(_("Ligne {0} : précisez l'utilisateur.").format(r.idx))
		before = self.get_doc_before_save()
		if before and before.statut == "Active":
			self.version = cint(before.version) + 1
		self.version = cint(self.version) or 1
