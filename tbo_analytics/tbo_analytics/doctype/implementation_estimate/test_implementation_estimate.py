# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestImplementationEstimate(FrappeTestCase):
	def setUp(self):
		# Create test ERP Module Master if not exists
		if not frappe.db.exists("ERP Module Master", "Accounts"):
			frappe.get_doc({
				"doctype": "ERP Module Master",
				"module_name": "Accounts",
				"module_code": "ACC",
				"category": "Finance",
				"base_hours_complexity_1": 80,
				"base_hours_complexity_2": 130,
				"is_active": 1
			}).insert()

	def test_calculations(self):
		# Create a dummy estimate doc
		doc = frappe.get_doc({
			"doctype": "Implementation Estimate",
			"client_name": "C24004",
			"company_size": "Small",
			"target_margin_pct": 30.0,
			"recommended_band": "Standard",
			"module_selections": [
				{
					"module": "Accounts",
					"is_included": 1,
					"complexity": 1.0,
				}
			],
			"team_members": [
				{
					"role": "Project Manager",
					"hourly_cost": 1000.0,
					"allocated_hours": 40.0,
					"is_active_in_current_version": 1
				}
			]
		})

		# Save doc to trigger before_save hook
		doc.insert()

		# Verify AI hours populated
		self.assertGreater(doc.module_selections[0].ai_estimated_hours, 0)
		self.assertEqual(doc.module_selections[0].final_hours, doc.module_selections[0].ai_estimated_hours)

		# Verify total hours and grand total
		self.assertGreater(doc.grand_total_hours, 0)
		self.assertEqual(doc.total_modules_hours, doc.module_selections[0].total_module_hours)

		# Verify cost and pricing calculations
		self.assertEqual(doc.team_cost_total, 40000.0) # 1000 * 40
		self.assertGreater(doc.grand_total_cost, 0)
		self.assertGreater(doc.recommended_price, 0)
		self.assertGreater(doc.floor_price, 0)
		self.assertGreater(doc.standard_price, 0)
		self.assertGreater(doc.premium_price, 0)

		# Verify break-even calculations
		self.assertGreater(doc.break_even_hours, 0)
		self.assertGreater(doc.break_even_pct, 0)
		self.assertIsNotNone(doc.break_even_note)


def run_test():
	import unittest
	suite = unittest.TestLoader().loadTestsFromTestCase(TestImplementationEstimate)
	runner = unittest.TextTestRunner(verbosity=2)
	runner.run(suite)

