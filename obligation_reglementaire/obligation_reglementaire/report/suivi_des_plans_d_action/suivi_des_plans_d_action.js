// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.query_reports["Suivi des plans d'action"] = {
	filters: [
		{ fieldname: "organisation", label: __("Organisation"), fieldtype: "Link", options: "Reg Organization" },
		{ fieldname: "statut", label: __("Statut"), fieldtype: "Select", options: "\nBrouillon\nOuvert\nEn cours\nBloqué\nEn attente de preuves\nEn attente de validation\nVérification d'efficacité\nClôturé\nRéouvert\nAnnulé" },
		{ fieldname: "ouverts_seulement", label: __("Plans ouverts seulement"), fieldtype: "Check", default: 1 },
		{ fieldname: "en_retard", label: __("En retard seulement"), fieldtype: "Check" },
		{ fieldname: "responsable", label: __("Responsable"), fieldtype: "Link", options: "User" },
		{ fieldname: "criticite", label: __("Criticité"), fieldtype: "Link", options: "Reg Criticality Level" },
	],
};
