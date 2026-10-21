// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Qualité du référentiel"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "tout_afficher", label: __("Afficher aussi les fiches complètes"), fieldtype: "Check" },
	],
};
