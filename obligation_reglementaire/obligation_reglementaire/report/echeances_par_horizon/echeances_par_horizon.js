// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Échéances par horizon"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "horizon", label: __("Horizon"), fieldtype: "Select",
			options: ["", "Échues", "Aujourd'hui", "1–7 j", "8–15 j", "16–30 j", "31–60 j", "61–90 j", "> 90 j"].join("\n") },
		{ fieldname: "responsable", label: __("Responsable"), fieldtype: "Link", options: "User" },
		{ fieldname: "unite", label: __("Unité"), fieldtype: "Link", options: "Reg Org Unit" },
		{ fieldname: "domaine", label: __("Domaine"), fieldtype: "Link", options: "Reg Domain" },
		{ fieldname: "criticite", label: __("Criticité"), fieldtype: "Link", options: "Reg Criticality Level" },
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
