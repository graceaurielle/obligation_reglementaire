import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures


class TestRegNonConformity(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def test_default_statut(self):
		nc = self.make_non_conformity()
		self.assertEqual(nc.statut, "Ouverte")

	def test_illegal_transition_throws(self):
		nc = self.make_non_conformity()
		nc.statut = "Clôturée"
		self.assertRaises(frappe.ValidationError, nc.save)

	def test_annulation_requires_motif(self):
		nc = self.make_non_conformity()
		nc.statut = "Annulée"
		self.assertRaises(frappe.ValidationError, nc.save)
		nc.reload()
		nc.statut = "Annulée"
		nc.motif_annulation = "Constat invalidé après vérification."
		nc.save()
		self.assertEqual(nc.statut, "Annulée")

	def test_closure_blocked_without_decision(self):
		nc = self.make_non_conformity()
		nc.statut = "En traitement"
		nc.save()
		nc.reload()
		nc.statut = "Clôturée"
		self.assertRaises(frappe.ValidationError, nc.save)

	def test_closure_requires_sod(self):
		# Sans plan d'action lié, le responsable de la NC ne peut pas la clôturer
		# lui-même (`assert_sod` dans `reg_non_conformity.py`).
		nc = self.make_non_conformity(responsable=self.user_a)
		nc.statut = "En traitement"
		nc.save()
		nc.reload()
		nc.statut = "Clôturée"
		nc.decision_cloture = "Mesures correctives mises en place."
		frappe.set_user(self.user_a)
		try:
			self.assertRaises(frappe.ValidationError, nc.save)
		finally:
			frappe.set_user("Administrator")

		nc.reload()
		nc.statut = "Clôturée"
		nc.decision_cloture = "Mesures correctives mises en place."
		frappe.set_user(self.user_b)
		try:
			nc.save()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(nc.statut, "Clôturée")
		self.assertTrue(nc.date_cloture)
