app_name = "tbo_analytics"
app_title = "tbo analytics"
app_publisher = "tbo"
app_description = "data science and analysis realted app"
app_email = "tbo@gmail.com"
app_license = "mit"

# Fixtures — loaded by: bench --site [site] migrate
# Order matters: Workflow State + Action Master must exist before the Workflow record.
fixtures = [
	{"dt": "ERP Module Master", "filters": []},
	{"dt": "Integration Type Master", "filters": []},
	{"dt": "Team Role Master", "filters": []},
	{"dt": "Workflow State", "filters": [["name", "in", [
		"Draft", "Under Review", "Revision Requested", "Approved", "Won", "Lost", "On Hold", "Delivered"
	]]]},
	{"dt": "Workflow Action Master", "filters": [["name", "in", [
		"Submit for Review", "Approve", "Request Revision", "Resubmit",
		"Mark Won", "Mark Lost", "Put on Hold", "Resume", "Mark Delivered"
	]]]},
	{"dt": "Workflow", "filters": [["name", "=", "Implementation Estimate Workflow"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "tbo analytics"]]},
	{"dt": "Dashboard", "filters": [["module", "=", "tbo analytics"]]},
	# Custom fields we install on standard ERPNext doctypes. Filter keeps re-exports
	# scoped to ours so we don't accidentally clobber other apps' custom fields.
	{"dt": "Custom Field", "filters": [["fieldname", "in", [
		"custom_implementation_estimate",
	]]]},
	{"dt": "Print Format", "filters": [["name", "in", [
		"Implementation Estimate Quote",
	]]]},
	{"dt": "Workspace", "filters": [["name", "in", [
		"Implementation Estimates",
	]]]},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "tbo_analytics",
# 		"logo": "/assets/tbo_analytics/logo.png",
# 		"title": "tbo analytics",
# 		"route": "/tbo_analytics",
# 		"has_permission": "tbo_analytics.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/tbo_analytics/css/tbo_analytics.css"
# app_include_js = "/assets/tbo_analytics/js/tbo_analytics.js"

# include js, css files in header of web template
# web_include_css = "/assets/tbo_analytics/css/tbo_analytics.css"
# web_include_js = "/assets/tbo_analytics/js/tbo_analytics.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "tbo_analytics/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Implementation Estimate": "public/js/implementation_estimate.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "tbo_analytics/public/icons.svg"

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
# 	"methods": "tbo_analytics.utils.jinja_methods",
# 	"filters": "tbo_analytics.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "tbo_analytics.install.before_install"
# after_install = "tbo_analytics.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "tbo_analytics.uninstall.before_uninstall"
# after_uninstall = "tbo_analytics.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "tbo_analytics.utils.before_app_install"
# after_app_install = "tbo_analytics.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "tbo_analytics.utils.before_app_uninstall"
# after_app_uninstall = "tbo_analytics.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "tbo_analytics.notifications.get_notification_config"

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

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Implementation Estimate": {
		"before_save": "tbo_analytics.tbo_analytics.handlers.calculate_ai_estimates",
		"on_submit": "tbo_analytics.tbo_analytics.handlers.validate_completeness",
	},
	"Project": {
		# When a Project is saved with custom_implementation_estimate set, mirror the
		# link back onto the Implementation Estimate's linked_project field. Lets the
		# JS button open a pre-filled new Project form and have the back-link establish
		# itself on user save (no silent server insert).
		"after_insert": "tbo_analytics.tbo_analytics.handlers.link_estimate_on_project_insert",
		"on_trash":     "tbo_analytics.tbo_analytics.handlers.clear_estimate_link_on_project_delete",
		# When a linked Project moves to status='Completed', auto-transition the connected
		# Implementation Estimate from Won → Delivered so it stops counting in capacity /
		# team-conflict checks.
		"on_update":    "tbo_analytics.tbo_analytics.handlers.auto_mark_estimate_delivered",
	},
	"Task": {
		"on_update": "tbo_analytics.tbo_analytics.handlers.update_time_coverage",
	},
	"Timesheet": {
		"on_submit": "tbo_analytics.tbo_analytics.handlers.update_time_coverage",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"weekly": [
		"tbo_analytics.tbo_analytics.tasks.update_historical_averages",
		"tbo_analytics.tbo_analytics.tasks.refresh_time_coverage_cache",
	],
}

# Testing
# -------

# before_tests = "tbo_analytics.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "tbo_analytics.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "tbo_analytics.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["tbo_analytics.utils.before_request"]
# after_request = ["tbo_analytics.utils.after_request"]

# Job Events
# ----------
# before_job = ["tbo_analytics.utils.before_job"]
# after_job = ["tbo_analytics.utils.after_job"]

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
# 	"tbo_analytics.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

