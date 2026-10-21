# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from obligation_reglementaire.engine import ged
from obligation_reglementaire.engine.common import check_transition

FROZEN_FIELDS = ("titre", "type_document", "organisation", "empreinte", "version_courante")


class RegDocument(Document):
	def validate(self):
		check_transition(self, ged.DOC_TRANSITIONS)
		before = self.get_doc_before_save()
		if before and before.statut == "Supprimé logiquement":
			frappe.throw(_("Document supprimé : aucune modification possible."))
		if before and before.statut in ged.LOCKED and not self.flags.reg_new_version and not frappe.flags.reg_system:
			changed = [f for f in FROZEN_FIELDS if str(before.get(f) or "") != str(self.get(f) or "")]
			if changed:
				frappe.throw(_("Document {0} : champs non modifiables ({1}).").format(before.statut.lower(), ", ".join(changed)))
		ged.validate_document(self)
		if self.has_value_changed("statut") and self.statut == "Soumis" and not self.fichier:
			frappe.throw(_("Joignez un fichier avant de soumettre le document."))

	def after_insert(self):
		ged.after_document_insert(self)
