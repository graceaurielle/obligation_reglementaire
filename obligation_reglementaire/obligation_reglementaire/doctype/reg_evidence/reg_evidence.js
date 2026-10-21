// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Evidence", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut;
		if (["Attendu", "Demandé", "À fournir", "À compléter", "Rejeté"].includes(st)) {
			frm.add_custom_button(__("Déposer un fichier"), () => {
				const d = new frappe.ui.Dialog({
					title: __("Dépôt du justificatif"),
					fields: [
						{ fieldname: "file_url", fieldtype: "Attach", label: __("Fichier"), reqd: 1 },
						{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") },
					],
					primary_action(v) {
						d.hide();
						const go = (confirmer) => frappe.call({
							method: or_reg.API + "deposit_evidence",
							args: { evidence_name: n, file_url: v.file_url, commentaire: v.commentaire, confirmer_doublon: confirmer },
							freeze: true,
							callback(r) {
								const m = r.message || {};
								if (m.doublon) {
									frappe.confirm(__("Ce fichier a déjà été déposé ({0}). Confirmer le dépôt ?", [m.doublon]), () => go(1));
									return;
								}
								frappe.show_alert({ message: __("Version {0} déposée", [m.numero]), indicator: m.en_retard ? "orange" : "green" });
								frm.reload_doc();
							},
						});
						go(0);
					},
				});
				d.show();
			}).addClass("btn-primary");
		}
		if (["Déposé", "Soumis à nouveau"].includes(st) && or_reg.has_role(...or_reg.COMPLIANCE, "OR Contrôleur", "OR Validateur")) {
			frm.add_custom_button(__("Démarrer le contrôle"), () => frappe.call({
				method: or_reg.API + "start_evidence_review", args: { evidence_name: n }, freeze: true,
				callback: (r) => frappe.set_route("Form", "Reg Evidence Review", r.message),
			})).addClass("btn-primary");
		}
		if (["Validé", "Validé avec réserve", "Expiré"].includes(st)) {
			or_reg.btn(frm, "Remplacer", "replace_evidence", { evidence_name: n }, { group: "Actions", fields: or_reg.motif("Motif du remplacement") });
			or_reg.btn(frm, "Réutiliser pour une autre échéance", "reuse_evidence", { evidence_name: n }, { group: "Actions", fields: [
				{ fieldname: "echeance", fieldtype: "Link", options: "Reg Deadline", label: __("Échéance"), reqd: 1 },
				{ fieldname: "contexte", fieldtype: "Small Text", label: __("Contexte") }] });
		}
		if (!["Annulé", "Archivé", "Remplacé"].includes(st)) {
			or_reg.btn(frm, "Annuler", "cancel_evidence", { evidence_name: n }, { group: "Actions", fields: or_reg.motif("Motif d'annulation") });
		}
		frm.add_custom_button(__("Versions"), () => frappe.set_route("List", "Reg Evidence Version", { justificatif: n }), __("Voir"));
		frm.add_custom_button(__("Contrôles"), () => frappe.set_route("List", "Reg Evidence Review", { justificatif: n }), __("Voir"));
	},
});
