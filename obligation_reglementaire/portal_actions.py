"""Table d'indices de boutons pour les pages de détail du portail web (www/).

Ceci ne fait qu'orienter l'affichage. Les dicos `*_TRANSITIONS` des modules `engine/*.py` et les
contrôles de rôle/SoD dans `api.py` restent la seule source de vérité : un bouton affiché ici peut
toujours être rejeté par le serveur (rôle insuffisant, transition invalide, blocage métier), et la
page doit afficher proprement ce rejet (voir `messageErreur()` côté client), jamais planter.

Chaque entrée : {"action": <valeur envoyée au endpoint>, "label": <texte du bouton>,
"roles": <tuple de rôles additionnels requis, ou None si ouvert à tout porteur d'un rôle OR
ayant le droit d'écriture sur le document>, "danger": <True pour un style visuel d'alerte>,
"needs_motif": <True si un motif/commentaire est demandé avant l'appel>}."""

from obligation_reglementaire.portal_common import OR_ROLES_PILOTAGE

COMPLIANCE_ROLES = tuple(OR_ROLES_PILOTAGE)

DEADLINE_ACTIONS = {
	"À venir": [{"action": "demarrer", "label": "Démarrer"}],
	"À traiter": [
		{"action": "demarrer", "label": "Démarrer"},
		{"action": "attente", "label": "Mettre en attente", "needs_motif": True},
		{"action": "soumettre", "label": "Soumettre pour validation"},
	],
	"En cours": [
		{"action": "attente", "label": "Mettre en attente", "needs_motif": True},
		{"action": "soumettre", "label": "Soumettre pour validation"},
		{"action": "suspendre", "label": "Suspendre", "needs_motif": True},
	],
	"En attente": [
		{"action": "soumettre", "label": "Soumettre pour validation"},
		{"action": "suspendre", "label": "Suspendre", "needs_motif": True},
	],
	"En retard": [
		{"action": "soumettre", "label": "Soumettre pour validation"},
		{"action": "suspendre", "label": "Suspendre", "needs_motif": True},
	],
	"Soumise pour validation": [
		{"action": "valider", "label": "Valider"},
		{"action": "rejeter", "label": "Rejeter", "needs_motif": True, "danger": True},
		{"action": "non_conforme", "label": "Non conforme", "needs_motif": True, "danger": True},
	],
	"Non conforme": [
		{"action": "soumettre", "label": "Soumettre pour validation"},
	],
	"Réalisée": [{"action": "cloturer", "label": "Clôturer"}],
	"Réalisée en retard": [{"action": "cloturer", "label": "Clôturer"}],
	"Clôturée": [{"action": "rouvrir", "label": "Rouvrir", "roles": COMPLIANCE_ROLES, "needs_motif": True}],
	"Suspendue": [{"action": "reprendre", "label": "Reprendre"}],
}
# Annuler : visible pour tout statut non final, réservé à la conformité.
DEADLINE_FINAL = ("Réalisée", "Réalisée en retard", "Clôturée", "Annulée")
DEADLINE_ANNULER = {"action": "annuler", "label": "Annuler", "roles": COMPLIANCE_ROLES, "needs_motif": True, "danger": True}

EVIDENCE_ACTIONS = {
	"Attendu": [{"action": "deposit", "label": "Déposer"}],
	"Demandé": [{"action": "deposit", "label": "Déposer"}],
	"À fournir": [{"action": "deposit", "label": "Déposer"}],
	"Déposé": [
		{"action": "deposit", "label": "Déposer une nouvelle version"},
		{"action": "start_review", "label": "Prendre en charge pour contrôle", "roles": COMPLIANCE_ROLES + ("OR Contrôleur", "OR Validateur")},
	],
	"Soumis à nouveau": [
		{"action": "deposit", "label": "Déposer une nouvelle version"},
		{"action": "start_review", "label": "Prendre en charge pour contrôle", "roles": COMPLIANCE_ROLES + ("OR Contrôleur", "OR Validateur")},
	],
	"À compléter": [{"action": "deposit", "label": "Déposer une version corrigée"}],
	"Rejeté": [{"action": "deposit", "label": "Déposer une version corrigée"}],
	"Validé": [{"action": "replace", "label": "Remplacer", "needs_motif": True}],
	"Validé avec réserve": [{"action": "replace", "label": "Remplacer", "needs_motif": True}],
	"Expiré": [{"action": "replace", "label": "Remplacer", "needs_motif": True}],
}
EVIDENCE_LOCKED = ("Annulé", "Remplacé", "Archivé")
EVIDENCE_ANNULER = {"action": "cancel", "label": "Annuler", "roles": COMPLIANCE_ROLES, "needs_motif": True, "danger": True}

