// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["À traiter aujourd'hui"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "utilisateur", label: __("Utilisateur"), fieldtype: "Link", options: "User", default: frappe.session.user },
		{ fieldname: "horizon", label: __("Horizon (jours)"), fieldtype: "Int", default: 7 },
		{ fieldname: "tous", label: __("Tous les utilisateurs"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_value) {
		value = default_value(value, row, column, data);
		if (data && column.fieldname === "statut" && ["En retard", "Non conforme"].includes(data.statut)) {
			value = `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		if (data && column.fieldname === "jours" && data.jours !== null && data.jours < 0) {
			value = `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
