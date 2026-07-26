import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Extrusion Log", "fieldname": "name", "fieldtype": "Link", "options": "Extrusion Log", "width": 130},
		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 95},
		{"label": "Shift", "fieldname": "shift", "fieldtype": "Data", "width": 60},
		{"label": "Die No", "fieldname": "die_no", "fieldtype": "Data", "width": 90},
		{"label": "Item", "fieldname": "sec_no", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": "OK Pcs", "fieldname": "ok_pcs", "fieldtype": "Int", "width": 80},
		{"label": "Per Pc Weight (Kg)", "fieldname": "per_pc_weight", "fieldtype": "Float", "width": 110},
		{"label": "Total Input (Kg)", "fieldname": "total_input", "fieldtype": "Float", "width": 110},
		{"label": "Output (Kg)", "fieldname": "output", "fieldtype": "Float", "width": 100},
		{"label": "Rec %", "fieldname": "rec_percent", "fieldtype": "Percent", "width": 80},
		{"label": "Shift Production Log", "fieldname": "included_in_shift_log", "fieldtype": "Link", "options": "Shift Production Log", "width": 150},
		{"label": "Stock Entry", "fieldname": "stock_entry", "fieldtype": "Link", "options": "Stock Entry", "width": 130},
		{"label": "Stock Entry Status", "fieldname": "stock_entry_status", "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	conditions = ["el.docstatus = 1"]
	values = {}

	if filters.get("company"):
		conditions.append("el.company = %(company)s")
		values["company"] = filters["company"]

	if filters.get("item"):
		conditions.append("el.sec_no = %(item)s")
		values["item"] = filters["item"]

	if filters.get("from_date"):
		conditions.append("el.date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("el.date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	rows = frappe.db.sql(
		"""
		select
			el.name, el.date, el.shift, el.die_no, el.sec_no, el.ok_pcs,
			el.per_pc_weight, el.total_input, el.output, el.rec_percent,
			el.included_in_shift_log, el.stock_entry, se.docstatus as se_docstatus
		from `tabExtrusion Log` el
		left join `tabStock Entry` se on se.name = el.stock_entry
		where {conditions}
		order by el.date desc, el.name desc
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)

	status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
	for row in rows:
		row["stock_entry_status"] = status_map.get(row.pop("se_docstatus"), "") if row.get("stock_entry") else ""

	return rows
