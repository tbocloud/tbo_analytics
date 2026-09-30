# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

"""
Create the "Project Approver" role on sites that already have the app installed
(or where an earlier install failed partway). Runs pre_model_sync because the
Implementation Estimate DocType grants permissions to this role. Fresh installs
get it from install.before_install instead, since Frappe skips patches on install.
"""

from tbo_analytics.install import create_custom_roles


def execute():
	create_custom_roles()
