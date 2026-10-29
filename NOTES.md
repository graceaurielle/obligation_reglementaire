# Obligation Réglementaire — Notes de développement

> App GRC Frappe v16 — site `compliance` — module "Obligation Reglementaire"

---

## Architecture

### DocTypes (111)

Chemin : `obligation_reglementaire/obligation_reglementaire/doctype/`

**Principaux (non-enfants) :**

| Catégorie | DocTypes |
|---|---|
| Obligations & échéances | Reg Obligation, Reg Deadline, Reg Deadline Change, Reg Deadline Dependency, Reg Deadline Suspension |
| Justificatifs | Reg Evidence, Reg Evidence Review (submittable), Reg Evidence Version, Reg Evidence Usage, Reg Evidence Type |
| Non-conformités & plans | Reg Non Conformity, Reg Action Plan, Reg Corrective Action, Reg Action Proof, Reg Extension Request, Reg Finding, Reg Effectiveness Check, Reg Compliance Check |
| Sources réglementaires | Reg Source, Reg Source Version, Reg Impact Analysis, Reg Version Comparison |
| Applicabilité | Reg Profile, Reg Applicability Proposal, Reg Applicability Decision, Reg Applicability Criterion, Reg Template Obligation, Reg Template Update Notice |
| GED | Reg Document, Reg Document Version, Reg Document Share, Reg Document Category, Reg Document Type, Reg Retention Rule |
| Rapports | Reg Report Instance, Reg Report Template |
| Organisation | Reg Organization, Reg Org Unit, Reg Member, Reg Governance Mandate, Reg License, Reg Authority |
| Notifications | Reg Notification Log, Reg Notification Rule, Reg Notification Template, Reg Escalation Rule |
| Paramétrage | Reg Settings, Reg Config Change Request, Reg Criticality Level, Reg Calendar, Reg Domain, Reg Indicator |

### Rôles (11)

```
OR Administrateur
OR Responsable Conformité
OR Analyste Réglementaire
OR Responsable Obligation
OR Contributeur
OR Contrôleur
OR Validateur
OR Auditeur
OR Direction Générale
OR Gestionnaire Reporting
OR Gestionnaire Documentaire
```

---

## Backend Python

### api.py (~50 endpoints)

| Groupe | Fonctions principales |
|---|---|
| Obligations | `obligation_transition`, `obligation_update_with_justification`, `generate_deadlines`, `deadline_preview`, `create_obligation_from_template` |
| Échéances | `deadline_action` (demarrer/soumettre/valider/rejeter/non_conforme/suspendre/reprendre/annuler…), `request_deadline_change`, `decide_deadline_change` |
| Justificatifs | `deposit_evidence`, `start_evidence_review`, `replace_evidence`, `add_evidence`, `cancel_evidence`, `reuse_evidence` |
| NC & plans | `finding_to_nc`, `create_plan_from_nc`, `close_nc`, `plan_action` (ouvrir/demander_cloture/valider/refuser/annuler…), `corrective_action`, `review_action_proof`, `decide_extension` |
| Applicabilité | `evaluate_profile`, `decide_proposal`, `decide_template_notice` |
| Sources | `compare_source_versions`, `create_impact_analysis`, `source_duplicates` |
| GED | `add_document_version`, `validate_document_version`, `document_action`, `share_document`, `revoke_share`, `shared_document` (guest) |
| Rapports | `report_action` (generer/soumettre/controler/valider/diffuser/transmettre/accuse/cloturer…) |
| Config | `config_action` |
| Notifications | `simulate_notification`, `acknowledge`, `mark_read` |
| Dashboard | `dashboard`, `indicator_value`, `my_tasks`, `export_audit_trail`, `run_daily_now` |

### tasks.py

- `daily()` : 15 étapes isolées (chaque erreur est journalisée sans bloquer les suivantes)
  1. Génération des échéances → Statuts → NC sur retard
  2. Expiration justificatifs → Contrôles en retard → Plans d'action
  3. Licences/mandats → Sources entrées en vigueur → GED
  4. Alertes → Relances → Escalades → Annulation relances résolues
  5. Rapports planifiés → Historique indicateurs
