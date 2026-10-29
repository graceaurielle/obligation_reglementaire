import frappe
from frappe.tests import IntegrationTestCase

from obligation_reglementaire.obligation_reglementaire.tests.fixtures import CommonFixtures, uniq


class TestRegDocument(IntegrationTestCase, CommonFixtures):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.setup_common_fixtures()

	def _real_file_url(self):
		# `check_document_file` lit le contenu réel via `File.get_content()` : un
		# simple chemin fictif ne suffit pas, il faut un enregistrement `File` réel.
		file_doc = frappe.get_doc({
			"doctype": "File",
			"file_name": f"{uniq('doc-')}.txt",
			"content": "Contenu de test.",
			"is_private": 1,
		}).insert(ignore_permissions=True)
		return file_doc.file_url

	def test_default_statut_is_brouillon(self):
		doc = self.make_document()
		self.assertEqual(doc.statut, "Brouillon")

	def test_illegal_transition_throws(self):
		doc = self.make_document()
		doc.statut = "Validé"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_submit_requires_fichier(self):
		doc = self.make_document()
		doc.statut = "Soumis"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_gel_requires_motif(self):
		doc = self.make_document()
		doc.gel = 1
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		doc.gel = 1
		doc.motif_gel = "Litige en cours."
		doc.save()
		self.assertEqual(doc.gel, 1)

	def test_frozen_fields_once_validated(self):
		doc = self.make_document()
		doc.fichier = self._real_file_url()
		doc.statut = "Soumis"
		doc.save()
		doc.reload()
		doc.statut = "Validé"
		doc.save()

		doc.titre = "Nouveau titre"
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_deleted_document_is_immutable(self):
		doc = self.make_document()
		doc.statut = "Supprimé logiquement"
		doc.save()

		doc.titre = "Titre modifié"
		self.assertRaises(frappe.ValidationError, doc.save)
