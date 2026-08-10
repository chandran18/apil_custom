import frappe
from frappe.utils import cint, flt, getdate

ENTRY_FETCH_FIELDS = [
	"item", "powder_item", "batch_no_ref", "cut_length", "pieces", "actual_powder_consumption",
	"calculated_gas_consumption", "remarks",
]


def before_save(doc, method=None):
	"""Refresh each batch row from its Powder Coat Log - fetch_from is a
	client-side-only convenience, so this guarantees the row data is correct
	regardless of how it got here - then recompute shift totals. Mirrors
	apil_custom/shift_production_log.py's before_save.
	"""
	seen = set()
	for entry in doc.entries:
		if not entry.powder_coat_log:
			continue
		if entry.powder_coat_log in seen:
			frappe.throw("Powder Coat Log {0} is listed more than once in this shift.".format(entry.powder_coat_log))
		seen.add(entry.powder_coat_log)

		log_values = frappe.db.get_value("Powder Coat Log", entry.powder_coat_log, ENTRY_FETCH_FIELDS, as_dict=True)
		if log_values:
			entry.update(log_values)

	doc.total_pieces = sum(cint(e.pieces) for e in doc.entries)
	doc.total_powder_consumption = round(sum(flt(e.actual_powder_consumption) for e in doc.entries), 4)
	doc.total_gas_consumption = round(sum(flt(e.calculated_gas_consumption) for e in doc.entries), 4)

	# Free-entry field: default from the calculated total for convenience,
	# but never overwrite a figure the supervisor already entered by hand -
	# same auto-fill-then-editable pattern as each batch's own Actual
	# Powder Consumption field.
	if not doc.actual_total_powder_consumption:
		doc.actual_total_powder_consumption = doc.total_powder_consumption


def before_submit(doc, method=None):
	"""Block submit if any row's batch isn't ready: not actually submitted
	yet, already claimed by another shift's consolidation, from a different
	Company/Date/Shift than this document, or if the shift's aggregate
	raw-material need exceeds what's really in the warehouse. Mirrors
	apil_custom/shift_production_log.py's before_submit.
	"""
	if not doc.entries:
		frappe.throw("Add at least one batch before submitting.")

	rm_needed = {}

	for entry in doc.entries:
		log = frappe.get_doc("Powder Coat Log", entry.powder_coat_log)

		if log.docstatus != 1:
			frappe.throw("Powder Coat Log {0} is not submitted yet.".format(log.name))

		if log.included_in_shift_log and log.included_in_shift_log != doc.name:
			frappe.throw(
				"Powder Coat Log {0} is already part of Powder Coat Shift Production Log {1}.".format(
					log.name, log.included_in_shift_log
				)
			)

		if log.company != doc.company or getdate(log.date) != getdate(doc.date) or log.shift != doc.shift:
			frappe.throw(
				"Powder Coat Log {0} is Company/Date/Shift {1}/{2}/{3}, which doesn't match this "
				"Powder Coat Shift Production Log ({4}/{5}/{6}).".format(
					log.name, log.company, log.date, log.shift, doc.company, doc.date, doc.shift
				)
			)

		if not log.bom or not log.rm_item:
			frappe.throw("Powder Coat Log {0} has no BOM/M-F item resolved for item {1}.".format(log.name, log.item))

		conversion_factor = 1
		if log.cut_length:
			stock_uom = frappe.db.get_value("Item", log.rm_item, "stock_uom")
			if log.cut_length != stock_uom:
				conversion_factor = frappe.db.get_value(
					"UOM Conversion Detail", {"parent": log.rm_item, "uom": log.cut_length}, "conversion_factor"
				) or 1

		key = (log.rm_item, log.source_warehouse)
		rm_needed[key] = rm_needed.get(key, 0) + flt(log.pieces) * flt(conversion_factor)

	for (rm_item, warehouse), needed in rm_needed.items():
		available_qty = frappe.db.get_value("Bin", {"item_code": rm_item, "warehouse": warehouse}, "actual_qty") or 0
		if flt(needed) > flt(available_qty):
			frappe.throw(
				"Insufficient {0} stock in {1}: available {2}, this shift needs {3} across all its batches. "
				"Please arrange more stock before submitting.".format(rm_item, warehouse, available_qty, needed),
				title="Stock Not Sufficient",
			)