- `daily_digest()` : cron 7h — résumé quotidien
- `hourly()` : renvoi des notifications en échec

### events.py

Hooks globaux sur tous les `Reg *` (sauf child tables) :
- `validate` → `common.before_validate`
- `on_update` → `common.audit_changes` (Reg Audit Log)
- `on_trash` → `forbid_delete`
- `before_save` → protection du Reg Audit Log

### install.py

Seed data idempotent (`_ensure` ne remplace jamais un enregistrement existant) :
- Rôles, paramètres par défaut (Reg Settings)
- 4 niveaux de criticité (Critique 4, Élevée 3, Moyenne 2, Faible 1)
- Arbre de 15 domaines réglementaires sous racine TOUS
- Calendrier "Calendrier standard" avec jours fériés CI
- 58 règles de notification + 6 règles d'escalade
- 26 indicateurs, 4 modèles de rapport
- 14 types de justificatifs, listes de référence

### engine/ (12 modules)

| Module | Responsabilité |
|---|---|
| `common.py` | `check_transition`, `assert_sod`, `require_text`, `require_roles`, `log_audit`, `forbid_delete`, `SystemAction`, `criticality_weight` |
| `calendar.py` | Calendrier ouvré, ajustement des jours non ouvrés |
| `deadline.py` | Génération d'échéances, `period_start` (alignement civil), statuts automatiques, NC sur retard |
| `evidence.py` | Dépôt (empreinte SHA-256, détection doublons), contrôle, expiration |
| `action_plan.py` | Progression pondérée, blocages de clôture, vérification d'efficacité |
| `notification.py` | Émission, alertes, escalade, digest, retry |
| `indicators.py` | Calcul et snapshot des 26 indicateurs |
| `reporting.py` | Génération de rapports, circuit de validation, transmission |
| `source.py` | Gestion des sources, comparaison de versions |
| `applicability.py` | Évaluation de profils, propositions, décisions |
| `ged.py` | Gestion documentaire, versionnement, partage par token |
| `config.py` | Circuit de validation des changements de paramétrage |

---

## Frontend JavaScript

### Fichier commun — `public/js/obligation_reglementaire.js`

Chargé via `app_include_js`. Fournit l'objet global `or_reg` :
- `or_reg.call(frm, method, args, message)` — appel API + rechargement
- `or_reg.btn(frm, label, method, args, {group, fields, confirm})` — bouton d'action avec dialogue optionnel
- `or_reg.motif(label, reqd)` — champ motif réutilisable
- `or_reg.has_role(...roles)`, `or_reg.is_compliance()` — vérification de rôle
- `or_reg.indicator(frm)` — indicateur coloré selon le statut
- `or_reg.COMPLIANCE` — `["OR Administrateur", "OR Responsable Conformité", "System Manager"]`

### 23 formulaires enrichis

Chaque formulaire ajoute des boutons contextuels selon le statut et le rôle de l'utilisateur. Les boutons appellent les endpoints de `api.py`.

---

## 8 Script Reports

Chemin : `obligation_reglementaire/report/`

| Rapport | DocType de référence | Description |
|---|---|---|
| Échéances par horizon | Reg Deadline | Répartition temporelle avec graphique en barres |
| Taux de conformité | Reg Deadline | Par domaine/unité/responsable/criticité, pondéré ou non |
| Suivi des plans d'action | Reg Action Plan | Statuts, réalisation, retards, prolongations |
| Qualité du référentiel | Reg Obligation | Score de complétude des fiches |
| Exposition aux risques | Reg Obligation | Score criticité × retards × NC ouvertes |
| À traiter aujourd'hui | Reg Deadline | Vue consolidée multi-rôle des tâches urgentes |
| Prolongations et reports | Reg Extension Request | Historique des demandes et décisions |
| Suivi des justificatifs | Reg Evidence | Dépôts, contrôles en retard, expirations |

---

## Workspace et Sidebar

