import frappe
from erpnext.accounts.utils import repost_gle_for_stock_vouchers

# One-off setup, not a permanent patch: run manually once via
#   bench --site f.com execute apil_custom.patches.create_warehouse_specific_accounts.execute
#
# The 3 melting/casting warehouses were all pointed at the same shared
# '1.1.8.1 - Stock In Hand - Ap' account, so ERPNext netted every transfer
# between them to zero and posted no GL entry at all. Per explicit request,
# each warehouse gets its own account so the value transformation
# (raw material -> finished goods, loss absorbed at 0 cost) shows up as a
# real GL entry. Can't nest these under Stock In Hand itself - it already
# has 382 GL Entries and Frappe won't let a leaf-with-entries become a
# group - so these are created as siblings under the same parent group
# (1.1.8 - Stock Assets - Ap) instead.

COMPANY = "Alu Products Industries Ltd"
PARENT_ACCOUNT = "1.1.8 - Stock Assets - Ap"

COMPANY_ABBR = "Ap"

# account_name here excludes the company abbreviation - Frappe's Account
# autoname appends " - {company_abbr}" itself, so including it here would
# double it up (as happened on the first attempt: "...Furnace - Ap - Ap").
NEW_ACCOUNTS = {
	"Furnace - Ap": ("1.1.8.2", "Stock In Hand - Furnace"),
	"Stores - Ap": ("1.1.8.3", "Stock In Hand - Stores"),
	"Extrusion Mill Finish - Ap": ("1.1.8.4", "Stock In Hand - Extrusion Mill Finish"),
}

TARGET_DOCS = [
	"MAT-STE-2026-01020-1",
	"MAT-STE-2026-01021-2",
	"MAT-STE-2026-01022-2",
	"MAT-STE-2026-01023-2",
	"MAT-STE-2026-01024-2",
]


def execute():
	for warehouse, (account_number, account_name) in NEW_ACCOUNTS.items():
		full_name = f"{account_number} - {account_name} - {COMPANY_ABBR}"
		if not frappe.db.exists("Account", full_name):
			acc = frappe.new_doc("Account")
			acc.account_name = account_name
			acc.account_number = account_number
			acc.parent_account = PARENT_ACCOUNT
			acc.company = COMPANY
			acc.root_type = "Asset"
			acc.account_type = "Stock"
			acc.is_group = 0
			acc.insert()
			print(f"Created account {acc.name}")
		else:
			print(f"Account {full_name} already exists")

		wh = frappe.get_doc("Warehouse", warehouse)
		wh.account = full_name
		wh.save()
		print(f"Linked {warehouse} -> {full_name}")

	frappe.db.commit()

	stock_vouchers = [("Stock Entry", name) for name in TARGET_DOCS]
	repost_gle_for_stock_vouchers(stock_vouchers, "2026-02-16", company=COMPANY)
	frappe.db.commit()

	for name in TARGET_DOCS:
		count = frappe.db.count("GL Entry", {"voucher_no": name, "is_cancelled": 0})
		print(f"{name}: {count} GL Entries now")
