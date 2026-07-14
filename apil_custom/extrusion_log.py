import frappe
from frappe.utils import flt, time_diff_in_seconds


def before_save(doc, method=None):
	"""Live calculations: Total Input, Die Running Time, Rec%, Output/Hr,
	auto-managed Al-Scrap row, and the linked BOM lookup.

	Moved here from a database-stored Server Script: identical logic, but
	as a real app file it isn't subject to the RestrictedPython sandbox
	(which turned out to cause a hard-to-diagnose Stock Entry valuation
	bug specifically for the After Submit stock-creation step - see
	on_submit() below).
	"""
	total_input = sum([(d.billet_weight or 0) for d in doc.billet_charges])
	doc.total_input = total_input

	if doc.die_in and doc.die_out:
		diff = time_diff_in_seconds(doc.die_out, doc.die_in)
		if diff < 0:
			diff += 24 * 3600
		doc.die_running_time = diff

	if doc.output and total_input:
		if doc.output > total_input:
			frappe.throw(
				"Output ({0} kg) cannot exceed Total Input ({1} kg). Please check the entered figures.".format(
					doc.output, total_input
				)
			)
		doc.rec_percent = round((doc.output / total_input) * 100, 2)
	else:
		doc.rec_percent = 0

	if doc.output and doc.die_running_time:
		hours = doc.die_running_time / 3600.0
		doc.output_per_hr = round(doc.output / hours, 2) if hours > 0 else 0
	else:
		doc.output_per_hr = 0

	# Auto-manage a single Al-Scrap row (marked auto_calculated) inside the
	# scrap_items child table, without touching any other rows the operator
	# may have added manually for other scrap categories.
	auto_scrap_qty = round(max((total_input or 0) - (doc.output or 0), 0), 4)
	auto_row = None
	for d in doc.scrap_items:
		if d.auto_calculated:
			auto_row = d
			break

	if auto_scrap_qty > 0:
		if auto_row:
			auto_row.scrap_item = auto_row.scrap_item or "Al-Scrap"
			auto_row.qty = auto_scrap_qty
			auto_row.warehouse = auto_row.warehouse or doc.target_warehouse
		else:
			doc.append("scrap_items", {
				"scrap_item": "Al-Scrap",
				"qty": auto_scrap_qty,
				"warehouse": doc.target_warehouse,
				"auto_calculated": 1,
			})
	elif auto_row:
		doc.scrap_items = [d for d in doc.scrap_items if d != auto_row]

	doc.total_scrap_qty = round(sum([(d.qty or 0) for d in doc.scrap_items]), 4)

	if doc.sec_no:
		doc.bom = frappe.db.get_value(
			"BOM", {"item": doc.sec_no, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
		)


def before_submit(doc, method=None):
	"""Block submit (not save) if the warehouse doesn't have enough of the
	BOM's raw material to cover this log's Total Input.
	"""
	if not doc.bom:
		frappe.throw("No active BOM found for {0}. Cannot validate or create stock movement.".format(doc.sec_no))

	bom_doc = frappe.get_doc("BOM", doc.bom)
	rm_item = bom_doc.items[0].item_code

	available_qty = frappe.db.get_value("Bin", {"item_code": rm_item, "warehouse": doc.source_warehouse}, "actual_qty") or 0

	if flt(doc.total_input) > flt(available_qty):
		frappe.throw(
			"Insufficient {0} stock in {1}: available {2} kg, this log needs {3} kg. "
			"Please arrange more stock (Material Receipt / additional casting) before submitting this log.".format(
				rm_item, doc.source_warehouse, available_qty, doc.total_input
			),
			title="Stock Not Sufficient",
		)


def on_submit(doc, method=None):
	"""Auto-create and submit the matching Stock Entry (Manufacture)."""
	if not doc.bom:
		frappe.throw("No active submitted BOM found for item {0}. Cannot create Stock Entry.".format(doc.sec_no))

	bom_doc = frappe.get_doc("BOM", doc.bom)
	rm_item = bom_doc.items[0].item_code

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Manufacture"
	se.company = doc.company
	se.posting_date = doc.date
	se.set_posting_time = 1
	se.bom_no = doc.bom
	se.from_bom = 1
	se.remarks = "Auto-created from Extrusion Log {0} (Die {1}, Sec {2}, Shift {3})".format(
		doc.name, doc.die_no, doc.sec_no, doc.shift
	)

	se.append("items", {
		"item_code": rm_item,
		"qty": doc.total_input,
		"uom": "Kg",
		"s_warehouse": doc.source_warehouse,
	})

	if doc.gas_item and doc.gas_consumed and doc.gas_consumed > 0:
		# Gas is a consumable stocked alongside chemicals/profiles in
		# target_warehouse (Stores), not in source_warehouse (Finished
		# Goods, where billets live) - different item, different shelf.
		se.append("items", {
			"item_code": doc.gas_item,
			"qty": doc.gas_consumed,
			"uom": "Kg",
			"s_warehouse": doc.target_warehouse,
		})

	se.append("items", {
		"item_code": doc.sec_no,
		"qty": doc.ok_pcs,
		"uom": "6.4M Length",
		"t_warehouse": doc.target_warehouse,
		"is_finished_item": 1,
	})

	for row in doc.scrap_items:
		if row.qty and row.qty > 0:
			se.append("items", {
				"item_code": row.scrap_item,
				"qty": row.qty,
				"uom": "Kg",
				"t_warehouse": row.warehouse or doc.target_warehouse,
				"is_scrap_item": 1,
				"basic_rate": 250,
				"set_basic_rate_manually": 1,
			})

	se.insert(ignore_permissions=True)
	se.submit()
	frappe.db.set_value("Extrusion Log", doc.name, "stock_entry", se.name)
