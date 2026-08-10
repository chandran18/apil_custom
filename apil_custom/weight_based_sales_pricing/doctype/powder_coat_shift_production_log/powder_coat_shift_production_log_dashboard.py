from frappe import _


def get_data():
	return {
		"fieldname": "included_in_shift_log",
		"internal_links": {
			"Stock Entry": ["created_stock_entries", "stock_entry"],
		},
		"transactions": [
			{"label": _("Batches"), "items": ["Powder Coat Log"]},
			{"label": _("Stock"), "items": ["Stock Entry"]},
		],
	}
