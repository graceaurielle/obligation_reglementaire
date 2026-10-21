// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Finding", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		if (frm.doc.non_conformite) {
			frm.add_custom_button(__("Non-conformité"), () => frappe.set_route("Form", "Reg Non Conformity", frm.doc.non_conformite), __("Voir"));
		} else if (["Ouvert", "Qualifié"].includes(frm.doc.statut)) {
			frm.add_custom_button(__("Transformer en non-conformité"), () => frappe.call({
				method: or_reg.API + "finding_to_nc", args: { finding: frm.doc.name }, freeze: true,
				callback: (r) => frappe.set_route("Form", "Reg Non Conformity", r.message),
			})).addClass("btn-primary");
		}
	},
});