- **Workspace** : `obligation_reglementaire/workspace/obligation_reglementaire/obligation_reglementaire.json` — 12 groupes de liens, 6 raccourcis
- **Sidebar** : `workspace_sidebar/obligation_reglementaire.json` — 12 sections repliables

---

## Patterns et conventions

| Pattern | Mécanisme |
|---|---|
| Transition de statut | `check_transition(doc, TRANSITIONS_DICT)` dans `validate()` |
| Séparation des tâches | `assert_sod(doc, "proprietaire", "responsable_operationnel")` |
| Texte obligatoire | `require_text(value, label)` |
| Rôles requis | `require_roles(*roles)` |
| Audit automatique | `log_audit(message, doctype, name)` → Reg Audit Log |
| Suppression bloquée | `forbid_delete(doc, method)` — contournable avec `frappe.flags.reg_allow_delete = True` |
| Actions système | `with SystemAction():` → pose `frappe.flags.reg_system = True` |
| Modifications sensibles | `doc.flags.reg_justification = "texte"` permet les champs gelés |
| NestedSet | Reg Domain, Reg Document Category, Reg Retention Rule — multiple roots autorisées |

---

## Cycle de vie et relais entre rôles

Qui déclenche quoi, et à qui la main passe ensuite. `COMPLIANCE_ROLES` = OR Administrateur + OR
Responsable Conformité (quasi-partout habilités, en plus du rôle "métier" indiqué).

