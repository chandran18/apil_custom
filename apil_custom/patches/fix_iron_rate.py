import frappe

# One-off data fix, not a permanent patch: run manually once via
#   bench --site f.com execute apil_custom.patches.fix_iron_rate.execute
# Follow-up to fix_burning_loss_and_dross_rate.py - that pass fixed Dross
# and added Burning Loss but missed that "Iron" byproduct rows carry the
# same fictitious rate=50 pattern. Targets the currently-active "-1"
# amendments from that earlier pass.

ENTRIES = [
	"MAT-STE-2026-01021-1",
	"MAT-STE-2026-01022-1",
	"MAT-STE-2026-01023-1",
	"MAT-STE-2026-01024-1",
]


def execute():
	for name in ENTRIES:
		se = frappe.get_doc("Stock Entry", name)
		se.cancel()

		amended = frappe.copy_doc(se)
		amended.amended_from = se.name
		amended.docstatus = 0

		for row in amended.items:
			if row.item_code == "Iron":
				row.basic_rate = 0
				row.basic_amount = 0
				row.set_basic_rate_manually = 1

		amended.insert()
		amended.submit()
		frappe.db.commit()
		print(f"{name} -> amended as {amended.name}: Iron rate zeroed")
