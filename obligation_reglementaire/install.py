"""Installation et données de référence (idempotent : rejouable à chaque migrate, ne modifie jamais un paramétrage existant)."""

import frappe
from frappe.utils import getdate

from obligation_reglementaire.engine.common import SystemAction

ROLES = (
	("OR Administrateur", "Paramétrage du module, référentiels, droits, configuration sensible"),
	("OR Responsable Conformité", "Pilotage de la conformité, validation, arbitrages, reporting"),
	("OR Analyste Réglementaire", "Veille, sources, dispositions, qualification et applicabilité des obligations"),
	("OR Responsable Obligation", "Propriétaire / responsable opérationnel d'obligations et d'échéances"),
	("OR Contributeur", "Contribution : dépôt de justificatifs, réalisation d'actions"),
	("OR Contrôleur", "Contrôle des justificatifs, des actions et des rapports"),
	("OR Validateur", "Validation des échéances, plans d'action, reports et prolongations"),
	("OR Auditeur", "Consultation en lecture, piste d'audit, gel documentaire"),
	("OR Direction Générale", "Consultation des tableaux de bord et validation des rapports de direction"),
	("OR Gestionnaire Reporting", "Production et diffusion des rapports réglementaires"),
	("OR Gestionnaire Documentaire", "Gestion électronique des documents : versions, conservation, partage"),
)


def after_install():
	after_migrate()


def after_migrate():
	frappe.flags.in_install = True
	try:
		with SystemAction():
			create_roles()
			setup_settings()
			for fn in (criticality_levels, reference_lists, domains, document_setup, evidence_types, calendar,
					notification_setup, escalation_rules, indicators, report_templates, print_formats):
				try:
					fn()
				except Exception:
					frappe.log_error(title=f"Obligations réglementaires — installation {fn.__name__}")
		frappe.db.commit()
	finally:
		frappe.flags.in_install = False


def _ensure(doctype, name, values):
	"""Crée l'enregistrement s'il n'existe pas (le paramétrage client n'est jamais écrasé)."""
	if frappe.db.exists(doctype, name):
		return None
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.insert(ignore_mandatory=True, ignore_if_duplicate=True)
	return doc


# ------------------------------------------------------------------ rôles et paramètres
def create_roles():
	for role, desc in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "description": desc}).insert(ignore_permissions=True)


SETTINGS_DEFAULTS = {
	"fuseau_horaire": "Africa/Abidjan",
	"langue_defaut": "fr",
	"devise": "XOF",
	"format_reference": "OBL-.YYYY.-.#####",
	"separation_taches": 1,
	"validation_parametres_sensibles": 1,
	"justification_changements_sensibles": 1,
	"autoriser_suppression_logique": 1,
	"horizon_generation_jours": 365,
	"jours_alerte_defaut": "30,15,7,3,1,0",
	"jours_a_traiter": 30,
	"heure_limite_defaut": "23:59:00",
	"regle_jour_non_ouvre": "Jour ouvré précédent",
	"max_occurrences_generation": 60,
	"taille_max_mo": 25,
	"formats_autorises": "pdf,docx,doc,xlsx,xls,csv,odt,ods,png,jpg,jpeg,msg,eml,zip,txt",
	"jours_controle_defaut": 5,
	"jours_resoumission_defaut": 5,
	"alertes_expiration_defaut": "60,30,15,7",
	"nc_auto_sur_rejet": 1,
	"nc_auto_sur_retard": 1,
	"jours_retard_nc": 1,
	"pa_auto_poids_min": 3,
	"efficacite_requise_poids_min": 3,
	"max_prolongations_alerte": 2,
	"notifications_actives": 1,
	"email_actif": 1,
	"fenetre_anti_doublon_heures": 24,
	"max_tentatives_envoi": 3,
	"resume_quotidien_actif": 1,
	"poids_critique": 4,
	"poids_elevee": 3,
	"poids_moyenne": 2,
	"poids_faible": 1,
	"seuil_vigilance_retard": 5,
	"seuil_alerte_retard": 10,
	"horizons_echeances": "7,15,30,60,90",
	"tranches_anciennete_nc": "30,60,90,180",
	"duree_conservation_defaut": 10,
	"point_depart_conservation": "Validation",
}


def setup_settings():
	"""Première installation : toutes les valeurs par défaut ; ensuite seuls les champs vides sont complétés."""
	first = not frappe.db.exists("Singles", {"doctype": "Reg Settings"})
	s = frappe.get_single("Reg Settings")
	changed = False
	for k, v in SETTINGS_DEFAULTS.items():
		if s.meta.has_field(k) and (first or s.get(k) in (None, "")):
			s.set(k, v)
			changed = True
	if changed:
		s.flags.ignore_permissions = True
		s.flags.ignore_links = True
		s.save()


# ------------------------------------------------------------------ référentiels
def criticality_levels():
	for libelle, code, poids, delai, couleur, desc in (
		("Critique", "CRIT", 4, 1, "#c92a2a", "Sanction lourde, retrait d'agrément, responsabilité pénale ou atteinte grave à la réputation"),
		("Élevée", "ELEV", 3, 3, "#e8590c", "Sanction financière significative, injonction de l'autorité, impact client"),
		("Moyenne", "MOY", 2, 7, "#f08c00", "Observation de l'autorité, régularisation possible sans sanction lourde"),
		("Faible", "FAIB", 1, 15, "#2f9e44", "Impact limité, formalité administrative"),
	):
		_ensure("Reg Criticality Level", libelle, {"libelle": libelle, "code": code, "ordre": 5 - poids, "poids": poids,
			"delai_escalade_jours": delai, "couleur": couleur, "actif": 1, "description": desc})


SOURCE_TYPES = (("Constitution", 1, 0), ("Traité ou convention internationale", 2, 0), ("Acte communautaire", 3, 0), ("Loi", 4, 0),
	("Ordonnance", 5, 0), ("Décret", 6, 0), ("Arrêté", 7, 0), ("Décision d'autorité", 8, 0), ("Circulaire ou instruction", 9, 0),
	("Norme ou référentiel", 10, 0), ("Code de conduite professionnel", 11, 0), ("Politique interne", 12, 1),
	("Procédure interne", 13, 1), ("Engagement contractuel", 14, 1))

AUTHORITY_TYPES = ("Ministère", "Autorité de régulation", "Banque centrale", "Administration fiscale", "Organisme de sécurité sociale",
	"Juridiction", "Autorité communautaire", "Organisme de normalisation", "Collectivité territoriale", "Autre")

