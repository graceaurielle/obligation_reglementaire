// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Applicability Proposal", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new() || !["Proposée", "En analyse"].includes(frm.doc.statut)) return;
		if (!or_reg.has_role(...or_reg.COMPLIANCE, "OR Analyste Réglementaire")) return;
		["Applicable", "Applicable sous condition", "Non applicable", "À analyser"].forEach((dec) => {
			// Justification obligatoire si la décision s'écarte de la proposition ou restreint l'applicabilité
			const reqd = dec !== frm.doc.etat_propose || ["Non applicable", "Applicable sous condition"].includes(dec);
			or_reg.btn(frm, dec, "decide_proposal", { proposal: frm.doc.name, decision: dec }, { group: "Décision",
				fields: [{ fieldname: "justification", fieldtype: "Small Text", label: __("Justification"), reqd: reqd ? 1 : 0 }] });
		});
	},
});
