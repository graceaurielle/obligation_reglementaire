app_name = "obligation_reglementaire"
app_title = "Obligation Reglementaire"
app_publisher = "grace"
app_description = "il s\'agit du troisieme module de compliance intitulé obligation reglementaire"
app_email = "gatse007@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "obligation_reglementaire",
# 		"logo": "/assets/obligation_reglementaire/logo.png",
# 		"title": "Obligation Reglementaire",
# 		"route": "/obligation_reglementaire",
# 		"has_permission": "obligation_reglementaire.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/obligation_reglementaire/css/obligation_reglementaire.css"
app_include_js = "/assets/obligation_reglementaire/js/obligation_reglementaire.js"

# include js, css files in header of web template
# web_include_css = "/assets/obligation_reglementaire/css/obligation_reglementaire.css"
# web_include_js = "/assets/obligation_reglementaire/js/obligation_reglementaire.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "obligation_reglementaire/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "obligation_reglementaire/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "obligation_reglementaire.utils.jinja_methods",
# 	"filters": "obligation_reglementaire.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "obligation_reglementaire.install.before_install"
# after_install = "obligation_reglementaire.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "obligation_reglementaire.uninstall.before_uninstall"
# after_uninstall = "obligation_reglementaire.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "obligation_reglementaire.utils.before_app_install"
# after_app_install = "obligation_reglementaire.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "obligation_reglementaire.utils.before_app_uninstall"
# after_app_uninstall = "obligation_reglementaire.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "obligation_reglementaire.notifications.get_notification_config"

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

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"obligation_reglementaire.tasks.all"
# 	],
# 	"daily": [
# 		"obligation_reglementaire.tasks.daily"
# 	],
# 	"hourly": [
# 		"obligation_reglementaire.tasks.hourly"
# 	],
# 	"weekly": [
# 		"obligation_reglementaire.tasks.weekly"
# 	],
# 	"monthly": [
# 		"obligation_reglementaire.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "obligation_reglementaire.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "obligation_reglementaire.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "obligation_reglementaire.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "obligation_reglementaire.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["obligation_reglementaire.utils.before_request"]
# after_request = ["obligation_reglementaire.utils.after_request"]

# Job Events
# ----------
# before_job = ["obligation_reglementaire.utils.before_job"]
# after_job = ["obligation_reglementaire.utils.after_job"]

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
# 	"obligation_reglementaire.auth.validate"
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

# ----------------------------------------------------------------------------- installation / migration
after_install = "obligation_reglementaire.install.after_install"
after_migrate = "obligation_reglementaire.install.after_migrate"

# Les rôles métiers sont livrés par code (install.py) afin de rester idempotents et indépendants des fixtures.

# ----------------------------------------------------------------------------- événements transverses
# Organisation par défaut, organisation suspendue, journal d'audit, interdiction de suppression physique.
doc_events = {
	"*": {
		"validate": "obligation_reglementaire.events.validate",
		"on_update": "obligation_reglementaire.events.on_update",
		"on_trash": "obligation_reglementaire.events.on_trash",
		"before_save": "obligation_reglementaire.events.before_save_log",
	},
}

# ----------------------------------------------------------------------------- portail web cross-app
update_website_context = "obligation_reglementaire.website.inject_obligation_nav"
before_request = ["obligation_reglementaire.website.install_landing_page_patch"]

# ----------------------------------------------------------------------------- planificateur
scheduler_events = {
	"daily": [
		"obligation_reglementaire.tasks.daily",
	],
	"hourly": [
		"obligation_reglementaire.tasks.hourly",
	],
	"cron": {
		# Résumé quotidien envoyé en début de journée ouvrée
		"0 7 * * *": ["obligation_reglementaire.tasks.daily_digest"],
	},
}


