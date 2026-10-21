# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from obligation_reglementaire.engine.common import assert_sod, check_transition, require_text

TEMPLATE_TRANSITIONS = {"Brouillon": {"En validation", "Retiré"}, "En validation": {"Validé", "Brouillon"},
	"Validé": {"Actif", "Retiré", "En validation"}, "Actif": {"Retiré", "En validation"}, "Retiré": {"Brouillon"}}
CONTENT = ("intitule", "description", "source", "version_source", "disposition", "domaine", "criticite", "nature_temporelle",
	"frequence", "evenement_declencheur", "delai_valeur", "delai_unite", "regle_calcul", "controle_attendu", "consequence_nc")


class RegTemplateObligation(Document):
	def validate(self):
		check_transition(self, TEMPLATE_TRANSITIONS)
		self.version = cint(self.version) or 1
		before = self.get_doc_before_save()
		if before and before.statut in ("Validé", "Actif"):
			changed = [f for f in CONTENT if str(before.get(f) or "") != str(self.get(f) or "")]
			if changed:
				require_text(self.resume_derniere_modif if self.resume_derniere_modif != before.resume_derniere_modif else None,
					_("Le résumé de la modification (nouvelle version du modèle)"))
				self.version = cint(before.version) + 1
				self.flags.reg_new_template_version = True
		if self.has_value_changed("statut") and self.statut == "Validé":
			if not cint(self.valide_juridiquement):
				frappe.throw(_("Le modèle doit être validé juridiquement avant publication."))
			assert_sod(frappe.session.user, self.owner if self.owner != "Administrator" else None,
				message=_("Séparation des tâches : l'auteur du modèle ne peut pas le valider."))
			self.valide_par, self.date_validation = frappe.session.user, today()
		if self.statut in ("Validé", "Actif") and not (self.nature_temporelle and self.criticite and self.domaine):
			frappe.throw(_("Nature temporelle, criticité et domaine sont obligatoires pour un modèle publié."))

	def on_update(self):
		if self.flags.reg_new_template_version:
			from obligation_reglementaire.engine.applicability import on_template_update
			on_template_update(self)
