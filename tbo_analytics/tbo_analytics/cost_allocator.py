# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

"""
Cost allocator — pulls indirect cost lines from live GL averages and computes
per-project allocation using cost-driver-based formulas.

See INDIRECT_COST_ALLOCATION.md at the repo root for the methodology.
"""

import frappe
from frappe.utils import nowdate, add_months


# ─── Driver constants ───────────────────────────────────────────────────────
DRIVER_HEADCOUNT     = "Headcount"
DRIVER_LABOUR_HOURS  = "Labour Hours"
DRIVER_PROJECT_COUNT = "Project Count"
DRIVER_REVENUE       = "Revenue"
DRIVER_FIXED_PCT     = "Fixed Pct"

# Backwards-compat mapping for the original Indirect Cost Item.allocation_method values
LEGACY_DRIVER_MAP = {
	"Per Head":  DRIVER_HEADCOUNT,
	"By Hours":  DRIVER_LABOUR_HOURS,
	"Fixed %":   DRIVER_FIXED_PCT,
	"Manual":    DRIVER_FIXED_PCT,
}

def normalize_driver(value):
	"""Accept old or new driver names; return the canonical new name."""
	if not value:
		return DRIVER_FIXED_PCT
	return LEGACY_DRIVER_MAP.get(value, value)


# ─── Default-driver lookup table ────────────────────────────────────────────
# Order matters — first keyword match wins. See INDIRECT_COST_ALLOCATION.md §3.
DEFAULT_DRIVER_RULES = [
	# Headcount drivers
	("rent",            DRIVER_HEADCOUNT),
	("electricity",     DRIVER_HEADCOUNT),
	("water",           DRIVER_HEADCOUNT),
	("telephone",       DRIVER_HEADCOUNT),
	("internet",        DRIVER_HEADCOUNT),
	("office",          DRIVER_HEADCOUNT),
	("workspace",       DRIVER_HEADCOUNT),
	("cleaning",        DRIVER_HEADCOUNT),
	("laptop",          DRIVER_HEADCOUNT),
	("depreciation",    DRIVER_HEADCOUNT),
	("welfare",         DRIVER_HEADCOUNT),
	("food",            DRIVER_HEADCOUNT),
	("staff",           DRIVER_HEADCOUNT),
	("celebration",     DRIVER_HEADCOUNT),
	("birthday",        DRIVER_HEADCOUNT),
	("festival",        DRIVER_HEADCOUNT),
	("recruitment",     DRIVER_HEADCOUNT),
	("training",        DRIVER_HEADCOUNT),
	("postal",          DRIVER_HEADCOUNT),
	("stationery",      DRIVER_HEADCOUNT),
	("stationary",      DRIVER_HEADCOUNT),
	("print",           DRIVER_HEADCOUNT),
	# Labour-hours drivers
	("cloud service",   DRIVER_LABOUR_HOURS),
	# Project-count drivers
	("domain",          DRIVER_PROJECT_COUNT),
	("frappe cloud",    DRIVER_PROJECT_COUNT),
	("audit",           DRIVER_PROJECT_COUNT),
	("accounting",      DRIVER_PROJECT_COUNT),
	("legal",           DRIVER_PROJECT_COUNT),
	("professional",    DRIVER_PROJECT_COUNT),
	("consult",         DRIVER_PROJECT_COUNT),
	("filing",          DRIVER_PROJECT_COUNT),
	("advisory",        DRIVER_PROJECT_COUNT),
	("documentation",   DRIVER_PROJECT_COUNT),
	("travel",          DRIVER_PROJECT_COUNT),
	("fuel",            DRIVER_PROJECT_COUNT),
	("daily allowance", DRIVER_PROJECT_COUNT),
	("client shoot",    DRIVER_PROJECT_COUNT),
	("client entertainment", DRIVER_PROJECT_COUNT),
	# Revenue drivers
	("marketing",       DRIVER_REVENUE),
	("promotion",       DRIVER_REVENUE),
	("meta ad",         DRIVER_REVENUE),
	("brokerage",       DRIVER_REVENUE),
	("commission",      DRIVER_REVENUE),
	("bank charge",     DRIVER_REVENUE),
	("exchange",        DRIVER_REVENUE),
	("gst expense",     DRIVER_REVENUE),
	("income tax",      DRIVER_REVENUE),
	("website",         DRIVER_REVENUE),
	# Fixed-pct fallbacks
	("late fee",        DRIVER_FIXED_PCT),
	("write off",       DRIVER_FIXED_PCT),
	("miscellaneous",   DRIVER_FIXED_PCT),
	("rounded off",     DRIVER_FIXED_PCT),
	("interest & fines",DRIVER_FIXED_PCT),
	("charity",         DRIVER_FIXED_PCT),
]