| Objet | Déclenché par | Relais vers | Fonction / action |
|---|---|---|---|
| **Obligation** | OR Analyste Réglementaire (création depuis modèle) | OR Validateur / Compliance (transition vers Validée/Archivée/Obsolète uniquement — les autres statuts sont libres) | `create_obligation_from_template`, `obligation_transition` |
| **Échéance** | OR Responsable Obligation / Contributeur (démarrer, soumettre) | le valideur désigné, OR Validateur, OR Contrôleur ou Compliance (valider/rejeter/non-conforme) ; Compliance seul pour dérogation/rouvrir/annuler | `deadline_action` (demarrer/attente/soumettre/valider/rejeter/non_conforme/cloturer/rouvrir/annuler/suspendre/reprendre) |
| **Report de date d'échéance** | tout porteur avec accès write (demande) | OR Validateur / Compliance (décision) | `request_deadline_change` → `decide_deadline_change` |
| **Justificatif** | OR Contributeur / OR Responsable Obligation (dépôt) | OR Contrôleur / OR Validateur / Compliance (prise en charge du contrôle) | `deposit_evidence` → `start_evidence_review` → `submit_evidence_review` (déclenche `validate()`/`on_submit` : NC automatique possible en cas de rejet) |
| **Non-conformité** | automatique (retard/rejet) ou OR Auditeur (`finding_to_nc` depuis un Reg Finding) | OR Responsable Obligation (analyser/traiter/mesure compensatoire) puis Compliance + OR Validateur (clôture) | `nc_action` (analyser/traiter/mesure_compensatoire/verifier/annuler), `close_nc` |
| **Plan d'action** | OR Responsable Obligation (création depuis la NC, pilotage) | OR Validateur / Compliance (valider_cloture/refuser_cloture/rouvrir/annuler) | `create_plan_from_nc`, `plan_action` |
| **Action corrective** | OR Responsable Obligation / Contributeur (démarrer, soumettre) | le contrôleur désigné, OR Contrôleur, OR Validateur ou Compliance (valider/retourner) | `corrective_action` |
| **Preuve d'action** | l'exécutant de l'action (dépôt) | le contrôleur désigné (accepter/rejeter/compléter — séparation des tâches : le déposant ne peut pas se contrôler lui-même) | `review_action_proof` |
| **Prolongation de délai** | tout porteur avec accès write (demande) | OR Validateur / Compliance (décision) | `request_extension` → `decide_extension` |
| **Document (GED)** | OR Gestionnaire Documentaire (dépôt/nouvelle version) | OR Contrôleur / OR Validateur / OR Gestionnaire Documentaire (validation de version) ; publier ouvert à tout accès write ; geler/dégeler/supprimer réservés à Gestionnaire Documentaire + Compliance (geler aussi ouvert à l'Auditeur) | `add_document_version` → `validate_document_version`, `document_action` |
| **Rapport réglementaire** | OR Gestionnaire Reporting (générer, soumettre) | OR Contrôleur / OR Auditeur (contrôler) puis OR Validateur / OR Direction Générale (validation finale) ; diffusion/transmission ensuite par Gestionnaire Reporting | `report_action` (generer/soumettre/controler/valider/rejeter/diffuser/transmettre/accuse/cloturer) |
| **Demande de changement de paramétrage** | tout porteur habilité (proposer) | OR Responsable Conformité / OR Contrôleur (contrôler, SoD vs proposant) → OR Administrateur / OR Responsable Conformité (valider, SoD vs proposant+contrôleur) → OR Administrateur seul (activer) | `config_action` (`engine/config.py` : Proposée → Contrôlée → Validée → Activée) |
| **Proposition d'applicabilité / avis de modèle** | automatique ou analyste | OR Analyste Réglementaire / Compliance (décision) | `decide_proposal`, `decide_template_notice` |

**À retenir** : l'UI (boutons JS, nav du portail) n'est qu'un indice d'ergonomie — le seul rempart
réel est `api.py::_doc()` (permission Frappe du doctype) + les `require_roles`/`has_any_role` dans
chaque fonction + les dicos `*_TRANSITIONS` (`check_transition`, `engine/*.py`). Un bouton visible
peut toujours échouer côté serveur si le DocPerm sous-jacent manque — c'était exactement le bug
corrigé ci-dessous pour OR Gestionnaire Documentaire.

---

## Comptes de test (environnement `compliance`)

Tous les comptes ci-dessous sont en `@test.local`, mot de passe commun **`Test@1234!`**. Ne
jamais attribuer de rôle OR au compte réel de l'utilisateur (`@gmail.com`) — uniquement ces
comptes de test.

| Rôle | Compte |
|---|---|
| OR Administrateur | or.admin@test.local |
| OR Responsable Conformité | or.conf@test.local |
| OR Analyste Réglementaire | or.analyste@test.local |
| OR Responsable Obligation | or.resp@test.local (porte aussi OR Contributeur) |
| OR Contributeur | or.resp@test.local |
| OR Contrôleur | or.ctrl@test.local |
| OR Validateur | or.valid@test.local |
| OR Auditeur | or.audit@test.local |
| OR Direction Générale | or.dg@test.local |
| OR Gestionnaire Reporting | or.report@test.local |
| OR Gestionnaire Documentaire | or.doc@test.local |

### Correctif oct. 2026 : permissions OR Gestionnaire Documentaire

Audit complet des `DocPerm` des 11 rôles : seul OR Gestionnaire Documentaire avait **zéro**
permission réelle (0 doctype), malgré son usage dans les gardes de rôle de `document_action`
(geler/dégeler/supprimer) et `validate_document_version`. Corrigé par ajout de permissions dans :
- `reg_document.json`, `reg_document_version.json`, `reg_document_share.json` : create/write/share/read
- `reg_document_category.json`, `reg_document_type.json` : lecture seule (référentiels)
- `portal_common.py` (`_NAV_PAR_ROLE`) : ajout de l'onglet `obligations-documents` pour ce rôle

Vérifié en conditions réelles (HTTP, compte `or.doc@test.local`) : accès à `/obligations-documents`,
ouverture Desk de `Reg Document`, listage réel via `frappe.client.get_list` (permission effective
en base, pas seulement apparente).

---

## Scénario de test E2E

```bash
# Copier le script depuis le scratchpad puis exécuter :
bench --site compliance execute obligation_reglementaire._scenario.run
```

Couvre : création obligation → SoD → échéances → justificatifs → contrôle → NC automatique → plan d'action → action corrective → clôture → dashboard.

**Dernier run : ✅ complet** (132 notifications, 92 entrées d'audit)

---

## Portail web (www/)

Architecture calquée sur `contract_te` : même page de connexion partagée `/vconnexion` (due_diligence),
mais atterrissage sur des pages différentes selon le rôle OR.

- **`portal_common.py`** : rôles (pilotage/opérationnels/contrôle/supervision), `_NAV_PAR_ROLE`
  (contrôle l'accès par page et par rôle), `base_context()` (auth + injection des variables
  communes), `resolve_portal_access()`, `user_org_filter()`, `est_operationnel_seul()`,
  `resoudre_noms(rows, *fields)` (résout un ID utilisateur en nom complet — **indispensable**
  car Jinja sandboxé n'expose pas `frappe.utils.get_fullname`, seulement `frappe.utils.formatdate`
  et consorts ; `frappe.get_fullname` existe mais seulement au niveau racine, pas sous `.utils`).
- **`website.py`** : hook `update_website_context` (déclaré dans `hooks.py`) qui injecte un lien
  « Obligations réglementaires » dans les portails DD et CT (sens inverse de la passerelle).
- **`templates/includes/or_list_page.html`** : template Jinja partagé par toutes les pages liste
  (stats, tableau avec colonnes `badge`/`date`/`percent`/`link_prefix`, responsive mobile).

### Pages (7)

| Route | Fichiers | Contenu |
|---|---|---|
| `/obligations` | `obligations.py` + `.html` | Dashboard : 9 KPI, horizons d'échéances, échéances urgentes, NC récentes |
| `/obligations-echeances` | `obligations_echeances.py` + `.html` | Échéances ouvertes |
| `/obligations-justificatifs` | `obligations_justificatifs.py` + `.html` | Justificatifs en souffrance |
| `/obligations-nc` | `obligations_nc.py` + `.html` | Non-conformités ouvertes |
| `/obligations-plans` | `obligations_plans.py` + `.html` | Plans d'action ouverts |
| `/obligations-sources` | `obligations_sources.py` + `.html` | Sources réglementaires (hors rôles opérationnels) |
| `/obligations-notifications` | `obligations_notifications.py` + `.html` | Notifications de l'utilisateur |

**Piège résolu** : Frappe résout le contrôleur Python d'une page www en remplaçant les `-` par des
`_` dans le nom de fichier (`page_name.replace("-", "_") + ".py"`, voir `frappe/website/router.py`),
alors que le `.html` garde les tirets. Les fichiers `.py` doivent donc impérativement être nommés
avec des underscores (`obligations_echeances.py`, pas `obligations-echeances.py`), sinon le
contrôleur n'est jamais chargé et la page tourne sans son `get_context` (variables manquantes,
pas d'auth appliquée). Vérifié contre le même piège potentiel dans `contract_te` (déjà correct
là-bas : `contrats-echeances.html` + `contrats_echeances.py`).

**Validé** : tests directs de `get_context()` pour les 4 rôles de test (`or.resp`, `or.ctrl`,
`or.valid`, `or.conf`) + tests HTTP réels (login + GET) sur les 7 pages — 200 partout, redirection
301 correcte vers `/app` pour les rôles sans accès à `obligations-sources`.

---

## Améliorations possibles

- [x] Tableaux de bord graphiques — voir « Tableaux de bord graphiques » ci-dessous
- [ ] Traductions FR complètes (fichier .csv)
- [x] Tests unitaires Python (`test_*.py` par doctype) — voir « Tests unitaires Python » ci-dessous
- [x] Print formats pour les rapports réglementaires — voir « Print formats » ci-dessous
- [ ] Intégration e-mail réelle pour les notifications
- [ ] Permissions par organisation (User Permission sur Reg Organization)
- [x] Import en masse d'obligations depuis Excel/CSV — voir « Import en masse » ci-dessous

---

## Tableaux de bord graphiques

Implémentés directement dans le dashboard du portail web (`www/obligations.py` + `.html`), **pas**
en `Dashboard Chart`/`Number Card` Frappe natifs (le workspace Desk n'a aucun chart : `"charts":
[]` dans `obligation_reglementaire.json`) — choix cohérent avec le reste du portail (pages
autonomes, sans dépendance JS externe).

- **Bar chart horizontal** « Horizons d'échéances » (`get_context`, fonction inline) : compte les
  `Reg Deadline` non closes par tranche (Échues, Aujourd'hui, 1–7 j, 8–15 j, 16–30 j, 31–60 j,
  > 60 j), normalisé en `%` sur le maximum, coloré par urgence (rouge = échues, orange = ≤ 7 j,
  vert = reste) — palette statut réservée (`_GOOD`/`_WARNING`/`_CRITICAL`), jamais recyclée en
  décoration.
- **Donut chart SVG** « Répartition des obligations par statut » (`_donut_segments()`) : calcule
  les segments via la technique `stroke-dasharray`/`stroke-dashoffset` sur un cercle SVG
  (`viewBox="0 0 160 160"`, rayon 70), couleurs catégorielles fixes par statut
  (`_STATUT_COLOR`, ordre jamais recyclé en fonction des données affichées).
- Les deux respectent le périmètre utilisateur (`user_org_filter`, `est_operationnel_seul` →
  filtre sur `responsable` pour les rôles purement opérationnels).
- Le reste du dashboard (score de complétude, score de risque, etc.) reste couvert par les 8
  Script Reports existants, qui ont leurs propres graphiques Frappe natifs (`chart_type:
  "bar"` dans leur JSON).

---

## Print formats

Un print format Jinja personnalisé est livré pour **Reg Report Instance** : `"Rapport
réglementaire OR"` (`doc_type: Reg Report Instance`, `print_format_type: Jinja`, `standard: No`).

Il n'apparaît dans aucun fichier `print_format.json` : il est créé par code, de façon idempotente,
dans `install.py::print_formats()` (appelée par `after_install`/`after_migrate`, même mécanisme
que les rôles métier — voir note en tête de `install.py`), via `_ensure("Print Format", ...)`.
C'est pour cette raison qu'une recherche `find . -iname "*print_format*"` ne trouve rien : il n'y
a pas de fichier dédié, seulement un dict Python (`_REPORT_INSTANCE_PRINT_HTML`) injecté en base à
l'installation/migration de l'app. Entête (métadonnées, tableau des dates clés), corps (statut,
synthèse), et un tableau « circuit » (préparation/contrôle/validation avec intervenant + date)
repris du cycle de vie réel du rapport.

---

## Import en masse (Excel/CSV)

Endpoint whitelisté `obligation_reglementaire.api.import_obligations(file_url)`, réservé à
`COMPLIANCE_ROLES` + OR Analyste Réglementaire.

- **Formats acceptés** : `.csv` (lu via `read_csv_content`) et `.xlsx`/`.xls` (via
  `read_xlsx_file_from_attached_file`).
- **Colonnes reconnues** : par nom de champ *ou* par libellé Frappe, insensible à la casse
  (`_import_header_map()` construit la correspondance depuis le meta de `Reg Obligation`).
  Obligatoires : `organisation`, `titre`, `criticite`, `source`, `domaine`, `direction`,
  `proprietaire`, `date_debut`. Optionnelles : `description`, `nature_temporelle`, `frequence`,
  `intervalle`, `intervalle_unite`, `date_fixe`, `evenement_declencheur`, `delai_valeur`,
  `delai_unite`, `date_fin`, `sous_domaine`, `autorite`, `type_obligation`, `applicabilite`,
  `responsable_operationnel`, `referent_conformite`.
- Les champs Link sont vérifiés (`frappe.db.exists`) avant insertion ; les dates et entiers sont
  convertis au bon type.
- **Erreur par ligne, pas par lot** : chaque ligne est insérée indépendamment dans un `try/except`
  — une ligne en échec n'empêche pas les suivantes (`{"crees": [...], "erreurs": [{"ligne":
  ..., "erreur": ...}]}` en retour). Un audit (`log_audit`) trace le nombre de créations/échecs.
- Pas de bouton Desk dédié (« Importer » sur la liste `Reg Obligation`) — l'appel se fait via
  l'API ou la méthode standard Frappe « Import » (Data Import) sur le doctype ; non demandé à ce
  stade.

---

## Tests unitaires Python

10 fichiers `test_*.py`, un par doctype métier principal, placés **à côté** du contrôleur/`.json`
dans le dossier du doctype (pas dans un dossier `tests/` centralisé) :

```
doctype/reg_obligation/test_reg_obligation.py
doctype/reg_deadline/test_reg_deadline.py
doctype/reg_action_plan/test_reg_action_plan.py
doctype/reg_corrective_action/test_reg_corrective_action.py
doctype/reg_evidence/test_reg_evidence.py
doctype/reg_evidence_review/test_reg_evidence_review.py
doctype/reg_non_conformity/test_reg_non_conformity.py
doctype/reg_document/test_reg_document.py
doctype/reg_report_instance/test_reg_report_instance.py
doctype/reg_config_change_request/test_reg_config_change_request.py
```

**Fixtures communes** : `obligation_reglementaire/tests/fixtures.py`, classe `CommonFixtures` à
mélanger (`class TestXxx(IntegrationTestCase, CommonFixtures)`) + `setUpClass` appelant
`cls.setup_common_fixtures()`. Fournit des `make_xxx()` par doctype (organisation, obligation,
échéance, justificatif, plan, action, document, rapport, demande de config) et deux utilisateurs
de test (`self.user_a`, `self.user_b`) pour exercer la séparation des tâches.

**Garde de sécurité dans `make_user()`** : lève `frappe.throw` si l'e-mail ne finit pas par
`@test.local` — aucun rôle OR ne peut être attribué par les fixtures à un compte réel
(`@gmail.com`), y compris par erreur de copier-coller dans un futur test.

**Lancer les tests** :
```bash
# Un seul module
bench --site compliance run-tests --app obligation_reglementaire \
  --module obligation_reglementaire.obligation_reglementaire.doctype.reg_document.test_reg_document

