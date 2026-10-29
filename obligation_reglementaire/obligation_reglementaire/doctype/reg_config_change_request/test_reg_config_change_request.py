import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.engine import config
from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures


class TestRegConfigChangeRequest(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def _propose_as(self, user, **kwargs):
		frappe.set_user(user)
		try:
			return self.make_config_change_request(**kwargs)
		finally:
			frappe.set_user("Administrator")

	def test_default_statut_is_proposee(self):
		req = self.make_config_change_request()
		self.assertEqual(req.statut, "Proposée")
		self.assertEqual(req.propose_par, "Administrator")

	def test_illegal_transition_throws(self):
		req = self.make_config_change_request()
		req.statut = "Activée"
		self.assertRaises(frappe.ValidationError, req.save)

	def test_invalid_json_throws(self):
		self.assertRaises(frappe.ValidationError, self.make_config_change_request, valeurs_proposees="pas du json")

	def test_unknown_field_throws(self):
		self.assertRaises(frappe.ValidationError, self.make_config_change_request,
			valeurs_proposees=frappe.as_json({"champ_inexistant": 1}))

	def test_protected_field_throws(self):
		self.assertRaises(frappe.ValidationError, self.make_config_change_request,
			valeurs_proposees=frappe.as_json({"name": "Autre"}))

	def test_control_requires_sod(self):
		req = self._propose_as(self.user_a)
		frappe.set_user(self.user_a)
		try:
			self.assertRaises(frappe.ValidationError, config.control, req)
		finally:
			frappe.set_user("Administrator")

	def test_reject_requires_motif(self):
		req = self.make_config_change_request()
		self.assertRaises(frappe.ValidationError, config.reject, req, "")
		config.reject(req, "Changement non justifié.")
		self.assertEqual(req.statut, "Rejetée")

	def test_full_lifecycle_activates_target_value(self):
		req = self._propose_as(self.user_a)
		self.assertEqual(req.propose_par, self.user_a)

		frappe.set_user(self.user_b)
		try:
			config.control(req)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(req.statut, "Contrôlée")

		# Approbateur distinct du proposant (user_a) et du contrôleur (user_b) :
		# Administrator convient ici.
		config.approve(req)
		self.assertEqual(req.statut, "Validée")

		config.activate(req)
		self.assertEqual(req.statut, "Activée")
		self.assertEqual(frappe.db.get_value("Reg Criticality Level", self.crit_low, "delai_escalade_jours"), 5)
