# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, today

from obligation_reglementaire.engine.common import (
	SystemAction, assert_sod, check_transition, log_audit, require_text, today_date)
from obligation_reglementaire.engine.deadline import calc_rule_text

OBLIGATION_TRANSITIONS = {
	"Brouillon": {"En qualification", "Archivée"},
	"En qualification": {"Validée", "Brouillon", "Archivée"},
	"Validée": {"Active", "En qualification", "Archivée"},
	"Active": {"Suspendue", "Clôturée", "Obsolète", "En qualification"},
	"Suspendue": {"Active", "Clôturée", "Obsolète"},
	"Clôturée": {"Archivée", "Active"},
	"Obsolète": {"Archivée"},
	"Archivée": set(),
}

# Champs dont la modification sur une obligation active doit être justifiée (RG-OBL)
SENSITIVE = ("criticite", "frequence", "delai_valeur", "delai_unite", "nature_temporelle", "proprietaire",
	"responsable_operationnel", "validateur", "source", "disposition_principale", "date_reference", "date_fixe")


class RegObligation(Document):
	def validate(self):
		check_transition(self, OBLIGATION_TRANSITIONS)
		self._validate_dates()
		self._validate_timing()
		self._validate_evidence()
		self._validate_source()
		self._validate_status_requirements()
		self._sync_principal_provision()
		if not self.regle_calcul or self.has_value_changed("frequence") or self.has_value_changed("delai_valeur") \
				or self.has_value_changed("nature_temporelle") or self.has_value_changed("delai_unite"):
			self.regle_calcul = calc_rule_text(self)
		if not self.is_new() and self.statut in ("Active", "Suspendue"):
			changed = [f for f in SENSITIVE if self.has_value_changed(f)]
			if changed and not self.flags.reg_justification and not frappe.flags.reg_system:
				frappe.throw(_("La modification de {0} sur une obligation active doit être justifiée (bouton « Modifier avec justification »).")
					.format(", ".join(_(self.meta.get_label(f)) for f in changed)))

	def _validate_dates(self):
		if self.date_fin and self.date_debut and getdate(self.date_fin) < getdate(self.date_debut):
			frappe.throw(_("La date de fin précède la date de début."))

	def _validate_timing(self):
		nt = self.nature_temporelle
		if nt == "Périodique":
			if not self.frequence or self.frequence in ("Ponctuelle", "Événementielle", "Permanente"):
				frappe.throw(_("Une obligation périodique doit avoir une fréquence périodique."))
			if self.frequence == "Personnalisée" and not cint(self.intervalle):
				frappe.throw(_("Indiquez l'intervalle de la fréquence personnalisée."))
		elif nt == "Événementielle":
			self.frequence = "Événementielle"
			if not self.evenement_declencheur:
				frappe.throw(_("Une obligation événementielle doit préciser l'événement déclencheur."))
			if not self.delai_valeur and self.delai_valeur != 0:
				frappe.throw(_("Indiquez le délai de réalisation après l'événement."))
		elif nt in ("Ponctuelle", "Date fixe", "Relative à une date réglementaire"):
			if not (self.date_fixe or self.date_debut):
				frappe.throw(_("Indiquez la date de référence de l'obligation."))
			if nt == "Ponctuelle":
				self.frequence = "Ponctuelle"
		elif nt == "Permanente":
			self.frequence = "Permanente"
		if self.delai_valeur and not self.delai_unite:
			frappe.throw(_("Précisez l'unité du délai."))
		if self.jours_alerte:
			try:
				[int(x) for x in str(self.jours_alerte).replace(";", ",").split(",") if x.strip()]
			except ValueError:
				frappe.throw(_("Jours d'alerte : liste de nombres séparés par des virgules (ex. 30,15,7,1)."))

	def _validate_evidence(self):
		if cint(self.justificatif_requis) and self.statut in ("Validée", "Active"):
			active = [r for r in self.justificatifs if cint(r.actif)]
			if not active:
				frappe.throw(_("Un justificatif est requis mais aucun type de justificatif n'est défini."))
			if not any(cint(r.obligatoire) for r in active):
				frappe.throw(_("Au moins un justificatif doit être obligatoire."))
		seen = set()
		for r in self.justificatifs:
			key = (r.type_justificatif, (r.libelle or "").strip().lower())
			if key in seen:
				frappe.throw(_("Justificatif en double : {0}").format(r.libelle))
			seen.add(key)

	def _validate_source(self):
		if not self.source:
			return
		st = frappe.db.get_value("Reg Source", self.source, "statut")
		if st in ("Abrogée", "Archivée") and self.statut in ("Validée", "Active"):
			require_text(self.justification_source_abrogee, _("La justification du maintien sur une source abrogée"))
		if self.version_source and frappe.db.get_value("Reg Source Version", self.version_source, "source") != self.source:
			frappe.throw(_("La version de source ne correspond pas à la source."))
		if self.disposition_principale and frappe.db.get_value("Reg Provision", self.disposition_principale, "source") != self.source:
			frappe.throw(_("La disposition principale doit appartenir à la source de rattachement."))

	def _validate_status_requirements(self):
		if self.statut in ("Validée", "Active"):
			missing = [_(self.meta.get_label(f)) for f in ("criticite", "source", "domaine", "proprietaire", "direction",
				"nature_temporelle") if not self.get(f)]
			if self.applicabilite == "À analyser":
				missing.append(_("Décision d'applicabilité"))
			if missing:
				frappe.throw(_("Champs requis pour valider l'obligation : {0}").format(", ".join(missing)))
		if self.has_value_changed("statut") and self.statut == "Validée" and not frappe.flags.reg_system:
			self.valide_par = frappe.session.user
			self.date_validation = today()
			assert_sod(frappe.session.user, self.owner if self.owner != "Administrator" else None, self.proprietaire,
				message=_("Séparation des tâches : l'auteur ou le propriétaire ne peut pas valider l'obligation."))
		if self.has_value_changed("statut") and self.statut == "Active":
			if self.applicabilite not in ("Applicable", "Applicable sous condition"):
				frappe.throw(_("Seule une obligation applicable peut être activée."))
			self.date_activation = self.date_activation or today()
		if self.has_value_changed("statut") and self.statut in ("Clôturée", "Obsolète", "Suspendue") and not frappe.flags.reg_system:
			if not self.flags.reg_justification:
				frappe.throw(_("Un motif est obligatoire pour passer l'obligation au statut {0}.").format(self.statut))
		if self.has_value_changed("statut") and self.statut == "Archivée":
			self.date_archivage = today()

	def _sync_principal_provision(self):
		if self.disposition_principale and not any(r.disposition == self.disposition_principale for r in self.dispositions):
			self.append("dispositions", {"disposition": self.disposition_principale, "source": self.source, "role_lien": "Principal",
				"nature_lien": "Fondement", "ajoute_par": frappe.session.user, "date_ajout": today()})
		for r in self.dispositions:
			if r.disposition and not r.source:
				r.source = frappe.db.get_value("Reg Provision", r.disposition, "source")
			r.role_lien = "Principal" if r.disposition == self.disposition_principale else (r.role_lien or "Complémentaire")

	def after_insert(self):
		from obligation_reglementaire.engine import notification
		notification.emit("obligation_creee", self)

	def on_update(self):
		from obligation_reglementaire.engine import deadline, notification

		if self.has_value_changed("statut") and not self.is_new():
			notification.emit("obligation_statut", self)
		if self.has_value_changed("proprietaire") or self.has_value_changed("responsable_operationnel"):
			notification.emit("obligation_affectee", self)
			self._propagate_responsible()
		if self.has_value_changed("criticite") and self.get_doc_before_save():
			notification.emit("criticite_modifiee", self)
		if self.statut == "Active":
			deadline.generate_for_obligation(self)
		if self.has_value_changed("statut") and self.statut in ("Clôturée", "Obsolète", "Archivée"):
			self._cancel_future_deadlines()
		if self.has_value_changed("statut") and self.statut == "Suspendue":
			self._suspend_deadlines()
		if self.has_value_changed("statut") and self.statut == "Active" and \
				(self.get_doc_before_save() and self.get_doc_before_save().statut == "Suspendue"):
			self._resume_deadlines()

	def _propagate_responsible(self):
		"""Les échéances ouvertes non démarrées suivent le nouveau responsable (les historiques restent inchangés)."""
		resp = self.responsable_operationnel or self.proprietaire
		with SystemAction():
			for name in frappe.get_all("Reg Deadline", filters={"obligation": self.name, "statut": ("in", ("À venir", "À traiter"))},
					pluck="name"):
				frappe.db.set_value("Reg Deadline", name, "responsable", resp)

	def _cancel_future_deadlines(self):
		motif = self.flags.reg_justification or _("Obligation {0}").format(self.statut.lower())
		with SystemAction():
			for name in frappe.get_all("Reg Deadline", filters={"obligation": self.name, "statut": "À venir",
					"date_limite": (">", today_date())}, pluck="name"):
				d = frappe.get_doc("Reg Deadline", name)
				d.statut, d.motif_annulation = "Annulée", motif
				d.flags.ignore_permissions = True
				d.save()
		log_audit("Annulation des échéances futures", self, justification=motif)

	def _suspend_deadlines(self):
		from obligation_reglementaire.engine import deadline
		motif = self.flags.reg_justification or _("Obligation suspendue")
		with SystemAction():
			for name in frappe.get_all("Reg Deadline", filters={"obligation": self.name, "statut": ("in", ("À venir", "À traiter"))},
					pluck="name"):
				deadline.suspend(frappe.get_doc("Reg Deadline", name), motif)

	def _resume_deadlines(self):
		from obligation_reglementaire.engine import deadline
		with SystemAction():
			for name in frappe.get_all("Reg Deadline", filters={"obligation": self.name, "statut": "Suspendue"}, pluck="name"):
				deadline.resume(frappe.get_doc("Reg Deadline", name))
