"""Page de détail (lecture seule) d'une source réglementaire — /obligations-sources-detail?name=…

Reg Source / Reg Source Version n'exposent aucune transition de statut côté portail (décision
actée au moment du plan) : cette page n'affiche que des informations et les 3 outils d'analyse en
lecture (comparaison de versions, analyse d'impact, doublons potentiels), qui créent des
enregistrements d'analyse sans jamais changer le statut de la source elle-même.
"""

import frappe

from obligation_reglementaire.portal_actions import COMPLIANCE_ROLES
from obligation_reglementaire.portal_common import base_context, resoudre_noms

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-sources", title="Source réglementaire")

	name = frappe.form_dict.get("name")
	if not name or not frappe.db.exists("Reg Source", name):
		frappe.local.flags.redirect_location = "/obligations-sources"
		raise frappe.Redirect

	source = frappe.get_doc("Reg Source", name)
	try:
		source.check_permission("read")
	except frappe.PermissionError:
		frappe.local.flags.redirect_location = "/obligations-sources"
		raise frappe.Redirect

	versions = frappe.get_all("Reg Source Version", filters={"source": name},
		fields=["name", "numero_version", "libelle", "statut", "date_publication",
				"date_entree_vigueur", "date_fin_validite", "est_consolidee", "valide_par"],
		order_by="date_entree_vigueur desc, creation desc")
	resoudre_noms(versions, "valide_par")

	roles = set(frappe.get_roles(user))

	context.title = f"{source.name} — Source réglementaire"
	context.source = source
	context.responsable_interne_nom = frappe.utils.get_fullname(source.responsable_interne) if source.responsable_interne else None
	context.valide_par_nom = frappe.utils.get_fullname(source.valide_par) if source.valide_par else None
	context.versions = versions
	context.domaines = source.domaines
	context.territoires = source.territoires
	context.relations = source.relations
	context.peut_analyser = bool(roles.intersection(COMPLIANCE_ROLES + ("OR Analyste Réglementaire",)))
