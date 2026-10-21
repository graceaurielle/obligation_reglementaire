// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Notification Log", {
	refresh(frm) {
		or_reg.indicator(frm);
		if (frm.is_new()) return;
		if (!frm.doc.lu) or_reg.btn(frm, "Marquer comme lu", "mark_read", { name: frm.doc.name });
		if (frm.doc.accuse_requis && !frm.doc.date_accuse) or_reg.btn(frm, "Accuser réception", "acknowledge", { name: frm.doc.name });
	},
});
