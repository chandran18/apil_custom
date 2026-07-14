import frappe
from frappe.utils import flt


def _get_base_rate_and_discount(item_code, customer):
	"""APIL Settings.default_rate_per_kg (base) and the customer's Discount
	Price row matching this item's PC/Non-PC Category (0 if the customer
	has no row for that category). Returned separately - not just the
	final discounted number - so callers can display both on the
	transaction for transparency, regardless of whether the final
	Rate per Kg ends up auto-derived or manually typed.
	"""
	base_rate = frappe.db.get_single_value("APIL Settings", "default_rate_per_kg") or 0
	category = frappe.db.get_value("Item", item_code, "custom_pc_category")

	discount_percent = 0
	if customer and category:
		discount_percent = frappe.db.get_value(
			"Customer Discount Price", {"parent": customer, "category": category}, "discount_percent"
		) or 0

	return flt(base_rate), flt(discount_percent)


def _compute_weight_pricing(item_code, customer, qty, rate_per_kg, actual_weight=0):
	"""Shared calculation used by both the save-time hook (authoritative) and
	the live client-side preview API (so the two can never drift apart).

	Returns None if this item isn't weight-priced (no Catalogue Weight set),
	meaning standard Qty x Rate behaviour should apply untouched.
	"""
	qty = flt(qty)
	rate_per_kg = flt(rate_per_kg)
	actual_weight = flt(actual_weight)

	catalogue_weight_per_unit = frappe.db.get_value("Item", item_code, "custom_catalogue_weight") or 0
	if not catalogue_weight_per_unit:
		return None

	weight_basis = (frappe.db.get_value("Customer", customer, "custom_weight_basis") if customer else None) or "Catalogue Weight"
	catalogue_weight = flt(catalogue_weight_per_unit * qty, 4)

	if weight_basis == "Actual Weight":
		weight_used = actual_weight
	else:
		weight_used = catalogue_weight

	# Reference figures shown on the transaction so the discount is
	# transparent even when a manual Rate per Kg is used instead.
	base_rate_per_kg, discount_percent_applied = _get_base_rate_and_discount(item_code, customer)

	# Only auto-derive Rate per Kg from Settings + Category + Customer
	# discount when the user hasn't typed one in - a manually entered rate
	# always wins.
	if not rate_per_kg:
		rate_per_kg = flt(base_rate_per_kg * (1 - discount_percent_applied / 100), 4)

	adjusted_rate = flt(weight_used * rate_per_kg / qty, 4) if qty else 0

	return {
		"weight_basis": weight_basis,
		"catalogue_weight": catalogue_weight,
		"weight_used": weight_used,
		"rate_per_kg": rate_per_kg,
		"base_rate_per_kg": base_rate_per_kg,
		"discount_percent_applied": discount_percent_applied,
		"adjusted_rate": adjusted_rate,
	}


def set_weight_and_amount(doc, method=None):
	"""Bill by Weight x Rate per Kg instead of Qty x Rate (save-time,
	authoritative). See _compute_weight_pricing for the shared math, and
	get_weight_amount_preview below for the live client-side version of
	the same calculation.

	ERPNext's own calculate_taxes_and_totals() unconditionally recomputes
	item.amount = qty * item.rate every time it runs (see
	erpnext/controllers/taxes_and_totals.py: calculate_item_values). So we
	don't fight that - we feed it a pre-adjusted item.rate such that
	qty * adjusted_rate = weight_used * rate_per_kg, and let ERPNext's own
	engine do the rest (taxes, rounding, grand total all cascade correctly).

	Qty is left untouched (stock/delivery still tracks pieces correctly);
	only Rate (and the Amount/totals derived from it) changes.
	"""
	changed = False
	for item in doc.items:
		result = _compute_weight_pricing(
			item.item_code, doc.customer, item.qty, item.custom_rate_per_kg, item.custom_actual_weight
		)
		if result is None:
			continue

		if result["weight_basis"] == "Actual Weight" and not result["weight_used"]:
			frappe.throw(
				"Row #{0} ({1}): {2} is billed on Actual Weight. "
				"Please enter the Actual Weight (Kg) for this line before saving.".format(
					item.idx, item.item_code, doc.customer
				)
			)

		if not result["rate_per_kg"]:
			frappe.throw(
				"Row #{0} ({1}): please enter Rate per Kg, or configure a Default Rate per Kg "
				"in APIL Settings.".format(item.idx, item.item_code)
			)

		item.custom_catalogue_weight = result["catalogue_weight"]
		item.custom_weight_used = result["weight_used"]
		item.custom_rate_per_kg = result["rate_per_kg"]
		item.custom_base_rate_per_kg = result["base_rate_per_kg"]
		item.custom_discount_percent_applied = result["discount_percent_applied"]
		item.rate = flt(result["adjusted_rate"], item.precision("rate"))
		changed = True

	if changed:
		doc.calculate_taxes_and_totals()


@frappe.whitelist()
def get_weight_amount_preview(item_code, customer, qty, rate_per_kg=0, actual_weight=0):
	"""Live client-side preview: called from Sales Order/Invoice item grid JS
	on item_code/qty/rate_per_kg/actual_weight change, so Amount is correct
	on screen immediately, without needing to Save first.
	"""
	result = _compute_weight_pricing(item_code, customer, qty, rate_per_kg, actual_weight)
	if result is None:
		return {"is_weight_item": False}
	return {"is_weight_item": True, **result}
