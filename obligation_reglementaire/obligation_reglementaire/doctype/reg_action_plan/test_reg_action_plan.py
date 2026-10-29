import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.engine import action_plan
from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures


class TestRegActionPlan(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def test_default_statut_is_brouillon(self):
		plan = self.make_action_plan()
		self.assertEqual(plan.statut, "Brouillon")

	def test_illegal_transition_throws(self):
		plan = self.make_action_plan()
		plan.statut = "Clôturé"
		self.assertRaises(frappe.ValidationError, plan.save)

	def test_closure_blocked_without_corrective_action(self):
		# `reload()` avant le premier changement de statut : sans lui, `self.date_cible`
		# reste la chaîne de caractères posée à l'insertion, alors que le `before` lu
		# par `get_doc_before_save()` la recharge en objet date — comparaison toujours
		# inégale, et `reg_action_plan.py` exige alors (à tort) une prolongation.
		plan = self.make_action_plan()
		plan.reload()
		plan.statut = "Ouvert"
		plan.save()
		plan.reload()
		plan.statut = "En cours"
		plan.save()
		plan.reload()
		self.assertRaises(frappe.ValidationError, action_plan.request_closure, plan)

	def test_full_lifecycle_to_closure(self):
		# Criticité basse (`crit_low`, poids 1) : pas de vérification d'efficacité
		# requise, donc `validate_closure` doit clôturer directement le plan.
		plan = self.make_action_plan(responsable=self.user_a)
		plan.reload()
		plan.statut = "Ouvert"
		plan.save()
		plan.reload()
		plan.statut = "En cours"
		plan.save()

		action = self.make_corrective_action(plan, responsable=self.user_a)
		action.statut = "En cours"
		action.save()
		action.reload()
		action_plan.submit_action(action)
		action.reload()
		self.assertEqual(action.statut, "Soumise à contrôle")

		frappe.set_user(self.user_b)
		try:
			action_plan.validate_action(action)
		finally:
			frappe.set_user("Administrator")
		action.reload()
		self.assertEqual(action.statut, "Validée")

		plan.reload()
		action_plan.request_closure(plan)
		self.assertEqual(plan.statut, "En attente de validation")

		frappe.set_user(self.user_b)
		try:
			action_plan.validate_closure(plan, "Plan correctement exécuté.")
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(plan.statut, "Clôturé")
		self.assertTrue(plan.date_cloture)

	def test_closure_validation_requires_sod(self):
		plan = self.make_action_plan(responsable=self.user_a)
		plan.reload()
		plan.statut = "Ouvert"
		plan.save()
		plan.reload()
		plan.statut = "En cours"
		plan.save()

		action = self.make_corrective_action(plan, responsable=self.user_a)
		action.statut = "En cours"
		action.save()
		action.reload()
		action_plan.submit_action(action)
		frappe.set_user(self.user_b)
		try:
			action_plan.validate_action(action)
		finally:
			frappe.set_user("Administrator")

		plan.reload()
		action_plan.request_closure(plan)

		# Le responsable du plan ne peut pas valider sa propre demande de clôture.
		frappe.set_user(self.user_a)
		try:
			self.assertRaises(frappe.ValidationError, action_plan.validate_closure, plan, "Auto-validation.")
		finally:
			frappe.set_user("Administrator")
