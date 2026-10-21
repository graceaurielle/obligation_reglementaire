# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from obligation_reglementaire.engine.common import check_transition
from obligation_reglementaire.engine.config import CONFIG_TRANSITIONS, validate_request


class RegConfigChangeRequest(Document):
	def validate(self):
		check_transition(self, CONFIG_TRANSITIONS)
		validate_request(self)
