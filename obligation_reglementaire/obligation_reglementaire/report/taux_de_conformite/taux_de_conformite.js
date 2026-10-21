// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Taux de conformité"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "regroupement", label: __("Regrouper par"), fieldtype: "Select", options: "domaine\nunite\nresponsable\ncriticite\nobligation", default: "domaine" },
		{ fieldname: "date_debut", label: __("Du"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -12) },
		{ fieldname: "date_fin", label: __("Au"), fieldtype: "Date", default: frappe.datetime.get_today() },
	],
};
