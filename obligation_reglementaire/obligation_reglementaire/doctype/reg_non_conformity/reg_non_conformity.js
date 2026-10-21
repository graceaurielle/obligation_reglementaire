// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Non Conformity", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut;
		if (!frm.doc.plan_action && !["Clôturée", "Annulée"].includes(st)) {
			frm.add_custom_button(__("Créer un plan d'action"), () => frappe.call({
				method: or_reg.API + "create_plan_from_nc", args: { nc: n }, freeze: true,
				callback: (r) => frappe.set_route("Form", "Reg Action Plan", r.message),
			})).addClass("btn-primary");
		}
		if (frm.doc.plan_action) frm.add_custom_button(__("Plan d'action"), () => frappe.set_route("Form", "Reg Action Plan", frm.doc.plan_action), __("Voir"));
		if (!["Clôturée", "Annulée"].includes(st) && or_reg.has_role(...or_reg.COMPLIANCE, "OR Validateur")) {
			or_reg.btn(frm, "Clôturer", "close_nc", { nc: n }, { fields: [
				{ fieldname: "decision", fieldtype: "Small Text", label: __("Décision de clôture"), reqd: 1 },
				{ fieldname: "risque_residuel_accepte", fieldtype: "Check", label: __("Risque résiduel accepté") },
				{ fieldname: "justification_acceptation", fieldtype: "Small Text", label: __("Justification de l'acceptation"), depends_on: "risque_residuel_accepte" }] });
		}
	},
});
