// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Evidence Review", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.set_intro(__("Renseignez le résultat de chaque point de contrôle puis validez le contrôle (Soumettre)."), "blue");
		}
	},
});