OBLIGATION_TYPES = (("DECL", "Déclaration"), ("REPORT", "Reporting réglementaire"), ("PAIE", "Paiement"), ("AUTOR", "Autorisation / licence"),
	("CTRL", "Contrôle"), ("FORM", "Formation"), ("GOUV", "Gouvernance"), ("CONS", "Conservation"), ("INFO", "Information / publication"),
	("INTERD", "Interdiction"), ("PERM", "Conformité permanente"), ("NOTIF", "Notification d'événement"))

DELAY_CAUSES = (("ATT_INFO", "Attente d'information interne", 0), ("ATT_TIERS", "Attente d'un tiers ou prestataire", 0),
	("CHARGE", "Surcharge de travail", 0), ("OUTIL", "Indisponibilité d'un outil", 0), ("AUTORITE", "Retard de l'autorité / plateforme", 0),
	("VALID", "Validation interne tardive", 0), ("ORGA", "Changement d'organisation", 0), ("OUBLI", "Omission", 1), ("AUTRE", "Autre", 1))

CAUSE_CATEGORIES = ("Humaine", "Organisationnelle", "Processus", "Technique / système", "Documentaire", "Externe / tiers",
	"Juridique / interprétation", "Financière")

RELATION_TYPES = (("Modifie", "Modifié par"), ("Abroge", "Abrogé par"), ("Complète", "Complété par"), ("Remplace", "Remplacé par"),
	("Applique", "Appliqué par"), ("Transpose", "Transposé par"), ("Cite", "Cité par"), ("Précise", "Précisé par"))

TRIGGER_EVENTS = (("NOMINATION_DIRIGEANT", "Nomination ou départ d'un dirigeant", "Gouvernance"),
	("MODIF_STATUTS", "Modification des statuts", "Gouvernance"), ("CHANGEMENT_ACTIONNARIAT", "Changement d'actionnariat", "Gouvernance"),
	("AUGMENTATION_CAPITAL", "Augmentation ou réduction de capital", "Gouvernance"),
	("INCIDENT_SECURITE", "Incident de sécurité majeur", "Incident"), ("VIOLATION_DONNEES", "Violation de données personnelles", "Incident"),
	("INCIDENT_OPERATIONNEL", "Incident opérationnel significatif", "Incident"), ("FRAUDE", "Fraude détectée", "Incident"),
	("NOUVEAU_PRODUIT", "Lancement d'un nouveau produit ou service", "Commercial"),
	("OUVERTURE_ETABLISSEMENT", "Ouverture ou fermeture d'un établissement", "Opérationnel"),
	("EXTERNALISATION", "Externalisation d'une activité importante", "Contrat"),
	("CONTROLE_AUTORITE", "Contrôle ou inspection d'une autorité", "Réglementaire"),
	("INJONCTION", "Injonction ou mise en demeure d'une autorité", "Réglementaire"),
	("DECLARATION_SOUPCON", "Opération suspecte (LCB-FT)", "Réglementaire"))

REJECTION_REASONS = (("ILLISIBLE", "Document illisible ou incomplet", "Tous"), ("PERIODE", "Période couverte incorrecte", "Justificatif"),
	("SIGNATURE", "Signature ou cachet manquant", "Tous"), ("MAUVAIS_DOC", "Document ne correspondant pas à l'attendu", "Tous"),
	("EXPIRE", "Document expiré", "Tous"), ("FORMAT", "Format non conforme", "Tous"), ("INCOHERENCE", "Incohérence avec d'autres données", "Tous"),
	("PREUVE_INSUF", "Preuve insuffisante de la réalisation", "Preuve d'action"), ("VERSION", "Version non définitive", "Document"),
	("DONNEES_RAPPORT", "Données du rapport erronées ou incomplètes", "Reporting"), ("AUTRE", "Autre motif (à préciser)", "Tous"))


def reference_lists():
	for libelle, niveau, interne in SOURCE_TYPES:
		_ensure("Reg Source Type", libelle, {"libelle": libelle, "niveau_hierarchique": niveau, "interne": interne, "actif": 1})
	for libelle in AUTHORITY_TYPES:
		_ensure("Reg Authority Type", libelle, {"libelle": libelle, "actif": 1})
	for code, libelle in OBLIGATION_TYPES:
		_ensure("Reg Obligation Type", libelle, {"libelle": libelle, "code": code, "actif": 1})
	for code, libelle, comment in DELAY_CAUSES:
		_ensure("Reg Delay Cause", code, {"code": code, "libelle": libelle, "commentaire_obligatoire": comment, "actif": 1})
	for libelle in CAUSE_CATEGORIES:
		_ensure("Reg Cause Category", libelle, {"libelle": libelle, "actif": 1})
	for libelle, inverse in RELATION_TYPES:
		_ensure("Reg Relation Type", libelle, {"libelle": libelle, "libelle_inverse": inverse, "actif": 1})
	for code, libelle, cat in TRIGGER_EVENTS:
		_ensure("Reg Trigger Event Type", code, {"code": code, "libelle": libelle, "categorie": cat, "actif": 1})
	for code, libelle, scope in REJECTION_REASONS:
		_ensure("Reg Rejection Reason", code, {"code": code, "libelle": libelle, "s_applique_a": scope, "actif": 1})


DOMAINS = (("GOUV", "Gouvernance d'entreprise"), ("CORPO", "Droit des sociétés"), ("FISC", "Fiscalité"), ("SOCIAL", "Social et travail"),
	("COMPTA", "Comptabilité et information financière"), ("LCBFT", "Lutte contre le blanchiment et le financement du terrorisme"),
	("DONNEES", "Protection des données personnelles"), ("SSI", "Sécurité des systèmes d'information"), ("PRUD", "Prudentiel"),
	("CONSO", "Protection des consommateurs"), ("HSE", "Santé, sécurité et environnement"), ("CONCUR", "Concurrence"),
	("ANTICOR", "Anticorruption et éthique"), ("CHANGE", "Réglementation des changes"), ("SECT", "Réglementation sectorielle"))


def domains():
	_ensure("Reg Domain", "TOUS", {"code": "TOUS", "nom": "Tous les domaines", "is_group": 1, "actif": 1})
	for code, nom in DOMAINS:
		_ensure("Reg Domain", code, {"code": code, "nom": nom, "parent_reg_domain": "TOUS", "is_group": 0, "actif": 1})