NC_ACTIONS = {
	"Ouverte": [
		{"action": "analyser", "label": "Analyser"},
		{"action": "traiter", "label": "Mettre en traitement"},
		{"action": "mesure_compensatoire", "label": "Mesure compensatoire"},
	],
	"En analyse": [
		{"action": "traiter", "label": "Mettre en traitement"},
		{"action": "mesure_compensatoire", "label": "Mesure compensatoire"},
	],
	"En traitement": [
		{"action": "mesure_compensatoire", "label": "Mesure compensatoire"},
		{"action": "verifier", "label": "Soumettre à vérification"},
	],
	"Mesure compensatoire en place": [
		{"action": "traiter", "label": "Reprendre le traitement"},
		{"action": "verifier", "label": "Soumettre à vérification"},
	],
	"En attente de vérification": [
		{"action": "traiter", "label": "Renvoyer en traitement"},
	],
	"Clôturée": [
		{"action": "traiter", "label": "Rouvrir (reprendre le traitement)", "roles": COMPLIANCE_ROLES},
	],
}
NC_FINAL = ("Annulée",)
NC_ANNULER = {"action": "annuler", "label": "Annuler", "roles": COMPLIANCE_ROLES, "needs_motif": True, "danger": True}
# Clôturer est un endpoint dédié (close_nc), pas une valeur de nc_action : visible dès que le
# statut n'est pas déjà "Clôturée"/"Annulée".
NC_CLOTURABLE_DEPUIS = ("Ouverte", "En analyse", "En traitement", "Mesure compensatoire en place", "En attente de vérification")


def deadline_buttons(statut):
	actions = list(DEADLINE_ACTIONS.get(statut, []))
	if statut not in DEADLINE_FINAL:
		actions.append(DEADLINE_ANNULER)
	return actions


def evidence_buttons(statut):
	actions = list(EVIDENCE_ACTIONS.get(statut, []))
	if statut not in EVIDENCE_LOCKED:
		actions.append(EVIDENCE_ANNULER)
	return actions


def nc_buttons(statut):
	actions = list(NC_ACTIONS.get(statut, []))
	if statut not in NC_FINAL and statut != "Clôturée":
		actions.append(NC_ANNULER)
	return actions


PLAN_ACTIONS = {
	"Brouillon": [{"action": "ouvrir", "label": "Ouvrir"}],
	"Ouvert": [
		{"action": "demander_cloture", "label": "Demander la clôture"},
		{"action": "bloquer", "label": "Bloquer", "needs_motif": True},
	],
	"En cours": [
		{"action": "demander_cloture", "label": "Demander la clôture"},
		{"action": "bloquer", "label": "Bloquer", "needs_motif": True},
	],
	"Bloqué": [{"action": "debloquer", "label": "Débloquer"}],
	"En attente de validation": [
		{"action": "valider_cloture", "label": "Valider la clôture", "roles": COMPLIANCE_ROLES + ("OR Validateur",)},
		{"action": "refuser_cloture", "label": "Refuser la clôture", "needs_motif": True, "danger": True,
			"roles": COMPLIANCE_ROLES + ("OR Validateur",)},
	],
	"Vérification d'efficacité": [
		{"action": "rouvrir", "label": "Rouvrir", "roles": COMPLIANCE_ROLES + ("OR Validateur",), "needs_motif": True},
	],
	"Clôturé": [
		{"action": "rouvrir", "label": "Rouvrir", "roles": COMPLIANCE_ROLES + ("OR Validateur",), "needs_motif": True},
	],
	"Réouvert": [
		{"action": "demander_cloture", "label": "Demander la clôture"},
		{"action": "bloquer", "label": "Bloquer", "needs_motif": True},
	],
}
# "En attente de preuves" : jamais affecté dans le code (confirmé par grep) — aucun bouton n'y mène
# ni n'en part volontairement.
PLAN_LOCKED = ("Clôturé", "Annulé")
PLAN_ANNULER = {"action": "annuler", "label": "Annuler", "roles": COMPLIANCE_ROLES, "needs_motif": True,
	"needs_categorie": True, "danger": True}


def plan_buttons(statut):
	actions = list(PLAN_ACTIONS.get(statut, []))
	if statut not in PLAN_LOCKED:
		actions.append(PLAN_ANNULER)
	return actions


