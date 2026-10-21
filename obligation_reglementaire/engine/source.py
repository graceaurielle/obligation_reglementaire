"""Référentiel des sources (Ch3) : doublons, qualité, dispositions, versions, comparaison et analyse d'impact."""

import difflib
import hashlib
import re
import unicodedata

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from obligation_reglementaire.engine.deadline import OPEN_STATUSES
from obligation_reglementaire.engine.common import SystemAction, log_audit, require_text

SOURCE_TRANSITIONS = {
	"Brouillon": {"En analyse", "Archivée"},
	"En analyse": {"Vérifiée", "Brouillon", "Archivée"},
	"Vérifiée": {"Validée", "En analyse"},
	"Validée": {"En vigueur", "Suspendue", "Abrogée", "Archivée"},
	"En vigueur": {"Modifiée", "Remplacée", "Suspendue", "Abrogée"},
	"Modifiée": {"En vigueur", "Remplacée", "Suspendue", "Abrogée"},
	"Suspendue": {"En vigueur", "Validée", "Abrogée"},
	"Remplacée": {"Archivée"},
	"Abrogée": {"Archivée"},
	"Archivée": set(),
}

VERSION_TRANSITIONS = {
	"Brouillon": {"Validée", "Archivée"},
	"Validée": {"En vigueur", "Archivée"},
	"En vigueur": {"Remplacée"},
	"Remplacée": {"Archivée"},
	"Archivée": set(),
}

ACTIVE_SOURCE = ("Validée", "En vigueur", "Modifiée", "Suspendue")


def normalize(text):
	text = unicodedata.normalize("NFKD", (text or "").lower())
	text = "".join(c for c in text if not unicodedata.combining(c))
	return re.sub(r"[^a-z0-9]+", " ", text).strip()


def content_hash(text):
	return hashlib.sha256(normalize(text).encode()).hexdigest() if text else None


# ------------------------------------------------------------------ doublons & qualité
def find_duplicates(src):
	"""Doublon potentiel : même référence officielle normalisée, ou titre très proche avec même autorité / type."""
	found = []
	ref = normalize(src.reference_officielle)
	for o in frappe.get_all("Reg Source", filters={"name": ("!=", src.name or ""), "statut": ("!=", "Archivée")},
			fields=["name", "reference_officielle", "titre_officiel", "autorite", "type_source", "date_publication"]):
		if ref and normalize(o.reference_officielle) == ref and (o.autorite == src.autorite or not src.autorite):
			found.append(f"{o.name} — {_('même référence officielle')}")
			continue
		if src.titre_officiel and o.titre_officiel and o.autorite == src.autorite:
			ratio = difflib.SequenceMatcher(None, normalize(src.titre_officiel), normalize(o.titre_officiel)).ratio()
			same_date = src.date_publication and o.date_publication and getdate(src.date_publication) == getdate(o.date_publication)
			if ratio >= 0.9 or (ratio >= 0.75 and same_date):
				found.append(f"{o.name} — {_('titre similaire à {0} %').format(int(ratio * 100))}")
	return found


def check_duplicates(src):
	dups = find_duplicates(src)
	src.doublon_potentiel = "\n".join(dups) if dups else None
	if dups and not src.forcer_doublon:
		frappe.throw(_("Doublon potentiel détecté :<br>{0}<br>Cochez « Forcer malgré doublon » et justifiez pour continuer.")
			.format("<br>".join(dups)), title=_("Doublon"))
	if dups and src.forcer_doublon:
		require_text(src.justification_doublon, _("La justification du forçage de doublon"))