RETENTION_RULES = (("Conservation 10 ans après validation", 10, "Validation", 0), ("Conservation 5 ans après clôture de l'échéance", 5,
	"Clôture de l'échéance", 0), ("Conservation 5 ans après fin de l'obligation", 5, "Fin de l'obligation", 0),
	("Conservation 10 ans après clôture de la non-conformité", 10, "Clôture de la non-conformité", 0),
	("Conservation 5 ans après clôture du plan d'action", 5, "Clôture du plan d'action", 0),
	("Conservation 3 ans après création", 3, "Création", 0))

DOC_CATEGORIES = ("Textes réglementaires", "Justificatifs de conformité", "Preuves d'actions correctives", "Rapports réglementaires",
	"Correspondances avec les autorités", "Gouvernance", "Procédures et politiques internes", "Agréments et licences")

DOC_TYPES = (("Texte officiel", "Textes réglementaires", "Conservation 5 ans après fin de l'obligation", 0, 0),
	("Justificatif de conformité", "Justificatifs de conformité", "Conservation 5 ans après clôture de l'échéance", 0, 1),
	("Preuve d'action corrective", "Preuves d'actions correctives", "Conservation 5 ans après clôture du plan d'action", 0, 1),
	("Rapport réglementaire", "Rapports réglementaires", "Conservation 10 ans après validation", 0, 1),
	("Courrier d'une autorité", "Correspondances avec les autorités", "Conservation 10 ans après validation", 0, 0),
	("Accusé de réception", "Correspondances avec les autorités", "Conservation 10 ans après validation", 0, 0),
	("Procès-verbal d'organe social", "Gouvernance", "Conservation 10 ans après validation", 0, 1),
	("Procédure interne", "Procédures et politiques internes", "Conservation 3 ans après création", 0, 1),
	("Politique interne", "Procédures et politiques internes", "Conservation 3 ans après création", 0, 1),
	("Agrément / licence", "Agréments et licences", "Conservation 10 ans après validation", 1, 1),
	("Certificat", "Justificatifs de conformité", "Conservation 5 ans après clôture de l'échéance", 1, 1))


def document_setup():
	for nom, duree, depart, archive in RETENTION_RULES:
		_ensure("Reg Retention Rule", nom, {"nom": nom, "duree_annees": duree, "point_depart": depart, "duree_archivage_annees": archive,
			"actif": 1, "conditions_suppression": "Aucun gel actif, aucun contentieux, aucun contrôle en cours ; validation du gestionnaire documentaire."})
	_ensure("Reg Document Category", "Toutes les catégories", {"nom": "Toutes les catégories", "is_group": 1, "actif": 1})
	for nom in DOC_CATEGORIES:
		_ensure("Reg Document Category", nom, {"nom": nom, "parent_reg_document_category": "Toutes les catégories", "is_group": 0, "actif": 1})
	for libelle, cat, ret, exp, valid in DOC_TYPES:
		_ensure("Reg Document Type", libelle, {"libelle": libelle, "categorie": cat, "retention": ret, "necessite_date_expiration": exp,
			"validation_requise": valid, "actif": 1})


EVIDENCE_TYPES = (
	# libellé, code, catégorie, valider, émission, expiration, réf. externe, signature, période, validité (j)
	("Déclaration déposée", "DECL", "Déclaration", 1, 1, 0, 1, 0, 1, 0),
	("Accusé de réception de l'autorité", "AR", "Preuve de transmission", 1, 1, 0, 1, 0, 0, 0),
	("Preuve de transmission", "TRANS", "Preuve de transmission", 1, 1, 0, 1, 0, 0, 0),
	("Preuve de paiement", "PAIE", "Preuve de paiement", 1, 1, 0, 1, 0, 1, 0),
	("Rapport", "RAPPORT", "Rapport", 1, 1, 0, 0, 1, 1, 0),
	("Procès-verbal", "PV", "Procès-verbal", 1, 1, 0, 0, 1, 0, 0),
	("Attestation", "ATTEST", "Attestation", 1, 1, 1, 1, 1, 0, 365),
	("Certificat", "CERTIF", "Certificat", 1, 1, 1, 1, 0, 0, 365),
	("Registre tenu à jour", "REGISTRE", "Registre", 1, 0, 0, 0, 0, 1, 0),
	("Procédure approuvée", "PROC", "Procédure", 1, 1, 0, 0, 1, 0, 730),
	("Preuve de contrôle interne", "CTRL", "Preuve de contrôle", 1, 1, 0, 0, 0, 1, 0),
	("Preuve de formation", "FORM", "Preuve de formation", 1, 1, 0, 0, 0, 1, 0),
	("Correspondance", "CORRESP", "Correspondance", 0, 1, 0, 1, 0, 0, 0),
	("Autre justificatif", "AUTRE", "Autre", 1, 0, 0, 0, 0, 0, 0),
)


def evidence_types():
	formats = frappe.db.get_single_value("Reg Settings", "formats_autorises")
	for libelle, code, cat, valider, emission, expiration, ref, signature, periode, validite in EVIDENCE_TYPES:
		_ensure("Reg Evidence Type", libelle, {"libelle": libelle, "code": code, "categorie": cat, "actif": 1, "doit_etre_valide": valider,
			"necessite_date_emission": emission, "necessite_date_expiration": expiration, "necessite_reference_externe": ref,
			"necessite_signature": signature, "necessite_periode": periode, "utilisable_principal": 1, "utilisable_complementaire": 1,
			"obligatoire_defaut": 1 if code in ("DECL", "AR", "PAIE", "RAPPORT") else 0, "formats_autorises": formats,
			"duree_validite_jours": validite, "alertes_expiration": "60,30,15,7" if expiration else None,
			"retention_regle": "Conservation 10 ans après validation"})


# Jours fériés à date fixe (Côte d'Ivoire) — les fêtes mobiles sont saisies chaque année par l'administrateur
FIXED_HOLIDAYS = (("01-01", "Jour de l'An"), ("05-01", "Fête du Travail"), ("08-07", "Fête de l'Indépendance"),
	("08-15", "Assomption"), ("11-01", "Toussaint"), ("11-15", "Journée nationale de la Paix"), ("12-25", "Noël"))


