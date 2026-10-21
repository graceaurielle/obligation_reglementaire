// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Action Proof", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new() || frm.doc.statut !== "À contrôler") return;
		if (!or_reg.has_role(...or_reg.COMPLIANCE, "OR Contrôleur", "OR Validateur")) return;
		const n = frm.doc.name;
		or_reg.btn(frm, "Accepter", "review_action_proof", { proof: n, decision: "Acceptée" }, { group: "Contrôle" });
		or_reg.btn(frm, "Rejeter", "review_action_proof", { proof: n, decision: "Rejetée" }, { group: "Contrôle", fields: or_reg.motif("Motif du rejet") });
		or_reg.btn(frm, "Demander un complément", "review_action_proof", { proof: n, decision: "Complément demandé" },
			{ group: "Contrôle", fields: or_reg.motif("Complément attendu") });
	},
});
