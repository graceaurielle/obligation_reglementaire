import frappe

from obligation_reglementaire.portal_common import base_context, detail_url

login_required = True
no_cache = 1


def get_context(context):
	user, role = base_context(context, active_page="obligations-notifications",
							  title="Notifications réglementaires")

	rows = frappe.get_all("Reg Notification Log", filters={
		"destinataire": user},
		fields=["name", "titre", "evenement", "statut", "lu", "accuse_requis",
				"date_accuse", "creation", "reference_doctype", "reference_name",
				"priorite"],
		order_by="creation desc", limit_page_length=200)

	non_lues = sum(1 for r in rows if not r.lu)
	accuse_en_attente = sum(1 for r in rows if r.accuse_requis and not r.date_accuse)

	for r in rows:
		r["lu_label"] = "Non lu" if not r.lu else "Lu"
		r["accuse_label"] = "En attente" if r.accuse_requis and not r.date_accuse else (
			"Fait" if r.date_accuse else "")
		r["lien_href"] = detail_url(r.reference_doctype, r.reference_name) if (
			r.reference_doctype and r.reference_name) else None
		r["lien_ref"] = r.reference_name if r.lien_href else ""
		r["detail_href"] = f"/obligations-notifications-detail?name={r.name}"

	context.page_title = "Notifications"
	context.columns = [
		{"label": "Notification", "key": "name", "href_key": "detail_href"},
		{"label": "Titre", "key": "titre"},
		{"label": "Objet lié", "key": "lien_ref", "href_key": "lien_href"},
		{"label": "Événement", "key": "evenement"},
		{"label": "Priorité", "key": "priorite", "badge": True},
		{"label": "Statut", "key": "statut", "badge": True},
		{"label": "Lu", "key": "lu_label", "badge": True},
		{"label": "Accusé", "key": "accuse_label", "badge": True},
		{"label": "Date", "key": "creation", "date": True},
	]
	context.rows = rows
	context.empty_message = "Aucune notification."
	context.stats = [
		{"label": "Non lues", "value": non_lues, "color": "#be185d"},
		{"label": "Accusé en attente", "value": accuse_en_attente, "color": "#d97706"},
		{"label": "Total", "value": len(rows), "color": "#64748b"},
	]
