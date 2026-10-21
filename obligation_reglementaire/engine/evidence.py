"""Moteur des justificatifs (Ch7) : justificatifs attendus, dépôt versionné, empreinte, doublons,
contrôle, rejet → non-conformité, expiration → renouvellement."""

import hashlib
import mimetypes
import os

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime

from obligation_reglementaire.engine.common import SystemAction, assert_sod, get_settings, log_audit, today_date
from obligation_reglementaire.engine.deadline import refresh_doc_state

EVIDENCE_TRANSITIONS = {
	"Attendu": {"Demandé", "À fournir", "Déposé", "Annulé"},
	"Demandé": {"À fournir", "Déposé", "Annulé"},
	"À fournir": {"Déposé", "Annulé"},
	"Déposé": {"En cours de contrôle", "Validé", "Validé avec réserve", "À compléter", "Rejeté", "Déposé", "Annulé", "Remplacé"},
	"En cours de contrôle": {"Validé", "Validé avec réserve", "À compléter", "Rejeté", "Déposé"},
	"À compléter": {"Soumis à nouveau", "Annulé"},
	"Rejeté": {"Soumis à nouveau", "Annulé"},
	"Soumis à nouveau": {"En cours de contrôle", "Validé", "Validé avec réserve", "À compléter", "Rejeté", "Soumis à nouveau"},
	"Validé": {"Expiré", "Remplacé", "Archivé"},
	"Validé avec réserve": {"Validé", "Expiré", "Remplacé", "Archivé"},
	"Expiré": {"Remplacé", "Archivé"},
	"Remplacé": {"Archivé"},
	"Archivé": set(),
	"Annulé": set(),
}

LOCKED = ("Validé", "Validé avec réserve", "Expiré", "Remplacé", "Archivé", "Annulé")


def create_expected(deadline):
	"""Crée un justificatif « Attendu » par justificatif requis de l'obligation (Ch7)."""
	if isinstance(deadline, str):
		deadline = frappe.get_doc("Reg Deadline", deadline)
	obl = frappe.get_cached_doc("Reg Obligation", deadline.obligation)
	if not cint(obl.justificatif_requis):
		return []
	created = []
	with SystemAction():
		for row in obl.justificatifs:
			if not cint(row.actif):
				continue
			if frappe.db.exists("Reg Evidence", {"echeance": deadline.name, "type_justificatif": row.type_justificatif,
					"libelle": row.libelle}):
				continue
			ev = frappe.get_doc({
				"doctype": "Reg Evidence",
				"organisation": deadline.organisation,
				"obligation": obl.name,
				"echeance": deadline.name,
				"type_justificatif": row.type_justificatif,
				"libelle": row.libelle,
				"description": row.description,
				"nature": row.nature or "Principal",
				"obligatoire": row.obligatoire,
				"statut": "Attendu",
				"responsable": row.responsable_depot or deadline.responsable,
				"controleur": deadline.controleur or obl.controleur,
				"periode_du": deadline.debut_periode if cint(row.periode_couverte_requise) else None,
				"periode_au": deadline.fin_periode if cint(row.periode_couverte_requise) else None,
				"generee_automatiquement": 1,
				"date_demande": now_datetime(),
			})
			_copy_type_metadata(ev)
			ev.insert(ignore_permissions=True, ignore_mandatory=True)
			created.append(ev.name)
	if created:
		refresh_doc_state(deadline.name)
	return created


def _copy_type_metadata(ev):
	if not ev.type_justificatif or ev.metadonnees:
		return
	t = frappe.get_cached_doc("Reg Evidence Type", ev.type_justificatif)
	for m in t.metadonnees:
		ev.append("metadonnees", {"cle": m.cle, "libelle": m.libelle, "obligatoire": m.obligatoire})


def allowed_formats(type_justificatif):
	fmt = frappe.db.get_value("Reg Evidence Type", type_justificatif, "formats_autorises") if type_justificatif else None
	fmt = fmt or get_settings().formats_autorises or ""
	return {f.strip().lower().lstrip(".") for f in fmt.replace(";", ",").split(",") if f.strip()}


