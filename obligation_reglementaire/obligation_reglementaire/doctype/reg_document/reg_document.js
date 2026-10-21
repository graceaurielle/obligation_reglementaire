// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Document", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut, A = (label, action, opts) =>
			or_reg.btn(frm, label, "document_action", { document: n, action: action }, Object.assign({ group: "Actions" }, opts || {}));
		if (!["Supprimé logiquement", "Archivé"].includes(st)) {
			or_reg.btn(frm, "Nouvelle version", "add_document_version", { document: n }, { group: "Actions", fields: [
				{ fieldname: "file_url", fieldtype: "Attach", label: __("Fichier"), reqd: 1 },
				{ fieldname: "type_version", fieldtype: "Select", label: __("Type de version"), options: "Mineure\nMajeure", default: "Mineure" },
				{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") }] });
		}
		if (["Brouillon", "Rejeté"].includes(st)) A("Soumettre", "soumettre");
		if (st === "Validé") A("Publier", "publier");
		if (["Validé", "Publié", "Expiré"].includes(st)) A("Archiver", "archiver", { confirm: "Archiver ce document ?" });
		if (frm.doc.gel) A("Lever le gel", "degeler", { fields: or_reg.motif() });
		else A("Gel juridique", "geler", { fields: or_reg.motif("Motif du gel") });
		if (st !== "Supprimé logiquement") A("Supprimer (logique)", "supprimer", { fields: or_reg.motif("Motif de suppression") });
		if (["Validé", "Publié"].includes(st)) {
			or_reg.btn(frm, "Partager (lien temporaire)", "share_document", { document: n }, { group: "Partage", fields: [
				{ fieldname: "destinataire", fieldtype: "Data", options: "Email", label: __("Destinataire"), reqd: 1 },
				{ fieldname: "date_expiration", fieldtype: "Date", label: __("Expire le"), reqd: 1 },
				{ fieldname: "motif", fieldtype: "Small Text", label: __("Motif") }] });
		}
		frm.add_custom_button(__("Versions"), () => frappe.set_route("List", "Reg Document Version", { document: n }), __("Voir"));
		frm.add_custom_button(__("Partages"), () => frappe.set_route("List", "Reg Document Share", { document: n }), __("Voir"));
	},
});
