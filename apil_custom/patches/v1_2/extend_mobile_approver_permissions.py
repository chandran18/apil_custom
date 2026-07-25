import frappe

ROLE = "APIL Mobile Approver"

# doctype -> perm flags to ensure are set (existing rows are updated in
# place, never recreated, so this only ever turns flags on).
DOCPERM_UPDATES = {
	"Purchase Order": {"read": 1, "submit": 1},
	"Purchase Invoice": {"read": 1, "submit": 1, "report": 1},
	"Payment Entry": {"read": 1, "submit": 1},
	"Sales Invoice": {"report": 1},
	"GL Entry": {"read": 1, "report": 1},
	"Stock Ledger Entry": {"read": 1, "report": 1},
	# v1_1 only granted read=1 on Extrusion Log; the Executive Dashboard and
	# the Extrusion Log Summary report both also need report=1
	# (frappe.desk.query_report.run checks has_permission(ref_doctype,
	# "report") separately from the report's own allowed-roles list).
	"Extrusion Log": {"read": 1, "report": 1},
}

# report_name -> ref_doctype, so we know the report is genuinely one whose
# is_permitted() check we need to extend. Roles are read from the report's
# existing "Has Role" rows and preserved - a Custom Role record *replaces*
# the allowed-roles list rather than adding to it (see
# frappe.core.doctype.report.report.Report.is_permitted), so dropping the
# original roles here would revoke desk users' access to these reports.
REPORT_ROLE_OVERRIDES = [
	"Accounts Payable",
	"Purchase Register",
	"Stock Balance",
	"Profit and Loss Statement",
	"General Ledger",
]


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

	for report_name in REPORT_ROLE_OVERRIDES:
		original_roles = frappe.get_all(
			"Has Role", filters={"parent": report_name, "parenttype": "Report"}, pluck="role"
		)
		allowed_roles = sorted(set(original_roles) | {ROLE})

		custom_role_name = frappe.db.get_value("Custom Role", {"report": report_name})
		if custom_role_name:
			doc = frappe.get_doc("Custom Role", custom_role_name)
		else:
			doc = frappe.new_doc("Custom Role")
			doc.report = report_name

		doc.set("roles", [{"role": r} for r in allowed_roles])
		doc.save(ignore_permissions=True)

	frappe.clear_cache(doctype="Purchase Order")
	frappe.clear_cache(doctype="Purchase Invoice")
	frappe.clear_cache(doctype="Payment Entry")
	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="GL Entry")
	frappe.clear_cache(doctype="Stock Ledger Entry")
	frappe.clear_cache(doctype="Extrusion Log")
