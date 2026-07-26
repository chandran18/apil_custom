import frappe
from frappe.utils import flt, time_diff_in_seconds


def before_save(doc, method=None):
	"""Live calculations: Total Input, Die Running Time, Rec%, Output/Hr,
	and the linked BOM lookup.

	Moved here from a database-stored Server Script: identical logic, but
	as a real app file it isn't subject to the RestrictedPython sandbox
	(which turned out to cause a hard-to-diagnose Stock Entry valuation
	bug specifically for the After Submit stock-creation step - see
	apil_custom/shift_production_log.py, which now owns that step instead).
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

	if doc.sec_no:
		doc.bom = frappe.db.get_value(
			"BOM", {"item": doc.sec_no, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
		)


def before_submit(doc, method=None):
	"""Block submit (not save) if the warehouse doesn't have enough of the
	BOM's raw material to cover this log's Total Input.

	This is a real-time sanity check for the operator submitting a single
	Die run; it's not the final word - the Shift Production Log that later
	consolidates several logs re-checks the aggregate total when it's
	submitted, since several logs drafted in the same shift can each
	individually pass this check against stock none of them have deducted
	yet (Stock Entries stay Draft until a supervisor submits them).
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
