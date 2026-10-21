"""Reporting (Ch10) : jeux de données par section, gel des données, rendu HTML/PDF/Excel/CSV, circuit
préparation → contrôle → validation → diffusion → transmission, versions et rejets."""

import csv
import io
import json

import frappe
from frappe import _
from frappe.utils import cint, escape_html, formatdate, getdate, now_datetime

from obligation_reglementaire.engine import indicators
from obligation_reglementaire.engine.common import assert_sod, log_audit, require_text

REPORT_TRANSITIONS = {
	"Brouillon": {"En préparation", "Échec de génération", "Archivé"},
	"En préparation": {"À contrôler", "À valider", "Validé", "Échec de génération", "Archivé", "Brouillon"},
	"Échec de génération": {"En préparation", "Brouillon"},
	"À contrôler": {"Contrôlé", "Rejeté"},
	"Contrôlé": {"À valider", "Rejeté"},
	"À valider": {"Validé", "Rejeté"},
	"Rejeté": {"À corriger", "En préparation"},
	"À corriger": {"En préparation", "À contrôler"},
	"Validé": {"Diffusé", "Prêt à transmettre", "Clôturé", "Archivé"},
	"Diffusé": {"Prêt à transmettre", "Clôturé", "Archivé"},
	"Prêt à transmettre": {"Transmis"},
	"Transmis": {"Accusé réception obtenu", "Rejeté par le destinataire", "Clôturé"},
	"Accusé réception obtenu": {"Clôturé"},
	"Rejeté par le destinataire": {"À corriger après transmission"},
	"À corriger après transmission": {"En préparation"},
	"Clôturé": {"Archivé"},
	"Archivé": set(),
}

FROZEN = ("Validé", "Diffusé", "Prêt à transmettre", "Transmis", "Accusé réception obtenu", "Clôturé", "Archivé")


def _filters(inst, date_field=None):
	f = {"organisation": inst.organisation}
	if inst.direction:
		f["_direction"] = inst.direction
	return f


def _apply_common(f, inst, dt):
	meta = frappe.get_meta(dt)
	f = {k: v for k, v in f.items() if not k.startswith("_")}
	if inst.direction:
		for fld in ("direction", "unite"):
			if meta.has_field(fld):
				f[fld] = inst.direction
				break
	if inst.domaine and meta.has_field("domaine"):
		f["domaine"] = inst.domaine
	if inst.criticite:
		for fld in ("criticite", "gravite"):
			if meta.has_field(fld):
				f[fld] = inst.criticite
				break
	if inst.responsable_filtre and meta.has_field("responsable"):
		f["responsable"] = inst.responsable_filtre
	if inst.autorite and meta.has_field("autorite"):
		f["autorite"] = inst.autorite
	return f