def quality_score(src):
	"""Score de complétude / cohérence de la fiche source (Ch3 — qualité du référentiel)."""
	checks = [
		(src.reference_officielle, _("Référence officielle manquante")),
		(src.titre_officiel, _("Titre officiel manquant")),
		(src.type_source, _("Type de source manquant")),
		(src.autorite, _("Autorité émettrice manquante")),
		(src.date_publication, _("Date de publication manquante")),
		(src.date_entree_vigueur, _("Date d'entrée en vigueur manquante")),
		(src.domaines, _("Aucun domaine")),
		(src.responsable_interne, _("Responsable interne manquant")),
		(src.resume, _("Résumé manquant")),
		(src.lien_officiel or src.documents, _("Ni lien officiel ni document officiel")),
	]
	anomalies = [msg for ok, msg in checks if not ok]
	if src.date_publication and src.date_entree_vigueur and getdate(src.date_entree_vigueur) < getdate(src.date_publication):
		anomalies.append(_("Entrée en vigueur antérieure à la publication"))
	if src.date_fin_application and src.date_debut_application and getdate(src.date_fin_application) < getdate(src.date_debut_application):
		anomalies.append(_("Fin d'application antérieure au début"))
	if src.statut == "Abrogée" and not src.date_abrogation:
		anomalies.append(_("Source abrogée sans date d'abrogation"))
	if src.name and not frappe.db.exists("Reg Provision", {"source": src.name}):
		anomalies.append(_("Aucune disposition structurée"))
	src.score_qualite = round(100 * (len(checks) + 3 - len(anomalies)) / (len(checks) + 3), 1) if anomalies else 100
	src.anomalies_qualite = "\n".join(anomalies) or None
	return src.score_qualite


def validate_source(src):
	if src.statut in ("Validée", "En vigueur") and not src.reference_officielle:
		frappe.throw(_("La référence officielle est obligatoire pour valider une source."))
	if src.statut == "Abrogée" and not src.date_abrogation:
		frappe.throw(_("La date d'abrogation est obligatoire."))
	for r in src.relations or []:
		if r.source_liee == src.name:
			frappe.throw(_("Une source ne peut pas être liée à elle-même."))
		if r.source_liee and not r.titre_source_liee:
			r.titre_source_liee = frappe.db.get_value("Reg Source", r.source_liee, "titre_court") or \
				frappe.db.get_value("Reg Source", r.source_liee, "titre_officiel")
	for d in src.documents or []:
		if d.fichier and not d.empreinte_sha256:
			try:
				f = frappe.get_doc("File", {"file_url": d.fichier})
				content = f.get_content()
				content = content.encode() if isinstance(content, str) else content
				d.empreinte_sha256 = hashlib.sha256(content).hexdigest()
				d.taille_octets = len(content)
				d.format = (f.file_name or "").rsplit(".", 1)[-1].upper()
			except Exception:
				pass
	for s in src.suspensions or []:
		if s.date_fin and s.date_debut and getdate(s.date_fin) < getdate(s.date_debut):
			frappe.throw(_("Suspension : la date de fin précède la date de début."))
	# statut automatique de suspension
	t = getdate(today())
	active_susp = [s for s in src.suspensions or [] if getdate(s.date_debut) <= t and (not s.date_fin or getdate(s.date_fin) >= t)]
	if active_susp and src.statut in ("En vigueur", "Modifiée", "Validée"):
		src.statut = "Suspendue"
	if src.date_entree_vigueur:
		src.non_encore_applicable = 1 if getdate(src.date_entree_vigueur) > t else 0
	check_duplicates(src)
	quality_score(src)


def inverse_relations_html(src):
	rows = frappe.get_all("Reg Source Relation", filters={"source_liee": src.name, "parenttype": "Reg Source"},
		fields=["parent", "type_relation", "date_effet"])
	if not rows:
		return f"<p class='text-muted'>{_('Aucune relation inverse.')}</p>"
	out = ["<ul>"]
	for r in rows:
		inv = frappe.db.get_value("Reg Relation Type", r.type_relation, "libelle_inverse") or r.type_relation
		out.append(f"<li>{frappe.utils.escape_html(inv)} : <a href='/app/reg-source/{r.parent}'>{r.parent}</a>"
			f" {frappe.utils.formatdate(r.date_effet) if r.date_effet else ''}</li>")
	out.append("</ul>")
	return "".join(out)