# Patterns that exclude an account from auto-allocation altogether.
# These are labour costs already captured via timesheet × hourly_cost.
EXCLUDED_NAME_PATTERNS = [
	"salary", "allowance", "incentive", "stipend", "partner",
	"deduction", "wages", "payroll",
]
EXCLUDED_PARENT_NAMES = [
	"hr expense", "partners salary",
]


# Account-name keywords that flag a line as "Infrastructure" — shared physical assets
# whose cost is split per-head across active projects. Anything matching one of these
# is OWNED by pull_infrastructure_lines() and is removed from pull_indirect_lines()
# so the two pulls never double-count.
INFRA_NAME_KEYWORDS = [
	"laptop", "equipment", "internet", "electricity", "software depreciation",
	"depreciation",  # broad — covers "Depreciation of Laptops" etc.
]


def _is_infra_account(account_label):
	n = (account_label or "").lower()
	return any(k in n for k in INFRA_NAME_KEYWORDS)


def _infra_category_from_label(account_label):
	"""Map a GL account name to one of Infrastructure Cost Item's category options."""
	n = (account_label or "").lower()
	if "laptop"   in n: return "Laptop"
	if "internet" in n: return "Internet"
	if "electric" in n: return "Electricity"
	if "software" in n: return "Software"
	if "equipment" in n or "depreciation" in n: return "Equipment"
	return "Other"


def suggest_driver(account_name):
	"""Pick the most likely cost driver for an account based on its name."""
	if not account_name:
		return DRIVER_PROJECT_COUNT
	n = account_name.lower()
	for pattern, driver in DEFAULT_DRIVER_RULES:
		if pattern in n:
			return driver
	return DRIVER_PROJECT_COUNT  # safe default


def _is_salary_flavoured(account_name, parent_account):
	"""True if this looks like a per-employee compensation account
	(salary, allowance, stipend, wages, etc. under HR Expense)."""
	n = (account_name or "").lower()
	pn = (parent_account or "").lower()
	if any(p in n for p in EXCLUDED_NAME_PATTERNS):
		return True
	if any(p in pn for p in EXCLUDED_PARENT_NAMES):
		return True
	return False


# Overhead departments — their salary cost rolls up into the Indirect Cost table
# via pull_overhead_salary_rollup(). Each group maps to one Indirect Cost row
# whose `category` matches the Indirect Cost Item dropdown.
# Sales / BD / Marketing are deliberately NOT here — those salaries are tied to
# revenue generation, not project delivery, so they're handled elsewhere.
OVERHEAD_DEPARTMENT_GROUPS = [
	{"category": "HR & Admin",  "keywords": ["hr", "human resource", "admin"]},
	{"category": "Finance",     "keywords": ["account", "finance"]},
]


def _overhead_dept_keywords():
	return [k for grp in OVERHEAD_DEPARTMENT_GROUPS for k in grp["keywords"]]


def get_overhead_dept_employee_names(company=None):
	"""Set of lowercase name tokens for every employee in an overhead department
	(HR, Accounts/Finance, Sales/BD). Used by the GL pull to keep any per-employee
	salary accounts that match these names; everyone else's salary account is
	excluded because they're either billable (Team Composition × CTC) or handled
	manually as a Direct Cost row.
	"""
	patterns = [f"%{k}%" for k in _overhead_dept_keywords()]
	like_clause = " OR ".join(["LOWER(department) LIKE %s"] * len(patterns))
	rows = frappe.db.sql(f"""
		SELECT employee_name, department
		FROM `tabEmployee`
		WHERE status = 'Active'
		  AND ({like_clause})
	""", patterns, as_dict=True)

	tokens = set()
	for r in rows:
		full = (r.employee_name or "").strip().lower()
		if not full:
			continue
		tokens.add(full)
		first = full.split()[0] if full.split() else ""
		if len(first) >= 3:  # avoid 1–2 letter false positives
			tokens.add(first)
	return tokens


