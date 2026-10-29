import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures


class TestRegDeadline(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def test_default_statut(self):
		obl = self.make_obligation()
		dl = self.make_deadline(obl)
		self.assertEqual(dl.statut, "À venir")

	def test_illegal_transition_throws(self):
		obl = self.make_obligation()
		dl = self.make_deadline(obl)
		dl.statut = "Clôturée"
		self.assertRaises(frappe.ValidationError, dl.save)

	def test_attente_requires_motif(self):
		obl = self.make_obligation()
		dl = self.make_deadline(obl, statut="À traiter")
		dl.statut = "En attente"
		self.assertRaises(frappe.ValidationError, dl.save)
		dl.reload()
		dl.statut = "En attente"
		dl.motif_attente = "Attente d'une clarification de l'autorité."
		dl.save()
		self.assertEqual(dl.statut, "En attente")

	def test_submit_blocked_without_mandatory_evidence(self):
		# `justificatif_requis` vaut 1 par défaut sur l'obligation : la soumission
		# pour validation doit être bloquée tant qu'aucun justificatif n'est déposé.
		obl = self.make_obligation()
		dl = self.make_deadline(obl, statut="À traiter")
		dl.statut = "Soumise pour validation"
		self.assertRaisesRegex(frappe.ValidationError, "Justificatifs obligatoires manquants", dl.save)

	def test_full_lifecycle_with_derogation(self):
		obl = self.make_obligation()
		dl = self.make_deadline(obl, statut="À traiter")
		dl.statut = "Soumise pour validation"
		dl.derogation_justificatif = 1
		dl.justification_derogation = "Justificatif non exigible pour cette échéance."
		dl.save()
		self.assertTrue(dl.date_soumission)

		dl.reload()
		dl.statut = "Réalisée"
		dl.date_realisation = frappe.utils.nowdate()
		frappe.set_user(self.user_b)
		try:
			dl.save()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(dl.statut, "Réalisée")
		self.assertEqual(dl.delai_respecte, 1)

	def test_realisation_validator_cannot_be_responsable(self):
		obl = self.make_obligation()
		dl = self.make_deadline(obl, statut="À traiter", responsable=self.user_a,
			derogation_justificatif=1, justification_derogation="Dérogation.")
		dl.statut = "Soumise pour validation"
		dl.save()

		dl.reload()
		dl.statut = "Réalisée"
		dl.date_realisation = frappe.utils.nowdate()
		frappe.set_user(self.user_a)
		try:
			self.assertRaises(frappe.ValidationError, dl.save)
		finally:
			frappe.set_user("Administrator")
