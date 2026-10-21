// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Document Version", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new() || !["Soumise", "En contrôle"].includes(frm.doc.statut)) return;
		if (!or_reg.has_role(...or_reg.COMPLIANCE, "OR Contrôleur", "OR Validateur", "OR Gestionnaire Documentaire")) return;
		const n = frm.doc.name;
		or_reg.btn(frm, "Valider la version", "validate_document_version", { version: n, accepter: 1 },
			{ group: "Contrôle", fields: [{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") }] });
		or_reg.btn(frm, "Rejeter la version", "validate_document_version", { version: n, accepter: 0 },
			{ group: "Contrôle", fields: [{ fieldname: "motif_rejet", fieldtype: "Small Text", label: __("Motif du rejet"), reqd: 1 }] });
	},
});
