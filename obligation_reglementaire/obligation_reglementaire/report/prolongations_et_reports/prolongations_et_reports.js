// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Prolongations et reports"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "type", label: __("Type"), fieldtype: "Select", options: "\nProlongation\nReport d'échéance" },
		{ fieldname: "statut", label: __("Statut"), fieldtype: "Data" },
		{ fieldname: "date_debut", label: __("Demandées du"), fieldtype: "Date" },
		{ fieldname: "date_fin", label: __("au"), fieldtype: "Date" },
	],
};
