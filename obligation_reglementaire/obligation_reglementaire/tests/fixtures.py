"""Fixtures partagées pour les tests unitaires de l'app obligation_reglementaire.

Nom choisi volontairement hors du motif `test_*.py` : Frappe scanne `**/test_*.py`
pour découvrir les suites de tests, et ce module n'en est pas une — seulement des
fabriques réutilisées par les vraies suites (`test_reg_*.py` dans chaque dossier
de doctype).

IMPORTANT (sécurité) : `make_user` n'accepte que des adresses `@test.local`. Ne
jamais attribuer de rôle OR à un compte réel (notamment `@gmail.com`).
"""

import frappe

TEST_DOMAIN = "test.local"


def uniq(prefix):
	return f"{prefix}{frappe.generate_hash(length=8)}"


def ensure_role(role_name):
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)
	return role_name


def make_user(email, roles=None, full_name=None):
	if not email.endswith("@" + TEST_DOMAIN):
		frappe.throw("Les comptes de test doivent utiliser le domaine @test.local")
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc({
			"doctype": "User",
			"email": email,
			"first_name": full_name or email.split("@")[0],
			"send_welcome_email": 0,
		}).insert(ignore_permissions=True)
	existing = {r.role for r in user.roles}
	changed = False
	for role in roles or []:
		ensure_role(role)
		if role not in existing:
			user.append("roles", {"role": role})
			changed = True
	if changed:
		user.save(ignore_permissions=True)
	return user.name


def make_organization(statut="Active", code=None):
	code = code or uniq("ORG")
	doc = frappe.get_doc({
		"doctype": "Reg Organization",
		"code": code,
		"nom_legal": f"Organisation {code}",
		"nom_affichage": f"Organisation {code}",
		"pays": "Ivory Coast",
		"statut": statut,
	}).insert(ignore_permissions=True)
	return doc.name


def make_criticality(poids, libelle=None):
	"""`actif=0` : la contrainte d'unicité du poids ne s'applique qu'entre niveaux
	actifs, et le poids réel est importé tel quel par `criticality_weight()` quel
	que soit `actif` — ceci évite toute collision avec les niveaux déjà en base."""
	libelle = libelle or uniq("Niveau")
	doc = frappe.get_doc({
		"doctype": "Reg Criticality Level",
		"libelle": libelle,
		"code": libelle,
		"poids": poids,
		"actif": 0,
	}).insert(ignore_permissions=True)
	return doc.name


def make_domain(nom=None):
	code = uniq("DOM")
	doc = frappe.get_doc({
		"doctype": "Reg Domain",
		"code": code,
		"nom": nom or code,
	}).insert(ignore_permissions=True)
	return doc.name


def make_org_unit(organisation, nom=None):
	code = uniq("UNIT")
	doc = frappe.get_doc({
		"doctype": "Reg Org Unit",
		"code": code,
		"nom_unite": nom or code,
		"organisation": organisation,
	}).insert(ignore_permissions=True)
	return doc.name


def make_source_type():
	libelle = uniq("TypeSource")
	doc = frappe.get_doc({"doctype": "Reg Source Type", "libelle": libelle}).insert(ignore_permissions=True)
	return doc.name


def make_authority():
	sigle = uniq("AUT")
	doc = frappe.get_doc({
		"doctype": "Reg Authority",
		"sigle": sigle,
		"nom_officiel": f"Autorité {sigle}",
	}).insert(ignore_permissions=True)
	return doc.name


def make_source(type_source=None, autorite=None):
	# `pays` a pour défaut JSON "Cote d'Ivoire", qui ne correspond à aucun Country
	# existant (le pays réel est "Ivory Coast") : on le force explicitement.
	ref = uniq("REF")
	doc = frappe.get_doc({
		"doctype": "Reg Source",
		"reference_officielle": ref,
		"titre_officiel": f"Texte officiel {ref}",
		"titre_court": ref,
		"type_source": type_source or make_source_type(),
		"autorite": autorite or make_authority(),
		"pays": "Ivory Coast",
	}).insert(ignore_permissions=True)
	return doc.name


def make_document_type():
	libelle = uniq("TypeDoc")
	doc = frappe.get_doc({"doctype": "Reg Document Type", "libelle": libelle}).insert(ignore_permissions=True)
	return doc.name


def make_evidence_type():
	libelle = uniq("TypeJust")
	doc = frappe.get_doc({
		"doctype": "Reg Evidence Type",
		"libelle": libelle,
		"code": libelle,
	}).insert(ignore_permissions=True)
	return doc.name


def make_rejection_reason():
	code = uniq("MOTIF")
	doc = frappe.get_doc({
		"doctype": "Reg Rejection Reason",
		"code": code,
		"libelle": f"Motif {code}",
	}).insert(ignore_permissions=True)
	return doc.name


def make_evidence_version(evidence, **kwargs):
	"""Crée une version factice (sans I/O réel : `fichier` n'est jamais lu par le
	contrôleur à l'insertion) et la pose comme version courante du justificatif."""
	evidence_name = evidence if isinstance(evidence, str) else evidence.name
	values = {
		"doctype": "Reg Evidence Version",
		"justificatif": evidence_name,
		"fichier": f"/files/{uniq('test-evidence-')}.txt",
	}
	values.update(kwargs)
	version = frappe.get_doc(values).insert(ignore_permissions=True)
	frappe.db.set_value("Reg Evidence", evidence_name, "version_courante", version.name)
	return version.name


