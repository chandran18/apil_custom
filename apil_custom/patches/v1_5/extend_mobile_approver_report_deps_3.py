import frappe

ROLE = "APIL Mobile Approver"

# Third round: Purchase Register cross-references Purchase Receipt (to show
# what a Purchase Invoice was received against). Same story as v1_3/v1_4 -
# only surfaces when testing as the restricted role, not as Administrator.
DOCPERM_UPDATES = {
	"Purchase Receipt": {"read": 1},
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
