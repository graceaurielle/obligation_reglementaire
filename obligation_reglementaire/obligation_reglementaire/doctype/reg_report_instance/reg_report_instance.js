// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Report Instance", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut, A = (label, action, opts) =>
			or_reg.btn(frm, label, "report_action", { name: n, action: action }, Object.assign({ group: "Circuit" }, opts || {}));
		const dialog = (title, fields, action) => frm.add_custom_button(__(title), () => {
			const d = new frappe.ui.Dialog({ title: __(title), fields: fields,
				primary_action(v) { d.hide(); or_reg.call(frm, "report_action", { name: n, action: action, values: v }); } });
			d.show();
		}, __("Circuit"));
		if (["Brouillon", "En préparation", "À corriger", "Échec de génération"].includes(st)) {
			A("Générer", "generer");
			A("Soumettre au contrôle", "soumettre");
		}
		if (st === "À contrôler") {
			A("Contrôler", "controler");
			A("Rejeter", "rejeter", { fields: or_reg.motif("Motif du rejet").concat([
				{ fieldname: "elements", fieldtype: "Small Text", label: __("Éléments à corriger") }]) });
		}
		if (["Contrôlé", "À valider"].includes(st)) {
			A("Valider", "valider", { fields: [{ fieldname: "reserves", fieldtype: "Small Text", label: __("Réserves") }] });
			A("Rejeter", "rejeter", { fields: or_reg.motif("Motif du rejet") });
		}
		if (st === "Validé") {
			A("Diffuser", "diffuser", { fields: [
				{ fieldname: "users", fieldtype: "Small Text", label: __("Destinataires (e-mails séparés par des virgules)"), reqd: 1 },
				{ fieldname: "canal", fieldtype: "Select", label: __("Canal"), options: "Plateforme\nE-mail", default: "Plateforme" }] });
		}
		if (["Validé", "Diffusé", "Prêt à transmettre"].includes(st)) {
			dialog("Transmettre à l'autorité", [
				{ fieldname: "date_transmission", fieldtype: "Datetime", label: __("Date-heure de transmission"), default: frappe.datetime.now_datetime(), reqd: 1 },
				{ fieldname: "canal_transmission", fieldtype: "Select", label: __("Canal"), options: "Portail de l'autorité\nE-mail\nCourrier\nDépôt physique\nAutre", reqd: 1 },
				{ fieldname: "destinataire_transmission", fieldtype: "Data", label: __("Destinataire") },
				{ fieldname: "reference_transmission", fieldtype: "Data", label: __("Référence de dépôt") },
				{ fieldname: "fichier_transmis", fieldtype: "Attach", label: __("Fichier transmis (sinon le PDF généré)") },
				{ fieldname: "preuve_depot", fieldtype: "Attach", label: __("Preuve de dépôt") }], "transmettre");
		}
		if (st === "Transmis") {
			dialog("Accusé de réception", [{ fieldname: "accuse_reception", fieldtype: "Attach", label: __("Accusé"), reqd: 1 }], "accuse");
			dialog("Rejet de l'autorité", [
				{ fieldname: "motif_rejet_autorite", fieldtype: "Small Text", label: __("Motif"), reqd: 1 },
				{ fieldname: "courrier_autorite", fieldtype: "Attach", label: __("Courrier") },
				{ fieldname: "date_rejet_autorite", fieldtype: "Date", label: __("Date du rejet"), default: frappe.datetime.get_today() },
				{ fieldname: "nouvelle_echeance", fieldtype: "Date", label: __("Nouvelle échéance") },
				{ fieldname: "responsable_correction", fieldtype: "Link", options: "User", label: __("Responsable de la correction") }], "rejet_autorite");
		}
		if (["Accusé réception obtenu", "Diffusé", "Validé"].includes(st)) A("Clôturer", "cloturer");
		if (!["Brouillon", "En préparation"].includes(st)) {
			A("Exporter (PDF/Excel)", "exporter");
			A("Nouvelle version", "nouvelle_version", { confirm: "Créer une nouvelle version de ce rapport ?" });
		}
	},
});
