// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Exposition aux risques"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "tout_afficher", label: __("Inclure les obligations maîtrisées"), fieldtype: "Check" },
	],
};