def section_data(section, inst):
	src = section.source_donnees
	limit = cint(section.limite) or 50
	start, end, arrete = getdate(inst.date_debut), getdate(inst.date_fin), getdate(inst.date_arrete)
	base = _filters(inst)
	if src == "Synthèse":
		rate = indicators.compliance_rate(inst.organisation)
		wrate = indicators.weighted_compliance_rate(inst.organisation)
		return {"type": "kpi", "rows": [
			{"Indicateur": "Taux de conformité", "Valeur": f"{rate['valeur']} %" if rate["calculable"] else "Non calculable",
				"Détail": f"{rate['num']}/{rate['den']} évaluées — {rate['details']['non_evaluees']} non évaluée(s)"},
			{"Indicateur": "Taux de conformité pondéré", "Valeur": f"{wrate['valeur']} %" if wrate["calculable"] else "Non calculable", "Détail": "Pondération par criticité"},
			*[{"Indicateur": lab, "Valeur": indicators.compute(m, inst.organisation)["valeur"], "Détail": ""} for lab, m in (
				("Échéances en retard", "echeances_en_retard"), ("Échéances à 7 jours", "echeances_7_jours"),
				("Justificatifs en attente de contrôle", "justificatifs_en_controle"), ("Non-conformités ouvertes", "nc_ouvertes"),
				("Plans d'action en retard", "pa_en_retard"), ("Prolongations en attente", "prolongations_en_attente"))],
		]}
	if src == "Obligations":
		f = _apply_common(base, inst, "Reg Obligation")
		rows = frappe.get_all("Reg Obligation", filters={**f, "statut": ("in", ("Active", "Validée", "Suspendue"))},
			fields=["name as Référence", "titre as Intitulé", "statut as Statut", "etat_conformite as Conformité",
				"criticite as Criticité", "direction as Direction", "proprietaire as Propriétaire"], limit=limit, order_by="criticite desc")
		return {"type": "table", "rows": rows}
	if src == "Échéances":
		f = _apply_common(base, inst, "Reg Deadline")
		rows = frappe.get_all("Reg Deadline", filters={**f, "date_limite": ("between", (start, end))},
			fields=["name as Référence", "libelle as Libellé", "date_limite as `Date limite`", "statut as Statut",
				"etat_documentaire as `État documentaire`", "jours_retard as `Jours de retard`", "responsable as Responsable"],
			limit=limit, order_by="date_limite asc")
		return {"type": "table", "rows": rows}
	if src == "Justificatifs":
		f = _apply_common(base, inst, "Reg Evidence")
		rows = frappe.get_all("Reg Evidence", filters={**f, "modified": ("<=", f"{arrete} 23:59:59")},
			fields=["name as Référence", "libelle as Libellé", "statut as Statut", "date_depot as `Dépôt`",
				"date_validation as Validation", "depose_apres_echeance as `Tardif`"], limit=limit, order_by="modified desc")
		return {"type": "table", "rows": rows}
	if src == "Non-conformités":
		f = _apply_common(base, inst, "Reg Non Conformity")
		rows = frappe.get_all("Reg Non Conformity", filters={**f, "date_detection": ("<=", arrete)},
			fields=["name as Référence", "intitule as Intitulé", "gravite as Gravité", "statut as Statut",
				"date_detection as Détection", "anciennete_jours as Ancienneté", "plan_action as Plan"], limit=limit, order_by="date_detection asc")
		return {"type": "table", "rows": rows, "aging": indicators.nc_aging(inst.organisation)}
	if src == "Plans d'action":
		f = _apply_common(base, inst, "Reg Action Plan")
		rows = frappe.get_all("Reg Action Plan", filters=f, fields=["name as Référence", "intitule as Intitulé",
			"criticite as Criticité", "statut as Statut", "taux_realisation as `Réalisation %`", "date_cible as `Date cible`",
			"nb_prolongations as Prolongations", "en_retard as `En retard`"], limit=limit, order_by="date_cible asc")
		return {"type": "table", "rows": rows}
	if src == "Actions":
		f = _apply_common(base, inst, "Reg Corrective Action")
		rows = frappe.get_all("Reg Corrective Action", filters=f, fields=["name as Référence", "intitule as Intitulé",
			"plan as Plan", "statut as Statut", "date_fin_prevue as `Fin prévue`", "responsable as Responsable"], limit=limit,
			order_by="date_fin_prevue asc")
		return {"type": "table", "rows": rows}
	if src == "Prolongations":
		rows = frappe.get_all("Reg Extension Request", filters={"organisation": inst.organisation,
			"date_demande": ("between", (f"{start} 00:00:00", f"{end} 23:59:59"))}, fields=["name as Référence", "plan as Plan",
			"action as Action", "date_initiale as `Date initiale`", "nouvelle_date as `Nouvelle date`", "statut as Statut", "motif as Motif"],
			limit=limit)
		return {"type": "table", "rows": rows}
	if src == "Qualité des données":
		return {"type": "kpi", "rows": [{"Indicateur": k, "Valeur": v, "Détail": ""} for k, v in indicators.data_quality(inst.organisation).items()]}
	if src == "Performance du processus":
		return {"type": "kpi", "rows": [{"Indicateur": lab, "Valeur": indicators.compute(m, inst.organisation)["valeur"], "Détail": ""} for lab, m in (
			("Délai moyen de validation des justificatifs (j)", "delai_moyen_validation_justificatifs"),
			("Taux de rejet des justificatifs (%)", "taux_rejet_justificatifs"),
			("Ancienneté moyenne des NC (j)", "nc_anciennete_moyenne"),
			("Taux de réouverture des plans (%)", "taux_reouverture_pa"),
			("Taux de retard des échéances (%)", "taux_retard_echeances"))]}
	if src == "Indicateur" and section.indicateur:
		ind = frappe.get_cached_doc("Reg Indicator", section.indicateur)
		r = indicators.compute(ind.methode, inst.organisation)
		return {"type": "kpi", "rows": [{"Indicateur": ind.libelle, "Valeur": r["valeur"] if r["calculable"] else "Non calculable",
			"Détail": ind.definition or ""}]}
	return {"type": "text", "text": section.texte or ""}


