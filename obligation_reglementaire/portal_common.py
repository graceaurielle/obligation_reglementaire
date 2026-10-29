"""Cœur du portail web obligation_reglementaire (pages www/).

Réutilise le design system du portail due_diligence (includes v_base_style / v_sidebar /
v_table_style) et la page de connexion partagée (/vconnexion), sans modifier aucun fichier
due_diligence. Si due_diligence n'est pas installée, un repli local prend le relais.

Le sens inverse (faire apparaître « Obligations » dans les portails DD et CT) est assuré par le
hook update_website_context dans obligation_reglementaire/website.py.
"""

import frappe

# ── Rôles ──────────────────────────────────────────────────────────────────────

# Rôles de pilotage : accès complet au portail
OR_ROLES_PILOTAGE = [
	"OR Administrateur",
	"OR Responsable Conformité",
]

# Rôles opérationnels : vue sur leurs propres obligations et échéances
OR_ROLES_OPERATIONNELS = [
	"OR Analyste Réglementaire",
	"OR Responsable Obligation",
	"OR Contributeur",
]

# Rôles de contrôle et validation
OR_ROLES_CONTROLE = [
	"OR Contrôleur",
	"OR Validateur",
]

# Rôles de supervision (lecture transverse)
OR_ROLES_SUPERVISION = [
	"OR Auditeur",
	"OR Direction Générale",
	"OR Gestionnaire Reporting",
	"OR Gestionnaire Documentaire",
]

# Rôles due_diligence / contract_te qui accèdent aussi au portail OR (vue transverse)
DD_SUPERVISEURS = ["DD Manager Compliance", "DD DG"]

ROLE_LABELS = {
	"OR Administrateur": "Administrateur réglementaire",
	"OR Responsable Conformité": "Responsable Conformité",
	"OR Analyste Réglementaire": "Analyste réglementaire",
	"OR Responsable Obligation": "Responsable d'obligation",
	"OR Contributeur": "Contributeur",
	"OR Contrôleur": "Contrôleur",
	"OR Validateur": "Validateur",
	"OR Auditeur": "Auditeur",
	"OR Direction Générale": "Direction Générale",
	"OR Gestionnaire Reporting": "Gestionnaire Reporting",
	"OR Gestionnaire Documentaire": "Gestionnaire Documentaire",
	"DD Manager Compliance": "Manager Compliance",
	"DD DG": "Direction Générale",
	"Administrator": "Administration",
	"System Manager": "Administration",
}

# ── Icônes SVG ─────────────────────────────────────────────────────────────────

_ICON_DASHBOARD = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>'
_ICON_ECHEANCE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>'
_ICON_JUSTIFICATIF = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>'
_ICON_NC = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
_ICON_PLAN = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>'
_ICON_SOURCE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5V5a2 2 0 0 1 2-2h13v18H6.5A2.5 2.5 0 0 1 4 19.5z"/><line x1="8" y1="7" x2="15" y2="7"/><line x1="8" y1="11" x2="15" y2="11"/></svg>'
_ICON_NOTIF = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>'
_ICON_VERS_OR = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="10 13 13 16 10 19"/></svg>'
_ICON_VERS_DD = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="13 9 10 12 13 15"/></svg>'
_ICON_VERS_CT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="10 13 13 16 10 19"/></svg>'
_ICON_DOCUMENT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>'
_ICON_RAPPORT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'

# ── Navigation ─────────────────────────────────────────────────────────────────

NAV_ITEMS = {
	"obligations": {"href": "/obligations", "label": "Tableau de bord", "icon": _ICON_DASHBOARD},
	"obligations-echeances": {"href": "/obligations-echeances", "label": "Échéances", "icon": _ICON_ECHEANCE},
	"obligations-justificatifs": {"href": "/obligations-justificatifs", "label": "Justificatifs", "icon": _ICON_JUSTIFICATIF},
	"obligations-nc": {"href": "/obligations-nc", "label": "Non-conformités", "icon": _ICON_NC},
	"obligations-plans": {"href": "/obligations-plans", "label": "Plans d'action", "icon": _ICON_PLAN},
	"obligations-sources": {"href": "/obligations-sources", "label": "Sources", "icon": _ICON_SOURCE},
	"obligations-documents": {"href": "/obligations-documents", "label": "Documents", "icon": _ICON_DOCUMENT},
	"obligations-rapports": {"href": "/obligations-rapports", "label": "Rapports", "icon": _ICON_RAPPORT},
	"obligations-notifications": {"href": "/obligations-notifications", "label": "Notifications", "icon": _ICON_NOTIF},
}

