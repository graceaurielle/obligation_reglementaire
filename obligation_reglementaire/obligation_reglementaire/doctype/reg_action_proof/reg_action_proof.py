# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from obligation_reglementaire.engine.common import require_text
from obligation_reglementaire.engine.evidence import file_fingerprint


class RegActionProof(Document):
	def validate(self):
		act = frappe.db.get_value("Reg Corrective Action", self.action, ["plan", "organisation", "statut"], as_dict=True)
		if not act:
			frappe.throw(_("Action introuvable."))
		self.plan, self.organisation = act.plan, act.organisation
		if not self.fichier:
			frappe.throw(_("Le fichier de preuve est obligatoire."))
		require_text(self.libelle, _("Le libellé de la preuve"))
		before = self.get_doc_before_save()
		if before and before.fichier != self.fichier:
			frappe.throw(_("Une preuve déposée ne se modifie pas : déposez une nouvelle version (champ « Remplace »)."))
		if before and before.statut in ("Acceptée", "Remplacée") and not frappe.flags.reg_system and before.statut != self.statut \
				and self.statut != "Remplacée":
			frappe.throw(_("Une preuve acceptée est verrouillée."))
		if self.is_new():
			if act.statut in ("Validée", "Annulée"):
				frappe.throw(_("Aucune preuve ne peut être ajoutée à une action {0}.").format(act.statut.lower()))
			_name, size, _mime, digest = file_fingerprint(self.fichier)
			self.empreinte, self.taille_octets = digest, size
			self.deposant = frappe.session.user
			self.date_depot = now_datetime()
			self.statut = "À contrôler"
			self.numero_version = (cint(frappe.db.get_value("Reg Action Proof", self.remplace, "numero_version")) + 1) \
				if self.remplace else 1

	def after_insert(self):
		if self.remplace:
			frappe.db.set_value("Reg Action Proof", self.remplace, "statut", "Remplacée")
