import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures


class TestRegReportInstance(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def test_default_statut_is_brouillon(self):
		inst = self.make_report_instance()
		self.assertEqual(inst.statut, "Brouillon")
		self.assertEqual(inst.version, 1)

	def test_illegal_transition_throws(self):
		inst = self.make_report_instance()
		inst.statut = "Validé"
		self.assertRaises(frappe.ValidationError, inst.save)

	def test_incoherent_period_throws(self):
		# La garde se déclenche dès `validate()`, donc dès l'`insert()` de la
		# fixture : il n'y a pas d'objet déjà créé sur lequel appeler `.save()`.
		today = frappe.utils.nowdate()
		self.assertRaises(frappe.ValidationError, self.make_report_instance,
			date_debut=today, date_fin=frappe.utils.add_days(today, -5))

	def test_frozen_once_validated(self):
		inst = self.make_report_instance()
		inst.statut = "En préparation"
		inst.save()
		inst.reload()
		inst.statut = "Validé"
		inst.save()

		inst.donnees = "{}"
		self.assertRaises(frappe.ValidationError, inst.save)

	def test_fige_flag_blocks_changes_even_in_draft(self):
		# `fige` gèle les données indépendamment du statut (contrôle séparé du statut
		# `FROZEN`), donc même un rapport encore "Brouillon" doit être bloqué.
		inst = self.make_report_instance()
		inst.fige = 1
		inst.save()
		inst.reload()

		inst.donnees = "{}"
		self.assertRaises(frappe.ValidationError, inst.save)