def max_size_bytes(type_justificatif):
	mo = flt(frappe.db.get_value("Reg Evidence Type", type_justificatif, "taille_max_mo")) if type_justificatif else 0
	mo = mo or flt(get_settings().taille_max_mo) or 50
	return int(mo * 1024 * 1024)


def file_fingerprint(file_url):
	"""Retourne (nom, taille, mime, sha256) d'un fichier déjà téléversé."""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode()
	name = file_doc.file_name or os.path.basename(file_url)
	mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
	return name, len(content or b""), mime, hashlib.sha256(content or b"").hexdigest()


def check_file(file_url, type_justificatif):
	name, size, mime, digest = file_fingerprint(file_url)
	ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
	allowed = allowed_formats(type_justificatif)
	if allowed and ext not in allowed:
		frappe.throw(_("Format « {0} » non autorisé. Formats acceptés : {1}.").format(ext or "?", ", ".join(sorted(allowed))))
	if size <= 0:
		frappe.throw(_("Le fichier est vide ou illisible."))
	limit = max_size_bytes(type_justificatif)
	if size > limit:
		frappe.throw(_("Le fichier dépasse la taille maximale autorisée ({0} Mo).").format(round(limit / 1048576, 1)))
	return name, size, mime, digest


def find_duplicates(digest, organisation, exclude_evidence=None):
	rows = frappe.db.sql("""
		select v.name, v.justificatif, e.libelle, e.echeance from `tabReg Evidence Version` v
		join `tabReg Evidence` e on e.name = v.justificatif
		where v.empreinte = %s and e.organisation = %s and v.justificatif != %s
	""", (digest, organisation, exclude_evidence or ""), as_dict=True)
	return rows


def deposit_version(evidence, file_url, commentaire=None, confirmer_doublon=0, motif_remplacement=None):
	"""Dépôt d'une nouvelle version (Ch7) : contrôle format/taille, empreinte, doublon, dépôt tardif."""
	ev = frappe.get_doc("Reg Evidence", evidence) if isinstance(evidence, str) else evidence
	if ev.statut in ("Validé", "Validé avec réserve"):
		frappe.throw(_("Le justificatif est validé : utilisez « Remplacer » pour déposer une nouvelle version (l'ancienne reste conservée)."))
	if ev.statut in ("Archivé", "Annulé", "Remplacé", "Expiré"):
		frappe.throw(_("Aucun dépôt possible sur un justificatif {0}.").format(ev.statut.lower()))
	name, size, mime, digest = check_file(file_url, ev.type_justificatif)
	dups = find_duplicates(digest, ev.organisation, ev.name)
	if dups and not cint(confirmer_doublon):
		return {"doublon": dups}
	# même fichier que la version courante
	if ev.version_courante and frappe.db.get_value("Reg Evidence Version", ev.version_courante, "empreinte") == digest:
		frappe.throw(_("Ce fichier est identique à la version courante."))
	late = False
	if ev.echeance:
		dl = frappe.db.get_value("Reg Deadline", ev.echeance, ["date_limite", "statut"], as_dict=True)
		late = bool(dl and getdate(dl.date_limite) < today_date())
	numero = cint(frappe.db.count("Reg Evidence Version", {"justificatif": ev.name})) + 1
	ver = frappe.get_doc({
		"doctype": "Reg Evidence Version",
		"justificatif": ev.name,
		"numero": numero,
		"statut": "Déposée",
		"fichier": file_url,
		"auteur": frappe.session.user,
		"date_depot": now_datetime(),
		"deposee_apres_echeance": 1 if late else 0,
		"nom_original": name,
		"taille_octets": size,
		"type_mime": mime,
		"algorithme": "SHA-256",
		"empreinte": digest,
		"date_calcul_empreinte": now_datetime(),
		"commentaire": commentaire,
		"motif_remplacement": motif_remplacement,
		"doublon_detecte": ", ".join(f"{d.justificatif} ({d.name})" for d in dups) if dups else None,
		"doublon_confirme": 1 if dups else 0,
	})
	ver.insert(ignore_permissions=True)
	# les versions non validées précédentes sont remplacées
	for prev in frappe.get_all("Reg Evidence Version", filters={"justificatif": ev.name, "name": ("!=", ver.name),
			"statut": ("in", ("Déposée", "En contrôle", "À compléter", "Rejetée"))}, pluck="name"):
		frappe.db.set_value("Reg Evidence Version", prev, "statut", "Remplacée")
	resub = ev.statut in ("Rejeté", "À compléter", "Soumis à nouveau")
	ev.statut = "Soumis à nouveau" if resub else "Déposé"
	ev.version_courante = ver.name
	ev.numero_version_courante = numero
	ev.deposant = frappe.session.user
	ev.date_depot = now_datetime()
	ev.depose_apres_echeance = 1 if late else 0
	ev.flags.ignore_permissions = True
	ev.save()
	if dups:
		log_audit("Dépôt malgré doublon", ev, details={"doublons": dups})
	refresh_doc_state(ev.echeance)
	_on_deposit_deadline(ev)
	from obligation_reglementaire.engine import notification
	notification.emit("justificatif_depose", ev)
	if cint(frappe.db.get_value("Reg Evidence Type", ev.type_justificatif, "doit_etre_valide") if ev.type_justificatif else 1):
		notification.emit("justificatif_soumis_controle", ev)
	return {"version": ver.name, "numero": numero, "empreinte": digest, "en_retard": late}


