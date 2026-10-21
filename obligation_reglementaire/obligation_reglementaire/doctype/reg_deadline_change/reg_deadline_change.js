// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Deadline Change", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new() || frm.doc.statut !== "Demandée") return;
		if (!or_reg.has_role(...or_reg.COMPLIANCE, "OR Validateur")) return;
		const f = [{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") }];
		or_reg.btn(frm, "Approuver", "decide_deadline_change", { name: frm.doc.name, decision: "Approuvée" }, { group: "Décision", fields: f });
		or_reg.btn(frm, "Refuser", "decide_deadline_change", { name: frm.doc.name, decision: "Refusée" }, { group: "Décision", fields: f });
	},
});
