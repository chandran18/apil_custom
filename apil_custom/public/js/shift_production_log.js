// Shift Production Log: pick the shift's already-submitted Extrusion Logs,
// one row per Die run - a "Fetch" button offers every matching unclaimed
// log for the chosen Company/Date/Shift, and the child table's own Link
// field is filtered the same way for adding rows one at a time.

frappe.ui.form.on("Shift Production Log", {
	refresh: function (frm) {
		(frm.doc.created_stock_entries || []).forEach(function (row) {
			frm.add_custom_button(row.reference + " - " + row.stock_entry, function () {
				frappe.set_route("Form", "Stock Entry", row.stock_entry);
			}, "View Stock Entries");
		});
		if (frm.doc.docstatus === 0 && frm.doc.company && frm.doc.date && frm.doc.shift) {
			frm.add_custom_button("Fetch Shift's Extrusion Logs", function () {
				fetch_matching_logs(frm);
			});
		}
	},
	company: set_entries_query,
	date: set_entries_query,
	shift: set_entries_query,
});

function set_entries_query(frm) {
	frm.set_query("extrusion_log", "entries", function () {
		return {
			filters: {
				company: frm.doc.company,
				date: frm.doc.date,
				shift: frm.doc.shift,
				docstatus: 1,
				included_in_shift_log: ["in", ["", null, frm.doc.name]],
			},
		};
	});
}

function fetch_matching_logs(frm) {
	frappe.db
		.get_list("Extrusion Log", {
			filters: {
				company: frm.doc.company,
				date: frm.doc.date,
				shift: frm.doc.shift,
				docstatus: 1,
				included_in_shift_log: ["in", ["", null, frm.doc.name]],
			},
			fields: ["name"],
			limit_page_length: 0,
		})
		.then(function (logs) {
			let existing = (frm.doc.entries || []).map((r) => r.extrusion_log);
			let added = 0;
			logs.forEach(function (log) {
				if (existing.includes(log.name)) return;
				let row = frm.add_child("entries");
				row.extrusion_log = log.name;
				added += 1;
			});
			refresh_field("entries");
			if (added) {
				frm.script_manager.trigger("entries_add");
			}
			frappe.show_alert({
				message: added ? `Added ${added} Die run(s).` : "No new Die runs found for this Company/Date/Shift.",
				indicator: added ? "green" : "orange",
			});
		});
}