def _on_deposit_deadline(ev):
	"""Le premier dépôt fait passer l'échéance « À venir / À traiter » à « En cours »."""
	if not ev.echeance:
		return
	dl = frappe.get_doc("Reg Deadline", ev.echeance)
	if dl.statut in ("À venir", "À traiter", "Reportée"):
		dl.statut = "En cours"
		dl.flags.ignore_permissions = True
		dl.save()


def replace_evidence(evidence, motif):
	"""Remplacement d'un justificatif validé : nouveau justificatif, l'ancien reste conservé (Ch7)."""
	old = frappe.get_doc("Reg Evidence", evidence)
	if old.statut not in ("Validé", "Validé avec réserve", "Expiré"):
		frappe.throw(_("Seul un justificatif validé ou expiré peut être remplacé."))
	new = frappe.copy_doc(old)
	new.update({"statut": "À fournir", "version_courante": None, "numero_version_courante": 0, "remplace": old.name,
		"date_depot": None, "deposant": None, "date_validation": None, "validateur": None, "dernier_controle": None,
		"motif_rejet": None, "reserve": None, "date_demande": now_datetime(), "generee_automatiquement": 0})
	new.insert(ignore_permissions=True, ignore_mandatory=True)
	old.statut = "Remplacé"
	old.date_remplacement = now_datetime()
	old.flags.reg_justification = motif
	old.flags.ignore_permissions = True
	old.save()
	from obligation_reglementaire.engine import notification
	notification.emit("justificatif_remplace", old)
	return new.name