ACTION_ACTIONS = {
	"Non commencée": [{"action": "demarrer", "label": "Démarrer"}],
	"Planifiée": [{"action": "demarrer", "label": "Démarrer"}],
	"En cours": [
		{"action": "soumettre", "label": "Soumettre à contrôle"},
		{"action": "bloquer", "label": "Bloquer", "needs_motif": True},
	],
	"Bloquée": [{"action": "demarrer", "label": "Reprendre"}],
	"Soumise à contrôle": [
		{"action": "valider", "label": "Valider", "roles": COMPLIANCE_ROLES + ("OR Contrôleur", "OR Validateur")},
		{"action": "retourner", "label": "Retourner pour correction", "needs_motif": True, "danger": True},
	],
	"Retour pour correction": [{"action": "soumettre", "label": "Soumettre à contrôle"}],
}
ACTION_FINAL = ("Annulée", "Validée")
ACTION_ANNULER = {"action": "annuler", "label": "Annuler", "needs_motif": True, "danger": True}


def action_buttons(statut):
	actions = list(ACTION_ACTIONS.get(statut, []))
	if statut not in ACTION_FINAL:
		actions.append(ACTION_ANNULER)
	return actions


# ================================================================== obligations
# Dérivée directement de OBLIGATION_TRANSITIONS (reg_obligation.py) : chaque bouton correspond à une
# transition réellement autorisée par le contrôleur, jamais une liste réinventée ici.
_OBLIGATION_ORDRE = ["Brouillon", "En qualification", "Validée", "Active", "Suspendue", "Clôturée", "Obsolète", "Archivée"]
_OBLIGATION_LABELS = {
	"Brouillon": "Repasser en brouillon",
	"En qualification": "Mettre en qualification",
	"Validée": "Valider",
	"Active": "Activer",
	"Suspendue": "Suspendre",
	"Clôturée": "Clôturer",
	"Obsolète": "Marquer obsolète",
	"Archivée": "Archiver",
}
# Motif obligatoire (cf. RegObligation._validate_status_requirements) et rôles restreints
# (cf. api.py::obligation_transition) pour certaines cibles.
_OBLIGATION_MOTIF_REQUIS = {"Clôturée", "Obsolète", "Suspendue"}
_OBLIGATION_ROLES_RESTREINTS = {"Validée", "Archivée", "Obsolète"}


def obligation_buttons(statut, transitions):
	"""`transitions` : le dico OBLIGATION_TRANSITIONS importé du contrôleur (source de vérité)."""
	cibles = sorted(transitions.get(statut, set()), key=lambda s: _OBLIGATION_ORDRE.index(s) if s in _OBLIGATION_ORDRE else 99)
	buttons = []
	for cible in cibles:
		b = {"action": cible, "label": _OBLIGATION_LABELS.get(cible, cible)}
		if cible in _OBLIGATION_MOTIF_REQUIS:
			b["needs_motif"] = True
		if cible in _OBLIGATION_ROLES_RESTREINTS:
			b["roles"] = COMPLIANCE_ROLES + ("OR Validateur",)
		if cible == "Archivée":
			b["danger"] = True
		buttons.append(b)
	return buttons


# ================================================================== documents (Reg Document)
# Dérivée de DOC_TRANSITIONS (engine/ged.py) et du corps réel de document_action() (api.py) :
# la vraie transition Soumis -> Validé/Rejeté passe par validate_document_version(), jamais par
# document_action -- "soumettre" ici ne fait que reposer le statut sur "Soumis" (dépôt manuel,
# sans passer par add_document_version). "En contrôle" n'est jamais affecté par aucun code (état
# mort) : aucun bouton n'y mène.
DOCUMENT_ACTIONS = {
	"Brouillon": [{"action": "soumettre", "label": "Soumettre"}],
	"Rejeté": [{"action": "soumettre", "label": "Resoumettre"}],
	"Validé": [
		{"action": "publier", "label": "Publier"},
		{"action": "soumettre", "label": "Repasser en soumission"},
		{"action": "archiver", "label": "Archiver", "danger": True},
	],
	"Publié": [
		{"action": "soumettre", "label": "Repasser en soumission"},
		{"action": "archiver", "label": "Archiver", "danger": True},
	],
	"Expiré": [
		{"action": "soumettre", "label": "Repasser en soumission"},
		{"action": "archiver", "label": "Archiver", "danger": True},
	],
}
# Geler/dégeler/supprimer logiquement : indépendants du statut documentaire (gel() travaille sur
# le drapeau doc.gel), seulement masqués une fois l'objet déjà "Supprimé logiquement".
DOCUMENT_GELER = {"action": "geler", "label": "Geler", "needs_motif": True,
	"roles": COMPLIANCE_ROLES + ("OR Gestionnaire Documentaire", "OR Auditeur")}
