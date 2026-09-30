# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

import frappe

# Roles this app introduces. The Implementation Estimate DocType permissions and
# fixtures/workflow.json both reference "Project Approver", so it must exist
# before doctypes and fixtures are synced. ("Projects Manager" comes from ERPNext.)
CUSTOM_ROLES = ["Project Approver"]


def before_install():
	# Runs before doctype + fixture sync on `bench install-app`. Patches don't help
	# here: a fresh install marks every patch as completed without running it.
	create_custom_roles()


def create_custom_roles():
	for role in CUSTOM_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Role",
				"role_name": role,
				"desk_access": 1,
			}).insert(ignore_permissions=True)
