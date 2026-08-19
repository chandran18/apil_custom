import frappe
from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost

# One-off cleanup, not a permanent patch: run manually once via
#   bench --site f.com execute apil_custom.patches.process_stuck_reposts.execute
# Manually processes the Repost Item Valuation queue entries for the
# item/warehouse combinations touched by the 5 amended Stock Entries
# (MAT-STE-2026-01020-1 .. 01024-2), instead of waiting for the hourly
# scheduled job (which also respects a configured reposting timeslot
# that may not be active right now). Scoped narrowly to these combos
# only - does not touch the rest of the company's repost queue.

TARGET_DOCS = [
	"MAT-STE-2026-01020-1",
	"MAT-STE-2026-01021-2",
	"MAT-STE-2026-01022-2",
	"MAT-STE-2026-01023-2",
	"MAT-STE-2026-01024-2",
]


def execute():
	pairs = frappe.db.sql(
		"""
		SELECT DISTINCT item_code, COALESCE(s_warehouse, t_warehouse) AS warehouse
		FROM `tabStock Entry Detail`
		WHERE parent IN %(docs)s
		""",
		{"docs": TARGET_DOCS},
		as_dict=True,
	)

	names = frappe.db.sql(
		"""
		SELECT name FROM `tabRepost Item Valuation`
		WHERE company = 'Alu Products Industries Ltd'
		  AND status = 'Queued'
		  AND (item_code, warehouse) IN %(pairs)s
		ORDER BY timestamp(posting_date, posting_time) ASC, creation ASC
		""",
		{"pairs": [(p.item_code, p.warehouse) for p in pairs]},
		as_dict=True,
	)

	print(f"Found {len(names)} queued repost entries to process")

	for i, row in enumerate(names, 1):
		doc = frappe.get_doc("Repost Item Valuation", row.name)
		repost(doc)
		print(f"[{i}/{len(names)}] {row.name} -> {doc.status}")
