# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

IMMUTABLE = ("document", "numero", "fichier", "empreinte", "taille_octets", "nom_fichier", "deposant", "date_depot")


class RegDocumentVersion(Document):
	def validate(self):
		before = self.get_doc_before_save()
		if before:
			changed = [f for f in IMMUTABLE if str(before.get(f) or "") != str(self.get(f) or "")]
			if changed:
				frappe.throw(_("Une version de document est immuable ({0}).").format(", ".join(changed)))
