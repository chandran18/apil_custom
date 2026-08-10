import frappe
from frappe.utils import cint, flt, getdate

ENTRY_FETCH_FIELDS = [
	"die_no", "sec_no", "cavity", "batch_no_ref", "cut_length", "total_input", "ok_pcs", "output", "rec_percent", "remarks",
]


def _notify_pending_approval(doc, created_count):
	"""Push a mobile notification if the optional apil_mobile app is
	installed; a no-op otherwise. apil_custom must work standalone (mobile
	approval is a separate, optional layer some sites don't install), so
	this can never be a hard import - the notification is a nice-to-have,
	never something that should block a shift's Stock Entries from being
	created.
	"""
	if "apil_mobile" not in frappe.get_installed_apps():
		return

	from apil_mobile.mobile_notifications import send_push_to_role

	send_push_to_role(
		"APIL Mobile Approver",
		title="Stock Entries pending approval",
		body="{0} Stock Entry(s) for Shift {1} ({2}) need review.".format(created_count, doc.shift, doc.date),
		data={"doctype": "Shift Production Log", "name": doc.name},
	)


def before_save(doc, method=None):
	"""Refresh each Die-run row from its Extrusion Log - fetch_from is a
	client-side-only convenience (it never runs for rows created via the
	API, bulk import, or amend), so this guarantees the row data is
	correct regardless of how it got here - then recompute shift totals.
	"""
	seen = set()
	for entry in doc.entries:
		if not entry.extrusion_log:
			continue
		if entry.extrusion_log in seen:
			frappe.throw("Extrusion Log {0} is listed more than once in this shift.".format(entry.extrusion_log))
		seen.add(entry.extrusion_log)

		log_values = frappe.db.get_value("Extrusion Log", entry.extrusion_log, ENTRY_FETCH_FIELDS, as_dict=True)
		if log_values:
			entry.update(log_values)

	doc.total_input = round(sum(flt(e.total_input) for e in doc.entries), 4)
	doc.total_output = round(sum(flt(e.output) for e in doc.entries), 4)
	doc.total_ok_pcs = sum(cint(e.ok_pcs) for e in doc.entries)
	doc.overall_rec_percent = round((doc.total_output / doc.total_input) * 100, 2) if doc.total_input else 0


def before_submit(doc, method=None):
	"""Block submit if any row's Die-run isn't ready: not actually
	submitted yet, already claimed by another shift's consolidation, from
	a different Company/Date/Shift than this document, or if the shift's
	aggregate raw-material need exceeds what's really in the warehouse.
	"""
	if not doc.entries:
		frappe.throw("Add at least one Die run before submitting.")

	rm_needed = {}
	bom_cache = {}

	for entry in doc.entries:
		log = frappe.get_doc("Extrusion Log", entry.extrusion_log)

		if log.docstatus != 1:
			frappe.throw("Extrusion Log {0} is not submitted yet.".format(log.name))

		if log.included_in_shift_log and log.included_in_shift_log != doc.name:
			frappe.throw(
				"Extrusion Log {0} is already part of Shift Production Log {1}.".format(
					log.name, log.included_in_shift_log
				)
			)

		if log.company != doc.company or getdate(log.date) != getdate(doc.date) or log.shift != doc.shift:
			frappe.throw(
				"Extrusion Log {0} is Company/Date/Shift {1}/{2}/{3}, which doesn't match this "
				"Shift Production Log ({4}/{5}/{6}).".format(
					log.name, log.company, log.date, log.shift, doc.company, doc.date, doc.shift
				)
			)

		if not log.bom:
			frappe.throw("Extrusion Log {0} has no BOM resolved for item {1}.".format(log.name, log.sec_no))

		if log.bom not in bom_cache:
			bom_cache[log.bom] = frappe.get_doc("BOM", log.bom).items[0].item_code
		rm_item = bom_cache[log.bom]

		key = (rm_item, log.source_warehouse)
		rm_needed[key] = rm_needed.get(key, 0) + flt(log.total_input)

	for (rm_item, warehouse), needed in rm_needed.items():
		available_qty = frappe.db.get_value("Bin", {"item_code": rm_item, "warehouse": warehouse}, "actual_qty") or 0
		if flt(needed) > flt(available_qty):
			frappe.throw(
				"Insufficient {0} stock in {1}: available {2} kg, this shift needs {3} kg across all its Die runs. "
				"Please arrange more stock before submitting.".format(rm_item, warehouse, available_qty, needed),
				title="Stock Not Sufficient",
			)


