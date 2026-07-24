"""Adds a 'Qty in Pcs' column to the standard (core ERPNext) Stock Ledger
report, without editing vendor code directly - it's monkey-patched onto the
report module at app-load time (see apil_custom/__init__.py), so it survives
ERPNext updates instead of being wiped out by them.

If ERPNext ever changes stock_ledger.execute()'s internal shape enough that
this patch stops applying cleanly, the wrapper below fails soft: the caller
(apil_custom/__init__.py) catches the exception and the standard report just
runs unpatched, without the extra column - it never breaks reporting itself.
"""

import frappe
from frappe import _


def apply():
	from erpnext.stock.report.stock_ledger import stock_ledger as report_module

	if getattr(report_module, "_apil_custom_pieces_patch_applied", False):
		return

	original_execute = report_module.execute

	def patched_execute(filters=None):
		columns, data = original_execute(filters)
		columns.append(
			{
				"label": _("Qty in Pcs"),
				"fieldname": "custom_qty_in_pcs",
				"fieldtype": "Float",
				"width": 90,
			}
		)

		lookup = _build_pieces_lookup(filters)
		for row in data:
			key = _row_key(row)
			if key in lookup:
				row["custom_qty_in_pcs"] = lookup[key]

		return columns, data

	report_module.execute = patched_execute
	report_module._apil_custom_pieces_patch_applied = True


def _row_key(row):
	return (
		row.get("voucher_type"),
		row.get("voucher_no"),
		row.get("item_code"),
		row.get("warehouse"),
		str(row.get("posting_date")),
		str(row.get("posting_time")),
		flt_key(row.get("actual_qty")),
	)


def flt_key(value):
	# Round to avoid float-precision mismatches between the two queries.
	return round(float(value or 0), 6)


def _build_pieces_lookup(filters):
	filters = filters or {}
	if not filters.get("from_date") or not filters.get("to_date"):
		return {}

	sle = frappe.qb.DocType("Stock Ledger Entry")
	query = (
		frappe.qb.from_(sle)
		.select(
			sle.voucher_type,
			sle.voucher_no,
			sle.item_code,
			sle.warehouse,
			sle.posting_date,
			sle.posting_time,
			sle.actual_qty,
			sle.custom_qty_in_pcs,
		)
		.where(
			(sle.docstatus < 2)
			& (sle.is_cancelled == 0)
			& (sle.posting_date[filters.get("from_date") : filters.get("to_date")])
			& (sle.custom_qty_in_pcs.notnull())
		)
	)

	if filters.get("company"):
		query = query.where(sle.company == filters.get("company"))

	rows = query.run(as_dict=True)

	lookup = {}
	for row in rows:
		key = (
			row.voucher_type,
			row.voucher_no,
			row.item_code,
			row.warehouse,
			str(row.posting_date),
			str(row.posting_time),
			flt_key(row.actual_qty),
		)
		lookup[key] = row.custom_qty_in_pcs

	return lookup
