"""Socle transverse : organisation, transitions, séparation des tâches, audit, interdiction de suppression."""

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, today

MODULE = "Obligation Reglementaire"

ADMIN_ROLES = ("System Manager", "OR Administrateur")

# Champs techniques jamais journalisés
_IGNORED = {"modified", "modified_by", "creation", "owner", "idx", "lft", "rgt", "old_parent", "_user_tags",
	"_comments", "_assign", "_liked_by", "_seen", "docstatus"}

_NO_VALUE = ("Section Break", "Column Break", "Tab Break", "HTML", "Table", "Table MultiSelect", "Button", "Heading")


def get_settings():
	return frappe.get_cached_doc("Reg Settings")


def system_context():
	"""Vrai lorsqu'un traitement automatique (planificateur, moteur) est en cours."""
	return bool(frappe.flags.reg_system or frappe.flags.in_install or frappe.flags.in_migrate
		or frappe.flags.in_patch or frappe.flags.in_import)


class SystemAction:
	"""with SystemAction(): … — marque les écritures comme traitements automatiques (audités comme tels)."""

	def __enter__(self):
		self._prev = frappe.flags.reg_system
		frappe.flags.reg_system = True

	def __exit__(self, *exc):
		frappe.flags.reg_system = self._prev


def is_admin(user=None):
	roles = frappe.get_roles(user or frappe.session.user)
	return any(r in roles for r in ADMIN_ROLES) or (user or frappe.session.user) == "Administrator"


def has_any_role(*roles, user=None):
	user_roles = frappe.get_roles(user or frappe.session.user)
	return any(r in user_roles for r in roles + ADMIN_ROLES)


def require_roles(*roles):
	if system_context():
		return
	if not has_any_role(*roles):
		frappe.throw(_("Action réservée aux rôles : {0}").format(", ".join(roles)), frappe.PermissionError)


# ------------------------------------------------------------------ organisation
def user_organisation(user=None):
	user = user or frappe.session.user
	org = frappe.db.get_value("Reg Member", user, "organisation")
	if not org:
		org = frappe.db.get_single_value("Reg Settings", "organisation_defaut")
	return org


def criticality_weight(level):
	if not level:
		return 0
	return cint(frappe.db.get_value("Reg Criticality Level", level, "poids"))


def assert_org_active(org):
	if not org or system_context():
		return
	statut = frappe.db.get_value("Reg Organization", org, "statut")
	if statut and statut != "Active":
		frappe.throw(_("L'organisation {0} est {1} : aucune nouvelle opération n'est autorisée.").format(org, statut.lower()))


# ------------------------------------------------------------------ transitions & séparation des tâches
def check_transition(doc, transitions, field="statut"):
	"""Contrôle qu'un changement de statut respecte la matrice (ancien -> {nouveaux})."""
	if doc.is_new() or not doc.has_value_changed(field):
		return
	if frappe.flags.reg_force_transition:
		return
	old = (doc.get_doc_before_save() or frappe._dict()).get(field)
	new = doc.get(field)
	if old == new or old is None:
		return
	allowed = transitions.get(old)
	if allowed is not None and new not in allowed:
		frappe.throw(_("Transition interdite pour {0} : « {1} » → « {2} ».").format(_(doc.doctype), old, new),
			title=_("Cycle de vie"))


def set_status(doc, status, field="statut", **values):
	"""Change le statut via save() pour passer par validate (transitions, audit, notifications)."""
	doc.set(field, status)
	for k, v in values.items():
		doc.set(k, v)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


def assert_sod(actor, *others, message=None):
	"""RG-SEC-004 : l'auteur / le responsable d'un objet ne peut pas le valider lui-même."""
	if system_context() or not cint(get_settings().separation_taches):
		return
	if actor and actor in [o for o in others if o]:
		frappe.throw(message or _("Séparation des tâches : vous ne pouvez pas valider un objet dont vous êtes l'auteur ou le responsable."),
			title=_("Séparation des tâches"))


def require_text(value, label):
	if not (value or "").strip():
		frappe.throw(_("{0} est obligatoire.").format(label))


