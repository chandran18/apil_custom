import frappe
from frappe import _

from erpnext.manufacturing.doctype.bom.bom import BOM, validate_bom_no


class CustomBOM(BOM):
	"""Allow Qty = 0 on BOM raw material rows.

	Two separate places in core ERPNext (erpnext/manufacturing/doctype/bom/bom.py)
	stop a deliberate qty=0 row from surviving:

	1. validate_materials() throws "Quantity required for Item X in row Y"
	   for any row with qty <= 0, with no override flag.
	2. set_bom_material_details() re-fetches missing row details via
	   get_bom_material_detail(), which computes
	   `qty = args.get("qty") or args.get("stock_qty") or 1` - since 0 is
	   falsy in Python, an explicit 0 is silently replaced with 1 (same
	   issue affects rate, via get_rm_rate falling back when no
	   valuation exists). This is a real bug in core: it can't tell
	   "qty was never set" apart from "qty was deliberately set to 0".

	Business need: some BOM rows (optional consumables) can legitimately
	be 0 for a given standard recipe variant, and the business wants that
	recorded explicitly rather than the row being left out.
	"""

	def validate_materials(self):
		if not self.get("items"):
			frappe.throw(_("Raw Materials cannot be blank."))

		check_list = []
		for m in self.get("items"):
			if m.bom_no:
				validate_bom_no(m.item_code, m.bom_no)
			# Zero/negative Qty intentionally allowed (see class docstring) - no throw here.
			check_list.append(m)

	def set_bom_material_details(self):
		# Snapshot what was explicitly set on each row before letting
		# ERPNext's own default-fetch logic run, then restore qty/rate/
		# stock_qty afterwards - this BOM workflow always sets these
		# explicitly per row, so there's no legitimate case here where we
		# actually want the auto-fetched fallback to win over a real value
		# (including a deliberate 0).
		snapshot = {item.name: (item.qty, item.rate, item.stock_qty) for item in self.get("items")}
		super().set_bom_material_details()
		for item in self.get("items"):
			qty, rate, stock_qty = snapshot.get(item.name, (None, None, None))
			if qty is not None:
				item.qty = qty
			if rate is not None:
				item.rate = rate
			if stock_qty is not None:
				item.stock_qty = stock_qty
