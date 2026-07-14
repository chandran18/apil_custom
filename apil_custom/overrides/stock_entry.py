import frappe
from frappe import _
from frappe.utils import flt

from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from erpnext.stock.get_item_details import get_conversion_factor


class CustomStockEntry(StockEntry):
	"""Allow Qty = 0 on Stock Entry item rows.

	Standard ERPNext (erpnext/stock/doctype/stock_entry/stock_entry.py:
	set_transfer_qty) calls validate_qty_is_not_zero() (which throws
	unless self.flags.allow_zero_qty is set - a flag nothing in the normal
	UI/API flow ever sets), and then has its OWN unconditional "Qty in
	Stock UOM can not be zero" throw right after, which has no flag
	escape at all. Business need: furnace-charge Stock Entries have
	optional consumable rows (e.g. Ceramic Foam Filter, Grain Refiner)
	that are legitimately 0 for some casts, and the business wants that
	recorded explicitly rather than the row being omitted.

	Re-implements set_transfer_qty verbatim, only removing both zero-qty
	throws.
	"""

	def set_transfer_qty(self):
		for item in self.get("items"):
			if not flt(item.conversion_factor):
				item.conversion_factor = (
					flt(get_conversion_factor(item.item_code, item.uom).get("conversion_factor")) or 1
				)
			if not flt(item.conversion_factor):
				frappe.throw(_("Row {0}: UOM Conversion Factor is mandatory").format(item.idx))
			item.transfer_qty = flt(
				flt(item.qty) * flt(item.conversion_factor), self.precision("transfer_qty", item)
			)
			# Zero Qty intentionally allowed (see class docstring) - no throw here.