def calendar():
	name = "Calendrier standard"
	year = getdate().year
	holidays = [{"date": f"{y}-{md}", "libelle": lib, "type_jour": "Jour férié"} for y in (year, year + 1) for md, lib in FIXED_HOLIDAYS]
	pays = "Ivory Coast" if frappe.db.exists("Country", "Ivory Coast") else ("Côte d'Ivoire" if frappe.db.exists("Country", "Côte d'Ivoire") else None)
	if _ensure("Reg Calendar", name, {"nom": name, "type_calendrier": "Standard", "pays": pays, "fuseau_horaire": "Africa/Abidjan",
			"heure_limite": "23:59:00", "actif": 1, "lundi": 1, "mardi": 1, "mercredi": 1, "jeudi": 1, "vendredi": 1, "samedi": 0,
			"dimanche": 0, "jours_feries": holidays}) is None:
		cal = frappe.get_doc("Reg Calendar", name)
		known = {str(h.date) for h in cal.jours_feries}
		missing = [h for h in holidays if h["date"] not in known]
		if missing and getdate(f"{year}-01-01") <= getdate():
			for h in missing:
				cal.append("jours_feries", h)
			cal.flags.ignore_permissions = True
			cal.save()
	if not frappe.db.get_single_value("Reg Settings", "calendrier_defaut"):
		frappe.db.set_single_value("Reg Settings", "calendrier_defaut", name)


# ------------------------------------------------------------------ notifications
_BODY = """<p>{texte}</p>
<table>
<tr><td>Référence</td><td><b>{{{{ reference }}}}</b></td></tr>
<tr><td>Objet</td><td>{{{{ intitule }}}}</td></tr>
{{% if obligation %}}<tr><td>Obligation</td><td>{{{{ obligation }}}}</td></tr>{{% endif %}}
{{% if date_echeance %}}<tr><td>Date</td><td>{{{{ date_echeance }}}}{{% if jours_restants != "" %}} (J{{{{ "+" if jours_restants < 0 else "-" }}}}{{{{ jours_restants|abs }}}}){{% endif %}}</td></tr>{{% endif %}}
{{% if criticite %}}<tr><td>Criticité</td><td>{{{{ criticite }}}}</td></tr>{{% endif %}}
<tr><td>Statut</td><td>{{{{ statut }}}}</td></tr>
{{% if motif %}}<tr><td>Motif</td><td>{{{{ motif }}}}</td></tr>{{% endif %}}
</table>
<p><b>Action attendue :</b> {action}</p>
<p><a href="{{{{ lien }}}}">Ouvrir dans la plateforme</a></p>"""

R, RO, PO, RE, PJ, CT, VA, MG, RD, FC, DG = ("Responsable de l'objet", "Responsable de l'obligation", "Propriétaire de l'obligation",
	"Responsable de l'échéance", "Propriétaire du justificatif", "Contrôleur", "Validateur", "Manager", "Responsable de la direction",
	"Fonction conformité", "Direction Générale")

