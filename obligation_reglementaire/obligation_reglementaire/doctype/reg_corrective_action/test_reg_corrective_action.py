import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.engine import action_plan
from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures


class TestRegCorrectiveAction(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def _open_plan(self):
		plan = self.make_action_plan(responsable=self.user_a)
		plan.reload()
		plan.statut = "Ouvert"
		plan.save()
		plan.reload()
		plan.statut = "En cours"
		plan.save()
		return plan

	def test_default_statut_is_non_commencee(self):
		plan = self._open_plan()
		action = self.make_corrective_action(plan)
		self.assertEqual(action.statut, "Non commencée")

	def test_illegal_transition_throws(self):
		plan = self._open_plan()
		action = self.make_corrective_action(plan)
		action.statut = "Validée"
		self.assertRaises(frappe.ValidationError, action.save)

	def test_blocage_requires_motif(self):
		plan = self._open_plan()
		action = self.make_corrective_action(plan)
		action.statut = "Bloquée"
		self.assertRaises(frappe.ValidationError, action.save)
		action.reload()
		action.statut = "Bloquée"
		action.motif_blocage = "Dépendance externe non résolue."
		action.save()
		self.assertEqual(action.statut, "Bloquée")

	def test_annulation_requires_motif(self):
		plan = self._open_plan()
		action = self.make_corrective_action(plan)
		action.statut = "Annulée"
		self.assertRaises(frappe.ValidationError, action.save)
		action.reload()
		action.statut = "Annulée"
		action.motif_annulation = "Action devenue sans objet."
		action.save()
		self.assertEqual(action.statut, "Annulée")

	def test_statut_soumise_requires_dedicated_endpoint(self):
		# `_on_status_change` interdit de poser "Soumise à contrôle" par simple
		# affectation : seul `action_plan.submit_action()` (qui pose
		# `flags.ignore_permissions`) est autorisé. `insert(ignore_permissions=True)`
		# pose ce drapeau sur l'instance pour toute sa vie (un `.reload()` ne le
		# réinitialise pas) : il faut un `frappe.get_doc()` frais pour retrouver un
		# objet sans ce drapeau et tester réellement le garde-fou.
		plan = self._open_plan()
		action = self.make_corrective_action(plan)
		action.statut = "En cours"
		action.save()

		fresh = frappe.get_doc("Reg Corrective Action", action.name)
		fresh.statut = "Soumise à contrôle"
		self.assertRaises(frappe.ValidationError, fresh.save)

	def test_date_fin_prevue_change_guard_after_start(self):
		# Contrairement à `reg_action_plan.py`, ce garde-fou est protégé par
		# `before.statut != "Non commencée"` : il ne se déclenche pas à tort sur le
		# premier changement de statut (pas besoin de `.reload()` préalable ici).
		plan = self._open_plan()
		action = self.make_corrective_action(plan)
		action.statut = "En cours"
		action.save()

		action.reload()
		action.date_fin_prevue = frappe.utils.add_days(action.date_fin_prevue, 5)
		self.assertRaises(frappe.ValidationError, action.save)

	def test_full_lifecycle_submit_and_validate(self):
		plan = self._open_plan()
		action = self.make_corrective_action(plan, responsable=self.user_a)
		action.statut = "En cours"
		action.save()
		action.reload()

		action_plan.submit_action(action)
		action.reload()
		self.assertEqual(action.statut, "Soumise à contrôle")

		# Séparation des tâches : le responsable ne peut pas valider sa propre action.
		frappe.set_user(self.user_a)
		try:
			self.assertRaises(frappe.ValidationError, action_plan.validate_action, action)
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(self.user_b)
		try:
			action_plan.validate_action(action)
		finally:
			frappe.set_user("Administrator")
		action.reload()
		self.assertEqual(action.statut, "Validée")
		self.assertEqual(action.valide_par, self.user_b)
