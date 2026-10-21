// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

const EXT_LABELS = { "Acceptée": "Accepter", "Refusée": "Refuser", "Informations demandées": "Demander des informations" };

frappe.ui.form.on("Reg Extension Request", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new() || !["Demandée", "Informations demandées"].includes(frm.doc.statut)) return;
		if (!or_reg.has_role(...or_reg.COMPLIANCE, "OR Validateur")) return;
		const f = [{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") }];
		Object.keys(EXT_LABELS).forEach((dec) =>
			or_reg.btn(frm, EXT_LABELS[dec], "decide_extension", { name: frm.doc.name, decision: dec }, { group: "Décision", fields: f }));
	},
});
