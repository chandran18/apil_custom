import frappe

# These 5 doctypes were originally created via the Desk "New DocType" screen
# (custom=1, schema stored only in the database). Converting them to native
# app doctypes writes their schema as json + controller files under
# apil_custom/weight_based_sales_pricing/doctype/*, so the app fully owns
# them - no fixture export needed for DocType itself, matching every other
# real doctype in the app.
DOCTYPES = [
	"Extrusion Log",
	"Extrusion Log Billet Charge",
	"APIL Settings",
	"Customer Discount Price",
]


def execute():
	frappe.flags.allow_doctype_export = True
	for name in DOCTYPES:
		doc = frappe.get_doc("DocType", name)
		if not doc.custom:
			continue
		doc.custom = 0
		doc.save()
	frappe.flags.allow_doctype_export = False
