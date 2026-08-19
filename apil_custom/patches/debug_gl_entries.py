import frappe
from erpnext.stock import get_warehouse_account_map


def execute():
	company = "Alu Products Industries Ltd"
	warehouse_account = get_warehouse_account_map(company)
	print("warehouse_account map:")
	for k, v in warehouse_account.items():
		print(" ", k, "->", v.get("account") if hasattr(v, "get") else v)

	doc = frappe.get_doc("Stock Entry", "MAT-STE-2026-01024-2")
	print("\nis_perpetual_inventory_enabled:", frappe.get_cached_value(
		"Company", company, "enable_perpetual_inventory"
	))

	try:
		gle = doc.get_gl_entries(warehouse_account)
		print("\nget_gl_entries returned", len(gle), "entries")
		for g in gle:
			print(" ", g.get("account"), "debit=", g.get("debit"), "credit=", g.get("credit"))
	except Exception as e:
		print("\nEXCEPTION calling get_gl_entries:", repr(e))
		import traceback
		traceback.print_exc()
