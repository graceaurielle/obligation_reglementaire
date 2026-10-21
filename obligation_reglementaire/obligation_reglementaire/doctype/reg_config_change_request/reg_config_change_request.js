// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Config Change Request", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut, A = (label, action, opts) =>
			or_reg.btn(frm, label, "config_action", { name: n, action: action }, Object.assign({ group: "Circuit" }, opts || {}));
		if (st === "Proposée") A("Contrôler", "controler");
		if (st === "Contrôlée") A("Valider", "valider");
		if (st === "Validée") A("Activer", "activer", { confirm: "Activer ce changement de paramétrage ?" });
		if (["Proposée", "Contrôlée", "Validée"].includes(st)) A("Rejeter", "rejeter", { fields: or_reg.motif("Motif du rejet") });
	},
});
