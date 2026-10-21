"""Événements de document communs à tous les objets « Reg * » (branchés en doc_events « * » dans hooks.py)."""

from obligation_reglementaire.engine import common

# Journaux techniques : ni audit de leurs propres écritures, ni contrôle d'organisation
_NO_AUDIT = {"Reg Audit Log", "Reg Notification Log", "Reg Indicator Value"}


def _is_reg(doc):
	return doc.doctype.startswith("Reg ") and not doc.meta.istable


def validate(doc, method=None):
	if _is_reg(doc) and doc.doctype not in _NO_AUDIT:
		common.before_validate(doc, method)


def on_update(doc, method=None):
	if _is_reg(doc) and doc.doctype not in _NO_AUDIT and not doc.meta.issingle:
		common.audit_changes(doc, method)
	elif doc.doctype == "Reg Settings":
		common.log_audit("Modification des paramètres généraux", doc, justification=doc.flags.get("reg_justification"))


def on_trash(doc, method=None):
	if _is_reg(doc) and not doc.meta.issingle:
		common.forbid_delete(doc, method)


def before_save_log(doc, method=None):
	if doc.doctype == "Reg Audit Log":
		common.forbid_log_edit(doc, method)