# Toute la suite
bench --site compliance run-tests --app obligation_reglementaire
```
Dernier run complet : **54 tests, 0 échec** (~27 s), aucune interférence entre suites.

**Pièges rencontrés (à relire avant d'écrire un nouveau test)** :
1. **`TimestampMismatchError`** (deux causes) : (a) réutiliser un doc après un `.save()` externe
   sans `.reload()` ; (b) appeler deux fonctions métier à la suite sur le même objet sans recharger
   entre les deux.
2. **Incohérence de type de date** : `get_doc_before_save()` recharge les champs `Date` en objets
   `date`, alors qu'un champ posé juste après l'insertion peut encore être une chaîne — un
   `plan.reload()` avant le premier changement de statut évite une comparaison toujours fausse
   (ex. `reg_action_plan.py` exigeant à tort une prolongation).
3. **`flags.ignore_permissions` persistant** : `insert(ignore_permissions=True)` pose
   `self.flags.ignore_permissions = True` **pour toute la vie de l'objet Python** — un `.reload()`
   ne réinitialise pas les `flags`, seulement les champs. Pour tester un garde-fou qui inspecte ce
   flag (ex. `_on_status_change` de `reg_corrective_action.py`), il faut repartir d'un objet
   **fraîchement récupéré** via `frappe.get_doc(doctype, name)`, jamais réutiliser l'instance de
   la fixture.
4. **Validation déclenchée dès `insert()`, pas seulement `save()`** : une règle sans condition de
   statut (ex. cohérence de période dans `reg_report_instance.py`) se déclenche dès la création —
   il faut englober l'appel à la fixture elle-même dans `assertRaises`, pas seulement un `.save()`
   ultérieur.
5. **Dépôt de fichier réel requis** : `check_document_file`/`file_fingerprint` lisent le contenu
   via `File.get_content()` — un `file_url` fictif ne suffit pas, il faut un vrai document `File`
   (`frappe.get_doc({"doctype": "File", ...}).insert(ignore_permissions=True)`).
- [ ] Import en masse d'obligations depuis Excel/CSV
