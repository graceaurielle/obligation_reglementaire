// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Source", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		frm.add_custom_button(__("Rechercher des doublons"), () => frappe.call({
			method: or_reg.API + "source_duplicates", args: { source_name: frm.doc.name },
			callback(r) {
				const rows = r.message || [];
				frappe.msgprint({ title: __("Doublons potentiels"), indicator: rows.length ? "orange" : "green",
					message: rows.length ? rows.map((x) => {
						const name = x.name || x;
						return `• <a href="/app/reg-source/${encodeURIComponent(name)}">${frappe.utils.escape_html(x.titre_officiel || name)}</a>`;
					}).join("<br>") : __("Aucun doublon détecté.") });
			},
		}), __("Analyse"));
		frm.add_custom_button(__("Versions"), () => frappe.set_route("List", "Reg Source Version", { source: frm.doc.name }), __("Voir"));
		frm.add_custom_button(__("Obligations"), () => frappe.set_route("List", "Reg Obligation", { source: frm.doc.name }), __("Voir"));
	},
});
