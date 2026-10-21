// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Profile", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Évaluer l'applicabilité"), () => frappe.call({
			method: or_reg.API + "evaluate_profile", args: { profile: frm.doc.name }, freeze: true,
			callback(r) {
				const m = r.message;
				frappe.msgprint(__("{0} proposition(s) générée(s).", [Array.isArray(m) ? m.length : (m || 0)]));
				frm.reload_doc();
			},
		})).addClass("btn-primary");
		frm.add_custom_button(__("Propositions"), () => frappe.set_route("List", "Reg Applicability Proposal", { profil: frm.doc.name }), __("Voir"));
	},
});
