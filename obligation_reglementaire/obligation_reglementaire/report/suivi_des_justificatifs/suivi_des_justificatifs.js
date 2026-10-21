// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Suivi des justificatifs"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "en_souffrance", label: __("En souffrance uniquement"), fieldtype: "Check", default: 1 },
		{ fieldname: "horizon", label: __("Échéance dans (jours)"), fieldtype: "Int" },
		{ fieldname: "responsable", label: __("Responsable"), fieldtype: "Link", options: "User" },
		{ fieldname: "controleur", label: __("Contrôleur"), fieldtype: "Link", options: "User" },
		{ fieldname: "type_justificatif", label: __("Type"), fieldtype: "Link", options: "Reg Evidence Type" },
	],
};
