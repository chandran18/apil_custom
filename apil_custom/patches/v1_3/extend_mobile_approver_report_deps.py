import frappe

ROLE = "APIL Mobile Approver"

# Read-only permissions the standard reports need on doctypes they touch
# internally, discovered by actually running each report as a
# non-Administrator APIL Mobile Approver user (Administrator bypasses all
# permission checks, so v1_2's own testing didn't catch these):
#   - Company: report filters are Link fields to Company, and Frappe checks
#     read permission on the linked document when resolving them.
#   - Journal Entry: Accounts Payable looks up bill_no/bill_date via a
#     Journal Entry sub-query.
#   - Supplier: Purchase Register joins Supplier for the supplier name/group.
#   - Account: Profit and Loss Statement / General Ledger read the Chart of
#     Accounts directly.
DOCPERM_UPDATES = {
	"Company": {"read": 1},
	"Journal Entry": {"read": 1, "report": 1},
	"Supplier": {"read": 1},
	"Account": {"read": 1, "report": 1},
}


def execute():
	for doctype, perms in DOCPERM_UPDATES.items():
		name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": ROLE})
		if name:
			frappe.db.set_value("Custom DocPerm", name, perms)
			continue
		frappe.get_doc({
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": ROLE,
			**perms,
		}).insert(ignore_permissions=True)

	for doctype in DOCPERM_UPDATES:
		frappe.clear_cache(doctype=doctype)
