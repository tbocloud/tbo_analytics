# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

"""
Pre-migration patch: convert the `complexity` column from the old Select values
("1 — Standard", "2 — Complex", "1 — Simple") to numeric strings ("1.0", "2.0")
before Frappe's schema sync changes the column type from VARCHAR to DECIMAL.

MariaDB strict mode rejects the implicit ALTER TABLE cast from "2 — Complex" to
DECIMAL with "Truncated incorrect DECIMAL value", so this patch normalises the
strings first.

Affects three child doctypes:
  - Module Selection
  - Custom Module Request
  - Integration Requirement
"""

import frappe


# Exact mapping of every legacy Select value → numeric string equivalent.
# The em-dash here is U+2014 (the exact character Frappe used in the Select options).
LEGACY_TO_FLOAT = {
	"1 — Standard": "1.0",
	"1 — Simple":   "1.0",
	"2 — Complex":  "2.0",
	"":                   "1.0",
}


def execute():
	tables = [
		"tabModule Selection",
		"tabCustom Module Request",
		"tabIntegration Requirement",
	]
	for tbl in tables:
		if not frappe.db.table_exists(tbl):
			continue

		# First, replace each known legacy value with its numeric equivalent.
		# Parameterised so PyMySQL doesn't try to interpret % characters.
		for old_value, new_value in LEGACY_TO_FLOAT.items():
			frappe.db.sql(
				f"UPDATE `{tbl}` SET complexity = %s WHERE complexity = %s",
				(new_value, old_value),
			)

		# Anything still NULL becomes the safe default "1.0".
		frappe.db.sql(f"UPDATE `{tbl}` SET complexity = '1.0' WHERE complexity IS NULL")

		# Anything that doesn't look numeric at this point — log it loudly and force
		# to "1.0" rather than leaving it to crash the ALTER TABLE.
		stragglers = frappe.db.sql(
			f"SELECT DISTINCT complexity FROM `{tbl}` "
			f"WHERE complexity NOT IN ('1.0', '1.5', '2.0', '1.6', '1.25', '1.75')",
			as_dict=False,
		)
		# (the list above just narrows the warning; any other value is force-defaulted below)
		frappe.db.sql(
			f"UPDATE `{tbl}` SET complexity = '1.0' "
			f"WHERE complexity NOT REGEXP %s",
			(r"^[0-9]+(\.[0-9]+)?$",),
		)
		if stragglers:
			frappe.logger().info(
				f"complexity_string_to_float: {tbl} had non-mapped values {stragglers} — forced to 1.0"
			)

	frappe.db.commit()