_NAV_ORDONNE = [
	"obligations", "obligations-echeances", "obligations-justificatifs",
	"obligations-nc", "obligations-plans", "obligations-sources",
	"obligations-documents", "obligations-rapports", "obligations-notifications",
]

_NAV_COMPLET = set(_NAV_ORDONNE)

# Onglets par rôle
_NAV_PAR_ROLE = {
	# Pilotage : tout
	"OR Administrateur": _NAV_COMPLET,
	"OR Responsable Conformité": _NAV_COMPLET,
	# Opérationnels : pas les sources ; pas les rapports (aucune permission sur Reg Report Instance,
	# confirmé par audit des fixtures de permissions des doctypes)
	"OR Analyste Réglementaire": _NAV_COMPLET - {"obligations-rapports"},
	"OR Responsable Obligation": _NAV_COMPLET - {"obligations-sources", "obligations-rapports"},
	"OR Contributeur": {"obligations", "obligations-echeances", "obligations-justificatifs",
		"obligations-documents", "obligations-notifications"},
	# Contrôle et validation : lecture+écriture sur Reg Document et Reg Report Instance, déjà
	# couverts par _NAV_COMPLET
	"OR Contrôleur": _NAV_COMPLET - {"obligations-sources"},
	"OR Validateur": _NAV_COMPLET - {"obligations-sources"},
	# Supervision (lecture)
	"OR Auditeur": _NAV_COMPLET,
	"OR Direction Générale": {"obligations", "obligations-nc", "obligations-plans", "obligations-notifications"},
	"OR Gestionnaire Reporting": {"obligations", "obligations-echeances", "obligations-nc", "obligations-plans",
		"obligations-rapports"},
	"OR Gestionnaire Documentaire": {"obligations", "obligations-documents", "obligations-justificatifs",
		"obligations-notifications"},
	# DD superviseurs
	"DD Manager Compliance": _NAV_COMPLET,
	"DD DG": {"obligations", "obligations-nc", "obligations-plans"},
	# Admin
	"Administrator": _NAV_COMPLET,
	"System Manager": _NAV_COMPLET,
}

# Passerelle ALLER : injectée dans les portails DD et CT par le hook
NAV_ITEM_OBLIGATIONS = {
	"href": "/obligations",
	"label": "Obligations réglementaires",
	"icon": _ICON_VERS_OR,
	"cross_app": True,
}


def roles_autorises():
	"""Tous les rôles ayant accès à au moins une page du portail OR."""
	return (OR_ROLES_PILOTAGE + OR_ROLES_OPERATIONNELS + OR_ROLES_CONTROLE
			+ OR_ROLES_SUPERVISION + DD_SUPERVISEURS + ["Administrator", "System Manager"])


def roles_pour_page(cle_nav):
	"""Rôles autorisés sur la page `cle_nav`."""
	return [role for role, pages in _NAV_PAR_ROLE.items() if cle_nav in pages]


def nav_pour_roles(user_roles):
	"""Onglets visibles : union des rôles de l'utilisateur, dans l'ordre de référence."""
	visibles = set()
	for role in user_roles:
		visibles |= _NAV_PAR_ROLE.get(role, set())
	return [NAV_ITEMS[k] for k in _NAV_ORDONNE if k in visibles] or [NAV_ITEMS["obligations"]]


def _label_pour_role(role):
	return ROLE_LABELS.get(role, "Obligations réglementaires")


def _user_identity(user):
	"""Réutilise l'identité DD si présente, sinon repli local."""
	try:
		from due_diligence.portal_common import user_identity
		return user_identity(user)
	except Exception:
		full_name = frappe.utils.get_fullname(user) or user
		initials = "".join(p[0] for p in full_name.split()[:2]).upper() or "?"
		return full_name, initials


def _nav_retour_due_diligence(user_roles):
	"""Item « Revenir aux due diligences », ou None."""
	try:
		from due_diligence.portal_common import ROLE_NAV
	except Exception:
		return None
	role_dd = next((r for r in ROLE_NAV if r in user_roles), None)
	if not role_dd:
		return None
	href = "/ctableau-de-bord" if role_dd == "DD Client" else "/vtableau-de-bord"
	return {"href": href, "label": "Due diligences", "icon": _ICON_VERS_DD, "cross_app": True}


def _nav_contrats(user_roles):
	"""Item « Contrats » si contract_te est installée et accessible."""
	try:
		from contract_te.portal_common import roles_autorises as ct_roles
	except Exception:
		return None
	if set(user_roles).intersection(ct_roles()):
		return {"href": "/contrats", "label": "Contrats", "icon": _ICON_VERS_CT, "cross_app": True}
	return None