def generate(inst):
	"""Calcule et fige les données de l'instance ; aucune donnée d'un rapport officiel validé n'est recalculée."""
	if inst.statut in FROZEN:
		frappe.throw(_("Les données d'un rapport validé sont figées : créez une nouvelle version."))
	tpl = frappe.get_doc("Reg Report Template", inst.modele)
	if tpl.statut not in ("Validé", "Actif"):
		frappe.throw(_("Le modèle {0} n'est pas actif.").format(tpl.name))
	try:
		data = {"modele": tpl.name, "version_modele": tpl.version, "genere_le": str(now_datetime()), "sections": []}
		for s in sorted(tpl.sections, key=lambda x: cint(x.ordre)):
			data["sections"].append({"titre": s.titre, "source": s.source_donnees, "type_section": s.type_section,
				"texte": s.texte, **section_data(s, inst)})
		inst.donnees = json.dumps(data, default=str, ensure_ascii=False, indent=1)
		inst.filtres_appliques = json.dumps({k: inst.get(k) for k in ("date_debut", "date_fin", "date_arrete", "direction",
			"domaine", "autorite", "responsable_filtre", "criticite")}, default=str, ensure_ascii=False)
		inst.formules = _("Taux de conformité = obligations conformes / obligations évaluées (non évaluées exclues, affichées à part). "
			"Taux pondéré : poids de criticité (Critique 4, Élevée 3, Moyenne 2, Faible 1).")
		inst.version_modele = tpl.version
		inst.date_generation = now_datetime()
		inst.date_actualisation_donnees = now_datetime()
		inst.genere_par = frappe.session.user
		inst.preparateur = inst.preparateur or frappe.session.user
		inst.erreur_generation = None
		inst.resultat_html = render_html(inst, data)
		if inst.statut == "Brouillon" or inst.statut == "Échec de génération":
			inst.statut = "En préparation"
	except frappe.ValidationError:
		raise
	except Exception as e:
		inst.statut = "Échec de génération"
		inst.erreur_generation = str(e)[:1000]
		frappe.log_error(title=f"Génération du rapport {inst.name}")
	inst.flags.ignore_permissions = True
	inst.save()
	return inst


def render_html(inst, data=None):
	data = data or json.loads(inst.donnees or "{}")
	h = [f"<div class='reg-report'><h2>{escape_html(inst.intitule)}</h2>",
		f"<p><b>{_('Organisation')} :</b> {escape_html(inst.organisation)} — <b>{_('Période')} :</b> "
		f"{formatdate(inst.date_debut)} → {formatdate(inst.date_fin)} — <b>{_('Situation arrêtée au')} :</b> {formatdate(inst.date_arrete)}"
		f" — <b>{_('Version')} :</b> {inst.version}</p>"]
	for s in data.get("sections", []):
		h.append(f"<h3>{escape_html(s['titre'])}</h3>")
		if s.get("texte"):
			h.append(f"<p>{escape_html(s['texte'])}</p>")
		rows = s.get("rows") or []
		if rows:
			cols = list(rows[0].keys())
			h.append("<table class='table table-bordered table-condensed'><thead><tr>" + "".join(f"<th>{escape_html(str(c))}</th>" for c in cols) + "</tr></thead><tbody>")
			for r in rows:
				h.append("<tr>" + "".join(f"<td>{escape_html(str(r.get(c) if r.get(c) is not None else ''))}</td>" for c in cols) + "</tr>")
			h.append("</tbody></table>")
		elif s.get("type") == "table":
			h.append(f"<p><i>{_('Aucune donnée sur le périmètre.')}</i></p>")
		if s.get("aging"):
			h.append("<p>" + " — ".join(f"{escape_html(k)} : {v}" for k, v in s["aging"].items()) + "</p>")
	if inst.synthese:
		h.append(f"<h3>{_('Synthèse')}</h3>{inst.synthese}")
	for c in inst.commentaires or []:
		h.append(f"<p><b>{escape_html(c.section or '')}</b> — {escape_html(c.contenu)} <small>({escape_html(c.auteur or '')})</small></p>")
	if data.get("genere_le"):
		h.append(f"<p class='text-muted small'>{_('Données générées le')} {data['genere_le']} — {escape_html(inst.formules or '')}</p>")
	h.append("</div>")
	return "".join(h)


