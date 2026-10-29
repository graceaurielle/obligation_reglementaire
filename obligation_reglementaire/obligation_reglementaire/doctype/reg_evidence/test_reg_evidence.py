import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures, make_evidence_version


class TestRegEvidence(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def test_default_statut(self):
		obl = self.make_obligation()
		ev = self.make_evidence(obl)
		self.assertEqual(ev.statut, "Attendu")

	def test_illegal_transition_throws(self):
		obl = self.make_obligation()
		ev = self.make_evidence(obl)
		ev.statut = "Validé"
		self.assertRaises(frappe.ValidationError, ev.save)

	def test_cancel_requires_motif(self):
		obl = self.make_obligation()
		ev = self.make_evidence(obl)
		ev.statut = "Annulé"
		self.assertRaises(frappe.ValidationError, ev.save)
		ev.reload()
		ev.statut = "Annulé"
		ev.motif_annulation = "Justificatif devenu sans objet."
		ev.save()
		self.assertEqual(ev.statut, "Annulé")

	def test_frozen_fields_once_validated(self):
		obl = self.make_obligation()
		ev = self.make_evidence(obl)
		ev.statut = "Déposé"
		ev.save()
		make_evidence_version(ev)
		ev.reload()
		ev.statut = "Validé"
		ev.validateur = self.user_b
		ev.save()

		ev.libelle = "Nouveau libellé"
		self.assertRaises(frappe.ValidationError, ev.save)
