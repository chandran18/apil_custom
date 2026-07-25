import frappe

ROLE = "APIL Mobile Approver"

# Second round of hidden report dependencies, again only found by actually
# exercising each report as the restricted role (Administrator bypasses all
# permission checks, so this can't be caught by testing as Administrator -
# see v1_2/v1_3 for the same lesson):
#   - Payment Ledger Entry: Accounts Payable's ageing calc reads this ledger.
#   - Supplier Group: Purchase Register joins the supplier's group.
#   - Currency: Profit and Loss Statement resolves the company currency.
# All three are read-only reference/ledger data, not sensitive documents.
DOCPERM_UPDATES = {
	"Payment Ledger Entry": {"read": 1, "report": 1},
	"Supplier Group": {"read": 1},
	"Currency": {"read": 1},
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
