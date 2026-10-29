import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import (
	CommonFixtures,
	make_evidence_version,
	make_rejection_reason,
)


class TestRegEvidenceReview(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def _deposited_evidence(self, auteur=None):
		obl = self.make_obligation()
		ev = self.make_evidence(obl)
		ev.statut = "Déposé"
		ev.save()
		make_evidence_version(ev, auteur=auteur or self.user_a)
		ev.reload()
		return ev

	def test_controleur_cannot_be_depositor(self):
		# Séparation des tâches : le contrôleur ne peut pas être l'auteur de la
		# version qu'il contrôle (`assert_sod` dans `validate_review`).
		ev = self._deposited_evidence(auteur=self.user_a)
		review = self.make_evidence_review(ev, controleur=self.user_a)
		review.resultat = "Rejeté"
		review.append("motifs", {"motif": make_rejection_reason()})
		self.assertRaises(frappe.ValidationError, review.submit)

	def test_rejection_requires_motif_and_applies_to_evidence(self):
		ev = self._deposited_evidence(auteur=self.user_a)
		review = self.make_evidence_review(ev, controleur=self.user_b)
		review.resultat = "Rejeté"
		self.assertRaises(frappe.ValidationError, review.submit)

		# Un `submit()` qui échoue pose quand même `docstatus=1` et avance
		# `self.modified` en mémoire sans écrire en base : `reload()` repart d'un
		# état propre avant de retenter (sinon `check_if_latest` échoue à tort).
		review.reload()
		review.resultat = "Rejeté"
		review.append("motifs", {"motif": make_rejection_reason()})
		review.submit()

		ev.reload()
		self.assertEqual(ev.statut, "Rejeté")
		self.assertTrue(ev.motif_rejet)

	def test_cannot_cancel_submitted_review(self):
		ev = self._deposited_evidence(auteur=self.user_a)
		review = self.make_evidence_review(ev, controleur=self.user_b)
		review.resultat = "Rejeté"
		review.append("motifs", {"motif": make_rejection_reason()})
		review.submit()

		# `apply_review()` pose `date_decision` par un `db.set_value` direct, ce qui
		# rend l'objet en mémoire périmé (timestamp) : on recharge avant d'annuler.
		review.reload()
		self.assertRaises(frappe.ValidationError, review.cancel)
