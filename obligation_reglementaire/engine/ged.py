"""GED réglementaire (Ch9) : versions, empreintes, contrôle / publication, gel, conservation, suppression logique,
partage sécurisé par lien expirant."""

import secrets

import frappe
from frappe import _
from frappe.utils import add_years, cint, get_url, getdate, today

from obligation_reglementaire.engine.common import SystemAction, assert_sod, log_audit, require_text
from obligation_reglementaire.engine.evidence import file_fingerprint, max_size_bytes

DOC_TRANSITIONS = {
	"Brouillon": {"Soumis", "Supprimé logiquement"},
	"Soumis": {"En contrôle", "Validé", "Rejeté", "Brouillon"},
	"En contrôle": {"Validé", "Rejeté"},
	"Rejeté": {"Soumis", "Brouillon", "Supprimé logiquement"},
	"Validé": {"Publié", "Expiré", "Archivé", "Soumis"},
	"Publié": {"Expiré", "Archivé", "Soumis"},
	"Expiré": {"Archivé", "Soumis"},
	"Archivé": {"Supprimé logiquement"},
	"Supprimé logiquement": set(),
}

LOCKED = ("Validé", "Publié", "Archivé")


def check_document_file(file_url, document_type=None):
	"""Contrôle format / taille selon le type de document (à défaut, les paramètres généraux) ; retourne l'empreinte."""
	name, size, mime, digest = file_fingerprint(file_url)
	fmt = (frappe.db.get_value("Reg Document Type", document_type, "formats_autorises") if document_type else None) \
		or frappe.db.get_single_value("Reg Settings", "formats_autorises") or ""
	allowed = {f.strip().lower().lstrip(".") for f in fmt.replace(";", ",").split(",") if f.strip()}
	ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
	if allowed and ext not in allowed:
		frappe.throw(_("Format « {0} » non autorisé. Formats acceptés : {1}.").format(ext or "?", ", ".join(sorted(allowed))))
	if size <= 0:
		frappe.throw(_("Le fichier est vide ou illisible."))
	if size > max_size_bytes(None):
		frappe.throw(_("Le fichier dépasse la taille maximale autorisée."))
	return name, size, mime, digest


def validate_document(doc):
	if doc.fichier and (doc.is_new() or doc.has_value_changed("fichier")):
		if not doc.is_new() and doc.statut in LOCKED and not doc.flags.reg_new_version:
			frappe.throw(_("Le fichier d'un document validé ne peut pas être écrasé : déposez une nouvelle version."))
		name, size, _mime, digest = check_document_file(doc.fichier, doc.type_document)
		doc.nom_fichier, doc.taille_octets, doc.empreinte = name, size, digest
		doc.extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
		doc.date_depot = doc.date_depot or today()
	if doc.type_document:
		t = frappe.get_cached_doc("Reg Document Type", doc.type_document)
		doc.categorie = doc.categorie or t.categorie
		doc.retention = doc.retention or t.retention
		if t.necessite_date_expiration and not doc.date_expiration and doc.statut not in ("Brouillon",):
			frappe.throw(_("Ce type de document exige une date d'expiration."))
	if doc.date_expiration and doc.date_entree_vigueur and getdate(doc.date_expiration) < getdate(doc.date_entree_vigueur):
		frappe.throw(_("La date d'expiration précède l'entrée en vigueur."))
	if doc.gel and not doc.motif_gel:
		frappe.throw(_("Le motif du gel est obligatoire."))
	compute_retention(doc)


def compute_retention(doc):
	if not doc.retention:
		return
	rule = frappe.get_cached_doc("Reg Retention Rule", doc.retention)
	doc.duree_conservation_annees = rule.duree_annees
	doc.point_depart_conservation = rule.point_depart
	start = None
	if rule.point_depart == "Création":
		start = doc.creation or today()
	elif rule.point_depart == "Validation":
		start = frappe.db.get_value("Reg Document Version", doc.version_courante, "date_validation") if doc.version_courante else None
	elif rule.point_depart == "Fin de l'obligation" and doc.obligation:
		start = frappe.db.get_value("Reg Obligation", doc.obligation, "date_fin")
	elif rule.point_depart == "Clôture de l'échéance" and doc.echeance:
		start = frappe.db.get_value("Reg Deadline", doc.echeance, "date_validation")
	elif rule.point_depart == "Clôture de la non-conformité" and doc.non_conformite:
		start = frappe.db.get_value("Reg Non Conformity", doc.non_conformite, "date_cloture")
	elif rule.point_depart == "Clôture du plan d'action" and doc.plan_action:
		start = frappe.db.get_value("Reg Action Plan", doc.plan_action, "date_cloture")
	if start:
		start = getdate(start)
		doc.date_archivage_prevue = add_years(start, cint(rule.duree_annees))
		doc.date_suppression_prevue = add_years(doc.date_archivage_prevue, cint(rule.duree_archivage_annees)) \
			if rule.duree_archivage_annees else None


