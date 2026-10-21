// Outils communs aux formulaires « Obligations réglementaires »
frappe.provide("or_reg");

or_reg.API = "obligation_reglementaire.api.";

// Appel d'une méthode de l'API puis rechargement du formulaire
or_reg.call = function (frm, method, args, message) {
	return frappe.call({
		method: or_reg.API + method,
		args: args,
		freeze: true,
		callback(r) {
			if (message !== false) {
				frappe.show_alert({ message: message || __("Opération effectuée"), indicator: "green" });
			}
			if (frm) frm.reload_doc();
			return r;
		},
	});
};

// Bouton d'action ; si des champs sont fournis, une boîte de dialogue les saisit avant l'appel
or_reg.btn = function (frm, label, method, args, opts) {
	opts = opts || {};
	frm.add_custom_button(__(label), () => {
		const run = (values) => or_reg.call(frm, method, Object.assign({}, args, values || {}), opts.message);
		if (!opts.fields) {
			if (opts.confirm) frappe.confirm(__(opts.confirm), () => run());
			else run();
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __(label),
			fields: opts.fields,
			primary_action_label: __("Valider"),
			primary_action(values) {
				d.hide();
				run(values);
			},
		});
		d.show();
	}, opts.group ? __(opts.group) : undefined);
};

or_reg.motif = (label, reqd) => [{ fieldname: "motif", fieldtype: "Small Text", label: __(label || "Motif"), reqd: reqd === false ? 0 : 1 }];

or_reg.has_role = (...roles) => roles.some((r) => frappe.user.has_role(r));
or_reg.COMPLIANCE = ["OR Administrateur", "OR Responsable Conformité", "System Manager"];
or_reg.is_compliance = () => or_reg.has_role(...or_reg.COMPLIANCE);

// Indicateur coloré selon le statut
or_reg.COLORS = {
	"Brouillon": "gray", "À venir": "blue", "À traiter": "orange", "En cours": "blue", "En attente": "yellow",
	"Soumise pour validation": "purple", "Réalisée": "green", "Réalisée en retard": "orange", "En retard": "red",
	"Non conforme": "red", "Suspendue": "gray", "Annulée": "gray", "Clôturée": "green", "Active": "green",
	"Validée": "green", "Validé": "green", "Rejeté": "red", "Rejetée": "red", "Ouverte": "red", "Ouvert": "orange",
	"Bloqué": "red", "Bloquée": "red", "Clôturé": "green", "Publié": "green", "Expiré": "red",
};
or_reg.indicator = function (frm) {
	if (frm.doc.statut && !frm.is_new()) frm.page.set_indicator(__(frm.doc.statut), or_reg.COLORS[frm.doc.statut] || "blue");
};