def export_files(inst):
	"""Produit le PDF (et l'Excel / CSV) figé de la version validée."""
	from frappe.utils.file_manager import save_file
	from frappe.utils.pdf import get_pdf

	tpl_fmt = frappe.db.get_value("Reg Report Template", inst.modele, "format_sortie") or "PDF"
	html = inst.resultat_html or render_html(inst)
	base = f"{inst.name}-v{inst.version}"
	if "PDF" in tpl_fmt:
		pdf = get_pdf(f"<html><head><meta charset='utf-8'></head><body>{html}</body></html>")
		f = save_file(f"{base}.pdf", pdf, inst.doctype, inst.name, is_private=1)
		inst.db_set("fichier_pdf", f.file_url)
	if "Excel" in tpl_fmt or "CSV" in tpl_fmt:
		data = json.loads(inst.donnees or "{}")
		if "Excel" in tpl_fmt:
			from frappe.utils.xlsxutils import make_xlsx
			rows = []
			for s in data.get("sections", []):
				rows.append([s["titre"]])
				if s.get("rows"):
					cols = list(s["rows"][0].keys())
					rows.append(cols)
					rows += [[r.get(c) for c in cols] for r in s["rows"]]
				rows.append([])
			x = make_xlsx(rows, "Rapport")
			f = save_file(f"{base}.xlsx", x.getvalue(), inst.doctype, inst.name, is_private=1)
			inst.db_set("fichier_excel", f.file_url)
		else:
			buf = io.StringIO()
			w = csv.writer(buf, delimiter=";")
			for s in data.get("sections", []):
				w.writerow([s["titre"]])
				if s.get("rows"):
					cols = list(s["rows"][0].keys())
					w.writerow(cols)
					for r in s["rows"]:
						w.writerow([r.get(c) for c in cols])
			f = save_file(f"{base}.csv", buf.getvalue().encode("utf-8-sig"), inst.doctype, inst.name, is_private=1)
			inst.db_set("fichier_excel", f.file_url)


# ------------------------------------------------------------------ circuit
def submit_for_control(inst):
	if not inst.donnees:
		frappe.throw(_("Générez les données avant de soumettre le rapport."))
	circuit = cint(frappe.db.get_value("Reg Report Template", inst.modele, "circuit_validation"))
	inst.statut = "À contrôler" if inst.controleur else ("À valider" if circuit else "Validé")
	inst.flags.ignore_permissions = True
	inst.save()
	from obligation_reglementaire.engine import notification
	notification.emit("rapport_a_controler" if inst.statut == "À contrôler" else "rapport_a_valider", inst)


def control(inst):
	assert_sod(frappe.session.user, inst.preparateur, message=_("Séparation des tâches : le préparateur ne peut pas contrôler le rapport."))
	inst.statut = "Contrôlé"
	inst.date_controle = now_datetime()
	inst.controleur = inst.controleur or frappe.session.user
	inst.flags.ignore_permissions = True
	inst.save()
	inst.statut = "À valider"
	inst.save()
	from obligation_reglementaire.engine import notification
	notification.emit("rapport_a_valider", inst)


def approve(inst, reserves=None):
	assert_sod(frappe.session.user, inst.preparateur, message=_("Séparation des tâches : le préparateur ne peut pas valider le rapport."))
	inst.statut = "Validé"
	inst.validateur = frappe.session.user
	inst.date_validation = now_datetime()
	inst.reserves = reserves or inst.reserves
	inst.fige = 1
	inst.flags.ignore_permissions = True
	inst.save()
	try:
		export_files(inst)
	except Exception:
		frappe.log_error(title=f"Export du rapport {inst.name}")
	log_audit("Validation du rapport", inst, details={"version": inst.version})


def reject(inst, motif, elements):
	require_text(motif, _("Le motif de rejet"))
	inst.statut = "Rejeté"
	inst.motif_rejet = motif
	inst.elements_a_corriger = elements
	inst.rejete_par = frappe.session.user
	inst.date_rejet = now_datetime()
	inst.flags.reg_justification = motif
	inst.flags.ignore_permissions = True
	inst.save()
	inst.statut = "À corriger"
	inst.save()
	from obligation_reglementaire.engine import notification
	notification.emit("rapport_rejete", inst)


