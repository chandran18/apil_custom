// Live form calculations for Extrusion Log: Total Input, Die Running Time,
// Rec%, Output/Hr, stock availability indicator, and quick-nav buttons to
// the resulting Stock Entry / Stock Balance report.
//
// Migrated from a database-stored Client Script of the same name - identical
// behaviour, just living in the app instead of the database.

frappe.ui.form.on("Extrusion Log", {
	refresh: function (frm) {
		if (frm.doc.stock_entry) {
			frm.add_custom_button("View Stock Entry", function () {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
		if (frm.doc.included_in_shift_log) {
			frm.add_custom_button("View Shift Production Log", function () {
				frappe.set_route("Form", "Shift Production Log", frm.doc.included_in_shift_log);
			});
		}
		if (frm.doc.rm_item && frm.doc.source_warehouse) {
			frm.add_custom_button("View Billet Stock Balance", function () {
				frappe.route_options = { item_code: frm.doc.rm_item, warehouse: frm.doc.source_warehouse };
				frappe.set_route("query-report", "Stock Balance");
			});
		}
		show_stock_indicator(frm);
		set_cut_length_query(frm);
	},
	sec_no: function (frm) {
		fetch_availability(frm);
		set_cut_length_query(frm);
	},
	source_warehouse: function (frm) {
		fetch_availability(frm);
	},
	die_in: function (frm) {
		calc_running_time(frm);
	},
	die_out: function (frm) {
		calc_running_time(frm);
	},
	output: function (frm) {
		calc_rec(frm);
	},
});

frappe.ui.form.on("Extrusion Log Billet Charge", {
	billet_weight: function (frm) {
		calc_total_input(frm);
	},
	billet_charges_remove: function (frm) {
		calc_total_input(frm);
	},
});

function set_cut_length_query(frm) {
	// Only offer UOMs actually set up as alternates on this item (its Stock
	// UOM, e.g. standard "6.4M Length", plus any special-order lengths
	// added to its UOM table) - stops an operator picking an unrelated
	// length that has no conversion factor on this item at all.
	frm.set_query("cut_length", function () {
		return {
			query: "apil_custom.extrusion_log.query_item_uoms",
			filters: { item_code: frm.doc.sec_no },
		};
	});
}

function fetch_availability(frm) {
	if (!frm.doc.sec_no) return;
	frappe.call({
		method: "apil_custom.extrusion_log.get_extrusion_rm_availability",
		args: { item_code: frm.doc.sec_no, warehouse: frm.doc.source_warehouse },
		callback: function (r) {
			if (r.message) {
				frm.set_value("rm_item", r.message.rm_item);
				frm.set_value("available_stock", r.message.available_qty);
				frm.set_value("bom", r.message.bom);
				show_stock_indicator(frm);
				frm.refresh();
			}
		},
	});
}

function calc_total_input(frm) {
	let total = 0;
	(frm.doc.billet_charges || []).forEach(function (row) {
		total += flt(row.billet_weight);
	});
	frm.set_value("total_input", total);
	calc_rec(frm);
	show_stock_indicator(frm);
}

function calc_running_time(frm) {
	if (frm.doc.die_in && frm.doc.die_out) {
		let diff = moment.duration(frm.doc.die_out) - moment.duration(frm.doc.die_in);
		if (diff < 0) diff += 24 * 3600 * 1000;
		frm.set_value("die_running_time", diff / 1000);
		calc_output_per_hr(frm);
	}
}

function calc_rec(frm) {
	if (frm.doc.output && frm.doc.total_input) {
		frm.set_value("rec_percent", flt((frm.doc.output / frm.doc.total_input) * 100, 2));
	}
	calc_output_per_hr(frm);
}

function calc_output_per_hr(frm) {
	if (frm.doc.output && frm.doc.die_running_time) {
		let hours = frm.doc.die_running_time / 3600;
		if (hours > 0) frm.set_value("output_per_hr", flt(frm.doc.output / hours, 2));
	}
}

function show_stock_indicator(frm) {
	frm.dashboard.clear_headline();
	if (frm.doc.available_stock === undefined || frm.doc.available_stock === null) return;
	let needed = flt(frm.doc.total_input);
	let available = flt(frm.doc.available_stock);
	if (!needed) return;
	if (needed > available) {
		frm.dashboard.set_headline_alert(
			"Insufficient " + (frm.doc.rm_item || "billet") + " stock in " + frm.doc.source_warehouse +
				": available " + available + " kg, this log needs " + needed + " kg. Please refill stock before submitting.",
			"red"
		);
	} else {
		frm.dashboard.set_headline_alert(
			"Stock OK: " + available + " kg " + (frm.doc.rm_item || "billet") + " available (needs " + needed + " kg).",
			"green"
		);
	}
}
