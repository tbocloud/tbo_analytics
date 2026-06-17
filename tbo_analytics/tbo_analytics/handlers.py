# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

"""
Server-side event handlers for Implementation Estimate.
Registered in hooks.py under doc_events.
"""

import frappe
from frappe.utils import now_datetime


def calculate_ai_estimates(doc, method):
	"""Triggered before_save — delegates to DocType controller."""
	doc.calculate_ai_estimates()
	doc.calculate_final_hours()
	doc.calculate_costs()
	doc.calculate_pricing()
	doc.calculate_break_even()


def validate_completeness(doc, method):
	"""Triggered on_submit — basic completeness checks."""
	if not doc.module_selections and not doc.custom_module_requests:
		frappe.throw("Cannot submit an estimate with no modules or custom modules selected.")
	if not doc.team_members:
		frappe.throw("Cannot submit an estimate with no team members assigned.")
	if not doc.recommended_price:
		frappe.throw("Recommended price has not been calculated. Please save the estimate first.")


def link_estimate_on_project_insert(doc, method):
	"""Project.after_insert hook.

	If a newly-saved Project carries `custom_implementation_estimate`, mirror the link
	back onto that estimate's `linked_project` field. This is the back-half of the
	Create Project flow: the form button opens a pre-filled new Project, the user
	reviews + saves, and on save we wire both sides of the link.

	Guards against overwriting an estimate that's already linked to a different project
	— logs a warning and bails rather than silently clobbering.
	"""
	est_name = getattr(doc, "custom_implementation_estimate", None)
	if not est_name:
		return
	if not frappe.db.exists("Implementation Estimate", est_name):
		return

	existing = frappe.db.get_value("Implementation Estimate", est_name, "linked_project")
	if existing and existing != doc.name:
		frappe.log_error(
			f"Project {doc.name} claims estimate {est_name}, but {est_name} is already "
			f"linked to project {existing}. Leaving the existing link in place.",
			"Implementation Estimate — Project back-link conflict",
		)
		return

	frappe.db.set_value("Implementation Estimate", est_name, "linked_project", doc.name)
	est_doc = frappe.get_doc("Implementation Estimate", est_name)
	_notify_project_created(est_doc, doc.name)


def auto_mark_estimate_delivered(doc, method):
	"""Project.on_update hook.

	When a linked Project transitions to status='Completed', auto-move the
	connected Implementation Estimate from 'Won' to 'Delivered'. This drops it
	out of the per-estimate team-conflict / capacity-utilisation widget, which
	filters strictly on status='Won'.

	Only runs when the project's status actually changed (avoids redundant
	writes on every save).
	"""
	if not doc.has_value_changed("status"):
		return
	if (doc.status or "").lower() != "completed":
		return
	est_name = getattr(doc, "custom_implementation_estimate", None)
	if not est_name:
		return
	if not frappe.db.exists("Implementation Estimate", est_name):
		return

	current_status = frappe.db.get_value("Implementation Estimate", est_name, "status")
	if current_status != "Won":
		# Already Delivered, or never reached Won — nothing to do.
		return

	# `status` is the workflow_state_field per workflow.json — one write is enough.
	frappe.db.set_value("Implementation Estimate", est_name, "status", "Delivered")


def clear_estimate_link_on_project_delete(doc, method):
	"""Project.on_trash hook — clear the back-link so the estimate can recreate cleanly."""
	# Always clear any estimate pointing at this project — covers both the new flow
	# (custom_implementation_estimate set) and any legacy projects without it.
	for est in frappe.get_all(
		"Implementation Estimate",
		filters={"linked_project": doc.name},
		pluck="name",
	):
		frappe.db.set_value("Implementation Estimate", est, "linked_project", None)


def _notify_project_created(doc, project_name):
	"""Send in-app notification to assigned pre-sales and project managers."""
	users = set()
	if doc.assigned_pre_sales:
		users.add(doc.assigned_pre_sales)

	# Add all Project Manager role members from team
	for row in doc.team_members:
		if row.role == "Project Manager" and row.employee:
			emp_user = frappe.db.get_value("Employee", row.employee, "user_id")
			if emp_user:
				users.add(emp_user)

	msg = f"Implementation Estimate {doc.name} marked Won. Project {project_name} created."
	for user in users:
		frappe.publish_realtime(event="msgprint", message=msg, user=user)


def update_time_coverage(doc, method):
	"""
	Triggered when a Task or Timesheet is updated.
	Updates actual_hours_logged on the linked Project.
	"""
	project_name = None

	if doc.doctype == "Timesheet":
		# Get project from first detail row
		for detail in (doc.time_logs or []):
			if detail.project:
				project_name = detail.project
				break
	elif doc.doctype == "Task":
		project_name = doc.project

	if not project_name:
		return

	# Sum all timesheet hours for this project
	result = frappe.db.sql("""
		SELECT SUM(tsd.hours)
		FROM `tabTimesheet Detail` tsd
		INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
		WHERE tsd.project = %s AND ts.docstatus = 1
	""", project_name)

	actual_hours = (result[0][0] or 0) if result else 0

	if frappe.db.has_column("Project", "custom_actual_hours_logged"):
		frappe.db.set_value("Project", project_name, "custom_actual_hours_logged", actual_hours)