def distribute(inst, users, canal="Plateforme"):
	if inst.statut not in ("Validé", "Diffusé"):
		frappe.throw(_("Seul un rapport validé peut être diffusé."))
	for u in users:
		inst.append("diffusions", {"destinataire": u, "canal": canal, "version": inst.version, "date_diffusion": now_datetime()})
		frappe.share.add(inst.doctype, inst.name, u, read=1, flags={"ignore_share_permission": True}, notify=0)
	inst.statut = "Diffusé"
	inst.flags.ignore_permissions = True
	inst.save()
	from obligation_reglementaire.engine import notification
	notification.emit("rapport_diffuse", inst)


def transmit(inst, values):
	if inst.statut not in ("Validé", "Diffusé", "Prêt à transmettre"):
		frappe.throw(_("Seul un rapport validé peut être transmis."))
	for k in ("fichier_transmis", "date_transmission", "canal_transmission", "destinataire_transmission", "reference_transmission",
			"preuve_depot"):
		if values.get(k):
			inst.set(k, values.get(k))
	if not inst.date_transmission or not inst.canal_transmission:
		frappe.throw(_("La date-heure et le canal de transmission sont obligatoires."))
	inst.fichier_transmis = inst.fichier_transmis or inst.fichier_pdf
	inst.transmis_par = frappe.session.user
	if inst.statut != "Prêt à transmettre":
		inst.statut = "Prêt à transmettre"
		inst.flags.ignore_permissions = True
		inst.save()
	inst.statut = "Transmis"
	inst.flags.ignore_permissions = True
	inst.save()


def new_version(inst):
	"""Toute correction d'un rapport validé / rejeté par l'autorité crée une nouvelle version ; l'ancienne reste conservée."""
	new = frappe.copy_doc(inst)
	new.update({"statut": "Brouillon", "version": cint(inst.version) + 1, "version_precedente": inst.name, "fige": 0,
		"donnees": None, "resultat_html": None, "fichier_pdf": None, "fichier_excel": None, "date_validation": None,
		"validateur": inst.validateur, "date_controle": None, "diffusions": [], "fichier_transmis": None, "date_transmission": None,
		"preuve_depot": None, "accuse_reception": None, "transmis_par": None, "motif_rejet": None, "rejete_par": None, "date_rejet": None})
	new.insert(ignore_permissions=True)
	return new.name


def scheduled_generation():
	"""Génération automatique des modèles actifs planifiés (mensuel le 1er, trimestriel début de trimestre…)."""
	from frappe.utils import add_months, get_first_day, get_last_day

	t = getdate(frappe.utils.today())
	for tpl in frappe.get_all("Reg Report Template", filters={"statut": "Actif", "generation_automatique": 1},
			fields=["name", "intitule", "frequence"]):
		due = (tpl.frequence == "Mensuel" and t.day == 1) or (tpl.frequence == "Trimestriel" and t.day == 1 and t.month in (1, 4, 7, 10)) \
			or (tpl.frequence == "Annuel" and t.day == 1 and t.month == 1) or (tpl.frequence == "Hebdomadaire" and t.weekday() == 0) \
			or (tpl.frequence == "Semestriel" and t.day == 1 and t.month in (1, 7)) or tpl.frequence == "Journalier"
		if not due:
			continue
		months = {"Mensuel": 1, "Trimestriel": 3, "Semestriel": 6, "Annuel": 12}.get(tpl.frequence)
		start = get_first_day(add_months(t, -months)) if months else frappe.utils.add_days(t, -7 if tpl.frequence == "Hebdomadaire" else -1)
		end = get_last_day(add_months(t, -1)) if months else frappe.utils.add_days(t, -1)
		for org in frappe.get_all("Reg Organization", filters={"statut": "Active"}, pluck="name"):
			if frappe.db.exists("Reg Report Instance", {"modele": tpl.name, "organisation": org, "date_debut": start, "date_fin": end}):
				continue
			inst = frappe.get_doc({"doctype": "Reg Report Instance", "modele": tpl.name, "organisation": org,
				"intitule": f"{tpl.intitule} — {formatdate(start)} au {formatdate(end)}", "type_periode": "Personnalisée",
				"date_debut": start, "date_fin": end, "date_arrete": end})
			try:
				inst.insert(ignore_permissions=True)
				generate(inst)
			except Exception:
				frappe.db.rollback()
				frappe.log_error(title=f"Génération planifiée {tpl.name} / {org}")
				from obligation_reglementaire.engine import notification
				notification.emit("rapport_echec", frappe.get_doc("Reg Report Template", tpl.name),
					extra={"motif": _("Échec de génération pour {0}").format(org)})
