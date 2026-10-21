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

- [ ] Tableaux de bord graphiques (Number Card / Chart sur le workspace)
- [ ] Traductions FR complètes (fichier .csv)
- [ ] Tests unitaires Python (`test_*.py` par doctype)
- [ ] Print formats pour les rapports réglementaires
- [ ] Intégration e-mail réelle pour les notifications
- [ ] Permissions par organisation (User Permission sur Reg Organization)
- [ ] Import en masse d'obligations depuis Excel/CSV