def _resolve_monthly_salary(employee_name):
	"""Same lookup chain as get_employee_hourly_cost on Implementation Estimate:
	Employee.ctc (monthly) → Salary Structure Assignment.base → avg of last 3 Salary Slips."""
	ctc = frappe.db.get_value("Employee", employee_name, "ctc")
	if ctc and float(ctc) > 0:
		return float(ctc)
	ssa = frappe.db.sql("""
		SELECT base FROM `tabSalary Structure Assignment`
		WHERE employee = %s AND docstatus = 1
		ORDER BY from_date DESC LIMIT 1
	""", employee_name)
	if ssa and ssa[0][0]:
		return float(ssa[0][0])
	slips = frappe.db.sql("""
		SELECT gross_pay FROM `tabSalary Slip`
		WHERE employee = %s AND docstatus = 1
		ORDER BY start_date DESC LIMIT 3
	""", employee_name)
	if slips:
		vals = [float(s[0] or 0) for s in slips]
		if any(vals):
			return sum(vals) / len(vals)
	return 0.0


@frappe.whitelist()
def pull_overhead_salary_rollup(company):
	"""One indirect-cost row per overhead department category (HR & Admin,
	Finance). Each row's monthly cost is the sum of Employee.ctc for active
	employees in that department group.

	This is the authoritative source for overhead salaries — TBO's chart of
	accounts typically posts every employee's salary into a single 'Salaries'
	GL account, so the GL-based pull can't tell HR/Accounts salaries apart
	from billable-team salaries. Roll-up by department sidesteps that entirely.
	"""
	result = []
	for grp in OVERHEAD_DEPARTMENT_GROUPS:
		patterns = [f"%{k}%" for k in grp["keywords"]]
		like_clause = " OR ".join(["LOWER(department) LIKE %s"] * len(patterns))
		params = [company, *patterns]
		rows = frappe.db.sql(f"""
			SELECT name
			FROM `tabEmployee`
			WHERE status = 'Active' AND company = %s
			  AND ({like_clause})
		""", params, as_dict=True)
		if not rows:
			continue
		monthly_sum = 0.0
		for r in rows:
			monthly_sum += _resolve_monthly_salary(r.name)
		if monthly_sum <= 0:
			continue
		cat = grp["category"]
		result.append({
			"cost_item":          f"{cat} Salaries ({len(rows)} emp)",
			"category":           cat,
			"monthly_total_cost": round(monthly_sum, 2),
			"allocation_method":  DRIVER_HEADCOUNT,
			"project_share_pct":  0,
			"notes":              f"Roll-up of {len(rows)} active {cat} employees (monthly Employee.ctc, SSA / Salary Slip fallback)",
		})
	result.sort(key=lambda r: -r["monthly_total_cost"])
	return {"rows": result, "method": "Per-department sum of Employee.ctc"}


def is_excluded(account_name, parent_account, overhead_dept_names=None):
	"""True if this GL account must NOT be auto-allocated as overhead.

	All salary-flavoured accounts are excluded from the GL pull because the
	authoritative source for overhead salaries is now
	pull_overhead_salary_rollup() — which sums Employee.ctc per department
	and avoids double-counting against a single lumped 'Salaries' GL account.

	Non-salary accounts always pass through.

	`overhead_dept_names` is retained for signature compatibility but ignored.
	"""
	return _is_salary_flavoured(account_name, parent_account)


# Category that a GL account maps to (matches the Indirect Cost Item.category options).
# Checks the account label first so a leaf like "BDE Salaries" under "Indirect Expenses"
# still lands in Sales & BD instead of Other.
def _category_from_parent(parent_account_name, account_label=None):
	candidates = " ".join(filter(None, [account_label, parent_account_name])).lower()
	if not candidates:
		return "Other"
	if "hr" in candidates or "human resource" in candidates or "admin" in candidates:
		return "HR & Admin"
	if "finance" in candidates or "account" in candidates:
		return "Finance"
	if "office" in candidates or "rent" in candidates or "utility" in candidates:
		return "Office"
	return "Other"


