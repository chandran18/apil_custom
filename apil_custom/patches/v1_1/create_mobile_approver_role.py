import frappe

# Doctype -> perm flags granted to the mobile approver role. Extrusion Log is
# read-only here: mobile approvers need to see the die/shift/output that
# produced a pending Stock Entry, but submitting an Extrusion Log itself stays
# a System Manager action (unchanged).
ROLE = "APIL Mobile Approver"
DOCPERMS = {
	"Stock Entry": {"read": 1, "submit": 1},
	"Sales Order": {"read": 1, "submit": 1},
	"Sales Invoice": {"read": 1, "submit": 1},
	"Extrusion Log": {"read": 1},
}


def execute():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({
			"doctype": "Role",
			"role_name": ROLE,
			"desk_access": 1,
		}).insert(ignore_permissions=True)

	for doctype, perms in DOCPERMS.items():
		if frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": ROLE}):
			continue
		frappe.get_doc({
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": ROLE,
			**perms,
		}).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Stock Entry")
	frappe.clear_cache(doctype="Sales Order")
	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Extrusion Log")