def est_operationnel_seul(user=None):
	"""Vrai si l'utilisateur n'a que des rôles opérationnels (contributeur / responsable obligation)
	sans rôle de pilotage, contrôle ou supervision. Restreint la vue à ses propres obligations."""
	roles = set(frappe.get_roles(user or frappe.session.user))
	pilotage_ou_plus = set(OR_ROLES_PILOTAGE + OR_ROLES_CONTROLE + OR_ROLES_SUPERVISION
						   + DD_SUPERVISEURS + ["Administrator", "System Manager"])
	return bool(roles.intersection(OR_ROLES_OPERATIONNELS)) and not roles.intersection(pilotage_ou_plus)


def resolve_portal_access(allowed_roles, fallback_redirect="/app"):
	"""Contrôle d'accès unique pour les pages www/ du portail OR.

	Renvoie (user, role, role_label, nav_items). Redirige les Guests vers /vconnexion,
	et les utilisateurs sans rôle autorisé vers `fallback_redirect`."""
	user = frappe.session.user
	if user == "Guest":
		frappe.local.flags.redirect_location = "/vconnexion"
		raise frappe.Redirect

	roles = set(frappe.get_roles(user))
	autorises = [r for r in allowed_roles if r in roles]
	if not autorises:
		frappe.local.flags.redirect_location = fallback_redirect
		raise frappe.Redirect

	role = autorises[0]
	nav_items = nav_pour_roles(roles)

	# Passerelles vers les autres portails
	retour_dd = _nav_retour_due_diligence(roles)
	if retour_dd:
		nav_items.append(retour_dd)
	lien_ct = _nav_contrats(roles)
	if lien_ct:
		nav_items.append(lien_ct)

	return user, role, _label_pour_role(role), nav_items


def base_context(context, active_page, title, allowed_roles=None, fallback_redirect="/app"):
	"""Applique le squelette commun (auth + variables pour v_sidebar / v_base_style).

	Sans `allowed_roles` explicite, le droit est dérivé de `active_page` via roles_pour_page()."""
	user, role, role_label, nav_items = resolve_portal_access(
		allowed_roles or roles_pour_page(active_page) or roles_autorises(), fallback_redirect)
	full_name, initials = _user_identity(user)

	context.full_width = True
	context.active_page = active_page
	context.title = title
	context.role_label = role_label
	context.nav_items = nav_items
	context.user_full_name = full_name
	context.user_initials = initials
	return user, role


def user_org_filter(user):
	"""Filtre d'organisation : retourne le dict de filtre si l'utilisateur est membre d'une seule
	organisation, ou {} s'il en a plusieurs (vue transverse)."""
	orgs = frappe.get_all("Reg Member", filters={"utilisateur": user, "statut": "Actif"}, pluck="organisation")
	if len(orgs) == 1:
		return {"organisation": orgs[0]}
	return {}


# ── Routage des pages de détail ────────────────────────────────────────────────
# Complété phase après phase ; finalisé en Phase 5 pour la résolution des liens de notification.
DETAIL_ROUTE = {
	"Reg Deadline": "/obligations-echeances-detail",
	"Reg Evidence": "/obligations-justificatifs-detail",
	"Reg Evidence Review": "/obligations-controle-detail",
	"Reg Non Conformity": "/obligations-nc-detail",
	"Reg Action Plan": "/obligations-plans-detail",
	"Reg Corrective Action": "/obligations-actions-detail",
	"Reg Obligation": "/obligations-obligation-detail",
	"Reg Source": "/obligations-sources-detail",
	"Reg Document": "/obligations-documents-detail",
	"Reg Report Instance": "/obligations-rapports-detail",
	"Reg Config Change Request": "/obligations-config-detail",
	"Reg Applicability Proposal": "/obligations-proposition-detail",
}


def detail_url(doctype, name):
	"""URL de la page de détail portail pour `doctype`/`name`, ou None si ce doctype n'a pas
	(encore) de page de détail dédiée — jamais un lien cassé."""
	route = DETAIL_ROUTE.get(doctype)
	if not route or not name:
		return None
	return f"{route}?name={frappe.utils.quoted(name)}"


def resoudre_noms(rows, *fields):
	"""Remplace in-place, pour chaque champ donné, l'ID utilisateur par son nom complet.
	À utiliser côté Python : Jinja (sandboxé) n'expose pas frappe.utils.get_fullname."""
	for row in rows:
		for field in fields:
			val = row.get(field)
			if val:
				row[field] = frappe.utils.get_fullname(val) or val
