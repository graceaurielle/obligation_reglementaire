# Copyright (c) 2026, grace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, date_diff, getdate, now_datetime

from obligation_reglementaire.engine.common import get_settings, require_text


class RegExtensionRequest(Document):
	def validate(self):
		if self.type_objet == "Action":
			if not self.action:
				frappe.throw(_("Sélectionnez l'action à prolonger."))
			a = frappe.db.get_value("Reg Corrective Action", self.action, ["plan", "date_fin_prevue", "statut", "organisation"], as_dict=True)
			if a.statut in ("Validée", "Annulée"):
				frappe.throw(_("Une action {0} ne peut pas être prolongée.").format(a.statut.lower()))
			self.plan, self.organisation = a.plan, a.organisation
			current = a.date_fin_prevue
		else:
			p = frappe.db.get_value("Reg Action Plan", self.plan, ["date_cible", "statut", "organisation"], as_dict=True)
			if p.statut in ("Clôturé", "Annulé"):
				frappe.throw(_("Un plan {0} ne peut pas être prolongé.").format(p.statut.lower()))
			self.organisation = p.organisation
			current = p.date_cible
		if self.is_new():
			self.date_initiale = current
			self.demandeur = frappe.session.user
			self.date_demande = now_datetime()
			if frappe.db.exists("Reg Extension Request", {"plan": self.plan, "action": self.action, "type_objet": self.type_objet,
					"statut": ("in", ("Demandée", "Informations demandées"))}):
				frappe.throw(_("Une demande de prolongation est déjà en cours pour cet objet."))
		require_text(self.motif, _("Le motif"))
		require_text(self.justification, _("La justification"))
		if not self.nouvelle_date or getdate(self.nouvelle_date) <= getdate(self.date_initiale):
			frappe.throw(_("La nouvelle date doit être postérieure à la date actuelle ({0}).").format(self.date_initiale))
		self.jours_ajoutes = date_diff(self.nouvelle_date, self.date_initiale)
		nb = cint(frappe.db.get_value("Reg Action Plan", self.plan, "nb_prolongations"))
		if nb >= cint(get_settings().max_prolongations_alerte or 3) and self.is_new():
			frappe.msgprint(_("Ce plan a déjà été prolongé {0} fois : la demande sera signalée.").format(nb), indicator="orange")

	def after_insert(self):
		from obligation_reglementaire.engine import notification
		notification.emit("prolongation_demandee", self)
