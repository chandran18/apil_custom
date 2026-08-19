import frappe

# One-off cleanup, not a permanent patch: run manually once via
#   bench --site f.com execute apil_custom.patches.delete_cancelled_stock_entries.execute
# Permanently deletes the 9 cancelled Stock Entries left behind by the
# two-pass Dross/Iron/Burning Loss rate fix, per explicit user request
# accepting the loss of amendment audit trail on their replacements.

# Ordered newest-first within each amendment chain so a successor is
# deleted before its predecessor, even though force=1 bypasses the
# link check regardless of order.
NAMES = [
	"MAT-STE-2026-01021-1",
	"MAT-STE-2026-01021",
	"MAT-STE-2026-01022-1",
	"MAT-STE-2026-01022",
	"MAT-STE-2026-01023-1",
	"MAT-STE-2026-01023",
	"MAT-STE-2026-01024-1",
	"MAT-STE-2026-01024",
	"MAT-STE-2026-01020",
]


def execute():
	for name in NAMES:
		frappe.delete_doc("Stock Entry", name, force=1, ignore_permissions=True)
		frappe.db.commit()
		print(f"Deleted {name}")
