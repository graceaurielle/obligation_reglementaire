// Copyright (c) 2026, grace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reg Notification Rule", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Simuler"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Simulation de notification"),
				fields: [
					{ fieldname: "doctype_ref", fieldtype: "Link", options: "DocType", label: __("Type de document"), reqd: 1 },
					{ fieldname: "name_ref", fieldtype: "Dynamic Link", options: "doctype_ref", label: __("Document"), reqd: 1 }],
				primary_action(v) {
					d.hide();
					frappe.call({ method: or_reg.API + "simulate_notification", args: { rule: frm.doc.name, doctype: v.doctype_ref, name: v.name_ref },
						callback(r) {
							const m = r.message || {};
							frappe.msgprint({ title: __("Aperçu"), message: `<p><b>${__("Destinataires")}</b> : ${(m.destinataires || []).join(", ") || "—"}</p>
								<p><b>${m.sujet || m.titre || ""}</b></p><div>${m.message || m.corps || ""}</div>` });
						} });
				},
			});
			d.show();
		});
	},
});