# ─── WHITELISTED METHODS ────────────────────────────────────────────────────
@frappe.whitelist()
def get_company_benchmarks(company):
	"""Live denominators used by the share formulas. All windowed to the last
	6 months to smooth out short-term timesheet gaps."""
	headcount = frappe.db.count("Employee", {"company": company, "status": "Active"}) or 0

	hours_result = frappe.db.sql("""
		SELECT AVG(monthly_hours) FROM (
			SELECT DATE_FORMAT(ts.start_date, '%%Y-%%m') AS m,
			       SUM(tsd.hours) AS monthly_hours
			FROM `tabTimesheet Detail` tsd
			INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
			WHERE ts.docstatus = 1 AND ts.company = %(c)s
			  AND ts.start_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
			GROUP BY DATE_FORMAT(ts.start_date, '%%Y-%%m')
		) t
	""", {"c": company})
	avg_monthly_hours = float(hours_result[0][0] or 0) if hours_result else 0

	# "Active project" = had ≥ 4 hours of timesheet activity in the last 6 months.
	# Wider window than 60d to stay stable when timesheet hygiene dips. Floor at 3
	# to keep the share from collapsing to 100% on sparsely-tracked sites.
	active_projects_result = frappe.db.sql("""
		SELECT COUNT(*) FROM (
			SELECT tsd.project, SUM(tsd.hours) AS hrs
			FROM `tabTimesheet Detail` tsd
			INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
			WHERE ts.docstatus = 1 AND ts.company = %(c)s
			  AND ts.start_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
			  AND tsd.project IS NOT NULL AND tsd.project != ''
			GROUP BY tsd.project
			HAVING hrs >= 4
		) t
	""", {"c": company})
	active_projects = max(int(active_projects_result[0][0] or 0), 3) if active_projects_result else 3

	revenue_result = frappe.db.sql("""
		SELECT SUM(base_grand_total) / 6
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND company = %(c)s
		  AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
	""", {"c": company})
	avg_monthly_revenue = float(revenue_result[0][0] or 0) if revenue_result else 0

	return {
		"headcount":           int(headcount),
		"avg_monthly_hours":   round(avg_monthly_hours, 1),
		"active_projects":     active_projects,
		"avg_monthly_revenue": round(avg_monthly_revenue, 2),
	}


def _indirect_root_accounts(company):
	"""Return the lft/rgt of every Indirect-Expenses group account for this company.
	We walk descendants of any group account whose name contains 'indirect'."""
	rows = frappe.db.sql("""
		SELECT name, lft, rgt
		FROM `tabAccount`
		WHERE company = %(c)s AND is_group = 1 AND root_type = 'Expense'
		  AND LOWER(account_name) LIKE %(p)s
	""", {"c": company, "p": "%indirect%"}, as_dict=True)
	# fall back: no "Indirect" group found → empty list (caller decides what to do)
	return [(r.lft, r.rgt) for r in rows]


def _direct_root_accounts(company):
	"""Return the lft/rgt of the Direct-Expenses group account for this company.
	Stock Expenses (COGS) is typically a child of Direct Expenses so it's included
	automatically. Excludes 'Indirect Expenses' explicitly (LIKE '%direct%' matches it)."""
	rows = frappe.db.sql("""
		SELECT name, lft, rgt
		FROM `tabAccount`
		WHERE company = %(c)s AND is_group = 1 AND root_type = 'Expense'
		  AND LOWER(account_name) LIKE %(p)s
		  AND LOWER(account_name) NOT LIKE %(n)s
	""", {"c": company, "p": "%direct%", "n": "%indirect%"}, as_dict=True)
	return [(r.lft, r.rgt) for r in rows]


# Exponentially-weighted moving average — newest month gets highest weight.
# Designed for the 6-month lookback used by pull_indirect_lines / pull_shared_direct_lines.
# Trade-off vs simple mean: tracks trends without being thrown by a single outlier month.
EWMA_WEIGHTS_NEWEST_FIRST = [0.40, 0.25, 0.15, 0.10, 0.06, 0.04]

def ewma(values_newest_first, weights=None):
	"""Weighted average; weights are re-normalised if fewer values than weights exist."""
	if not values_newest_first:
		return 0.0
	weights = weights or EWMA_WEIGHTS_NEWEST_FIRST
	n = min(len(values_newest_first), len(weights))
	w = weights[:n]
	v = values_newest_first[:n]
	total_w = sum(w) or 1
	return sum(v[i] * w[i] for i in range(n)) / total_w


