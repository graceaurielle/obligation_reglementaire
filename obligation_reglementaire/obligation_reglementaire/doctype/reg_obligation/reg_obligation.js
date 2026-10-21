// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

const OBL_NEXT = {
	"Brouillon": ["En qualification", "Archivée"],
	"En qualification": ["Validée", "Brouillon", "Archivée"],
	"Validée": ["Active", "En qualification", "Archivée"],
	"Active": ["Suspendue", "Clôturée", "Obsolète", "En qualification"],
	"Suspendue": ["Active", "Clôturée", "Obsolète"],
	"Clôturée": ["Archivée", "Active"],
	"Obsolète": ["Archivée"],
};
const OBL_MOTIF = ["Suspendue", "Clôturée", "Obsolète", "Archivée", "Brouillon", "En qualification"];

frappe.ui.form.on("Reg Obligation", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		(OBL_NEXT[frm.doc.statut] || []).forEach((st) => {
			or_reg.btn(frm, st, "obligation_transition", { obligation: frm.doc.name, statut: st },
				{ group: "Statut", fields: OBL_MOTIF.includes(st) ? or_reg.motif() : null });
		});
		if (["Active", "Validée"].includes(frm.doc.statut)) {
			or_reg.btn(frm, "Générer les échéances", "generate_deadlines", { obligation: frm.doc.name }, { group: "Échéances" });
		}
		frm.add_custom_button(__("Aperçu du calendrier"), () => {
			frappe.call({
				method: or_reg.API + "deadline_preview", args: { obligation: frm.doc.name, nombre: 12 },
				callback(r) {
					const rows = (r.message.dates || []).map((d) => `<tr><td>${d.periode}</td><td>${frappe.datetime.str_to_user(d.date_limite)}</td></tr>`).join("");
					frappe.msgprint({ title: __("Prochaines échéances"),
						message: `<p>${r.message.regle || ""}</p><table class="table table-bordered"><tr><th>${__("Période")}</th><th>${__("Date limite")}</th></tr>${rows}</table>` });
				},
			});
		}, __("Échéances"));
		frm.add_custom_button(__("Voir les échéances"), () => frappe.set_route("List", "Reg Deadline", { obligation: frm.doc.name }), __("Échéances"));
		if (frm.doc.statut === "Active") {
			frm.add_custom_button(__("Modifier un champ sensible"), () => {
				const d = new frappe.ui.Dialog({
					title: __("Modification justifiée"),
					fields: [
						{ fieldname: "champ", fieldtype: "Select", label: __("Champ"), reqd: 1,
							options: ["criticite", "frequence", "delai_valeur", "delai_unite", "nature_temporelle", "proprietaire",
								"responsable_operationnel", "controleur", "validateur", "date_debut", "date_fin"].join("\n") },
						{ fieldname: "valeur", fieldtype: "Data", label: __("Nouvelle valeur"), reqd: 1 },
						{ fieldname: "justification", fieldtype: "Small Text", label: __("Justification"), reqd: 1 },
					],
					primary_action(v) {
						d.hide();
						or_reg.call(frm, "obligation_update_with_justification",
							{ obligation: frm.doc.name, values: { [v.champ]: v.valeur }, justification: v.justification });
					},
				});
				d.show();
			});
		}
		frm.add_custom_button(__("Journal d'audit"), () => frappe.set_route("List", "Reg Audit Log", { reference_name: frm.doc.name }), __("Voir"));
	},
});
