// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Template Update Notice", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.statut === "Décidée") return;
		if (!or_reg.has_role(...or_reg.COMPLIANCE, "OR Analyste Réglementaire")) return;
		frm.add_custom_button(__("Appliquer la décision"), () => {
			if (!frm.doc.decision) {
				frappe.msgprint(__("Choisissez d'abord une décision."));
				return;
			}
			frm.save().then(() => or_reg.call(frm, "decide_template_notice",
				{ notice: frm.doc.name, decision: frm.doc.decision, justification: frm.doc.justification }));
		}).addClass("btn-primary");
	},
});