# ------------------------------------------------------------------ audit
def log_audit(operation, doc=None, doctype=None, name=None, champ=None, ancienne=None, nouvelle=None,
		justification=None, details=None, organisation=None):
	try:
		ip = getattr(frappe.local, "request_ip", None)
	except Exception:
		ip = None
	entry = frappe.get_doc({
		"doctype": "Reg Audit Log",
		"horodatage": now_datetime(),
		"utilisateur": frappe.session.user if frappe.session else "Administrator",
		"organisation": organisation or (doc.get("organisation") if doc is not None and doc.meta.has_field("organisation") else None),
		"operation": operation,
		"reference_doctype": doctype or (doc.doctype if doc is not None else None),
		"reference_name": name or (doc.name if doc is not None else None),
		"automatique": 1 if system_context() else 0,
		"adresse_ip": ip,
		"champ": champ,
		"ancienne_valeur": None if ancienne is None else str(ancienne)[:2000],
		"nouvelle_valeur": None if nouvelle is None else str(nouvelle)[:2000],
		"justification": justification,
		"details": json.dumps(details, default=str, ensure_ascii=False) if details else None,
	})
	entry.flags.ignore_permissions = True
	entry.flags.ignore_links = True
	entry.db_insert()
	return entry


def audit_changes(doc, method=None):
	"""doc_event on_update : journalise création et modifications de champs significatifs."""
	if doc.doctype == "Reg Audit Log" or doc.meta.istable:
		return
	before = doc.get_doc_before_save()
	if before is None:
		log_audit("Création", doc, nouvelle=doc.get("statut"))
		return
	changes = []
	for df in doc.meta.fields:
		if df.fieldtype in _NO_VALUE or df.fieldname in _IGNORED:
			continue
		old, new = before.get(df.fieldname), doc.get(df.fieldname)
		if (old or None) != (new or None) and str(old or "") != str(new or ""):
			changes.append((df.fieldname, old, new))
	if not changes:
		return
	justification = doc.flags.get("reg_justification")
	for fieldname, old, new in changes:
		if fieldname in ("statut", "criticite", "gravite", "responsable", "proprietaire", "date_limite", "date_cible",
				"date_fin_prevue", "applicabilite", "etat_conformite", "resultat", "decision"):
			log_audit("Changement de statut" if fieldname == "statut" else "Modification", doc, champ=fieldname,
				ancienne=old, nouvelle=new, justification=justification)
	others = [c for c in changes if c[0] not in ("statut", "criticite", "gravite", "responsable", "proprietaire",
		"date_limite", "date_cible", "date_fin_prevue", "applicabilite", "etat_conformite", "resultat", "decision")]
	if others:
		log_audit("Modification", doc, champ=", ".join(c[0] for c in others)[:140],
			details={c[0]: {"avant": c[1], "apres": c[2]} for c in others}, justification=justification)


def before_validate(doc, method=None):
	"""doc_event validate commun : organisation par défaut, organisation suspendue (RG-ADM-008)."""
	if doc.meta.has_field("organisation") and not doc.get("organisation"):
		doc.organisation = user_organisation()
	if doc.is_new() and doc.meta.has_field("organisation"):
		assert_org_active(doc.get("organisation"))


def forbid_delete(doc, method=None):
	"""RG-SEC-012 / RG-JUS : aucun objet probant n'est supprimé physiquement — annulation ou archivage."""
	if frappe.flags.reg_allow_delete or frappe.flags.in_uninstall or frappe.flags.in_test:
		return
	if doc.get("docstatus") == 0 and doc.get("statut") in ("Brouillon",) and doc.owner == frappe.session.user \
			and doc.doctype not in ("Reg Audit Log", "Reg Notification Log", "Reg Evidence Version", "Reg Document Version"):
		log_audit("Suppression d'un brouillon", doc)
		return
	frappe.throw(_("Suppression interdite : {0} {1} doit être annulé(e) ou archivé(e), jamais supprimé(e).").format(
		_(doc.doctype), doc.name), title=_("Traçabilité"))


def forbid_log_edit(doc, method=None):
	if not doc.is_new() and not frappe.flags.reg_system:
		frappe.throw(_("Le journal est inaltérable."))


def fmt_date(d):
	return frappe.utils.formatdate(d, "dd/MM/yyyy") if d else ""


def today_date():
	return frappe.utils.getdate(today())
