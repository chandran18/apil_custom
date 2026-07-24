__version__ = "0.0.1"


def _apply_stock_ledger_report_patch():
	# Adds the "Qty in Pcs" column to the standard Stock Ledger report.
	# Runs once per process at app import time. Fails soft: if ERPNext's
	# internals shift enough to break this, the standard report still
	# works, just without the extra column.
	try:
		from apil_custom.overrides.stock_ledger_report import apply as apply_patch

		apply_patch()
	except Exception:
		# Import-time code with no guaranteed site/DB context - never let a
		# logging failure here take down app import itself.
		try:
			import frappe

			frappe.log_error(title="apil_custom: failed to patch Stock Ledger report")
		except Exception:
			pass


_apply_stock_ledger_report_patch()
