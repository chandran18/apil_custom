// Live client-side preview of Weight x Rate pricing, so Amount is correct
// on screen immediately as you type - no Save round-trip needed.
// The actual math is server-side (apil_custom.weight_pricing.sales) so
// this file never re-implements the formula, just displays what the
// server would compute.

function apil_apply_weight_rate(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (!row.item_code || !row.qty) return;

	frappe.call({
		method: "apil_custom.weight_pricing.sales.get_weight_amount_preview",
		args: {
			item_code: row.item_code,
			customer: frm.doc.customer,
			qty: row.qty,
			rate_per_kg: row.custom_rate_per_kg,
			actual_weight: row.custom_actual_weight,
		},
		callback: function (r) {
			if (!r.message || !r.message.is_weight_item) return;
			frappe.model.set_value(cdt, cdn, "custom_catalogue_weight", r.message.catalogue_weight);
			frappe.model.set_value(cdt, cdn, "custom_weight_used", r.message.weight_used);
			// If Rate per Kg was blank, this reflects what got auto-derived
			// from APIL Settings + Item Category + Customer discount - so
			// the user can see (and still override) the number that's
			// actually driving Amount.
			frappe.model.set_value(cdt, cdn, "custom_rate_per_kg", r.message.rate_per_kg);
			frappe.model.set_value(cdt, cdn, "custom_base_rate_per_kg", r.message.base_rate_per_kg);
			frappe.model.set_value(cdt, cdn, "custom_discount_percent_applied", r.message.discount_percent_applied);
			// Setting rate triggers ERPNext's own qty x rate amount calc +
			// totals rollup automatically - same trick the server uses.
			frappe.model.set_value(cdt, cdn, "rate", r.message.adjusted_rate);
		},
	});
}

["Sales Order Item", "Sales Invoice Item"].forEach(function (doctype) {
	frappe.ui.form.on(doctype, {
		item_code: function (frm, cdt, cdn) {
			apil_apply_weight_rate(frm, cdt, cdn);
		},
		qty: function (frm, cdt, cdn) {
			apil_apply_weight_rate(frm, cdt, cdn);
		},
		custom_rate_per_kg: function (frm, cdt, cdn) {
			apil_apply_weight_rate(frm, cdt, cdn);
		},
		custom_actual_weight: function (frm, cdt, cdn) {
			apil_apply_weight_rate(frm, cdt, cdn);
		},
	});
});

["Sales Order", "Sales Invoice"].forEach(function (doctype) {
	frappe.ui.form.on(doctype, {
		customer: function (frm) {
			// Weight basis depends on the customer - recompute every row
			// whenever the customer changes.
			(frm.doc.items || []).forEach(function (row) {
				apil_apply_weight_rate(frm, row.doctype, row.name);
			});
		},
	});
});