def on_submit(doc, method=None):
	"""Create one Stock Entry per distinct (item, cut length, powder item)
	batch this shift (Manufacture type - correctly auto-costed, one
	finished item each). Grouped by powder item as well as item/length: an
	operator can coat the same profile in two different real RAL colours
	within one shift (see Powder Coat Log's own Powder/Paint Item field),
	and those must never be merged into a single Stock Entry line sharing
	one paint total - each colour gets its own entry.

	Each Stock Entry consumes the M/F piece count and produces the P/C
	finished item. The paint/powder quantity is NOT summed up from each
	batch's own Actual Powder Consumption - the shift's Actual Total
	Powder Consumption is divided EQUALLY across however many Stock
	Entries this shift produces, and every group gets that same equal
	share regardless of its own pieces/weight. That equal share is also
	written back onto every child row belonging to that group (Powder Qty
	in Stock Entry), so it's visible here without opening each Stock Entry.
	Gas consumption tracking is currently disabled (see
	apil_custom/powder_coat_log.py).

	All created Stock Entries are left as Drafts - a supervisor reviews and
	submits each by hand, exactly like the Extrusion side.
	"""
	logs_by_group = {}
	for entry in doc.entries:
		log = frappe.get_doc("Powder Coat Log", entry.powder_coat_log)
		logs_by_group.setdefault((log.item, log.cut_length, log.powder_item), []).append((log, entry))

	equal_share = round(flt(doc.actual_total_powder_consumption) / len(logs_by_group), 4) if logs_by_group else 0

	created = []

	for (item, cut_length, powder_item), log_entry_pairs in logs_by_group.items():
		logs = [pair[0] for pair in log_entry_pairs]
		se = _build_item_stock_entry(doc, item, cut_length, powder_item, logs, equal_share)
		se.insert(ignore_permissions=True)
		reference = item if cut_length == "6.4M Length" else "{0} ({1})".format(item, cut_length)
		if powder_item:
			reference = "{0} [{1}]".format(reference, powder_item)
		created.append((reference, se))

		for log, entry in log_entry_pairs:
			frappe.db.set_value("Powder Coat Log", log.name, {
				"stock_entry": se.name,
				"included_in_shift_log": doc.name,
			})
			entry.stock_entry_powder_qty = equal_share

	for reference, se in created:
		doc.append("created_stock_entries", {"reference": reference, "stock_entry": se.name})
	doc.db_update_all()

	frappe.msgprint(
		"Created {0} draft Stock Entry(s) for this shift - one per item, each including its powder/paint "
		"consumption. Please review and submit each one manually.".format(len(created)),
		title="Shift Stock Entries Created",
		indicator="blue",
	)


def _build_item_stock_entry(doc, item, cut_length, powder_item, logs, paint_qty):
	bom_doc = frappe.get_doc("BOM", logs[0].bom)
	mf_item = bom_doc.items[0].item_code

	mf_totals = {}
	pieces_total = 0
	target_warehouse = logs[0].target_warehouse
	consumables_warehouse = logs[0].consumables_warehouse
	log_names = []

	for log in logs:
		log_names.append(log.name)
		mf_key = (mf_item, log.source_warehouse)
		mf_totals[mf_key] = mf_totals.get(mf_key, 0) + flt(log.pieces)

		# Gas consumption is disabled (see apil_custom/powder_coat_log.py)
		# - deliberately never added as a Stock Entry row, even for logs
		# created before this was disabled that still carry old gas figures.

		pieces_total += flt(log.pieces)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Manufacture"
	se.company = doc.company
	se.posting_date = doc.date
	se.set_posting_time = 1
	se.custom_extrusion_shift = doc.shift
	se.custom_extrusion_consolidated = 1
	se.remarks = "Auto-created from Powder Coat Shift Production Log {0} (Shift {1}, {2}) for item {3} ({4}), covering Powder Coat Logs: {5}".format(
		doc.name, doc.shift, doc.date, item, cut_length, ", ".join(log_names)
	)

	for (item_code, warehouse), qty in mf_totals.items():
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"uom": cut_length,
			"s_warehouse": warehouse,
		})

	if powder_item and flt(paint_qty) > 0:
		se.append("items", {
			"item_code": powder_item,
			"qty": paint_qty,
			"uom": "Kg",
			"s_warehouse": consumables_warehouse,
		})

	# No manual rate here - Manufacture type auto-costs the finished item
	# from the raw materials consumed (get_basic_rate_for_manufactured_item);
	# this entry always has exactly one finished item since each item gets
	# its own Stock Entry (Manufacture's one-finished-item-per-entry rule is
	# satisfied by construction).
	se.append("items", {
		"item_code": item,
		"qty": pieces_total,
		"uom": cut_length,
		"t_warehouse": target_warehouse,
		"is_finished_item": 1,
		"custom_qty_in_pcs": pieces_total,
	})

	return se
