// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Corrective Action", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut, A = (label, action, opts) =>
			or_reg.btn(frm, label, "corrective_action", { name: n, action: action }, Object.assign({ group: "Actions" }, opts || {}));
		if (["Non commencée", "Planifiée", "Bloquée", "Retour pour correction"].includes(st)) A("Démarrer", "demarrer");
		if (["En cours", "Retour pour correction"].includes(st)) {
			frm.add_custom_button(__("Ajouter une preuve"), () => frappe.new_doc("Reg Action Proof", { action: n }), __("Actions"));
			A("Soumettre au contrôle", "soumettre");
			A("Bloquer", "bloquer", { fields: or_reg.motif("Motif du blocage") });
		}
		if (st === "Soumise à contrôle") {
			A("Valider", "valider");
			A("Retourner pour correction", "retourner", { fields: or_reg.motif("Motif du retour") });
		}
		if (!["Validée", "Annulée"].includes(st)) {
			A("Annuler", "annuler", { fields: or_reg.motif("Motif d'annulation") });
			frm.add_custom_button(__("Demander une prolongation"), () =>
				frappe.new_doc("Reg Extension Request", { action: n }), __("Actions"));
		}
		frm.add_custom_button(__("Preuves"), () => frappe.set_route("List", "Reg Action Proof", { action: n }), __("Voir"));
	},
});
