import frappe

ROLE = "APIL Mobile Approver"

# Frappe's Document.submit() calls self.save() internally, which checks
# "write" permission before it ever gets to the docstatus 0->1 transition
# check - "submit" alone is not enough. v1_1/v1_2 only ever granted
# read+submit, so approve_document has been silently broken for every
# non-Administrator user since it was first built (Administrator bypasses
# all permission checks, so testing with the admin key never caught this -
# only surfaced once a real restricted user tried to approve something).
DOCTYPES = ["Stock Entry", "Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice", "Payment Entry"]


def execute():
	for doctype in DOCTYPES:
		name = frappe.db.get_value("Custom DocPerm", {"parent": doctype, "role": ROLE})
		if not name:
			continue
		frappe.db.set_value("Custom DocPerm", name, "write", 1)
		frappe.clear_cache(doctype=doctype)
