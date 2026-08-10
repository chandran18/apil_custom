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

	# Gas consumption tracking is disabled for now: several sites have
	# "Industrial Gas" set up as a non-stock Item, which makes ERPNext
	# reject any Stock Entry that tries to move it ("... is not a stock
	# Item"). Rather than require every site to fix that Item master data
	# before the Powder Coat workflow is usable, gas is left out of both
	# the calculation and the Stock Entry entirely until re-enabled.
	doc.rm_item = None
	doc.gas_item = None
	doc.calculated_gas_consumption = 0
	bom_paint_item = None
	if doc.bom:
		bom_items = frappe.get_all(
			"BOM Item", filters={"parent": doc.bom}, fields=["item_code", "qty"], order_by="idx asc"
		)
		if bom_items:
			doc.rm_item = bom_items[0].item_code
			for bom_item in bom_items[1:]:
				if bom_item.item_code != "Industrial Gas":
					bom_paint_item = bom_item.item_code

	# Free-entry field: default from the BOM's paint row for convenience,
	# but never overwrite a choice the operator already made - different
	# orders often coat the same profile in a different real RAL colour
	# than whatever the BOM happens to carry.
	if not doc.powder_item:
		doc.powder_item = bom_paint_item

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
	if not doc.powder_item:
		frappe.throw("Pick the Powder/Paint Item actually used for this batch before submitting.")

	# Catch a missing warehouse here, with a clear message naming this
	# exact batch and field - rather than letting it surface later as a
	# generic "Source warehouse is mandatory for row N" error from deep
	# inside the Stock Entry that Shift Production Log builds when it
	# consolidates this log (which doesn't say WHICH batch or field is at
	# fault).
	missing = []
	if not doc.source_warehouse:
		missing.append("M/F Source Warehouse")
	if not doc.target_warehouse:
		missing.append("P/C Output Warehouse")
	if not doc.consumables_warehouse:
		missing.append("Gas/Paint Warehouse")
	if missing:
		frappe.throw("Set the following before submitting this batch: {0}.".format(", ".join(missing)))

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
def query_powder_items(doctype, txt, searchfield, start, page_len, filters):
	"""Link-query for the Powder/Paint Item field: only offer real powder/
	paint items (named "RAL ..." in this catalog), not the furnace
	chemicals and filters that share the same generic 'Consumables' item
	group - see public/js/powder_coat_log.js.
	"""
	return frappe.db.sql(
		"""
		select name from `tabItem`
		where item_code like 'RAL%%'
		and disabled = 0
		and name like %(txt)s
		order by name
		limit %(start)s, %(page_len)s
		""",
		{"txt": "%{0}%".format(txt or ""), "start": start, "page_len": page_len},
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
