// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Deadline", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		const n = frm.doc.name, st = frm.doc.statut, A = (label, action, opts) =>
			or_reg.btn(frm, label, "deadline_action", { name: n, action: action }, Object.assign({ group: "Actions" }, opts || {}));
		if (["À venir", "À traiter", "En retard", "En attente"].includes(st)) A("Démarrer", "demarrer");
		if (["À venir", "À traiter", "En cours", "En retard"].includes(st)) A("Mettre en attente", "attente", { fields: or_reg.motif("Motif d'attente") });
		if (["À traiter", "En cours", "En retard", "En attente"].includes(st)) {
			const f = [{ fieldname: "date_realisation", fieldtype: "Date", label: __("Date de réalisation"), default: frappe.datetime.get_today(), reqd: 1 }];
			if (or_reg.is_compliance()) {
				f.push({ fieldname: "derogation", fieldtype: "Check", label: __("Dérogation (justificatif manquant)") },
					{ fieldname: "motif", fieldtype: "Small Text", label: __("Justification de la dérogation"), depends_on: "derogation" });
			}
			A("Soumettre pour validation", "soumettre", { fields: f });
		}
		if (st === "Soumise pour validation") {
			A("Valider", "valider", { fields: [
				{ fieldname: "cause_retard", fieldtype: "Link", options: "Reg Delay Cause", label: __("Cause du retard (si retard)") },
				{ fieldname: "commentaire", fieldtype: "Small Text", label: __("Commentaire") }] });
			A("Rejeter", "rejeter", { fields: or_reg.motif("Motif du rejet") });
		}
		if (!["Réalisée", "Réalisée en retard", "Non conforme", "Annulée", "Clôturée"].includes(st)) {
			A("Déclarer non conforme", "non_conforme", { fields: or_reg.motif("Motif de non-conformité") });
		}
		if (["Réalisée", "Réalisée en retard", "Non conforme"].includes(st)) A("Clôturer", "cloturer", { fields: or_reg.motif("Commentaire", false) });
		if (st === "Suspendue") A("Reprendre", "reprendre");
		else if (!["Annulée", "Clôturée", "Réalisée", "Réalisée en retard"].includes(st)) {
			A("Suspendre", "suspendre", { fields: or_reg.motif("Motif de suspension").concat([
				{ fieldname: "date_fin_prevue", fieldtype: "Date", label: __("Fin prévue") },
				{ fieldname: "autorite", fieldtype: "Link", options: "Reg Authority", label: __("Autorité") },
				{ fieldname: "justificatif", fieldtype: "Attach", label: __("Pièce justificative") }]) });
		}
		if (or_reg.is_compliance()) {
			if (["Réalisée", "Réalisée en retard", "Non conforme", "Clôturée"].includes(st)) A("Rouvrir", "rouvrir", { fields: or_reg.motif("Motif de réouverture") });
			if (!["Annulée", "Clôturée"].includes(st)) A("Annuler", "annuler", { fields: or_reg.motif("Motif d'annulation") });
		}
		if (!["Annulée", "Clôturée"].includes(st)) {
			or_reg.btn(frm, "Demander un report", "request_deadline_change", { echeance: n }, { group: "Actions", fields: [
				{ fieldname: "nouvelle_date", fieldtype: "Date", label: __("Nouvelle date"), reqd: 1 },
				{ fieldname: "type_modification", fieldtype: "Select", label: __("Type"), options: "Report métier\nCorrection technique", default: "Report métier" },
				{ fieldname: "motif", fieldtype: "Small Text", label: __("Motif"), reqd: 1 },
				{ fieldname: "piece", fieldtype: "Attach", label: __("Pièce justificative") },
				{ fieldname: "autorite", fieldtype: "Link", options: "Reg Authority", label: __("Autorité autorisant le report") }] });
			or_reg.btn(frm, "Ajouter un justificatif attendu", "add_evidence", { echeance: n }, { group: "Justificatifs", fields: [
				{ fieldname: "type_justificatif", fieldtype: "Link", options: "Reg Evidence Type", label: __("Type"), reqd: 1 },
				{ fieldname: "libelle", fieldtype: "Data", label: __("Libellé"), reqd: 1 },
				{ fieldname: "obligatoire", fieldtype: "Check", label: __("Obligatoire") }] });
		}
		frm.add_custom_button(__("Justificatifs"), () => frappe.set_route("List", "Reg Evidence", { echeance: n }), __("Justificatifs"));
		if (frm.doc.non_conformite) frm.add_custom_button(__("Non-conformité"), () => frappe.set_route("Form", "Reg Non Conformity", frm.doc.non_conformite), __("Voir"));
	},
});