def after_document_insert(doc):
	"""Le premier fichier devient la version 1."""
	if doc.fichier and not doc.version_courante:
		add_version(doc, doc.fichier, commentaire=_("Version initiale"), type_version="Majeure", initial=True)


def add_version(doc, file_url, commentaire=None, type_version="Mineure", initial=False):
	if isinstance(doc, str):
		doc = frappe.get_doc("Reg Document", doc)
	if doc.gel and not initial:
		frappe.throw(_("Document gelé ({0}) : aucune nouvelle version n'est possible.").format(doc.motif_gel))
	if doc.statut == "Supprimé logiquement":
		frappe.throw(_("Document supprimé."))
	name, size, mime, digest = check_document_file(file_url, doc.type_document)
	ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
	prev = doc.version_courante
	if prev:
		major, _sep, minor = (doc.numero_version or "1.0").partition(".")
		numero = f"{cint(major) + 1}.0" if type_version == "Majeure" else f"{cint(major)}.{cint(minor) + 1}"
	else:
		numero = "1.0"
	v = frappe.get_doc({"doctype": "Reg Document Version", "document": doc.name, "numero": numero, "type_version": type_version,
		"statut": "Soumise", "fichier": file_url, "version_precedente": prev, "auteur": doc.auteur,
		"deposant": frappe.session.user, "date_depot": today(), "nom_fichier": name,
		"type_mime": mime,
		"taille_octets": size, "empreinte": digest, "commentaire": commentaire})
	v.insert(ignore_permissions=True)
	upd = {"version_courante": v.name, "numero_version": numero, "fichier": file_url, "nom_fichier": name, "extension": ext,
		"taille_octets": size, "empreinte": digest, "date_depot": today()}
	if not initial:
		upd["statut"] = "Soumis"
	doc.db_set(upd)
	log_audit("Nouvelle version de document", doc, details={"version": numero, "empreinte": v.empreinte})
	return v.name


def validate_version(version, accepter=True, motif_rejet=None, commentaire=None):
	v = frappe.get_doc("Reg Document Version", version)
	doc = frappe.get_doc("Reg Document", v.document)
	if v.statut not in ("Soumise", "En contrôle"):
		frappe.throw(_("Cette version a déjà été traitée."))
	assert_sod(frappe.session.user, v.deposant, message=_("Séparation des tâches : le déposant ne peut pas valider sa propre version."))
	if accepter:
		for old in frappe.get_all("Reg Document Version", filters={"document": doc.name, "statut": "Validée", "name": ("!=", v.name)}, pluck="name"):
			frappe.db.set_value("Reg Document Version", old, "statut", "Remplacée")
		v.db_set({"statut": "Validée", "valide_par": frappe.session.user, "date_validation": today()})
		doc.reload()
		doc.statut = "Validé"
		doc.flags.reg_new_version = True
	else:
		if not motif_rejet:
			frappe.throw(_("Le motif de rejet est obligatoire."))
		v.db_set({"statut": "Rejetée", "motif_rejet": motif_rejet, "commentaire_rejet": commentaire})
		doc.reload()
		doc.statut = "Rejeté"
	doc.flags.ignore_permissions = True
	doc.save()


def publish(doc):
	if doc.statut != "Validé":
		frappe.throw(_("Seul un document validé peut être publié."))
	doc.statut = "Publié"
	doc.save(ignore_permissions=True)


def freeze(doc, motif, gel=True):
	require_text(motif, _("Le motif du gel"))
	doc.db_set({"gel": 1 if gel else 0, "motif_gel": motif if gel else None, "gel_par": frappe.session.user if gel else None,
		"date_gel": today() if gel else None})
	log_audit("Gel du document" if gel else "Levée du gel", doc, justification=motif)


