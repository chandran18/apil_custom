// Live form calculations for Powder Coat Log: powder/paint consumption
// (Catalogue Weight x Powder Consumption % x Pieces), BOM-driven gas use,
// stock availability indicator, and quick-nav buttons - mirrors
// public/js/extrusion_log.js.

frappe.ui.form.on("Powder Coat Log", {
	refresh: function (frm) {
		if (frm.doc.stock_entry) {
			frm.add_custom_button("View Stock Entry", function () {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
		if (frm.doc.included_in_shift_log) {
			frm.add_custom_button("View Shift Production Log", function () {
				frappe.set_route("Form", "Powder Coat Shift Production Log", frm.doc.included_in_shift_log);
			});
		}
		if (frm.doc.rm_item && frm.doc.source_warehouse) {
			frm.add_custom_button("View M/F Stock Balance", function () {
				frappe.route_options = { item_code: frm.doc.rm_item, warehouse: frm.doc.source_warehouse };
				frappe.set_route("query-report", "Stock Balance");
			});
		}
		show_stock_indicator(frm);
		set_cut_length_query(frm);
	},
	item: function (frm) {
		fetch_availability(frm);
		set_cut_length_query(frm);
		calc_powder_consumption(frm);
	},
	source_warehouse: function (frm) {
		fetch_availability(frm);
	},
	pieces: function (frm) {
		calc_powder_consumption(frm);
	},
});

function set_cut_length_query(frm) {
	// Reuses the same generic UOM link-query already built for Extrusion
	// Log - it just filters UOM Conversion Detail by item_code, so it works
	// for any item, not only Extrusion Log's own sec_no field.
	frm.set_query("cut_length", function () {
		return {
			query: "apil_custom.extrusion_log.query_item_uoms",
			filters: { item_code: frm.doc.item },
		};
	});
}

function fetch_availability(frm) {
	if (!frm.doc.item) return;
	frappe.call({
		method: "apil_custom.powder_coat_log.get_powder_coat_rm_availability",
		args: { item_code: frm.doc.item, warehouse: frm.doc.source_warehouse },
		callback: function (r) {
			if (r.message) {
				frm.set_value("rm_item", r.message.rm_item);
				frm.set_value("gas_item", r.message.gas_item);
				frm.set_value("available_stock", r.message.available_qty);
				frm.set_value("bom", r.message.bom);
				show_stock_indicator(frm);
				frm.refresh();
			}
		},
	});
}

function calc_powder_consumption(frm) {
	// Client-side preview only - apil_custom.powder_coat_log.before_save is
	// the source of truth and recomputes this the same way on save.
	if (!frm.doc.item) return;
	frappe.db.get_value("Item", frm.doc.item, ["custom_catalogue_weight", "custom_powder_consumption_percent"]).then((r) => {
		let weight = flt(r.message.custom_catalogue_weight);
		let percent = flt(r.message.custom_powder_consumption_percent);
		let calculated = flt(weight * (percent / 100) * flt(frm.doc.pieces), precision("calculated_powder_consumption", frm.doc));
		frm.set_value("catalogue_weight", weight);
		frm.set_value("consumption_percent", percent);
		frm.set_value("calculated_powder_consumption", calculated);
		if (!frm.doc.actual_powder_consumption) {
			frm.set_value("actual_powder_consumption", calculated);
		}
	});
}

function show_stock_indicator(frm) {
	frm.dashboard.clear_headline();
	if (frm.doc.available_stock === undefined || frm.doc.available_stock === null) return;
	let needed = flt(frm.doc.pieces);
	let available = flt(frm.doc.available_stock);
	if (!needed) return;
	if (needed > available) {
		frm.dashboard.set_headline_alert(
			"Insufficient " + (frm.doc.rm_item || "M/F") + " stock in " + frm.doc.source_warehouse +
				": available " + available + ", this batch needs " + needed + ". Please refill stock before submitting.",
			"red"
		);
	} else {
		frm.dashboard.set_headline_alert(
			"Stock OK: " + available + " " + (frm.doc.rm_item || "M/F") + " available (needs " + needed + ").",
			"green"
		);
	}
}
