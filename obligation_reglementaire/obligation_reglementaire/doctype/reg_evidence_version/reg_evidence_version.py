# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

IMMUTABLE = ("justificatif", "numero", "fichier", "empreinte", "algorithme", "taille_octets", "nom_original", "auteur", "date_depot")


class RegEvidenceVersion(Document):
	def validate(self):
		before = self.get_doc_before_save()
		if not before:
			return
		changed = [f for f in IMMUTABLE if str(before.get(f) or "") != str(self.get(f) or "")]
		if changed:
			frappe.throw(_("Une version déposée est immuable ({0}). Déposez une nouvelle version.").format(", ".join(changed)))
		if before.verrouillee and not frappe.flags.reg_system and before.statut != self.statut and self.statut not in ("Remplacée", "Archivée"):
			frappe.throw(_("Version verrouillée."))
