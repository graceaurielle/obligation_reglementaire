# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

from frappe.utils.nestedset import NestedSet

from obligation_reglementaire.engine.source import after_provision_save, validate_provision


class RegProvision(NestedSet):
	def validate(self):
		validate_provision(self)

	def on_update(self):
		super().on_update()
		after_provision_save(self)