def make_report_template(statut="Actif"):
	code = uniq("TPL")
	doc = frappe.get_doc({
		"doctype": "Reg Report Template",
		"code": code,
		"intitule": f"Modèle {code}",
		"categorie": "Conformité",
		"statut": statut,
		"sections": [{"titre": "Synthèse", "source_donnees": "Synthèse"}],
	}).insert(ignore_permissions=True)
	return doc.name


class CommonFixtures:
	"""Mixin : fournit un socle de référence partagé (organisation, criticités,
	domaine, unité, source, types, utilisateurs de test) à chaque suite."""

	@classmethod
	def setup_common_fixtures(cls):
		cls.org = make_organization()
		cls.crit_low = make_criticality(poids=1)
		cls.crit_high = make_criticality(poids=4)
		cls.domain = make_domain()
		cls.unit = make_org_unit(cls.org)
		cls.source = make_source()
		cls.doc_type = make_document_type()
		cls.evidence_type = make_evidence_type()
		cls.user_a = make_user(f"{uniq('or-a-')}@{TEST_DOMAIN}",
			roles=["OR Responsable Conformité", "OR Contrôleur", "OR Administrateur"])
		cls.user_b = make_user(f"{uniq('or-b-')}@{TEST_DOMAIN}",
			roles=["OR Responsable Conformité", "OR Contrôleur", "OR Administrateur"])

	def make_obligation(self, **kwargs):
		values = {
			"doctype": "Reg Obligation",
			"organisation": self.org,
			"titre": uniq("Obligation "),
			"criticite": self.crit_low,
			"source": self.source,
			"domaine": self.domain,
			"nature_temporelle": "Permanente",
			"date_debut": frappe.utils.nowdate(),
			"direction": self.unit,
			"proprietaire": self.user_a,
			# `justificatif_requis` vaut 1 par défaut : sans ceci, le passage à
			# Validée/Active échoue (« Au moins un justificatif doit être obligatoire »).
			"justificatifs": [{"type_justificatif": self.evidence_type, "libelle": uniq("Justificatif "),
				"obligatoire": 1, "actif": 1}],
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_deadline(self, obligation, **kwargs):
		values = {
			"doctype": "Reg Deadline",
			"organisation": self.org,
			"obligation": obligation if isinstance(obligation, str) else obligation.name,
			"libelle": uniq("Échéance "),
			"date_limite": frappe.utils.add_days(frappe.utils.nowdate(), 10),
			"responsable": self.user_a,
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_evidence(self, obligation, **kwargs):
		values = {
			"doctype": "Reg Evidence",
			"organisation": self.org,
			"obligation": obligation if isinstance(obligation, str) else obligation.name,
			"type_justificatif": self.evidence_type,
			"libelle": uniq("Justificatif "),
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_evidence_review(self, evidence, controleur=None, **kwargs):
		"""La `version` est obligatoire et ne s'auto-remplit qu'à partir de
		`version_courante` : on pose donc toujours une version avant d'insérer."""
		evidence_name = evidence if isinstance(evidence, str) else evidence.name
		version_courante = frappe.db.get_value("Reg Evidence", evidence_name, "version_courante")
		if not version_courante:
			version_courante = make_evidence_version(evidence_name)
		values = {
			"doctype": "Reg Evidence Review",
			"justificatif": evidence_name,
			"version": version_courante,
			"controleur": controleur or self.user_b,
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_non_conformity(self, gravite=None, **kwargs):
		values = {
			"doctype": "Reg Non Conformity",
			"organisation": self.org,
			"intitule": uniq("NC "),
			"origine": "Détection manuelle",
			"gravite": gravite or self.crit_low,
			"responsable": self.user_a,
			"description": "Description du constat.",
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_action_plan(self, **kwargs):
		values = {
			"doctype": "Reg Action Plan",
			"organisation": self.org,
			"intitule": uniq("Plan "),
			"origine": "Audit interne",
			"criticite": self.crit_low,
			"domaine": self.domain,
			"direction": self.unit,
			"responsable": self.user_a,
			"date_cible": frappe.utils.add_days(frappe.utils.nowdate(), 30),
			"description": "Description du plan.",
			"constat_texte": "Constat à l'origine du plan.",
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_corrective_action(self, plan, **kwargs):
		values = {
			"doctype": "Reg Corrective Action",
			"plan": plan if isinstance(plan, str) else plan.name,
			"intitule": uniq("Action "),
			"responsable": self.user_a,
			"date_fin_prevue": frappe.utils.add_days(frappe.utils.nowdate(), 20),
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_document(self, **kwargs):
		values = {
			"doctype": "Reg Document",
			"organisation": self.org,
			"titre": uniq("Document "),
			"type_document": self.doc_type,
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_report_instance(self, modele=None, **kwargs):
		today = frappe.utils.nowdate()
		values = {
			"doctype": "Reg Report Instance",
			"modele": modele or make_report_template(),
			"organisation": self.org,
			"intitule": uniq("Rapport "),
			"type_periode": "Mensuel",
			"date_debut": frappe.utils.add_months(today, -1),
			"date_fin": today,
			"date_arrete": today,
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def make_config_change_request(self, **kwargs):
		values = {
			"doctype": "Reg Config Change Request",
			"objet": uniq("Changement "),
			"cible_doctype": "Reg Criticality Level",
			"cible_nom": self.crit_low,
			"justification": "Justification du changement.",
			"valeurs_proposees": frappe.as_json({"delai_escalade_jours": 5}),
		}
		values.update(kwargs)
		return frappe.get_doc(values).insert(ignore_permissions=True)