DOCUMENT_DEGELER = {"action": "degeler", "label": "Dégeler", "needs_motif": True,
	"roles": COMPLIANCE_ROLES + ("OR Gestionnaire Documentaire",)}
DOCUMENT_SUPPRIMER = {"action": "supprimer", "label": "Supprimer logiquement", "needs_motif": True, "danger": True,
	"roles": COMPLIANCE_ROLES + ("OR Gestionnaire Documentaire",)}


def document_buttons(statut, gel):
	actions = list(DOCUMENT_ACTIONS.get(statut, []))
	if statut != "Supprimé logiquement":
		actions.append(DOCUMENT_DEGELER if gel else DOCUMENT_GELER)
		actions.append(DOCUMENT_SUPPRIMER)
	return actions


# ================================================================== config (Reg Config Change Request)
# Dérivée de CONFIG_TRANSITIONS (engine/config.py) et des gardes de rôle réelles : controler ->
# require_roles("OR Responsable Conformité", "OR Contrôleur") dans config.control() lui-même
# (OR Administrateur en est exclu, contrairement aux autres actions -- confirmé par lecture directe
# de config.py), valider -> OR Administrateur/OR Responsable Conformité (SoD contre propose_par ET
# controle_par), activer -> OR Administrateur seul (aucun compte de test actuel ne porte ce rôle,
# confirmé par grep).
CONFIG_ACTIONS = {
	"Proposée": [{"action": "controler", "label": "Contrôler", "roles": ("OR Responsable Conformité", "OR Contrôleur")}],
	"Contrôlée": [{"action": "valider", "label": "Valider", "roles": ("OR Administrateur", "OR Responsable Conformité")}],
	"Validée": [{"action": "activer", "label": "Activer", "roles": ("OR Administrateur",)}],
}
CONFIG_FINAL = ("Activée", "Rejetée")
CONFIG_REJETER = {"action": "rejeter", "label": "Rejeter", "needs_motif": True, "danger": True,
	"roles": COMPLIANCE_ROLES + ("OR Contrôleur",)}


def config_buttons(statut):
	actions = list(CONFIG_ACTIONS.get(statut, []))
	if statut not in CONFIG_FINAL:
		actions.append(CONFIG_REJETER)
	return actions


# ================================================================== rapports (Reg Report Instance)
# Couvre uniquement les transitions à champ unique ou sans champ de report_action() (api.py) :
# generer, soumettre, controler, valider, rejeter, cloturer. "Contrôlé" et "Rejeté" sont des états
# transitoires jamais persistés (control()/reject() re-sauvegardent immédiatement vers "À valider"/
# "À corriger" dans le même appel) : aucun bouton n'y mène. diffuser/transmettre/accuse/
# rejet_autorite/nouvelle_version/exporter exigent des champs structurés (destinataires, dates,
# fichiers) et sont rendus par des mini-formulaires dédiés dans la page de détail, pas ici.
# Aucune action "archiver" n'existe côté serveur pour ce doctype malgré REPORT_TRANSITIONS :
# volontairement absent ci-dessous.
REPORT_SIMPLE_ACTIONS = {
	"Brouillon": [{"action": "generer", "label": "Générer"}],
	"Échec de génération": [{"action": "generer", "label": "Régénérer"}],
	"En préparation": [{"action": "soumettre", "label": "Soumettre pour circuit de validation"}],
	"À corriger": [{"action": "soumettre", "label": "Resoumettre pour circuit de validation"}],
	"À contrôler": [
		{"action": "controler", "label": "Contrôler", "roles": COMPLIANCE_ROLES + ("OR Contrôleur", "OR Auditeur")},
		{"action": "rejeter", "label": "Rejeter", "needs_motif": True, "danger": True},
	],
	"À valider": [
		{"action": "valider", "label": "Valider", "roles": COMPLIANCE_ROLES + ("OR Validateur", "OR Direction Générale")},
		{"action": "rejeter", "label": "Rejeter", "needs_motif": True, "danger": True},
	],
	"Validé": [{"action": "cloturer", "label": "Clôturer"}],
	"Diffusé": [{"action": "cloturer", "label": "Clôturer"}],
	"Transmis": [{"action": "cloturer", "label": "Clôturer"}],
	"Accusé réception obtenu": [{"action": "cloturer", "label": "Clôturer"}],
}


def report_simple_buttons(statut):
	return list(REPORT_SIMPLE_ACTIONS.get(statut, []))
