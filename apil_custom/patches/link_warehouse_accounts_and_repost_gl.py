import frappe
from erpnext.accounts.utils import repost_gle_for_stock_vouchers

# One-off fix, not a permanent patch: run manually once via
#   bench --site f.com execute apil_custom.patches.link_warehouse_accounts_and_repost_gl.execute
#
# Root cause of "zero GL impact" on Manufacture entries for Alu Products
# Industries Ltd: the 3 warehouses used in the melting/casting process
# (Furnace - Ap, Stores - Ap, Extrusion Mill Finish - Ap) had no Account
# linked at all, so ERPNext computed zero expected GL entries for every
# stock transaction through them - not a reposting-queue problem.
#
# This links all 3 to the company's existing default inventory account,
# then directly reposts GL entries for the 5 amended Stock Entries
# (no need to go through the Repost Item Valuation queue again since
# those records are already marked Completed from the earlier pass).

WAREHOUSES = ["Furnace - Ap", "Stores - Ap", "Extrusion Mill Finish - Ap"]
DEFAULT_ACCOUNT = "1.1.8.1 - Stock In Hand - Ap"
COMPANY = "Alu Products Industries Ltd"

TARGET_DOCS = [
	"MAT-STE-2026-01020-1",
	"MAT-STE-2026-01021-2",
	"MAT-STE-2026-01022-2",
	"MAT-STE-2026-01023-2",
	"MAT-STE-2026-01024-2",
]


def execute():
	for wh_name in WAREHOUSES:
		wh = frappe.get_doc("Warehouse", wh_name)
		if not wh.account:
			wh.account = DEFAULT_ACCOUNT
			wh.save()
			print(f"Linked {wh_name} -> {DEFAULT_ACCOUNT}")

	frappe.db.commit()

	stock_vouchers = [("Stock Entry", name) for name in TARGET_DOCS]
	repost_gle_for_stock_vouchers(stock_vouchers, "2026-02-16", company=COMPANY)
	frappe.db.commit()

	for name in TARGET_DOCS:
		count = frappe.db.count("GL Entry", {"voucher_no": name, "is_cancelled": 0})
		print(f"{name}: {count} GL Entries now")