def start_review(evidence):
	ev = frappe.get_doc("Reg Evidence", evidence)
	if ev.statut not in ("Déposé", "Soumis à nouveau"):
		frappe.throw(_("Seul un justificatif déposé peut être pris en charge pour contrôle."))
	if not ev.version_courante:
		frappe.throw(_("Aucune version déposée."))
	assert_sod(frappe.session.user, frappe.db.get_value("Reg Evidence Version", ev.version_courante, "auteur"),
		message=_("Séparation des tâches : le déposant ne peut pas contrôler son propre justificatif."))
	existing = frappe.db.get_value("Reg Evidence Review", {"version": ev.version_courante, "docstatus": 0}, "name")
	if existing:
		return existing
	settings = get_settings()
	review = frappe.get_doc({
		"doctype": "Reg Evidence Review",
		"justificatif": ev.name,
		"version": ev.version_courante,
		"controleur": frappe.session.user,
		"date_prise_en_charge": now_datetime(),
		"date_limite_controle": ev.date_limite_controle or add_days(today_date(), cint(settings.jours_controle_defaut or 5)),
	})
	checklist = frappe.db.get_value("Reg Evidence Type", ev.type_justificatif, "checklist")
	if checklist:
		for item in frappe.get_doc("Reg Checklist", checklist).criteres:
			review.append("items", {"critere": item.critere, "type_controle": item.type_controle, "obligatoire": item.obligatoire})
	review.insert(ignore_permissions=True)
	frappe.db.set_value("Reg Evidence Version", ev.version_courante, "statut", "En contrôle")
	ev.statut = "En cours de contrôle"
	ev.date_prise_en_charge = now_datetime()
	ev.flags.ignore_permissions = True
	ev.save()
	refresh_doc_state(ev.echeance)
	return review.name


def validate_review(review):
	ev = frappe.get_cached_doc("Reg Evidence", review.justificatif)
	if review.version != ev.version_courante:
		frappe.throw(_("Le contrôle doit porter sur la version courante du justificatif ({0}).").format(ev.version_courante))
	author = frappe.db.get_value("Reg Evidence Version", review.version, "auteur")
	assert_sod(review.controleur, author, message=_("Séparation des tâches : le contrôleur ne peut pas être le déposant."))
	if review.resultat in ("Validé", "Validé avec réserve"):
		missing = [i.critere for i in review.items if cint(i.obligatoire) and not i.resultat]
		if missing:
			frappe.throw(_("Points de contrôle obligatoires non renseignés : {0}").format(", ".join(missing)))
		ko = [i.critere for i in review.items if cint(i.obligatoire) and i.resultat == "Non conforme"]
		if ko and review.resultat == "Validé":
			frappe.throw(_("Validation impossible : critères obligatoires non conformes ({0}).").format(", ".join(ko)))
		_check_required_metadata(ev)
	if review.resultat == "Rejeté" and not review.motifs:
		frappe.throw(_("Un rejet doit comporter au moins un motif structuré."))
	if review.resultat == "Validé avec réserve" and not review.reserve_statut:
		review.reserve_statut = "Ouverte"


def _check_required_metadata(ev):
	t = frappe.get_cached_doc("Reg Evidence Type", ev.type_justificatif)
	missing = []
	if cint(t.necessite_date_emission) and not ev.date_emission:
		missing.append(_("date d'émission"))
	if cint(t.necessite_date_expiration) and not ev.date_fin_validite and not cint(t.duree_validite_jours):
		missing.append(_("date de fin de validité"))
	if cint(t.necessite_reference_externe) and not ev.reference_externe:
		missing.append(_("référence externe"))
	if cint(t.necessite_signature) and not cint(ev.signe):
		missing.append(_("signature"))
	if cint(t.necessite_periode) and not (ev.periode_du and ev.periode_au):
		missing.append(_("période couverte"))
	missing += [m.libelle or m.cle for m in ev.metadonnees if cint(m.obligatoire) and not m.valeur]
	if missing:
		frappe.throw(_("Métadonnées obligatoires manquantes sur le justificatif : {0}").format(", ".join(missing)))