def on_source_status_change(src, old):
	"""Abrogation / remplacement / suspension → obligations liées marquées à revoir."""
	if src.statut in ("Abrogée", "Remplacée", "Suspendue", "Modifiée") and old != src.statut:
		mark_obligations(src.name, _("Source {0} passée au statut {1}").format(src.name, src.statut))


def mark_obligations(source, motif):
	obls = set(frappe.get_all("Reg Obligation", filters={"source": source, "statut": ("not in", ("Archivée", "Obsolète", "Clôturée"))}, pluck="name"))
	obls |= set(frappe.get_all("Reg Obligation Provision", filters={"source": source, "parenttype": "Reg Obligation"}, pluck="parent"))
	from obligation_reglementaire.engine import notification
	with SystemAction():
		for name in obls:
			obl = frappe.get_doc("Reg Obligation", name)
			if obl.statut in ("Archivée", "Obsolète", "Clôturée"):
				continue
			frappe.db.set_value("Reg Obligation", name, {"a_revoir": 1, "motif_revue": motif})
			notification.emit("obligation_a_revoir", obl, extra={"motif": motif})
	return len(obls)


# ------------------------------------------------------------------ dispositions
def validate_provision(p):
	parent_title = frappe.db.get_value("Reg Provision", p.parent_reg_provision, "titre_complet") if p.parent_reg_provision else None
	label = " ".join(x for x in (p.type_disposition, p.numero or p.reference) if x)
	if p.titre:
		label = f"{label} — {p.titre}" if label else p.titre
	p.titre_complet = (f"{parent_title} > {label}" if parent_title else label)[:140]
	if not p.reference:
		p.reference = p.numero or p.titre
	p.empreinte_contenu = content_hash(p.contenu)
	if p.parent_reg_provision:
		ps = frappe.db.get_value("Reg Provision", p.parent_reg_provision, "source")
		if ps and p.source and ps != p.source:
			frappe.throw(_("La disposition parente appartient à une autre source."))
	if p.date_fin_validite and p.date_debut_validite and getdate(p.date_fin_validite) < getdate(p.date_debut_validite):
		frappe.throw(_("La fin de validité précède le début."))
	if p.statut in ("Abrogée", "Supprimée") and p.name:
		old = frappe.db.get_value("Reg Provision", p.name, "statut")
		if old != p.statut:
			p.flags.reg_mark_obligations = True


def after_provision_save(p):
	if p.flags.reg_mark_obligations:
		obls = frappe.get_all("Reg Obligation Provision", filters={"disposition": p.name, "parenttype": "Reg Obligation"}, pluck="parent")
		obls += frappe.get_all("Reg Obligation", filters={"disposition_principale": p.name}, pluck="name")
		from obligation_reglementaire.engine import notification
		with SystemAction():
			for name in set(obls):
				frappe.db.set_value("Reg Obligation", name, {"a_revoir": 1,
					"motif_revue": _("Disposition {0} {1}").format(p.reference or p.name, p.statut.lower())})
				notification.emit("obligation_a_revoir", frappe.get_doc("Reg Obligation", name))


# ------------------------------------------------------------------ versions
def validate_version(v):
	if v.version_precedente == v.name:
		frappe.throw(_("Une version ne peut pas se précéder elle-même."))
	if v.version_precedente and frappe.db.get_value("Reg Source Version", v.version_precedente, "source") != v.source:
		frappe.throw(_("La version précédente doit appartenir à la même source."))
	if v.date_fin_validite and v.date_entree_vigueur and getdate(v.date_fin_validite) < getdate(v.date_entree_vigueur):
		frappe.throw(_("La fin de validité précède l'entrée en vigueur."))
	if v.statut == "En vigueur" and not v.chevauchement_autorise:
		other = frappe.db.get_value("Reg Source Version", {"source": v.source, "statut": "En vigueur", "name": ("!=", v.name or "")}, "name")
		if other and other != v.version_precedente:
			frappe.throw(_("La version {0} est déjà en vigueur ; cochez « Chevauchement autorisé » ou remplacez-la.").format(other))


