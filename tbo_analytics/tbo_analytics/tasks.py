# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

"""
Scheduled background tasks for tbo_analytics.
Registered in hooks.py under scheduler_events.
"""

import frappe
from frappe.utils import add_months, today, date_diff


def update_historical_averages():
	"""
	Weekly job: For each ERP Module Master record, query completed Tasks
	that have custom_module_tag set, calculate AVG actual time over last 24 months,
	and update historical_avg_hours on the master.
	"""
	if not frappe.db.has_column("Task", "custom_module_tag"):
		frappe.logger().info("update_historical_averages: custom_module_tag column not found on Task. Skipping.")
		return

	cutoff = add_months(today(), -24)
	modules = frappe.get_all("ERP Module Master", fields=["name"])

	updated = 0
	for m in modules:
		result = frappe.db.sql("""
			SELECT
				AVG(t.actual_time) as avg_hours,
				COUNT(*) as sample_count
			FROM `tabTask` t
			WHERE
				t.custom_module_tag = %s
				AND t.status = 'Completed'
				AND t.completed_on >= %s
				AND t.actual_time > 0
		""", (m.name, cutoff), as_dict=True)

		if result and result[0].avg_hours:
			frappe.db.set_value("ERP Module Master", m.name, {
				"historical_avg_hours": round(result[0].avg_hours, 1),
				"historical_sample_count": int(result[0].sample_count or 0),
			})
			updated += 1

	frappe.logger().info(f"update_historical_averages: Updated {updated}/{len(modules)} modules.")


def refresh_time_coverage_cache():
	"""
	Weekly job: Refresh actual_hours_logged on all active Projects
	that are linked to an Implementation Estimate.
	"""
	if not frappe.db.has_column("Project", "custom_actual_hours_logged"):
		frappe.logger().info("refresh_time_coverage_cache: custom_actual_hours_logged column not on Project. Skipping.")
		return

	linked_projects = frappe.db.sql("""
		SELECT DISTINCT linked_project
		FROM `tabImplementation Estimate`
		WHERE linked_project IS NOT NULL AND linked_project != ''
	""", as_list=True)

	for (project_name,) in linked_projects:
		result = frappe.db.sql("""
			SELECT SUM(tsd.hours)
			FROM `tabTimesheet Detail` tsd
			INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
			WHERE tsd.project = %s AND ts.docstatus = 1
		""", project_name)
		actual = (result[0][0] or 0) if result else 0
		frappe.db.set_value("Project", project_name, "custom_actual_hours_logged", actual)

	frappe.logger().info(f"refresh_time_coverage_cache: Refreshed {len(linked_projects)} projects.")
