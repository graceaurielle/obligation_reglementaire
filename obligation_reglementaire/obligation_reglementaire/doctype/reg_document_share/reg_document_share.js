// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Document Share", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.statut !== "Actif") return;
		or_reg.btn(frm, "Révoquer le partage", "revoke_share", { share: frm.doc.name }, { confirm: "Révoquer ce lien de partage ?" });
	},
});
