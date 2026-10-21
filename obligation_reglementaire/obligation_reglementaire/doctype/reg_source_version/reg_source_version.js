// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Source Version", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		frm.add_custom_button(__("Comparer avec une autre version"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Comparaison de versions"),
				fields: [{ fieldname: "autre", fieldtype: "Link", options: "Reg Source Version", label: __("Version à comparer"), reqd: 1,
					get_query: () => ({ filters: { source: frm.doc.source, name: ["!=", frm.doc.name] } }) }],
				primary_action(v) {
					d.hide();
					frappe.call({ method: or_reg.API + "compare_source_versions", args: { version_a: v.autre, version_b: frm.doc.name }, freeze: true,
						callback: (r) => r.message && frappe.set_route("Form", "Reg Version Comparison", r.message.name || r.message) });
				},
			});
			d.show();
		}, __("Analyse"));
		frm.add_custom_button(__("Créer une analyse d'impact"), () => frappe.call({
			method: or_reg.API + "create_impact_analysis", args: { version: frm.doc.name }, freeze: true,
			callback: (r) => frappe.set_route("Form", "Reg Impact Analysis", r.message),
		}), __("Analyse"));
	},
});
