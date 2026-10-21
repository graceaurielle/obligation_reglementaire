# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class RegMember(Document):
	def validate(self):
		self.nom_complet = self.nom_complet or frappe.db.get_value("User", self.utilisateur, "full_name")
		if self.suppleant == self.utilisateur or self.manager == self.utilisateur:
			frappe.throw(_("Le suppléant et le manager doivent être distincts de l'utilisateur."))
		if self.unite and frappe.db.get_value("Reg Org Unit", self.unite, "organisation") != self.organisation:
			frappe.throw(_("L'unité appartient à une autre organisation."))
		if self.has_value_changed("statut") and self.statut == "Désactivé":
			self.date_desactivation = today()
			self._check_open_items()

	def _check_open_items(self):
		open_items = frappe.db.count("Reg Deadline", {"responsable": self.utilisateur, "statut": ("not in", ("Réalisée",
			"Réalisée en retard", "Clôturée", "Annulée"))}) + frappe.db.count("Reg Corrective Action", {"responsable": self.utilisateur,
			"statut": ("not in", ("Validée", "Annulée"))})
		if open_items:
			frappe.msgprint(_("{0} élément(s) ouvert(s) restent affectés à cet utilisateur : pensez à les réaffecter.").format(open_items),
				indicator="orange")

	def on_update(self):
		self.sync_user_permission()

	def sync_user_permission(self):
		"""Cloisonnement multi-organisation : une User Permission par membre actif."""
		existing = frappe.get_all("User Permission", filters={"user": self.utilisateur, "allow": "Reg Organization"},
			fields=["name", "for_value"])
		for up in existing:
			if up.for_value != self.organisation or self.statut != "Actif":
				frappe.delete_doc("User Permission", up.name, ignore_permissions=True)
		if self.statut == "Actif" and not any(up.for_value == self.organisation for up in existing):
			frappe.get_doc({"doctype": "User Permission", "user": self.utilisateur, "allow": "Reg Organization",
				"for_value": self.organisation, "apply_to_all_doctypes": 1, "is_default": 1}).insert(ignore_permissions=True)