def on_submit(doc, method=None):
	"""Create one Stock Entry per distinct (item, cut length) run this shift
	(Manufacture type - correctly auto-costed from each item's BOM, one
	finished item each, no scrap-flag quirk). Grouped by item AND length,
	not item alone: a special-length order (e.g. 5.5M instead of the
	standard 6.4M) is a different UOM/quantity on the finished-item row, so
	it needs its own row rather than being summed in with standard-length
	pieces of the same item. The shift's single Scrap figure is split
	across all the created Stock Entries in proportion to each one's Total
	Input (raw material consumed) and added as a row on each.

	Not an equal split: a flat equal share breaks the moment run sizes vary
	a lot in the same shift (e.g. a handful of small trial runs alongside
	full production runs) - a trial run's tiny raw-material cost can be
	less than its flat equal share of scrap value, driving the finished
	item's auto-costed rate negative, which ERPNext rejects outright.
	Proportional-by-input keeps every share bounded by what was actually
	consumed, so this can't happen, and it's more intuitively fair besides:
	a run that used more material this shift absorbs more of the scrap.

	All created Stock Entries are left as Drafts - a supervisor reviews
	and submits each by hand.
	"""
	logs_by_group = {}
	for entry in doc.entries:
		log = frappe.get_doc("Extrusion Log", entry.extrusion_log)
		logs_by_group.setdefault((log.sec_no, log.cut_length), []).append(log)

	input_by_group = {
		key: sum(flt(log.total_input) for log in logs) for key, logs in logs_by_group.items()
	}
	total_input = sum(input_by_group.values())

	created = []

	for (sec_no, cut_length), logs in logs_by_group.items():
		group_share = (input_by_group[(sec_no, cut_length)] / total_input) if total_input else 0
		scrap_share = flt(doc.scrap_qty) * group_share

		se = _build_item_stock_entry(doc, sec_no, cut_length, logs, scrap_share)
		se.insert(ignore_permissions=True)
		reference = sec_no if cut_length == "6.4M Length" else "{0} ({1})".format(sec_no, cut_length)
		created.append((reference, se))

		for log in logs:
			frappe.db.set_value("Extrusion Log", log.name, {
				"stock_entry": se.name,
				"included_in_shift_log": doc.name,
			})

	for reference, se in created:
		doc.append("created_stock_entries", {"reference": reference, "stock_entry": se.name})
	doc.db_update_all()

	_notify_pending_approval(doc, len(created))

	frappe.msgprint(
		"Created {0} draft Stock Entry(s) for this shift - one per item, each including its equal share "
		"of the shift's scrap. Please review and submit each one manually.".format(len(created)),
		title="Shift Stock Entries Created",
		indicator="blue",
	)


def before_cancel(doc, method=None):
	"""Cancel every still-submitted Stock Entry this shift created, and
	clear the back-links on every Extrusion Log this shift claimed - both
	BEFORE Frappe's own link-integrity check runs, which would otherwise
	block cancelling this document outright ("Cannot cancel because ...
	is linked with Extrusion Log"). This fully undoes the consolidation:
	the Extrusion Logs become free again (pickable by a new shift log),
	and any real stock movement already made is reversed.
	"""
	# Clear the Extrusion Logs' own links to the Stock Entry FIRST - a
	# Stock Entry can't be cancelled while a still-submitted Extrusion
	# Log's `stock_entry` field still points at it.
	for entry in doc.entries:
		if entry.extrusion_log:
			frappe.db.set_value("Extrusion Log", entry.extrusion_log, {
				"stock_entry": None,
				"included_in_shift_log": None,
			})

	for row in doc.created_stock_entries:
		if not row.stock_entry:
			continue
		se = frappe.get_doc("Stock Entry", row.stock_entry)
		if se.docstatus == 1:
			se.cancel()