def logical_delete(doc, motif):
	require_text(motif, _("Le motif de suppression"))
	if doc.gel:
		frappe.throw(_("Document gelé : suppression impossible."))
	if doc.date_suppression_prevue and getdate(doc.date_suppression_prevue) > getdate(today()) and doc.statut in LOCKED:
		frappe.throw(_("La durée de conservation court jusqu'au {0} : suppression impossible.").format(frappe.utils.formatdate(doc.date_suppression_prevue)))
	if doc.justificatif and frappe.db.get_value("Reg Evidence", doc.justificatif, "statut") in ("Validé", "Validé avec réserve"):
		frappe.throw(_("Document rattaché à un justificatif validé : suppression impossible."))
	doc.db_set({"statut": "Supprimé logiquement", "motif_suppression": motif, "supprime_par": frappe.session.user})
	for s in frappe.get_all("Reg Document Share", filters={"document": doc.name, "statut": "Actif"}, pluck="name"):
		frappe.db.set_value("Reg Document Share", s, "statut", "Révoqué")
	log_audit("Suppression logique", doc, justification=motif)


# ------------------------------------------------------------------ partage sécurisé
def create_share(document, destinataire, date_expiration, motif=None):
	doc = frappe.get_doc("Reg Document", document)
	if doc.statut not in ("Validé", "Publié"):
		frappe.throw(_("Seul un document validé ou publié peut être partagé."))
	if doc.confidentialite in ("Strictement confidentiel", "Sensible"):
		frappe.throw(_("Un document {0} ne peut pas être partagé par lien.").format(doc.confidentialite.lower()))
	if not date_expiration or getdate(date_expiration) <= getdate(today()):
		frappe.throw(_("La date d'expiration du partage doit être future."))
	token = secrets.token_urlsafe(32)
	s = frappe.get_doc({"doctype": "Reg Document Share", "document": doc.name, "destinataire": destinataire,
		"date_expiration": date_expiration, "statut": "Actif", "jeton": token, "motif": motif,
		"lien": get_url(f"/api/method/obligation_reglementaire.api.shared_document?token={token}")})
	s.insert(ignore_permissions=True)
	log_audit("Partage de document", doc, details={"destinataire": destinataire, "expiration": str(date_expiration)})
	return s


def resolve_share(token):
	if not token:
		raise frappe.PermissionError
	name = frappe.db.get_value("Reg Document Share", {"jeton": token}, "name")
	if not name:
		raise frappe.PermissionError
	s = frappe.get_doc("Reg Document Share", name)
	if s.statut != "Actif" or (s.date_expiration and getdate(s.date_expiration) < getdate(today())):
		if s.statut == "Actif":
			s.db_set("statut", "Expiré")
		frappe.throw(_("Ce lien de partage a expiré ou a été révoqué."), frappe.PermissionError)
	doc_statut = frappe.db.get_value("Reg Document", s.document, "statut")
	if doc_statut not in ("Validé", "Publié"):
		frappe.throw(_("Le document n'est plus disponible."), frappe.PermissionError)
	s.db_set({"nb_acces": cint(s.nb_acces) + 1, "dernier_acces": today()})
	return frappe.get_doc("Reg Document", s.document)


def revoke_share(share):
	frappe.db.set_value("Reg Document Share", share, "statut", "Révoqué")


# ------------------------------------------------------------------ tâches planifiées
def daily():
	t = today()
	with SystemAction():
		for s in frappe.get_all("Reg Document Share", filters={"statut": "Actif", "date_expiration": ("<", t)}, pluck="name"):
			frappe.db.set_value("Reg Document Share", s, "statut", "Expiré")
		for d in frappe.get_all("Reg Document", filters={"statut": ("in", ("Validé", "Publié")), "date_expiration": ("<", t)}, pluck="name"):
			doc = frappe.get_doc("Reg Document", d)
			doc.statut = "Expiré"
			doc.save(ignore_permissions=True)
		for d in frappe.get_all("Reg Document", filters={"statut": ("in", ("Validé", "Publié", "Expiré")),
				"date_archivage_prevue": ("<=", t), "gel": 0}, pluck="name"):
			frappe.db.set_value("Reg Document", d, {"statut": "Archivé", "date_archivage": t})
			log_audit("Archivage automatique", frappe.get_doc("Reg Document", d))
		from obligation_reglementaire.engine import notification
		for d in frappe.get_all("Reg Document", filters={"statut": "Archivé", "date_suppression_prevue": ("<=", t), "gel": 0},
				fields=["name"]):
			notification.emit("document_a_supprimer", frappe.get_doc("Reg Document", d.name))
