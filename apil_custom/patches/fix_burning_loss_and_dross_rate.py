import frappe

# One-off data fix, not a permanent patch: run manually once via
#   bench --site f.com execute apil_custom.patches.fix_burning_loss_and_dross_rate.execute
# Not registered in patches.txt on purpose - it targets 5 specific historical
# Stock Entries recreated from Tally MFG vouchers, not a schema change that
# should replay on every site.

ENTRIES = {
	"MAT-STE-2026-01020": 80,
	"MAT-STE-2026-01021": 87,
	"MAT-STE-2026-01022": 83,
	"MAT-STE-2026-01023": 86,
	"MAT-STE-2026-01024": 88,
}

BURNING_LOSS_ITEM = "burning loss"
BURNING_LOSS_WAREHOUSE = "Furnace - Ap"


def execute():
	item = frappe.get_doc("Item", BURNING_LOSS_ITEM)
	if not item.is_stock_item:
		item.is_stock_item = 1
		item.save()
		frappe.db.commit()
		print(f"Converted '{BURNING_LOSS_ITEM}' to a stock item")

	for name, burning_loss_qty in ENTRIES.items():
		se = frappe.get_doc("Stock Entry", name)
		se.cancel()

		amended = frappe.copy_doc(se)
		amended.amended_from = se.name
		amended.docstatus = 0

		for row in amended.items:
			if row.item_code == "Dross":
				row.basic_rate = 0
				row.basic_amount = 0
				row.set_basic_rate_manually = 1

		amended.append("items", {
			"item_code": BURNING_LOSS_ITEM,
			"qty": burning_loss_qty,
			"uom": "Kg",
			"t_warehouse": BURNING_LOSS_WAREHOUSE,
			"is_scrap_item": 1,
			"basic_rate": 0,
			"basic_amount": 0,
			"set_basic_rate_manually": 1,
		})

		amended.insert()
		amended.submit()
		frappe.db.commit()
		print(f"{name} -> amended as {amended.name}: Dross rate zeroed, "
			  f"Burning Loss {burning_loss_qty} kg added")