# événement, sujet, texte, action attendue, cibles, priorité, accusé, mode, jours relatifs, relance (j), max relances, prio. selon criticité
NOTIFICATIONS = (
	("obligation_creee", "Nouvelle obligation : {{ intitule }}", "Une nouvelle obligation a été enregistrée.", "Qualifier et valider l'obligation.", (FC,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("obligation_affectee", "Obligation affectée : {{ intitule }}", "Vous êtes désormais responsable de cette obligation.", "Prendre connaissance de l'obligation et de ses échéances.", (PO, RO), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("obligation_statut", "Obligation {{ statut }} : {{ intitule }}", "Le statut de l'obligation a changé.", "Aucune, pour information.", (PO,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("obligation_applicable", "Obligation applicable : {{ intitule }}", "L'obligation a été déclarée applicable.", "Désigner les responsables et activer l'obligation.", (FC, PO), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("obligation_non_applicable", "Obligation non applicable : {{ intitule }}", "L'obligation a été déclarée non applicable.", "Vérifier la justification de non-applicabilité.", (FC,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("obligation_a_revoir", "Obligation à revoir : {{ intitule }}", "Une évolution réglementaire ou du profil impose de revoir cette obligation.", "Requalifier l'obligation.", (PO, FC), "Élevée", 0, "Immédiat", None, 0, 0, 1),
	("echeance_creee", "Nouvelle échéance : {{ intitule }}", "Une échéance vous a été attribuée.", "Planifier la réalisation avant la date limite.", (RE,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("echeance_approche", "Échéance à J-{{ seuil }} : {{ intitule }}", "Une échéance approche.", "Réaliser l'obligation et déposer les justificatifs.", (RE,), "Normale", 0, "Immédiat", None, 0, 0, 1),
	("echeance_depassee", "Échéance dépassée : {{ intitule }}", "La date limite est dépassée sans réalisation validée.", "Régulariser immédiatement et indiquer la cause du retard.", (RE, MG, FC), "Élevée", 1, "Immédiat", None, 0, 0, 1),
	("echeance_suspendue", "Échéance suspendue : {{ intitule }}", "L'échéance a été suspendue.", "Aucune, pour information.", (RE,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("echeance_reactivee", "Échéance réactivée : {{ intitule }}", "L'échéance est à nouveau active.", "Reprendre la réalisation.", (RE,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("echeance_reportee", "Échéance reportée : {{ intitule }}", "La date limite de l'échéance a été modifiée.", "Prendre en compte la nouvelle date.", (RE,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("report_refuse", "Report refusé : {{ intitule }}", "Votre demande de report a été refusée.", "Respecter la date limite initiale.", (R,), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("echeance_soumise", "Échéance à valider : {{ intitule }}", "Une échéance a été soumise pour validation.", "Contrôler les justificatifs et valider ou rejeter.", (VA,), "Normale", 0, "Immédiat", None, 0, 0, 1),
	("echeance_rejetee", "Soumission rejetée : {{ intitule }}", "La soumission de l'échéance a été rejetée.", "Corriger et soumettre à nouveau.", (RE,), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("echeance_cloturee", "Échéance clôturée : {{ intitule }}", "L'échéance est réalisée / clôturée.", "Aucune, pour information.", (RE,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_attendu", "Justificatif attendu : {{ intitule }}", "Un justificatif doit être fourni.", "Déposer le justificatif avant la date limite.", (PJ,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_manquant", "Justificatif manquant : {{ intitule }}", "Des justificatifs obligatoires manquent à l'approche de l'échéance.", "Déposer les justificatifs manquants.", (RE,), "Élevée", 0, "Immédiat", None, 0, 0, 1),
	("justificatif_depose", "Justificatif déposé : {{ intitule }}", "Un justificatif a été déposé.", "Aucune, pour information.", (RE,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_soumis_controle", "Justificatif à contrôler : {{ intitule }}", "Un justificatif attend votre contrôle.", "Contrôler le justificatif (checklist) et décider.", (CT,), "Normale", 0, "Immédiat", None, 0, 0, 1),
	("justificatif_valide", "Justificatif validé : {{ intitule }}", "Votre justificatif a été validé.", "Aucune.", (PJ,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_rejete", "Justificatif rejeté : {{ intitule }}", "Votre justificatif a été rejeté.", "Corriger et déposer une nouvelle version.", (PJ,), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_a_completer", "Justificatif à compléter : {{ intitule }}", "Le contrôleur demande un complément.", "Compléter le justificatif.", (PJ,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_expiration_proche", "Justificatif bientôt expiré : {{ intitule }}", "Un justificatif arrive à expiration.", "Renouveler le justificatif.", (PJ,), "Normale", 0, "Temporel", -30, 15, 2, 0),
	("justificatif_expire", "Justificatif expiré : {{ intitule }}", "Un justificatif a expiré.", "Fournir un justificatif à jour.", (PJ, FC), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("justificatif_remplace", "Justificatif remplacé : {{ intitule }}", "Un justificatif validé a été remplacé.", "Contrôler la nouvelle version.", (CT,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("nc_creee", "Non-conformité : {{ intitule }}", "Une non-conformité a été enregistrée.", "Analyser les causes et définir le traitement.", (R, FC), "Élevée", 0, "Immédiat", None, 0, 0, 1),
	("nc_cloturee", "Non-conformité clôturée : {{ intitule }}", "La non-conformité a été clôturée.", "Aucune.", (R,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("pa_cree", "Plan d'action : {{ intitule }}", "Un plan d'action vous a été confié.", "Définir et lancer les actions correctives.", (R,), "Normale", 0, "Immédiat", None, 0, 0, 1),
	("action_assignee", "Action corrective : {{ intitule }}", "Une action corrective vous a été assignée.", "Réaliser l'action et déposer les preuves.", (R,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("action_approche", "Action à J-7 : {{ intitule }}", "La date prévue de l'action approche.", "Finaliser l'action.", (R,), "Normale", 0, "Temporel", -7, 0, 0, 0),
	("action_retard", "Action en retard : {{ intitule }}", "L'action corrective est en retard.", "Réaliser l'action ou demander une prolongation justifiée.", (R, MG), "Élevée", 0, "Temporel", 1, 7, 3, 0),
	("action_bloquee", "Action bloquée : {{ intitule }}", "Une action corrective est bloquée.", "Lever le blocage.", (R, FC), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("action_soumise", "Action à contrôler : {{ intitule }}", "Une action est soumise à contrôle.", "Contrôler les preuves et valider ou retourner.", (CT,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("action_validee", "Action validée : {{ intitule }}", "L'action corrective est validée.", "Aucune.", (R,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("action_rejetee", "Action retournée : {{ intitule }}", "L'action a été retournée pour correction.", "Corriger et soumettre à nouveau.", (R,), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("preuve_rejetee", "Preuve rejetée : {{ intitule }}", "Une preuve d'action a été rejetée.", "Fournir une nouvelle preuve.", (R,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("prolongation_demandee", "Prolongation demandée : {{ intitule }}", "Une demande de prolongation attend votre décision.", "Accepter, refuser ou demander des informations.", (VA, FC), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("prolongation_acceptee", "Prolongation acceptée : {{ intitule }}", "Votre demande de prolongation est acceptée.", "Respecter la nouvelle date.", (R,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("prolongation_refusee", "Prolongation refusée : {{ intitule }}", "Votre demande de prolongation est refusée.", "Respecter la date prévue.", (R,), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("pa_cloture_demandee", "Clôture à valider : {{ intitule }}", "La clôture du plan d'action est demandée.", "Vérifier les preuves et valider la clôture.", (VA, FC), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("pa_cloture", "Plan d'action clôturé : {{ intitule }}", "Le plan d'action est clôturé.", "Aucune.", (R,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("pa_reouvert", "Plan d'action rouvert : {{ intitule }}", "Le plan d'action a été rouvert.", "Reprendre le traitement.", (R, FC), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("efficacite_a_controler", "Contrôle d'efficacité : {{ intitule }}", "Un contrôle d'efficacité est à réaliser.", "Réaliser le contrôle d'efficacité.", (R,), "Normale", 0, "Temporel", 0, 7, 2, 0),
	("criticite_modifiee", "Criticité modifiée : {{ intitule }}", "La criticité de l'obligation a été modifiée.", "Vérifier l'impact sur les échéances et alertes.", (PO, FC), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("responsable_modifie", "Nouveau responsable : {{ intitule }}", "Vous êtes désigné responsable.", "Prendre en charge l'objet.", (R,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("source_nouvelle_version", "Nouvelle version de texte : {{ intitule }}", "Une nouvelle version d'une source réglementaire a été enregistrée.", "Analyser l'impact sur les obligations.", (FC, "Rôle:OR Analyste Réglementaire"), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("source_entree_vigueur", "Entrée en vigueur : {{ intitule }}", "Une source réglementaire entre en vigueur.", "Vérifier l'activation des obligations liées.", (FC, "Rôle:OR Analyste Réglementaire"), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("impact_a_analyser", "Analyse d'impact requise : {{ intitule }}", "Une évolution réglementaire nécessite une analyse d'impact.", "Réaliser l'analyse d'impact.", ("Rôle:OR Analyste Réglementaire",), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("analyse_impact_creee", "Analyse d'impact créée : {{ intitule }}", "Une analyse d'impact a été ouverte.", "Compléter l'analyse.", (R, FC), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("modele_mis_a_jour", "Modèle d'obligation mis à jour : {{ intitule }}", "Un modèle du catalogue a évolué.", "Décider de l'application de la mise à jour.", (FC,), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("document_a_supprimer", "Document arrivé en fin de conservation : {{ intitule }}", "La durée de conservation est atteinte.", "Décider de la destruction ou de la prolongation.", ("Rôle:OR Gestionnaire Documentaire",), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("rapport_a_controler", "Rapport à contrôler : {{ intitule }}", "Un rapport attend votre contrôle.", "Contrôler le rapport.", ("Rôle:OR Contrôleur",), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("rapport_a_valider", "Rapport à valider : {{ intitule }}", "Un rapport attend votre validation.", "Valider ou rejeter le rapport.", (VA, "Rôle:OR Responsable Conformité"), "Normale", 0, "Immédiat", None, 0, 0, 0),
	("rapport_rejete", "Rapport rejeté : {{ intitule }}", "Le rapport a été rejeté.", "Corriger le rapport.", (R,), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("rapport_diffuse", "Rapport diffusé : {{ intitule }}", "Un rapport vous a été diffusé.", "Prendre connaissance du rapport.", (R,), "Information", 0, "Immédiat", None, 0, 0, 0),
	("rapport_echec", "Échec de génération de rapport : {{ intitule }}", "La génération automatique d'un rapport a échoué.", "Vérifier le modèle et relancer la génération.", ("Rôle:OR Gestionnaire Reporting",), "Élevée", 0, "Immédiat", None, 0, 0, 0),
	("licence_expiration_proche", "Licence bientôt expirée : {{ intitule }}", "Une licence / un agrément arrive à expiration.", "Engager le renouvellement.", (R, FC), "Élevée", 0, "Temporel", -90, 30, 2, 0),
)


def notification_setup():
	_ensure("Reg Notification Template", "ESCALADE", {"code": "ESCALADE", "titre": "Escalade", "actif": 1, "version": 1,
		"action_attendue": "Intervenir pour débloquer la situation.",
		"sujet": "[Escalade niveau {{ niveau }} — {{ palier }}] {{ intitule }}",
		"corps": _BODY.format(texte="Escalade : l'objet ci-dessous n'est pas traité dans les délais.",
			action="Intervenir pour débloquer la situation.")})
	_ensure("Reg Notification Template", "RESUME_QUOTIDIEN", {"code": "RESUME_QUOTIDIEN", "titre": "Résumé quotidien", "actif": 1,
		"version": 1, "sujet": "Votre résumé conformité du jour", "corps": "<p>{{ resume }}</p>"})
	for (event, sujet, texte, action, cibles, prio, accuse, mode, jours, relance, max_rel, selon_crit) in NOTIFICATIONS:
		code = event.upper()
		_ensure("Reg Notification Template", code, {"code": code, "titre": sujet.split(" :")[0], "actif": 1, "version": 1,
			"action_attendue": action, "contenu_confidentiel_email": 0, "sujet": sujet,
			"corps": _BODY.format(texte=texte, action=action)})
		dest = []
		for c in cibles:
			if c.startswith("Rôle:"):
				dest.append({"cible": "Rôle", "role": c.split(":", 1)[1]})
			else:
				dest.append({"cible": c})
		_ensure("Reg Notification Rule", code, {"code": code, "libelle": sujet.split(" :")[0], "evenement": event, "mode": mode,
			"statut": "Active", "version": 1, "jours_relatifs": jours, "frequence_relance_jours": relance, "max_relances": max_rel,
			"priorite": prio, "priorite_selon_criticite": selon_crit, "canal_application": 1, "canal_email": 1, "modele": code,
			"accuse_requis": accuse, "obligatoire": 1 if prio in ("Élevée", "Critique") else 0,
			"groupable": 1 if prio in ("Information",) else 0, "destinataires": dest})


def escalation_rules():
	_ensure("Reg Escalation Rule", "Échéances critiques", {"nom": "Échéances critiques", "objet": "Échéance", "actif": 1, "criticite": "Critique",
		"paliers": [
			{"niveau": 1, "jours_relatifs": -7, "cible": MG, "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 2, "jours_relatifs": -2, "cible": RD, "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 3, "jours_relatifs": 1, "cible": "Fonction conformité", "canal": "Application + E-mail", "priorite": "Critique"},
			{"niveau": 4, "jours_relatifs": 5, "cible": DG, "canal": "Application + E-mail", "priorite": "Critique"},
		]})
	_ensure("Reg Escalation Rule", "Échéances élevées", {"nom": "Échéances élevées", "objet": "Échéance", "actif": 1, "criticite": "Élevée",
		"paliers": [
			{"niveau": 1, "jours_relatifs": -3, "cible": MG, "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 2, "jours_relatifs": 3, "cible": "Fonction conformité", "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 3, "jours_relatifs": 15, "cible": RD, "canal": "Application + E-mail", "priorite": "Critique"},
		]})
	_ensure("Reg Escalation Rule", "Actions correctives en retard", {"nom": "Actions correctives en retard", "objet": "Action corrective", "actif": 1,
		"paliers": [
			{"niveau": 1, "jours_relatifs": 3, "cible": MG, "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 2, "jours_relatifs": 15, "cible": "Fonction conformité", "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 3, "jours_relatifs": 30, "cible": RD, "canal": "Application + E-mail", "priorite": "Critique"},
		]})
	_ensure("Reg Escalation Rule", "Plans d'action en retard", {"nom": "Plans d'action en retard", "objet": "Plan d'action", "actif": 1,
		"paliers": [
			{"niveau": 1, "jours_relatifs": 1, "cible": "Fonction conformité", "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 2, "jours_relatifs": 30, "cible": DG, "canal": "Application + E-mail", "priorite": "Critique"},
		]})
	_ensure("Reg Escalation Rule", "Non-conformités non traitées", {"nom": "Non-conformités non traitées", "objet": "Non-conformité", "actif": 1,
		"paliers": [
			{"niveau": 1, "jours_relatifs": 1, "cible": "Fonction conformité", "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 2, "jours_relatifs": 30, "cible": DG, "canal": "Application + E-mail", "priorite": "Critique"},
		]})
	_ensure("Reg Escalation Rule", "Justificatifs non resoumis", {"nom": "Justificatifs non resoumis", "objet": "Justificatif", "actif": 1,
		"paliers": [
			{"niveau": 1, "jours_relatifs": 1, "cible": "Responsable de l'objet", "canal": "Application + E-mail", "priorite": "Élevée"},
			{"niveau": 2, "jours_relatifs": 5, "cible": MG, "canal": "Application + E-mail", "priorite": "Élevée"},
		]})


# ------------------------------------------------------------------ indicateurs et rapports
UP, DOWN = "Plus haut est mieux", "Plus bas est mieux"
INDICATORS = (
	("taux_conformite", "Taux de conformité", "%", UP, 90, 80, "Part des échéances échues réalisées dans les délais parmi les échéances échues de la période.",
		"Échéances réalisées à temps / échéances échues (hors annulées, suspendues)"),
	("taux_conformite_pondere", "Taux de conformité pondéré", "%", UP, 90, 80, "Taux de conformité pondéré par la criticité des obligations (Critique 4, Élevée 3, Moyenne 2, Faible 1).",
		"Σ poids des échéances conformes / Σ poids des échéances échues"),
	("obligations_actives", "Obligations actives", "Nombre", UP, None, None, "Nombre d'obligations au statut Active.", None),
	("obligations_non_evaluees", "Obligations non évaluées", "Nombre", DOWN, 1, 5, "Obligations actives dont l'état de conformité n'est pas encore évalué.", None),
	("echeances_en_retard", "Échéances en retard", "Nombre", DOWN, 1, 5, "Échéances dont la date limite est dépassée sans réalisation validée.", None),
	("taux_retard_echeances", "Taux de retard des échéances", "%", DOWN, 5, 10, "Part des échéances échues réalisées en retard ou non réalisées.", None),
	("echeances_7_jours", "Échéances à 7 jours", "Nombre", DOWN, None, None, "Échéances ouvertes arrivant à terme dans les 7 prochains jours.", None),
	("justificatifs_attendus", "Justificatifs attendus", "Nombre", DOWN, None, None, "Justificatifs obligatoires non encore fournis.", None),
	("justificatifs_en_controle", "Justificatifs en contrôle", "Nombre", DOWN, 10, 25, "Justificatifs déposés en attente de contrôle.", None),
	("taux_rejet_justificatifs", "Taux de rejet des justificatifs", "%", DOWN, 10, 25, "Part des contrôles de justificatifs aboutissant à un rejet.", None),
	("delai_moyen_validation_justificatifs", "Délai moyen de validation des justificatifs", "Jours", DOWN, 5, 10, "Délai moyen entre dépôt et validation d'un justificatif.", None),
	("justificatifs_expires", "Justificatifs expirés", "Nombre", DOWN, 1, 5, "Justificatifs dont la date de fin de validité est dépassée.", None),
	("nc_ouvertes", "Non-conformités ouvertes", "Nombre", DOWN, 5, 15, "Non-conformités non clôturées.", None),
	("nc_critiques_ouvertes", "Non-conformités critiques ouvertes", "Nombre", DOWN, 1, 3, "Non-conformités de gravité Critique non clôturées.", None),
	("nc_anciennete_moyenne", "Ancienneté moyenne des NC", "Jours", DOWN, 30, 90, "Ancienneté moyenne des non-conformités ouvertes.", None),
	("pa_ouverts", "Plans d'action ouverts", "Nombre", DOWN, None, None, "Plans d'action non clôturés.", None),
	("pa_critiques_ouverts", "Plans d'action critiques ouverts", "Nombre", DOWN, 1, 3, "Plans d'action de criticité Critique non clôturés.", None),
	("pa_en_retard", "Plans d'action en retard", "Nombre", DOWN, 1, 5, "Plans d'action dont la date cible est dépassée.", None),
	("taux_realisation_pa", "Taux de réalisation des actions", "%", UP, 80, 60, "Part des actions correctives validées parmi les actions non annulées.", None),
	("actions_en_retard", "Actions correctives en retard", "Nombre", DOWN, 3, 10, "Actions correctives dont la date de fin prévue est dépassée.", None),
	("actions_bloquees", "Actions bloquées", "Nombre", DOWN, 1, 5, "Actions correctives au statut Bloquée.", None),
	("prolongations_en_attente", "Prolongations en attente", "Nombre", DOWN, 3, 10, "Demandes de prolongation non encore décidées.", None),
	("pa_prolonges_plusieurs_fois", "Plans prolongés plusieurs fois", "Nombre", DOWN, 1, 3, "Plans d'action ayant fait l'objet de plusieurs prolongations.", None),
	("taux_reouverture_pa", "Taux de réouverture des plans", "%", DOWN, 5, 15, "Part des plans d'action clôturés puis rouverts.", None),
	("obligations_sans_responsable", "Obligations sans responsable", "Nombre", DOWN, 1, 3, "Obligations actives sans propriétaire ni responsable opérationnel.", None),
	("sources_sans_obligation", "Sources sans obligation", "Nombre", DOWN, 5, 20, "Sources en vigueur auxquelles aucune obligation n'est rattachée.", None),
)


def indicators():
	for methode, libelle, unite, sens, vig, alerte, definition, formule in INDICATORS:
		code = methode.upper()
		_ensure("Reg Indicator", code, {"code": code, "libelle": libelle, "methode": methode, "unite": unite, "sens": sens,
			"seuil_vigilance": vig, "seuil_alerte": alerte, "actif": 1, "definition": definition, "formule": formule})


def report_templates():
	_ensure("Reg Report Template", "TDB-DG", {"code": "TDB-DG", "intitule": "Tableau de bord conformité — Direction Générale",
		"categorie": "Direction Générale", "statut": "Actif", "version": 1, "frequence": "Mensuel", "generation_automatique": 1,
		"circuit_validation": 1, "format_sortie": "PDF + Excel", "confidentialite": "Confidentiel",
		"description": "Synthèse mensuelle : conformité, retards, non-conformités et plans d'action critiques.",
		"sections": [
			{"ordre": 1, "titre": "Synthèse", "type_section": "Indicateurs", "source_donnees": "Synthèse"},
			{"ordre": 2, "titre": "Taux de conformité pondéré", "type_section": "Indicateurs", "source_donnees": "Indicateur", "indicateur": "TAUX_CONFORMITE_PONDERE"},
			{"ordre": 3, "titre": "Échéances en retard", "type_section": "Tableau", "source_donnees": "Échéances", "limite": 50},
			{"ordre": 4, "titre": "Non-conformités ouvertes", "type_section": "Tableau", "source_donnees": "Non-conformités", "limite": 50},
			{"ordre": 5, "titre": "Plans d'action", "type_section": "Tableau", "source_donnees": "Plans d'action", "limite": 50},
		]})
	_ensure("Reg Report Template", "SUIVI-OPS", {"code": "SUIVI-OPS", "intitule": "Suivi opérationnel des échéances et justificatifs",
		"categorie": "Opérationnel", "statut": "Actif", "version": 1, "frequence": "Hebdomadaire", "generation_automatique": 0,
		"circuit_validation": 0, "format_sortie": "Excel", "confidentialite": "Interne",
		"sections": [
			{"ordre": 1, "titre": "Échéances", "type_section": "Tableau", "source_donnees": "Échéances", "limite": 500},
			{"ordre": 2, "titre": "Justificatifs", "type_section": "Tableau", "source_donnees": "Justificatifs", "limite": 500},
			{"ordre": 3, "titre": "Actions correctives", "type_section": "Tableau", "source_donnees": "Actions", "limite": 500},
		]})
	_ensure("Reg Report Template", "RAPPORT-CONF", {"code": "RAPPORT-CONF", "intitule": "Rapport de conformité réglementaire",
		"categorie": "Conformité", "statut": "Actif", "version": 1, "frequence": "Trimestriel", "generation_automatique": 0,
		"circuit_validation": 1, "format_sortie": "PDF + Excel", "confidentialite": "Confidentiel",
		"sections": [
			{"ordre": 1, "titre": "Synthèse", "type_section": "Indicateurs", "source_donnees": "Synthèse"},
			{"ordre": 2, "titre": "Obligations", "type_section": "Tableau", "source_donnees": "Obligations", "limite": 1000},
			{"ordre": 3, "titre": "Échéances", "type_section": "Tableau", "source_donnees": "Échéances", "limite": 1000},
			{"ordre": 4, "titre": "Non-conformités", "type_section": "Tableau", "source_donnees": "Non-conformités", "limite": 500},
			{"ordre": 5, "titre": "Plans d'action", "type_section": "Tableau", "source_donnees": "Plans d'action", "limite": 500},
			{"ordre": 6, "titre": "Prolongations", "type_section": "Tableau", "source_donnees": "Prolongations", "limite": 200},
			{"ordre": 7, "titre": "Commentaire de la fonction conformité", "type_section": "Texte", "source_donnees": "Texte libre"},
		]})
	_ensure("Reg Report Template", "AUDIT-QUALITE", {"code": "AUDIT-QUALITE", "intitule": "Qualité du référentiel et performance du dispositif",
		"categorie": "Audit et contrôle", "statut": "Actif", "version": 1, "frequence": "Semestriel", "generation_automatique": 0,
		"circuit_validation": 1, "format_sortie": "PDF", "confidentialite": "Confidentiel",
		"sections": [
			{"ordre": 1, "titre": "Qualité des données", "type_section": "Tableau", "source_donnees": "Qualité des données"},
			{"ordre": 2, "titre": "Performance du processus", "type_section": "Indicateurs", "source_donnees": "Performance du processus"},
		]})


# ------------------------------------------------------------------ print formats
_REPORT_INSTANCE_PRINT_HTML = """
<div class="reg-print">
  <style>
    .reg-print { font-size: 12px; }
    .reg-print .reg-meta { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
    .reg-print .reg-meta td { padding: 3px 6px; border: 1px solid #ddd; }
    .reg-print .reg-meta td.reg-label { font-weight: bold; width: 160px; background: #f7f7f7; }
    .reg-print .reg-statut { display: inline-block; padding: 2px 10px; border-radius: 10px;
      font-weight: bold; background: #eef1f8; }
    .reg-print .reg-circuit { width: 100%; border-collapse: collapse; margin-top: 16px; }
    .reg-print .reg-circuit td, .reg-print .reg-circuit th { border: 1px solid #ddd; padding: 5px 8px; }
    .reg-print .reg-circuit th { background: #f7f7f7; text-align: left; }
    .reg-print .reg-reserves { margin-top: 10px; padding: 8px; background: #fff8e6; border: 1px solid #f0d998; }
    .reg-print table.table { width: 100%; border-collapse: collapse; margin: 8px 0 14px; }
    .reg-print table.table th, .reg-print table.table td { border: 1px solid #ddd; padding: 4px 6px; font-size: 11px; }
    .reg-print table.table th { background: #f0f0f0; }
    .reg-print h2 { font-size: 18px; margin-bottom: 4px; }
    .reg-print h3 { font-size: 14px; margin-top: 16px; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
  </style>

  <table class="reg-meta">
    <tr>
      <td class="reg-label">Statut</td>
      <td><span class="reg-statut">{{ doc.statut }}</span></td>
      <td class="reg-label">Version</td>
      <td>{{ doc.version }}{% if doc.officiel %} (officiel){% endif %}{% if doc.fige %} — données figées{% endif %}</td>
    </tr>
    <tr>
      <td class="reg-label">Organisation</td>
      <td>{{ doc.organisation }}</td>
      <td class="reg-label">Modèle</td>
      <td>{{ doc.modele }} (v{{ doc.version_modele }})</td>
    </tr>
    <tr>
      <td class="reg-label">Période</td>
      <td>{{ frappe.utils.formatdate(doc.date_debut) }} → {{ frappe.utils.formatdate(doc.date_fin) }}</td>
      <td class="reg-label">Situation arrêtée au</td>
      <td>{{ frappe.utils.formatdate(doc.date_arrete) }}</td>
    </tr>
    <tr>
      <td class="reg-label">Généré le</td>
      <td>{{ frappe.utils.format_datetime(doc.date_generation) if doc.date_generation else "—" }}</td>
      <td class="reg-label">Généré par</td>
      <td>{{ doc.genere_par or "—" }}</td>
    </tr>
  </table>

  {{ doc.resultat_html or "<p><i>Aucune donnée générée pour cette version.</i></p>" }}

  {% if doc.reserves %}
  <div class="reg-reserves"><b>Réserves :</b> {{ doc.reserves }}</div>
  {% endif %}

  {% if doc.motif_rejet %}
  <div class="reg-reserves"><b>Motif de rejet :</b> {{ doc.motif_rejet }}</div>
  {% endif %}

  <table class="reg-circuit">
    <tr><th>Étape</th><th>Intervenant</th><th>Date</th></tr>
    <tr><td>Préparation</td><td>{{ doc.preparateur or "—" }}</td><td>{{ frappe.utils.format_datetime(doc.date_generation) if doc.date_generation else "—" }}</td></tr>
    <tr><td>Contrôle</td><td>{{ doc.controleur or "—" }}</td><td>{{ frappe.utils.format_datetime(doc.date_controle) if doc.date_controle else "—" }}</td></tr>
    <tr><td>Validation</td><td>{{ doc.validateur or "—" }}</td><td>{{ frappe.utils.format_datetime(doc.date_validation) if doc.date_validation else "—" }}</td></tr>
  </table>
</div>
"""


def print_formats():
	_ensure("Print Format", "Rapport réglementaire OR", {
		"name": "Rapport réglementaire OR",
		"doc_type": "Reg Report Instance", "module": "Obligation Reglementaire",
		"standard": "No", "custom_format": 1, "print_format_type": "Jinja",
		"disabled": 0, "align_labels_right": 0, "font_size": 12,
		"html": _REPORT_INSTANCE_PRINT_HTML,
	})