def _summarise_account_months(rows):
	"""Group raw (account, month, month_total) tuples into one EWMA per account.
	`rows` is the list returned by SQL ordered by month DESC.
	Returns: dict {account_name: {monthly_avg, account_label, parent_account, active_months}}.
	"""
	by_account = {}
	for r in rows:
		# row: account, account_name, parent_account, month, month_total
		bucket = by_account.setdefault(r.account, {
			"account_label":  r.account_name,
			"parent_account": r.parent_account,
			"months":         [],
		})
		bucket["months"].append((r.month, float(r.month_total)))

	out = {}
	for account, info in by_account.items():
		# Sort months newest-first (in case SQL didn't preserve order)
		info["months"].sort(reverse=True)
		values_newest_first = [v for _, v in info["months"]]
		out[account] = {
			"monthly_avg":    round(ewma(values_newest_first), 2),
			"account_label":  info["account_label"],
			"parent_account": info["parent_account"],
			"active_months":  len(values_newest_first),
		}
	return out


def _fetch_account_month_totals(company, cutoff, subtree_filter):
	"""Pull per-(account, month) totals for any expense leaf in the given subtree.
	Returns rows ordered by month DESC so _summarise_account_months can EWMA them."""
	return frappe.db.sql(f"""
		SELECT
			a.name                                     AS account,
			a.account_name                             AS account_name,
			a.parent_account                           AS parent_account,
			DATE_FORMAT(gl.posting_date, '%%Y-%%m')    AS month,
			SUM(gl.debit - gl.credit)                  AS month_total
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` a ON a.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.company = %(c)s
		  AND a.root_type = 'Expense'
		  AND a.is_group = 0
		  AND gl.posting_date >= %(cutoff)s
		  {subtree_filter}
		GROUP BY a.name, a.account_name, a.parent_account, DATE_FORMAT(gl.posting_date, '%%Y-%%m')
		ORDER BY a.name, DATE_FORMAT(gl.posting_date, '%%Y-%%m') DESC
	""", {"c": company, "cutoff": cutoff}, as_dict=True)


@frappe.whitelist()
def pull_indirect_lines(company, lookback_months=6, include_direct=0):
	"""
	Return one suggested Indirect Cost Item row per qualifying GL account.

	Method: EWMA over the lookback window (newest months count more).
	Scope:
	 - Walks descendants of every "Indirect Expenses" group account (via lft/rgt).
	 - Excludes the HR/salary subtree (already captured in direct labour via timesheets).
	 - If no Indirect group exists, OR include_direct=1, walks every expense leaf.
	"""
	lookback_months = int(lookback_months or 6)
	include_direct  = int(include_direct or 0)
	cutoff = add_months(nowdate(), -lookback_months)

	indirect_subtrees = _indirect_root_accounts(company)
	if indirect_subtrees and not include_direct:
		range_clauses = " OR ".join(
			f"(a.lft > {int(lft)} AND a.rgt < {int(rgt)})" for lft, rgt in indirect_subtrees
		)
		subtree_filter = f"AND ({range_clauses})"
	else:
		subtree_filter = ""

	month_rows = _fetch_account_month_totals(company, cutoff, subtree_filter)
	by_account = _summarise_account_months(month_rows)
	overhead_dept_names = get_overhead_dept_employee_names(company)

	result, excluded_count = [], 0
	for account, info in by_account.items():
		if info["monthly_avg"] <= 0:
			continue
		if is_excluded(info["account_label"], info["parent_account"], overhead_dept_names):
			excluded_count += 1
			continue
		# Skip infrastructure-flagged accounts — those are owned by
		# pull_infrastructure_lines() and would otherwise be double-counted.
		if _is_infra_account(info["account_label"]):
			continue
		result.append({
			"cost_item":          info["account_label"],
			"category":           _category_from_parent(info["parent_account"], info["account_label"]),
			"monthly_total_cost": info["monthly_avg"],
			"allocation_method":  suggest_driver(info["account_label"]),
			"project_share_pct":  0,  # auto-computed by controller
			"notes":              f"From GL: EWMA of {info['active_months']} mo @ {account}",
		})
	# Sort by monthly cost desc for nicer UX
	result.sort(key=lambda r: -r["monthly_total_cost"])

	return {
		"rows":              result,
		"excluded_count":    excluded_count,
		"lookback_months":   lookback_months,
		"cutoff_date":       cutoff,
		"indirect_subtrees": len(indirect_subtrees),
		"include_direct":    bool(include_direct),
		"method":            "EWMA (newest month weighted 0.40)",
	}


