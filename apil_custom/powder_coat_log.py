import frappe
from frappe.utils import flt


def before_save(doc, method=None):
	"""Live calculations: resolve this item's Powder Coat BOM, then derive
	the reference powder and gas figures from it plus the item's own
	Catalogue Weight / Powder Consumption % (see
	Item-custom_powder_consumption_percent).

	Mirrors apil_custom/extrusion_log.py's before_save - a real app file
	(not a Client Script) so the same numbers come out whether the record
	is created from the desk form, the API, or a bulk import.
	"""
	if doc.item:
		doc.bom = frappe.db.get_value(
			"BOM", {"item": doc.item, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
		)
		item_values = frappe.db.get_value(
			"Item", doc.item, ["custom_catalogue_weight", "custom_powder_consumption_percent"], as_dict=True
		)
		doc.catalogue_weight = item_values.custom_catalogue_weight if item_values else 0
		doc.consumption_percent = item_values.custom_powder_consumption_percent if item_values else 0
	else:
		doc.bom = None
		doc.catalogue_weight = 0
		doc.consumption_percent = 0

	doc.calculated_powder_consumption = round(
		flt(doc.catalogue_weight) * (flt(doc.consumption_percent) / 100) * flt(doc.pieces), 4
	)
	# The one field that's both auto-calculated AND freely editable: pre-fill
	# it from the calculated figure, but never overwrite a value the
	# operator has already entered or adjusted by hand.
	if not doc.actual_powder_consumption:
		doc.actual_powder_consumption = doc.calculated_powder_consumption

	doc.rm_item = None
	doc.gas_item = None
	doc.calculated_gas_consumption = 0
	if doc.bom:
		bom_items = frappe.get_all(
			"BOM Item", filters={"parent": doc.bom}, fields=["item_code", "qty"], order_by="idx asc"
		)
		if bom_items:
			doc.rm_item = bom_items[0].item_code
			for bom_item in bom_items[1:]:
				if bom_item.item_code == "Industrial Gas":
					doc.gas_item = bom_item.item_code
					doc.calculated_gas_consumption = round(flt(bom_item.qty) * flt(doc.pieces), 4)

	if doc.rm_item and doc.source_warehouse:
		doc.available_stock = frappe.db.get_value(
			"Bin", {"item_code": doc.rm_item, "warehouse": doc.source_warehouse}, "actual_qty"
		) or 0


def before_submit(doc, method=None):
	"""Block submit if the M/F warehouse doesn't have enough stock to cover
	this batch's Pieces (converted via the item's UOM Conversion Detail if
	this batch is a special-order length). Mirrors the identical per-log
	check in apil_custom/extrusion_log.py.
	"""
	if not doc.bom:
		frappe.throw("No active BOM found for {0}. Cannot validate or create stock movement.".format(doc.item))
	if not doc.rm_item:
		frappe.throw("Could not resolve the M/F item from BOM {0}.".format(doc.bom))

	conversion_factor = 1
	if doc.cut_length:
		stock_uom = frappe.db.get_value("Item", doc.rm_item, "stock_uom")
		if doc.cut_length != stock_uom:
			conversion_factor = frappe.db.get_value(
				"UOM Conversion Detail", {"parent": doc.rm_item, "uom": doc.cut_length}, "conversion_factor"
			) or 1

	needed = flt(doc.pieces) * flt(conversion_factor)
	available_qty = frappe.db.get_value(
		"Bin", {"item_code": doc.rm_item, "warehouse": doc.source_warehouse}, "actual_qty"
	) or 0

	if needed > flt(available_qty):
		frappe.throw(
			"Insufficient {0} stock in {1}: available {2}, this batch needs {3}. "
			"Please arrange more M/F stock before submitting this batch.".format(
				doc.rm_item, doc.source_warehouse, available_qty, needed
			),
			title="Stock Not Sufficient",
		)


@frappe.whitelist()
def get_powder_coat_rm_availability(item_code, warehouse):
	"""Live stock check called from the Powder Coat Log form (see
	public/js/powder_coat_log.js) as the item/warehouse are picked - mirrors
	apil_custom.extrusion_log.get_extrusion_rm_availability.
	"""
	result = {"rm_item": None, "gas_item": None, "available_qty": 0, "bom": None}

	if item_code:
		bom_name = frappe.db.get_value(
			"BOM", {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
		)
		result["bom"] = bom_name
		if bom_name:
			bom_items = frappe.get_all(
				"BOM Item", filters={"parent": bom_name}, fields=["item_code"], order_by="idx asc"
			)
			if bom_items:
				result["rm_item"] = bom_items[0].item_code
				for bom_item in bom_items[1:]:
					if bom_item.item_code == "Industrial Gas":
						result["gas_item"] = bom_item.item_code

	if result["rm_item"] and warehouse:
		result["available_qty"] = frappe.db.get_value(
			"Bin", {"item_code": result["rm_item"], "warehouse": warehouse}, "actual_qty"
		) or 0

	return result
