import frappe
from frappe.utils import flt, time_diff_in_seconds

from apil_custom.mobile_notifications import send_push_to_role


def before_save(doc, method=None):
	"""Live calculations: Total Input, Die Running Time, Rec%, Output/Hr,
	and the linked BOM lookup. Scrap Items are entered manually by the
	operator - this only totals whatever rows are present.

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

	# Scrap Items are entered manually by the operator - just total them.
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
	"""Auto-create the matching Stock Entry (Manufacture) as a draft.

	Left as a draft intentionally - someone reviews and submits it by hand.
	Submitting the Extrusion Log does not depend on the Stock Entry's status.
	"""
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
		"custom_qty_in_pcs": doc.ok_pcs,
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
	frappe.db.set_value("Extrusion Log", doc.name, "stock_entry", se.name)

	send_push_to_role(
		"APIL Mobile Approver",
		title="Stock Entry pending approval",
		body="Stock Entry {0} (from Extrusion Log {1}, Die {2}) needs review.".format(
			se.name, doc.name, doc.die_no
		),
		data={"doctype": "Stock Entry", "name": se.name},
	)

	frappe.msgprint(
		"Stock Entry {0} created as a draft. Please review and submit it manually.".format(
			frappe.utils.get_link_to_form("Stock Entry", se.name)
		),
		title="Draft Stock Entry Created",
		indicator="blue",
	)


@frappe.whitelist()
def get_extrusion_rm_availability(item_code, warehouse):
	"""Live stock check called from the Extrusion Log form (see
	public/js/extrusion_log.js) as the die/warehouse are picked, so the
	operator sees available billet stock before submitting.

	Migrated from a database-stored Server Script (API type) of the same
	name, kept here as a real whitelisted function instead.
	"""
	result = {"rm_item": None, "available_qty": 0, "bom": None}

	if item_code:
		bom_name = frappe.db.get_value(
			"BOM", {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
		)
		result["bom"] = bom_name
		if bom_name:
			bom_items = frappe.get_all(
				"BOM Item", filters={"parent": bom_name}, fields=["item_code"], order_by="idx asc", limit_page_length=1
			)
			if bom_items:
				result["rm_item"] = bom_items[0].item_code

	if result["rm_item"] and warehouse:
		result["available_qty"] = frappe.db.get_value(
			"Bin", {"item_code": result["rm_item"], "warehouse": warehouse}, "actual_qty"
		) or 0

	return result