def _build_item_stock_entry(doc, sec_no, cut_length, logs, scrap_share):
	bom_doc = frappe.get_doc("BOM", logs[0].bom)
	rm_item = bom_doc.items[0].item_code

	rm_totals = {}
	gas_totals = {}
	ok_pcs_total = 0
	target_warehouse = logs[0].target_warehouse
	log_names = []

	for log in logs:
		log_names.append(log.name)
		key = (rm_item, log.source_warehouse)
		rm_totals[key] = rm_totals.get(key, 0) + flt(log.total_input)

		if log.gas_item and log.gas_consumed and log.gas_consumed > 0:
			# Gas is a consumable stocked alongside chemicals/profiles in
			# target_warehouse (Stores), not in source_warehouse (Finished
			# Goods, where billets live) - different item, different shelf.
			gkey = (log.gas_item, log.target_warehouse)
			gas_totals[gkey] = gas_totals.get(gkey, 0) + flt(log.gas_consumed)

		ok_pcs_total += flt(log.ok_pcs)

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Manufacture"
	se.company = doc.company
	se.posting_date = doc.date
	se.set_posting_time = 1
	se.custom_extrusion_shift = doc.shift
	se.custom_extrusion_consolidated = 1
	se.remarks = "Auto-created from Shift Production Log {0} (Shift {1}, {2}) for item {3} ({4}), covering Extrusion Logs: {5}".format(
		doc.name, doc.shift, doc.date, sec_no, cut_length, ", ".join(log_names)
	)

	for (item_code, warehouse), qty in rm_totals.items():
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"uom": "Kg",
			"s_warehouse": warehouse,
		})

	for (item_code, warehouse), qty in gas_totals.items():
		se.append("items", {
			"item_code": item_code,
			"qty": qty,
			"uom": "Kg",
			"s_warehouse": warehouse,
		})

	# No manual rate here - Manufacture type auto-costs the finished item
	# from the raw material consumed (get_basic_rate_for_manufactured_item),
	# the correct, real production cost, since this entry has exactly one
	# finished item (Manufacture's one-finished-item-per-entry rule is
	# satisfied by construction - each item gets its own Stock Entry).
	#
	# uom = the log's own cut_length, not a hardcoded standard length - a
	# special-order length (e.g. 5.5M instead of 6.4M) must use the item's
	# matching alternate UOM (set up on the Item's UOM table with the
	# correct conversion factor back to the stock UOM) so the piece count
	# here is never mislabeled as standard-length output.
	se.append("items", {
		"item_code": sec_no,
		"qty": ok_pcs_total,
		"uom": cut_length,
		"t_warehouse": target_warehouse,
		"is_finished_item": 1,
		"custom_qty_in_pcs": ok_pcs_total,
	})

	if scrap_share and scrap_share > 0:
		scrap_rate = 250
		se.append("items", {
			"item_code": doc.scrap_item,
			"qty": scrap_share,
			"uom": "Kg",
			"t_warehouse": doc.scrap_warehouse,
			"is_scrap_item": 1,
			"basic_rate": scrap_rate,
			# set_basic_rate_manually=1 makes ERPNext skip computing
			# basic_amount for this row entirely (it assumes a human fills
			# in both rate and amount via the UI) - since nothing else sets
			# it for us here, we compute it ourselves or it silently stays 0.
			"basic_amount": scrap_share * scrap_rate,
			"set_basic_rate_manually": 1,
		})

	return se