@frappe.whitelist()
def pull_shared_direct_lines(company, lookback_months=6):
	"""
	Return one suggested SHARED Direct Cost Item row per qualifying GL account.

	"Shared direct" = costs in the Direct Expenses / Stock Expenses chart-of-accounts
	subtree that AREN'T tagged to a specific project (the typical case for company-wide
	AWS / Hetzner / cloud bills that get classified as COGS).

	Each returned row is ready to insert with is_allocated_from_books = 1. The controller
	will compute project_share_pct via the driver and total_cost = monthly_cost × share × duration.
	"""
	lookback_months = int(lookback_months or 6)
	cutoff = add_months(nowdate(), -lookback_months)

	subtrees = _direct_root_accounts(company)
	if not subtrees:
		return {"rows": [], "method": "EWMA", "reason": "No 'Direct Expenses' group account found in chart of accounts"}

	range_clauses = " OR ".join(
		f"(a.lft > {int(lft)} AND a.rgt < {int(rgt)})" for lft, rgt in subtrees
	)
	subtree_filter = f"AND ({range_clauses})"

	# Pull only GL entries that DON'T have a project tag — those are the "shared" lines
	# that need allocation. Project-tagged entries are already attributed and not our concern.
	month_rows = frappe.db.sql(f"""
		SELECT
			a.name                                     AS account,
			a.account_name                             AS account_name,
			a.parent_account                           AS parent_account,
			DATE_FORMAT(gl.posting_date, '%%Y-%%m')    AS month,
			SUM(gl.debit - gl.credit)                  AS month_total
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` a ON a.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.company = %(c)s
		  AND a.root_type = 'Expense'
		  AND a.is_group = 0
		  AND gl.posting_date >= %(cutoff)s
		  AND (gl.project IS NULL OR gl.project = '')
		  {subtree_filter}
		GROUP BY a.name, a.account_name, a.parent_account, DATE_FORMAT(gl.posting_date, '%%Y-%%m')
		ORDER BY a.name, DATE_FORMAT(gl.posting_date, '%%Y-%%m') DESC
	""", {"c": company, "cutoff": cutoff}, as_dict=True)

	by_account = _summarise_account_months(month_rows)

	result = []
	for account, info in by_account.items():
		if info["monthly_avg"] <= 0:
			continue
		# Default driver for shared cloud / COGS: Labour Hours (scales with active work).
		# Override per row via the dropdown.
		name_lower = (info["account_label"] or "").lower()
		if "cogs" in name_lower or "cost of goods" in name_lower or "cloud" in name_lower:
			default_driver = DRIVER_LABOUR_HOURS
		else:
			default_driver = suggest_driver(info["account_label"])

		# Map category from the parent account name to one of Direct Cost Item's options
		parent_lower = (info["parent_account"] or "").lower()
		if "stock" in parent_lower or "cogs" in name_lower:
			category = "Third-party API"  # closest match for cloud services in Direct Cost Item's options
		elif "freelance" in name_lower:
			category = "Tools"
		elif "software" in name_lower:
			category = "Software License"
		else:
			category = "Other"

		result.append({
			"cost_item":                 info["account_label"],
			"category":                  category,
			"vendor":                    "",
			"monthly_cost":              info["monthly_avg"],
			"is_one_time":               0,
			"is_allocated_from_books":   1,
			"account":                   account,
			"allocation_method":         default_driver,
			"notes":                     f"Shared direct (allocated): EWMA of {info['active_months']} mo @ {account}",
		})
	result.sort(key=lambda r: -r["monthly_cost"])

	return {
		"rows":           result,
		"lookback_months": lookback_months,
		"cutoff_date":    cutoff,
		"method":         "EWMA (newest month weighted 0.40)",
	}


