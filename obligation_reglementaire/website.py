"""Intégration portail : injecte l'entrée « Obligations réglementaires » dans les portails
due_diligence et contract_te, sans modifier aucun fichier de ces apps. Gère aussi l'atterrissage
après la connexion partagée /vconnexion pour les porteurs de rôle OR.

Mécanisme (nav) : le hook Frappe `update_website_context` ajoute l'item de nav au `nav_items`
déjà présent dans le contexte des pages portail — la sidebar (v_sidebar.html) le rend
automatiquement. Si obligation_reglementaire n'est pas installée, le hook n'existe pas."""

import functools

import frappe

from obligation_reglementaire.portal_common import NAV_ITEM_OBLIGATIONS, roles_autorises


def inject_obligation_nav(context):
	"""Hook update_website_context. Idempotent — ne touche que les pages portail."""
	nav = context.get("nav_items") if hasattr(context, "get") else None
	if not nav:
		return

	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(roles_autorises()):
		return

	presents = {item.get("href") for item in nav}
	if NAV_ITEM_OBLIGATIONS["href"] not in presents:
		nav.append(NAV_ITEM_OBLIGATIONS)


# ------------------------------------------------------------------
# Atterrissage après la connexion partagée /vconnexion
# ------------------------------------------------------------------
# /vconnexion ne décide pas de la destination : après authentification le navigateur passe par
# /vpost-connexion, qui délègue à due_diligence.www.vconnexion.default_landing_page(). Cette
# fonction ne connaît que les rôles DD (et, une fois contract_te installée, les rôles CT) et renvoie
# « /app » (le Desk) pour tout le reste — un porteur de rôle OR sans rôle DD/CT atterrissait donc
# dans le Desk au lieu du portail réglementaire.
#
# due_diligence restant en lecture seule, on ne l'édite pas : on enveloppe la fonction au moment du
# démarrage de la requête (hook before_request), exactement comme le fait contract_te
# (contract_te/integrations/due_diligence.py). L'enveloppe est passive — elle ne remplace QUE le
# repli « /app » et laisse intacte toute autre destination (DD ou CT), qu'elle ait été calculée par
# due_diligence elle-même ou par un patch posé avant le nôtre. Le drapeau
# `_obligation_reglementaire_patched` est propre à cette app : qu'il s'installe avant ou après celui
# de contract_te, chaque enveloppe ne regarde que la fonction courante et les deux se composent sans
# se marcher dessus.
_REPLI_DD = "/app"


def _atterrissage_reglementaire(user):
	"""Destination réglementaire pour `user`, ou None s'il n'a aucun rôle OR."""
	roles = set(frappe.get_roles(user))
	if roles.intersection(roles_autorises()):
		return "/obligations"
	return None


def install_landing_page_patch():
	"""Hook `before_request` : enveloppe default_landing_page(). Idempotent et sans effet si
	due_diligence n'est pas installée sur le site."""
	if "due_diligence" not in frappe.get_installed_apps():
		return

	try:
		from due_diligence.www import vconnexion
	except Exception:
		return

	original = getattr(vconnexion, "default_landing_page", None)
	if original is None or getattr(original, "_obligation_reglementaire_patched", False):
		return

	@functools.wraps(original)
	def default_landing_page(user):
		destination = original(user)
		if destination == _REPLI_DD:
			return _atterrissage_reglementaire(user) or destination
		return destination

	default_landing_page._obligation_reglementaire_patched = True
	vconnexion.default_landing_page = default_landing_page
