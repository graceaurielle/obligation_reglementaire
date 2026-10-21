// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Action Plan", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut, A = (label, action, opts) =>
			or_reg.btn(frm, label, "plan_action", { plan: n, action: action }, Object.assign({ group: "Actions" }, opts || {}));
		if (st === "Brouillon") A("Ouvrir le plan", "ouvrir");
		if (["Ouvert", "En cours", "En attente de preuves", "Réouvert"].includes(st)) {
			frm.add_custom_button(__("Vérifier les blocages de clôture"), () => frappe.call({
				method: or_reg.API + "plan_action", args: { plan: n, action: "blocages" },
				callback(r) {
					const b = r.message || [];
					frappe.msgprint({ title: __("Clôture"), indicator: b.length ? "orange" : "green",
						message: b.length ? b.map((x) => "• " + x).join("<br>") : __("Aucun blocage : la clôture peut être demandée.") });
				},
			}), __("Actions"));
			A("Demander la clôture", "demander_cloture");
			A("Bloquer", "bloquer", { fields: or_reg.motif("Motif du blocage") });
		}
		if (st === "Bloqué") A("Débloquer", "debloquer");
		if (["En attente de validation", "Vérification d'efficacité"].includes(st)) {
			A("Valider la clôture", "valider_cloture", { fields: [{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") }] });
			A("Refuser la clôture", "refuser_cloture", { fields: or_reg.motif("Motif du refus") });
		}
		if (st === "Clôturé") A("Rouvrir", "rouvrir", { fields: or_reg.motif("Motif de réouverture").concat([
			{ fieldname: "nouveau_constat", fieldtype: "Small Text", label: __("Nouveau constat") }]) });
		if (!["Clôturé", "Annulé"].includes(st) && or_reg.is_compliance()) {
			A("Annuler", "annuler", { fields: [
				{ fieldname: "categorie", fieldtype: "Select", label: __("Catégorie"), reqd: 1, options: "Doublon\nMauvaise affectation\nErreur de création\nÉvénement invalidé\nAutre" },
				{ fieldname: "motif", fieldtype: "Small Text", label: __("Motif"), reqd: 1 }] });
		}
		frm.add_custom_button(__("Nouvelle action corrective"), () => frappe.new_doc("Reg Corrective Action", { plan: n }), __("Actions"));
		frm.add_custom_button(__("Actions correctives"), () => frappe.set_route("List", "Reg Corrective Action", { plan: n }), __("Voir"));
	},
});
