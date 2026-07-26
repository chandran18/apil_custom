app_name = "apil_custom"
app_title = "Weight Based Sales Pricing"
app_publisher = "Alu Products Industries Ltd"
app_description = "Custom app for weight-based sales pricing (Actual Weight / Catalogue Weight billing) for Alu Products Industries Ltd"
app_email = "admin@example.com"
app_license = "mit"

# Fixtures: ship the weight-pricing custom fields as part of this app
# (exported via `bench --site f.com export-fixtures`) instead of leaving
# them as bare database rows.
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [
			[
				"name", "in", [
					"Item-custom_catalogue_weight",
					"Customer-custom_weight_basis",
					"Sales Order Item-custom_catalogue_weight",
					"Sales Order Item-custom_actual_weight",
					"Sales Order Item-custom_weight_used",
					"Sales Order Item-custom_rate_per_kg",
					"Sales Invoice Item-custom_catalogue_weight",
					"Sales Invoice Item-custom_actual_weight",
					"Sales Invoice Item-custom_weight_used",
					"Sales Invoice Item-custom_rate_per_kg",
					"Contact-is_billing_contact",
					"Sales Order Item-custom_qty_in_pcs",
					"Sales Invoice Item-custom_qty_in_pcs",
					"Purchase Order Item-custom_qty_in_pcs",
					"Purchase Invoice Item-custom_qty_in_pcs",
					"Purchase Receipt Item-custom_qty_in_pcs",
					"Stock Entry Detail-custom_qty_in_pcs",
					"Stock Ledger Entry-custom_qty_in_pcs",
					"Stock Entry-custom_extrusion_shift",
					"Stock Entry-custom_extrusion_consolidated",
					"Stock Entry Detail-custom_auto_consolidated",
					"Stock Entry Detail-custom_extrusion_is_scrap",
					"Item-custom_pc_category",
					"Customer-discount_prices",
					"Sales Order Item-custom_base_rate_per_kg",
					"Sales Order Item-custom_discount_percent_applied",
					"Sales Invoice Item-custom_base_rate_per_kg",
					"Sales Invoice Item-custom_discount_percent_applied",
				]
			]
		]
	},
	{
		"doctype": "Property Setter",
		"filters": [
			[
				"doc_type", "in", ["Sales Order Item", "Sales Invoice Item"]
			],
			[
				"field_name", "in", ["rate", "custom_rate_per_kg", "custom_weight_used", "amount"]
			]
		]
	},
	{
		"doctype": "Role",
		"filters": [
			[
				"name", "=", "APIL Mobile Approver"
			]
		]
	},
	{
		"doctype": "Custom DocPerm",
		"filters": [
			[
				"role", "=", "APIL Mobile Approver"
			]
		]
	},
	{
		"doctype": "Custom Role",
		"filters": [
			[
				"report", "in", [
					"Accounts Payable",
					"Purchase Register",
					"Stock Balance",
					"Profit and Loss Statement",
					"General Ledger",
				]
			]
		]
	}
]
# APIL Mobile Approver (Role + Custom DocPerm rows) is created by the
# apil_custom.patches.v1_1.create_mobile_approver_role patch on migrate;
# the fixture filters above just capture it for export/version control
# afterwards (bench --site f.com export-fixtures), same as the Custom
# Field/Property Setter fixtures above.
# Extrusion Log, Extrusion Log Billet Charge, Shift Production Log,
# Shift Production Log Entry, APIL Settings and Customer Discount Price
# are NOT fixtures - they are native app doctypes (custom=0) with their
# own json + controller files under weight_based_sales_pricing/doctype/,
# converted via the
# convert_custom_doctypes_to_app_doctypes patch.

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "apil_custom",
# 		"logo": "/assets/apil_custom/logo.png",
# 		"title": "Weight Based Sales Pricing",
# 		"route": "/apil_custom",
# 		"has_permission": "apil_custom.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/apil_custom/css/apil_custom.css"
# app_include_js = "/assets/apil_custom/js/apil_custom.js"

# include js, css files in header of web template
# web_include_css = "/assets/apil_custom/css/apil_custom.css"
# web_include_js = "/assets/apil_custom/js/apil_custom.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "apil_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Sales Order": "public/js/weight_pricing.js",
	"Sales Invoice": "public/js/weight_pricing.js",
	"Extrusion Log": "public/js/extrusion_log.js",
	"Shift Production Log": "public/js/shift_production_log.js",
}
doctype_list_js = {
	"Extrusion Log": "public/js/extrusion_log_list.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "apil_custom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "apil_custom.utils.jinja_methods",
# 	"filters": "apil_custom.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "apil_custom.install.before_install"
# after_install = "apil_custom.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "apil_custom.uninstall.before_uninstall"
# after_uninstall = "apil_custom.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "apil_custom.utils.before_app_install"
# after_app_install = "apil_custom.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "apil_custom.utils.before_app_uninstall"
# after_app_uninstall = "apil_custom.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "apil_custom.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Stock Entry": "apil_custom.overrides.stock_entry.CustomStockEntry",
	"BOM": "apil_custom.overrides.bom.CustomBOM",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Order": {
		"validate": "apil_custom.weight_pricing.sales.set_weight_and_amount",
		"after_insert": "apil_custom.mobile_notifications.notify_new_weight_priced_document",
	},
	"Sales Invoice": {
		"validate": "apil_custom.weight_pricing.sales.set_weight_and_amount",
		"after_insert": "apil_custom.mobile_notifications.notify_new_weight_priced_document",
	},
	"Extrusion Log": {
		"validate": "apil_custom.extrusion_log.before_save",
		"before_submit": "apil_custom.extrusion_log.before_submit",
	},
	"Shift Production Log": {
		"validate": "apil_custom.shift_production_log.before_save",
		"before_submit": "apil_custom.shift_production_log.before_submit",
		"on_submit": "apil_custom.shift_production_log.on_submit",
	},
	"Stock Ledger Entry": {
		"validate": "apil_custom.overrides.stock_ledger.set_qty_in_pcs",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"apil_custom.tasks.all"
# 	],
# 	"daily": [
# 		"apil_custom.tasks.daily"
# 	],
# 	"hourly": [
# 		"apil_custom.tasks.hourly"
# 	],
# 	"weekly": [
# 		"apil_custom.tasks.weekly"
# 	],
# 	"monthly": [
# 		"apil_custom.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "apil_custom.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "apil_custom.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "apil_custom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["apil_custom.utils.before_request"]
# after_request = ["apil_custom.utils.after_request"]

# Job Events
# ----------
# before_job = ["apil_custom.utils.before_job"]
# after_job = ["apil_custom.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"apil_custom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