def activate_version(v):
	"""Mise en vigueur : la précédente est remplacée, la source pointe vers la nouvelle version, une analyse d'impact est ouverte."""
	with SystemAction():
		if v.version_precedente:
			prev = frappe.get_doc("Reg Source Version", v.version_precedente)
			if prev.statut == "En vigueur":
				prev.statut = "Remplacée"
				prev.date_fin_validite = prev.date_fin_validite or add_days(v.date_entree_vigueur or today(), -1)
				prev.flags.ignore_permissions = True
				prev.save()
		src = frappe.get_doc("Reg Source", v.source)
		src.version_courante = v.name
		if src.statut == "En vigueur" and v.version_precedente:
			src.statut = "Modifiée"
		elif src.statut == "Validée":
			src.statut = "En vigueur"
		src.flags.ignore_permissions = True
		src.save()
		if v.version_precedente and not v.analyse_impact:
			v.db_set("analyse_impact", create_impact_analysis(v))


def compare_versions(version_a, version_b):
	"""Comparaison disposition par disposition, appariées par référence."""
	a = {p.reference or p.name: p for p in frappe.get_all("Reg Provision", filters={"version": version_a},
		fields=["name", "reference", "titre", "contenu", "empreinte_contenu"])}
	b = {p.reference or p.name: p for p in frappe.get_all("Reg Provision", filters={"version": version_b},
		fields=["name", "reference", "titre", "contenu", "empreinte_contenu"])}
	source = frappe.db.get_value("Reg Source Version", version_b, "source")
	cmp = frappe.get_doc({"doctype": "Reg Version Comparison", "source": source, "version_a": version_a,
		"version_b": version_b, "date_comparaison": today()})
	counts = {"Ajoutée": 0, "Supprimée": 0, "Modifiée": 0, "Inchangée": 0}
	for ref in sorted(set(a) | set(b), key=lambda r: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", str(r))]):
		pa, pb = a.get(ref), b.get(ref)
		if pa and not pb:
			res, resume = "Supprimée", (pa.titre or "")
		elif pb and not pa:
			res, resume = "Ajoutée", (pb.titre or "")
		else:
			ha = pa.empreinte_contenu or content_hash(pa.contenu)
			hb = pb.empreinte_contenu or content_hash(pb.contenu)
			if ha == hb and normalize(pa.titre) == normalize(pb.titre):
				res, resume = "Inchangée", ""
			else:
				res = "Modifiée"
				diff = difflib.unified_diff((pa.contenu or "").splitlines(), (pb.contenu or "").splitlines(), lineterm="", n=0)
				resume = "\n".join(l for l in list(diff)[2:12])
		counts[res] += 1
		cmp.append("lignes", {"reference": ref, "resultat": res, "disposition_a": pa and pa.name,
			"disposition_b": pb and pb.name, "resume": resume[:1000]})
	cmp.nb_ajoutees, cmp.nb_supprimees = counts["Ajoutée"], counts["Supprimée"]
	cmp.nb_modifiees, cmp.nb_inchangees = counts["Modifiée"], counts["Inchangée"]
	cmp.insert(ignore_permissions=True)
	return cmp.name


def create_impact_analysis(v, organisation=None):
	"""Analyse d'impact : liste des obligations rattachées à la source (ou aux dispositions modifiées), à décider."""
	cmp_name = compare_versions(v.version_precedente, v.name) if v.version_precedente else None
	changed_refs = set()
	if cmp_name:
		changed_refs = {l.reference for l in frappe.get_doc("Reg Version Comparison", cmp_name).lignes if l.resultat != "Inchangée"}
	orgs = [organisation] if organisation else (frappe.get_all("Reg Obligation", filters={"source": v.source}, distinct=True,
		pluck="organisation") or [frappe.db.get_single_value("Reg Settings", "organisation_defaut")])
	first = None
	settings = frappe.get_cached_doc("Reg Settings")
	for org in {o for o in orgs if o}:
		ia = frappe.get_doc({"doctype": "Reg Impact Analysis", "source": v.source, "nouvelle_version": v.name,
			"version_precedente": v.version_precedente, "organisation": org, "statut": "À analyser",
			"analyste": frappe.db.get_value("Reg Source", v.source, "responsable_interne"),
			"date_effet": v.date_entree_vigueur, "date_limite_revue": add_days(today(), settings.get("jours_controle_defaut") or 15),
			"nature_evolution": ", ".join(n.nature for n in v.natures or []) or v.resume_modifications})
		obls = frappe.get_all("Reg Obligation", filters={"source": v.source, "organisation": org,
			"statut": ("not in", ("Archivée", "Obsolète", "Clôturée"))},
			fields=["name", "titre", "disposition_principale", "proprietaire"])
		for o in obls:
			disp_ref = frappe.db.get_value("Reg Provision", o.disposition_principale, "reference") if o.disposition_principale else None
			if changed_refs and disp_ref and disp_ref not in changed_refs:
				continue
			ia.append("lignes", {"obligation": o.name, "titre_obligation": o.titre, "disposition": o.disposition_principale,
				"responsable": o.proprietaire, "decision": "À décider",
				"nb_echeances_ouvertes": frappe.db.count("Reg Deadline", {"obligation": o.name,
					"statut": ("in", OPEN_STATUSES)})})
		ia.insert(ignore_permissions=True)
		first = first or ia.name
		for l in ia.lignes:
			frappe.db.set_value("Reg Obligation", l.obligation, {"a_revoir": 1,
				"motif_revue": _("Nouvelle version {0} de la source — analyse {1}").format(v.numero_version, ia.name)})
		from obligation_reglementaire.engine import notification
		notification.emit("analyse_impact_creee", ia)
	return first


def validate_impact(ia):
	if ia.statut in ("Terminée", "Validée"):
		pending = [l.obligation for l in ia.lignes if l.decision == "À décider"]
		if pending:
			frappe.throw(_("Décision manquante pour : {0}").format(", ".join(pending)))
	if ia.statut == "Validée" and not ia.valide_par:
		ia.valide_par = frappe.session.user
		ia.date_validation = today()


def apply_impact(ia):
	"""Applique les décisions validées : obsolescence, plan d'action, levée du marquage « à revoir »."""

	with SystemAction():
		for l in ia.lignes:
			if l.traitee:
				continue
			obl = frappe.get_doc("Reg Obligation", l.obligation)
			if l.decision == "Rendre obsolète":
				obl.statut = "Obsolète"
				obl.flags.reg_justification = l.commentaire or _("Analyse d'impact {0}").format(ia.name)
				frappe.flags.reg_force_transition = True
				try:
					obl.save(ignore_permissions=True)
				finally:
					frappe.flags.reg_force_transition = False
			elif l.decision == "Créer un plan d'action" and not l.plan_action:
				pa = frappe.get_doc({"doctype": "Reg Action Plan", "organisation": obl.organisation,
					"intitule": _("Mise en conformité — {0}").format(obl.titre)[:140], "origine": "Recommandation réglementaire",
					"type_plan": "Réglementaire", "criticite": obl.criticite, "obligation": obl.name, "source": ia.source,
					"responsable": l.responsable or obl.proprietaire, "date_cible": ia.date_effet or add_days(today(), 60),
					"date_cible_initiale": ia.date_effet or add_days(today(), 60), "statut": "Brouillon",
					"description": l.commentaire, "cree_automatiquement": 1})
				pa.insert(ignore_permissions=True, ignore_mandatory=True)
				l.plan_action = pa.name
			if l.decision in ("Aucune action", "Rendre obsolète", "Créer un plan d'action"):
				frappe.db.set_value("Reg Obligation", obl.name, {"a_revoir": 0, "motif_revue": None})
			if l.decision not in ("À décider",):
				l.traitee = 1 if l.decision in ("Aucune action", "Rendre obsolète", "Créer un plan d'action") else l.traitee
		log_audit("Application de l'analyse d'impact", ia)