def apply_review(review):
	"""on_submit du contrôle : la décision est appliquée au justificatif, à la version et à l'échéance."""
	from obligation_reglementaire.engine import notification
	from obligation_reglementaire.engine.action_plan import create_nc

	ev = frappe.get_doc("Reg Evidence", review.justificatif)
	vstatus = {"Validé": "Validée", "Validé avec réserve": "Validée avec réserve", "À compléter": "À compléter",
		"Rejeté": "Rejetée"}[review.resultat]
	vals = {"statut": vstatus}
	if review.resultat in ("Validé", "Validé avec réserve"):
		vals["verrouillee"] = 1
	else:
		vals["motif_rejet"] = ", ".join(m.libelle or m.motif for m in review.motifs) or review.complements_attendus
	frappe.db.set_value("Reg Evidence Version", review.version, vals)
	frappe.db.set_value("Reg Evidence Review", review.name, "date_decision", now_datetime())
	ev.dernier_controle = review.name
	ev.statut = review.resultat
	if review.resultat in ("Validé", "Validé avec réserve"):
		ev.validateur = review.controleur
		ev.date_validation = now_datetime()
		ev.reserve = review.reserve_nature if review.resultat == "Validé avec réserve" else None
		t = frappe.get_cached_doc("Reg Evidence Type", ev.type_justificatif)
		if cint(t.duree_validite_jours) and not ev.date_fin_validite:
			ev.date_debut_validite = ev.date_debut_validite or ev.date_emission or today_date()
			ev.date_fin_validite = add_days(ev.date_debut_validite, cint(t.duree_validite_jours))
	else:
		ev.motif_rejet = "; ".join(filter(None, [", ".join(m.libelle or m.motif for m in review.motifs),
			review.corrections_attendues, review.complements_attendus]))
		ev.date_limite_resoumission = review.date_limite_resoumission or add_days(today_date(),
			cint(get_settings().jours_resoumission_defaut or 10))
	ev.flags.ignore_permissions = True
	ev.save()
	refresh_doc_state(ev.echeance)
	event = {"Validé": "justificatif_valide", "Validé avec réserve": "justificatif_valide",
		"À compléter": "justificatif_a_completer", "Rejeté": "justificatif_rejete"}[review.resultat]
	notification.emit(event, ev)
	if review.resultat == "Rejeté" and cint(get_settings().nc_auto_sur_rejet):
		obl = frappe.db.get_value("Reg Obligation", ev.obligation, ["criticite", "proprietaire", "responsable_operationnel"], as_dict=True)
		nc = create_nc(origine="Justificatif rejeté", intitule=_("Justificatif rejeté : {0}").format(ev.libelle),
			description=_("Le justificatif {0} (version {1}) a été rejeté. Motifs : {2}. Corrections attendues : {3}").format(
				ev.name, ev.numero_version_courante, ev.motif_rejet, review.corrections_attendues or "-"),
			obligation=ev.obligation, echeance=ev.echeance, justificatif=ev.name, organisation=ev.organisation,
			responsable=ev.responsable or obl.responsable_operationnel or obl.proprietaire, gravite=obl.criticite, event=review)
		frappe.db.set_value("Reg Evidence Review", review.name, "non_conformite", nc.name)
	return ev


def expire_evidences():
	"""Expiration quotidienne : le justificatif expiré est conservé, une nouvelle demande est créée (Ch7)."""
	from obligation_reglementaire.engine import notification

	t = today_date()
	with SystemAction():
		for name in frappe.get_all("Reg Evidence", filters={"statut": ("in", ("Validé", "Validé avec réserve")),
				"date_fin_validite": ("<", t)}, pluck="name"):
			ev = frappe.get_doc("Reg Evidence", name)
			ev.statut = "Expiré"
			ev.flags.ignore_permissions = True
			ev.save()
			refresh_doc_state(ev.echeance)
			new = frappe.copy_doc(ev)
			new.update({"statut": "Demandé", "version_courante": None, "numero_version_courante": 0, "remplace": ev.name,
				"date_depot": None, "deposant": None, "date_validation": None, "validateur": None, "dernier_controle": None,
				"date_debut_validite": None, "date_fin_validite": None, "date_demande": now_datetime(),
				"generee_automatiquement": 1, "motif_rejet": None, "reserve": None})
			new.insert(ignore_permissions=True, ignore_mandatory=True)
			notification.emit("justificatif_expire", ev)


def late_review_alerts():
	"""Contrôles non réalisés dans le délai — alimente les alertes de retard de validation."""
	return frappe.get_all("Reg Evidence", filters={"statut": "En cours de contrôle", "date_limite_controle": ("<", today_date())},
		pluck="name")
