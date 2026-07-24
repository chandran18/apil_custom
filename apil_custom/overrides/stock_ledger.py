import frappe

# Maps a Stock Ledger Entry's voucher_type to the child doctype that holds
# the actual item row (via voucher_detail_no), for every voucher type that
# already carries a custom_qty_in_pcs fixture field. Voucher types not
# listed here (or without the field) are left blank - no error either way.
VOUCHER_ITEM_DOCTYPE = {
	"Stock Entry": "Stock Entry Detail",
	"Purchase Receipt": "Purchase Receipt Item",
	"Purchase Invoice": "Purchase Invoice Item",
	"Sales Invoice": "Sales Invoice Item",
}


def set_qty_in_pcs(doc, method=None):
	"""Copy Qty in Pcs from the source document's row onto this Stock
	Ledger Entry, so it's available for the Stock Ledger report.
	"""
	child_doctype = VOUCHER_ITEM_DOCTYPE.get(doc.voucher_type)
	if not child_doctype or not doc.voucher_detail_no:
		return

	if not frappe.get_meta(child_doctype).has_field("custom_qty_in_pcs"):
		return

	doc.custom_qty_in_pcs = frappe.db.get_value(
		child_doctype, doc.voucher_detail_no, "custom_qty_in_pcs"
	)
