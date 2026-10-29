import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures

EXTRA_TEST_RECORD_DEPENDENCIES = []


class TestRegObligation(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def test_default_statut_is_brouillon(self):
		obl = self.make_obligation()
		self.assertEqual(obl.statut, "Brouillon")
		self.assertEqual(obl.applicabilite, "À analyser")

	def test_illegal_transition_throws(self):
		obl = self.make_obligation()
		obl.statut = "Clôturée"
		self.assertRaises(frappe.ValidationError, obl.save)

	def test_validation_requires_applicability_decision(self):
		obl = self.make_obligation()
		obl.statut = "En qualification"
		obl.save()
		obl.statut = "Validée"
		self.assertRaisesRegex(frappe.ValidationError, "Décision d'applicabilité", obl.save)

	def test_full_lifecycle_to_active(self):
		# `reload()` entre chaque étape : reproduit des requêtes séparées (le cas
		# réel) et évite un faux positif de `reg_obligation.py` où un champ
		# numérique jamais renseigné (None en mémoire, 0 en base) serait à tort
		# détecté comme « modifié » lors du passage à Active.
		obl = self.make_obligation(applicabilite="Applicable")
		obl.statut = "En qualification"
		obl.save()
		obl.reload()
		obl.statut = "Validée"
		obl.save()
		self.assertEqual(obl.valide_par, frappe.session.user)
		obl.reload()
		obl.statut = "Active"
		obl.save()
		self.assertTrue(obl.date_activation)

	def test_sensitive_field_requires_justification_once_active(self):
		obl = self.make_obligation(applicabilite="Applicable")
		obl.statut = "En qualification"
		obl.save()
		obl.reload()
		obl.statut = "Validée"
		obl.save()
		obl.reload()
		obl.statut = "Active"
		obl.save()
		obl.reload()

		obl.criticite = self.crit_high
		self.assertRaisesRegex(frappe.ValidationError, "justifiée", obl.save)

		obl.reload()
		obl.criticite = self.crit_high
		obl.flags.reg_justification = "Réévaluation du risque suite à audit."
		obl.save()
		self.assertEqual(obl.criticite, self.crit_high)