# ─── Allocation logic used by the controller ───────────────────────────────
def compute_row_share(row, benchmarks, project_inputs):
	"""
	Return the share (as a fraction, NOT percentage) for one Indirect Cost Item
	row given the company benchmarks and this project's inputs.

	project_inputs is a dict with: team_size, monthly_project_hours,
	monthly_project_revenue.

	Falls back to the user-typed project_share_pct if the driver isn't recognised
	or the relevant benchmark is missing.
	"""
	driver = normalize_driver(row.allocation_method)

	if driver == DRIVER_HEADCOUNT and benchmarks.get("headcount"):
		return project_inputs["team_size"] / benchmarks["headcount"]

	if driver == DRIVER_LABOUR_HOURS and benchmarks.get("avg_monthly_hours"):
		return project_inputs["monthly_project_hours"] / benchmarks["avg_monthly_hours"]

	if driver == DRIVER_PROJECT_COUNT and benchmarks.get("active_projects"):
		return 1.0 / benchmarks["active_projects"]

	if driver == DRIVER_REVENUE and benchmarks.get("avg_monthly_revenue"):
		return project_inputs["monthly_project_revenue"] / benchmarks["avg_monthly_revenue"]

	# Fixed Pct / unknown / missing benchmark — fall back to user-typed value
	return (row.project_share_pct or 0) / 100


# ─── Infrastructure pull ─────────────────────────────────────────────────────
# Infrastructure = shared physical assets (laptops, equipment, internet, electricity,
# depreciation) whose cost is split per-head across the team. Returned rows match the
# Infrastructure Cost Item child-doctype shape.
#
# Note on currency: gl.debit / gl.credit are stored in company base currency. As long
# as the bench's default company is INR (which the user has confirmed), the EWMA is
# already in INR. If a non-INR account ever shows up here, the GL Entry's company-
# currency columns still convert at the posting-time rate — so values stay INR-correct
# without any extra conversion on our side.
@frappe.whitelist()
def pull_infrastructure_lines(company, lookback_months=6):
	lookback_months = int(lookback_months or 6)
	cutoff = add_months(nowdate(), -lookback_months)

	month_rows = _fetch_account_month_totals(company, cutoff, subtree_filter="")
	by_account = _summarise_account_months(month_rows)

	# Per-head split needs a headcount denominator; fetch once.
	headcount = frappe.db.count("Employee", {"company": company, "status": "Active"}) or 1
	overhead_dept_names = get_overhead_dept_employee_names(company)

	result = []
	for account, info in by_account.items():
		if info["monthly_avg"] <= 0:
			continue
		if is_excluded(info["account_label"], info["parent_account"], overhead_dept_names):
			continue
		if not _is_infra_account(info["account_label"]):
			continue
		result.append({
			"cost_item":                  info["account_label"],
			"category":                   _infra_category_from_label(info["account_label"]),
			"total_monthly_company_cost": info["monthly_avg"],
			"split_method":               "Per Head",
			"company_total_employees":    headcount,
			"notes":                      f"Infra (per-head): EWMA of {info['active_months']} mo @ {account}",
		})
	result.sort(key=lambda r: -r["total_monthly_company_cost"])

	return {
		"rows":            result,
		"lookback_months": lookback_months,
		"cutoff_date":     cutoff,
		"method":          "EWMA (newest month weighted 0.40)",
		"headcount":       headcount,
	}


# ─── One-shot wrapper used by the Load Overheads from Books button ───────────
@frappe.whitelist()
def pull_all_overhead(company, lookback_months=6):
	"""Single round-trip: returns indirect + infrastructure rows.

	Direct Cost is now fully manual (no GL pull) — the COGS account in TBO's
	books accumulates ALL projects' direct spend, so allocating a share of it
	to a new estimate was double-charging clients who had already paid. We
	therefore return an empty 'direct' list for backward-compat with the JS
	caller. To preserve the user's right to manually add direct rows, the
	form's quick-add buttons (Frappe Cloud, Claude AI, etc.) still work.
	"""
	indirect = pull_indirect_lines(company, lookback_months)
	infra = pull_infrastructure_lines(company, lookback_months)
	# Merge overhead-department salary roll-up (HR, Accounts, Sales/BD) into indirect.
	# GL salary accounts are all excluded above to avoid double-counting against the
	# typical single 'Salaries' GL account most charts of accounts use.
	salary_rollup = pull_overhead_salary_rollup(company)
	indirect["rows"].extend(salary_rollup.get("rows", []))
	indirect["rows"].sort(key=lambda r: -r["monthly_total_cost"])
	return {
		"direct":   {"rows": []},
		"indirect": indirect,
		"infra":    infra,
		"company":  company,
		"lookback_months": int(lookback_months or 6),
	}
