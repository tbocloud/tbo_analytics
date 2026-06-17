# Copyright (c) 2026, tbo and contributors
# For license information, please see license.txt

import math
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_months


COMPANY_SIZE_FACTORS = {
	"Micro": 0.8,
	"Small": 1.0,
	"Medium": 1.2,
	"Large": 1.4,
	"Enterprise": 1.7,
}

CUSTOMIZATION_BASE_HOURS = {
	"Custom Field": 4,
	"Custom Form": 16,
	"Workflow": 12,
	"Custom Report": 10,
	"Print Format": 10,
	"API / Integration": 24,
	"Other": 8,
}

# Multi-check model on Module Selection. Each ticked flag adds its hours to
# customization_ai_hours (multiplied by row complexity).
CUSTOMIZATION_FLAG_HOURS = {
	"cust_custom_field":     4,
	"cust_custom_form":     16,
	"cust_workflow":        12,
	"cust_custom_report":   10,
	"cust_print_format":    10,
	"cust_api_integration": 24,
	"cust_other":            8,
}

# Migration map: legacy single-Select value → new boolean flag fieldname.
CUSTOMIZATION_LEGACY_TO_FLAG = {
	"Custom Field":      "cust_custom_field",
	"Custom Form":       "cust_custom_form",
	"Workflow":          "cust_workflow",
	"Custom Report":     "cust_custom_report",
	"Print Format":      "cust_print_format",
	"API / Integration": "cust_api_integration",
	"Other":             "cust_other",
}

SCENARIO_MULTIPLIERS = {
	"optimistic": 0.85,
	"base": 1.00,
	"pessimistic": 1.30,
}


class ImplementationEstimate(Document):
	def before_save(self):
		self.calculate_ai_estimates()
		self.calculate_final_hours()
		self.calculate_costs()
		self.calculate_pricing()
		self.calculate_break_even()


	# ------------------------------------------------------------------
	# STEP 1: AI Estimation
	# ------------------------------------------------------------------
	def calculate_ai_estimates(self):
		size_factor = COMPANY_SIZE_FACTORS.get(self.company_size, 1.0)
		migration_factor = 1.15 if self.data_migration_required else 1.0

		def complexity_mult(c):
			"""Float complexity ∈ [1.0, 2.0]. Clamps out-of-range values."""
			try:
				v = float(c) if c is not None else 1.0
			except (TypeError, ValueError):
				return 1.0
			return max(1.0, min(v, 2.0))

		# Module selections
		for row in self.module_selections:
			if not row.module:
				continue
			# Persist the clamped complexity so user sees what we actually used
			row.complexity = complexity_mult(row.complexity)
			cmult = row.complexity
			weight = cmult - 1.0  # 0.0 at cmult=1.0, 1.0 at cmult=2.0

			try:
				m = frappe.get_cached_doc("ERP Module Master", row.module)
				# Base = historical avg if populated, else linearly interpolate between c1 and c2 base hours
				if m.historical_avg_hours:
					base = m.historical_avg_hours
				else:
					base = (1 - weight) * (m.base_hours_complexity_1 or 0) + weight * (m.base_hours_complexity_2 or 0)

				row.ai_estimated_hours = round(base * cmult * size_factor * migration_factor, 1)

				# Customization hours — multi-check model.
				# Sum base hours across every ticked Customization Type flag, then
				# scale by complexity. Auto-migrate any legacy single-Select value
				# (customization_type) into the matching boolean flag.
				if row.customization_required:
					# One-time migration of legacy data: if no flags ticked but the
					# old Select had a value, tick the matching flag silently.
					ticked_any = any(getattr(row, f, 0) for f in CUSTOMIZATION_FLAG_HOURS)
					if not ticked_any and row.customization_type:
						target = CUSTOMIZATION_LEGACY_TO_FLAG.get(row.customization_type)
						if target:
							setattr(row, target, 1)

					c_base = sum(
						hrs for flag, hrs in CUSTOMIZATION_FLAG_HOURS.items()
						if getattr(row, flag, 0)
					)
					row.customization_ai_hours = round(c_base * cmult, 1)
				else:
					row.customization_ai_hours = 0
			except Exception:
				pass

			# Resolve final hours
			row.final_hours = row.leader_estimated_hours if (row.leader_estimated_hours or 0) > 0 else (row.ai_estimated_hours or 0)
			row.customization_final_hours = (
				row.customization_manual_hours
				if (row.customization_manual_hours or 0) > 0
				else (row.customization_ai_hours or 0)
			)
			row.total_module_hours = round(
				(row.final_hours or 0) + (row.customization_final_hours or 0), 1
			)

		# Custom module requests — base / integration / per-report / per-dashboard
		# all scale linearly with complexity.
		for row in self.custom_module_requests:
			row.complexity = complexity_mult(row.complexity)
			cmult = row.complexity

			base     = 24 * cmult                                              # 24 at 1.0, 48 at 2.0
			int_add  = (16 * cmult) if row.needs_integration else 0            # 16 at 1.0, 32 at 2.0
			rpt_add  = 0
			dash_add = 0
			# Reports — 8 hrs × complexity per report
			if row.needs_reports and row.report_count:
				rpt_add = 8 * cmult * row.report_count                         # 8/rpt at 1.0, 16 at 2.0
				# Auto-suggest report_hours if the user hasn't typed one
				if not row.report_hours or row.report_hours == 0:
					row.report_hours = round(rpt_add, 1)
			# Dashboards — 12 hrs × complexity per dashboard (denser than reports:
			# charts, KPI cards, filters, drill-down all stack up)
			if row.needs_dashboards and row.dashboard_count:
				dash_add = 12 * cmult * row.dashboard_count                    # 12/dash at 1.0, 24 at 2.0
				if not row.dashboard_hours or row.dashboard_hours == 0:
					row.dashboard_hours = round(dash_add, 1)

			row.ai_estimated_hours = round(base + int_add + rpt_add + dash_add, 1)
			row.final_hours = row.leader_estimated_hours if (row.leader_estimated_hours or 0) > 0 else row.ai_estimated_hours
			row.total_hours = round(
				(row.final_hours or 0)
				+ (row.integration_hours or 0)
				+ (row.report_hours or 0)
				+ (row.dashboard_hours or 0),
				1,
			)

		# Integration requirements — linearly interpolate between base_hours_c1 and base_hours_c2
		for row in self.integration_requirements:
			if not row.integration_type:
				continue
			row.complexity = complexity_mult(row.complexity)
			weight = row.complexity - 1.0
			try:
				it = frappe.get_cached_doc("Integration Type Master", row.integration_type)
				row.ai_estimated_hours = round(
					(1 - weight) * (it.base_hours_c1 or 0) + weight * (it.base_hours_c2 or 0), 1
				)
			except Exception:
				pass
			row.final_hours = row.manual_hours if (row.manual_hours or 0) > 0 else (row.ai_estimated_hours or 0)

	# ------------------------------------------------------------------
	# STEP 2: Aggregate hours
	# ------------------------------------------------------------------
	def calculate_final_hours(self):
		self.total_modules_hours = round(
			sum((r.total_module_hours or 0) for r in self.module_selections if r.is_included), 1
		)
		self.total_custom_modules_hours = round(
			sum((r.total_hours or 0) for r in self.custom_module_requests), 1
		)
		self.total_integration_hours = round(
			sum((r.final_hours or 0) for r in self.integration_requirements), 1
		)
		self.grand_total_hours = round(
			self.total_modules_hours + self.total_custom_modules_hours + self.total_integration_hours, 1
		)

	# ------------------------------------------------------------------
	# STEP 3: Cost roll-up
	# ------------------------------------------------------------------
	def calculate_costs(self):
		# Team cost
		active_members = [r for r in self.team_members if r.is_active_in_current_version]
		team_cost = 0.0
		total_allocated = 0.0
		for row in active_members:
			row.total_cost = round((row.hourly_cost or 0) * (row.allocated_hours or 0), 2)
			team_cost += row.total_cost
			total_allocated += row.allocated_hours or 0
		self.team_cost_total = round(team_cost, 2)

		# Blended hourly rate
		self.blended_hourly_rate = round(team_cost / total_allocated, 2) if total_allocated > 0 else 0

		# Project duration — bottleneck-driven.
		#
		# A project's duration is determined by the person with the LONGEST individual
		# workload, not the team-wide average. This matches reality: if one person has
		# 800 hrs of specialised work, no amount of idle teammates makes them deliver
		# faster. The math is `max(allocated_hours / 132)` across active members.
		#
		# Fallback: if no one has allocated hours yet but grand_total_hours is set,
		# use the old average-based formula as a placeholder so the form still shows
		# a sensible duration before the team is sized.
		team_size = len(active_members)
		MONTHLY_HOURS = 6 * 22  # 132
		active_loads = [(r.allocated_hours or 0) for r in active_members]

		if active_loads and max(active_loads) > 0:
			bottleneck_months = max(active_loads) / MONTHLY_HOURS
			# Safety floor: if total team work exceeds what they can collectively do
			# in the bottleneck window, stretch the duration so the average load fits too.
			avg_months_if_pooled = (
				(self.grand_total_hours or 0) / (team_size * MONTHLY_HOURS)
			) if team_size > 0 else 0
			self.project_duration_months = max(
				math.ceil(bottleneck_months),
				math.ceil(avg_months_if_pooled),
				1,
			)
		elif team_size > 0 and self.grand_total_hours:
			# Team exists but hours not allocated yet → use old formula as a placeholder
			self.project_duration_months = max(
				math.ceil(self.grand_total_hours / (team_size * MONTHLY_HOURS)), 1
			)
		else:
			self.project_duration_months = 1

		dur = self.project_duration_months

		# Direct costs — fully manual, with two helper inputs:
		#
		#   1. Total Monthly (Company) + Project Share %  →  auto-fill monthly_cost
		#      (used for company-paid services like AWS that this project shares)
		#   2. monthly_cost typed directly                →  used as-is
		#
		# Per-row Duration is editable: if blank, falls back to project duration.
		#
		# Total per row = monthly_cost × row_duration  (or monthly_cost × 1 if one-time).
		direct_total = 0.0
		for row in self.direct_costs:
			# Default duration from the project, but respect a per-row override.
			if not row.project_duration_months or row.project_duration_months <= 0:
				row.project_duration_months = dur
			row_dur = row.project_duration_months

			# Auto-derive monthly_cost from share-of-company inputs ONLY when
			# both helpers are filled AND monthly_cost is blank. If the user
			# typed monthly_cost directly, that wins.
			t_co  = float(row.total_monthly_company_cost or 0)
			share = float(row.project_share_pct or 0)
			if (not row.monthly_cost or row.monthly_cost == 0) and t_co > 0 and share > 0:
				row.monthly_cost = round(t_co * share / 100.0, 2)

			if row.is_one_time:
				row.total_cost = round(row.monthly_cost or 0, 2)
			else:
				row.total_cost = round((row.monthly_cost or 0) * row_dur, 2)
			direct_total += row.total_cost
		self.direct_cost_total = round(direct_total, 2)

		# Indirect costs — driver-based allocation (Headcount / Labour Hours /
		# Project Count / Revenue / Fixed Pct). See cost_allocator.py + INDIRECT_COST_ALLOCATION.md.
		from tbo_analytics.tbo_analytics.cost_allocator import (
			compute_row_share, get_company_benchmarks, DRIVER_REVENUE, normalize_driver,
		)

		needs_benchmarks = any(
			normalize_driver(r.allocation_method) != "Fixed Pct" for r in self.indirect_costs
		)
		company_for_benchmarks = getattr(self, "company", None) or frappe.defaults.get_user_default("Company")
		benchmarks = get_company_benchmarks(company_for_benchmarks) if (needs_benchmarks and company_for_benchmarks) else {}

		# Use standard_price (deterministic from cost + margin) for the Revenue driver
		# to avoid circularity with recommended_price.
		margin = self.target_margin_pct or 30
		pre_indirect_cost = self.team_cost_total + self.direct_cost_total + (self.infrastructure_cost_total or 0)
		approx_standard_price = pre_indirect_cost / (1 - margin / 100) if margin < 100 else pre_indirect_cost * 2
		monthly_proj_revenue = approx_standard_price / max(dur, 1)
		monthly_proj_hours   = (self.grand_total_hours or 0) / max(dur, 1)

		project_inputs = {
			"team_size":               team_size,
			"monthly_project_hours":   monthly_proj_hours,
			"monthly_project_revenue": monthly_proj_revenue,
		}

		indirect_total = 0.0
		for row in self.indirect_costs:
			row.project_duration_months = dur
			share = compute_row_share(row, benchmarks, project_inputs)
			# Write the auto-computed share back so the user sees what was used
			row.project_share_pct = round(share * 100, 2)
			row.allocated_amount  = round((row.monthly_total_cost or 0) * share * dur, 2)
			indirect_total += row.allocated_amount
		self.indirect_cost_total = round(indirect_total, 2)

		# Infrastructure costs
		infra_total = 0.0
		for row in self.infrastructure_costs:
			row.project_team_size = team_size
			row.project_duration_months = dur
			if row.split_method == "Per Head" and (row.company_total_employees or 0) > 0:
				row.allocated_amount = round(
					(row.total_monthly_company_cost or 0) * (team_size / row.company_total_employees) * dur, 2
				)
			elif row.split_method == "By Project Count":
				# Count active Projects as proxy
				proj_count = frappe.db.count("Project", {"status": "Open"}) or 1
				row.allocated_amount = round(
					(row.total_monthly_company_cost or 0) / proj_count * dur, 2
				)
			elif row.split_method == "Fixed Amount":
				pass  # allocated_amount set manually by user
			else:
				row.allocated_amount = 0
			infra_total += row.allocated_amount or 0
		self.infrastructure_cost_total = round(infra_total, 2)

		# Post Go-Live Support — reserved hours × duration × hourly rate.
		# Folded into grand_total_cost so pricing covers it; broken out as separate fields
		# so the breakdown is visible and so the Won → Project handler can create a matching
		# "Support" task with the right hour reservation.
		monthly_supp_hrs = float(self.monthly_support_hours or 0)
		supp_months      = int(self.support_duration_months or 0)
		supp_rate        = float(self.support_hourly_rate or 0) or float(self.blended_hourly_rate or 0)
		self.total_support_hours = round(monthly_supp_hrs * supp_months, 1)
		self.total_support_cost  = round(self.total_support_hours * supp_rate, 2)
		# Section-K mirror so the cost breakdown reconciles visibly:
		# Team + Direct + Indirect + Infra + Support = Grand Total.
		self.support_cost_in_grand_total = self.total_support_cost

		self.grand_total_cost = round(
			self.team_cost_total
			+ self.direct_cost_total
			+ self.indirect_cost_total
			+ self.infrastructure_cost_total
			+ (self.total_support_cost or 0),
			2,
		)

	# ------------------------------------------------------------------
	# STEP 4: Pricing
	# ------------------------------------------------------------------
	def calculate_pricing(self):
		if not self.grand_total_cost:
			return

		margin = self.target_margin_pct or 30
		self.floor_price = round(self.grand_total_cost * 1.10, 2)
		self.standard_price = round(
			self.grand_total_cost / (1 - margin / 100) if margin < 100 else self.grand_total_cost * 2, 2
		)
		self.premium_price = round(self.standard_price * 1.25, 2)

		band = self.recommended_band or "Standard"
		if band == "Conservative":
			band_price = self.floor_price
		elif band == "Premium":
			band_price = self.premium_price
		else:
			band_price = self.standard_price

		# Custom price override — takes precedence over the band picker
		if self.use_custom_price and (self.custom_price or 0) > 0:
			self.recommended_price = float(self.custom_price)
		else:
			self.recommended_price = band_price

		if self.recommended_price:
			self.margin_at_recommended = round(
				(self.recommended_price - self.grand_total_cost) / self.recommended_price * 100, 2
			)
			self.price_per_hour = round(self.recommended_price / self.grand_total_hours, 2) if self.grand_total_hours else 0
			self.amc_suggested = round(self.recommended_price * 0.15, 2)

	# ------------------------------------------------------------------
	# STEP 5: Break-even
	# ------------------------------------------------------------------
	def calculate_break_even(self):
		# Treat support cost as a fixed labour reservation (already committed): subtract
		# it from price like any other non-team overhead so break-even reflects what's
		# left for the implementation team itself.
		non_team = (
			(self.direct_cost_total or 0)
			+ (self.indirect_cost_total or 0)
			+ (self.infrastructure_cost_total or 0)
			+ (self.total_support_cost or 0)
		)
		if self.blended_hourly_rate and self.recommended_price:
			self.break_even_hours = round(
				(self.recommended_price - non_team) / self.blended_hourly_rate, 1
			)
		else:
			self.break_even_hours = 0

		if self.grand_total_hours and self.break_even_hours:
			self.break_even_pct = round(self.break_even_hours / self.grand_total_hours * 100, 1)
			self.break_even_note = (
				f"You break even if the team takes up to {self.break_even_hours} hours "
				f"({self.break_even_pct}% of the estimate). "
				f"Beyond that, the project is at a loss."
			)
		else:
			self.break_even_pct = 0
			self.break_even_note = ""


@frappe.whitelist()
def verify_or_relink_project(estimate_name):
	"""Heal the linked_project pointer if the user renamed, deleted, or recreated
	the project.

	Returns one of:
	  - {"status": "unset"}                       — no link to verify
	  - {"status": "ok", "linked_project": ...}   — link still valid
	  - {"status": "renamed", "linked_project": ...} — original gone, but we found a
	      Project whose custom_implementation_estimate points back here, and re-linked it
	  - {"status": "missing"}                     — no recovery candidate; link cleared

	Recovery prefers the Custom Field `custom_implementation_estimate` (provisioned via
	fixtures) because it's a real Link and survives rename/recreate. Falls back to a
	notes-LIKE search for legacy projects created before the field existed. Frappe's
	rename_doc updates Link fields automatically, so a standard Rename action keeps
	the pointer alive without needing this recovery path — this exists for the
	delete-and-recreate or out-of-band rename cases.
	"""
	doc = frappe.get_doc("Implementation Estimate", estimate_name)
	if not doc.linked_project:
		# Even with no current link, check whether some Project already claims us via
		# the back-link Custom Field — that wins over leaving the field empty.
		claimed = frappe.db.get_value("Project", {"custom_implementation_estimate": estimate_name}, "name")
		if claimed:
			frappe.db.set_value("Implementation Estimate", estimate_name, "linked_project", claimed)
			return {"status": "renamed", "linked_project": claimed}
		return {"status": "unset"}

	if frappe.db.exists("Project", doc.linked_project):
		return {"status": "ok", "linked_project": doc.linked_project}

	# Primary recovery: the back-link Custom Field on Project.
	claimed = frappe.db.get_value("Project", {"custom_implementation_estimate": estimate_name}, "name")
	if claimed:
		frappe.db.set_value("Implementation Estimate", estimate_name, "linked_project", claimed)
		return {"status": "renamed", "linked_project": claimed}

	# Legacy fallback: the canonical tag we used to write into Project.notes.
	candidates = frappe.db.sql(
		"SELECT name FROM `tabProject` WHERE notes LIKE %s ORDER BY creation DESC LIMIT 1",
		(f"%Implementation Estimate {estimate_name}%",),
	)
	if candidates:
		new_pk = candidates[0][0]
		frappe.db.set_value("Implementation Estimate", estimate_name, "linked_project", new_pk)
		return {"status": "renamed", "linked_project": new_pk}

	frappe.db.set_value("Implementation Estimate", estimate_name, "linked_project", None)
	return {"status": "missing"}


@frappe.whitelist()
def run_monte_carlo(estimate_name, n_runs=1000,
                    hours_low=0.85, hours_high=1.30,
                    rate_low=0.95,  rate_high=1.15,
                    nonteam_low=0.90, nonteam_high=1.25):
	"""
	Run N Monte Carlo simulations on the estimate's economics.

	Three triangular distributions:
	- Hours        ~ Triangular(hours_low, 1.0, hours_high)
	- Blended rate ~ Triangular(rate_low, 1.0, rate_high)
	- Non-team $   ~ Triangular(nonteam_low, 1.0, nonteam_high)

	Returns P10/P50/P90 cost + profit, mean, probability of net loss, and
	a 25-bin histogram of profit for plotting.
	"""
	import random
	from statistics import mean

	doc = frappe.get_doc("Implementation Estimate", estimate_name)
	if not doc.recommended_price or not doc.grand_total_cost:
		return {"error": "Fill cost + recommended price before running Monte Carlo."}

	n_runs        = max(int(n_runs or 1000), 100)
	hours_low     = float(hours_low);    hours_high   = float(hours_high)
	rate_low      = float(rate_low);     rate_high    = float(rate_high)
	nonteam_low   = float(nonteam_low);  nonteam_high = float(nonteam_high)

	base_hours    = float(doc.grand_total_hours or 0)
	blended       = float(doc.blended_hourly_rate or 0)
	non_team_base = float((doc.direct_cost_total or 0)
	                      + (doc.indirect_cost_total or 0)
	                      + (doc.infrastructure_cost_total or 0)
	                      + (doc.total_support_cost or 0))
	price         = float(doc.recommended_price or 0)

	if base_hours <= 0 or blended <= 0:
		return {"error": "Need grand_total_hours and blended_hourly_rate > 0."}

	costs   = []
	profits = []
	loss_n  = 0
	for _ in range(n_runs):
		hm  = random.triangular(hours_low,  hours_high,  1.0)   # mode=1.0
		rm  = random.triangular(rate_low,   rate_high,   1.0)
		ntm = random.triangular(nonteam_low, nonteam_high, 1.0)
		team_cost_i = base_hours * hm * blended * rm
		non_team_i  = non_team_base * ntm
		total_i     = team_cost_i + non_team_i
		profit_i    = price - total_i
		costs.append(total_i); profits.append(profit_i)
		if profit_i < 0: loss_n += 1

	costs.sort(); profits.sort()
	def pct(lst, p):
		i = min(int(p / 100 * len(lst)), len(lst) - 1)
		return lst[i]

	# 25-bin histogram of PROFIT
	BINS = 25
	p_lo, p_hi = profits[0], profits[-1]
	if p_hi - p_lo < 1:
		p_hi = p_lo + 1
	bin_w = (p_hi - p_lo) / BINS
	hist  = [0] * BINS
	for v in profits:
		idx = min(int((v - p_lo) / bin_w), BINS - 1)
		hist[idx] += 1

	# Bucket edges for the histogram (centre of each bar)
	bin_centres = [p_lo + bin_w * (i + 0.5) for i in range(BINS)]

	return {
		"n_runs":           n_runs,
		"cost_p10":         round(pct(costs, 10), 0),
		"cost_p50":         round(pct(costs, 50), 0),
		"cost_p90":         round(pct(costs, 90), 0),
		"cost_mean":        round(mean(costs), 0),
		"profit_p10":       round(pct(profits, 10), 0),
		"profit_p50":       round(pct(profits, 50), 0),
		"profit_p90":       round(pct(profits, 90), 0),
		"profit_mean":      round(mean(profits), 0),
		"prob_loss_pct":    round(loss_n / n_runs * 100, 1),
		"base_cost":        round(float(doc.grand_total_cost), 0),
		"base_profit":      round(price - float(doc.grand_total_cost), 0),
		"price":            round(price, 0),
		"histogram":        hist,
		"histogram_bins":   [round(c, 0) for c in bin_centres],
		"params": {
			"hours_low": hours_low, "hours_high": hours_high,
			"rate_low": rate_low,   "rate_high": rate_high,
			"nonteam_low": nonteam_low, "nonteam_high": nonteam_high,
		},
	}


def _summary_html(title, lines, total_allocated, dur, company_monthly_sum, effective_share_pct, source_note):
	"""Shared HTML builder for Indirect + Infrastructure summary widgets."""
	cats = ", ".join(
		f"<tr><td style='padding:4px 8px;'>{frappe.utils.escape_html(c)}</td>"
		f"<td style='padding:4px 8px;text-align:right;'>₹{amt:,.0f}</td>"
		f"<td style='padding:4px 8px;text-align:right;color:#888;'>{(amt/total_allocated*100 if total_allocated else 0):.1f}%</td></tr>"
		for c, amt in lines
	)
	return f"""
	<div style="margin:6px 0;padding:12px;background:#f5f7fa;border-radius:6px;border:1px solid #dde2e8;">
		<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
			<div>
				<div style="font-size:12px;color:#666;text-transform:uppercase;">{title}</div>
				<div style="font-size:28px;font-weight:700;color:#2c3e50;margin-top:4px;">₹{total_allocated:,.0f}</div>
				<div style="font-size:12px;color:#888;margin-top:2px;">allocated to this project over {dur} month{'s' if dur != 1 else ''}</div>
			</div>
			<div style="text-align:right;font-size:12px;color:#666;line-height:1.6;">
				Company monthly: <b>₹{company_monthly_sum:,.0f}</b><br/>
				Effective project share: <b>{effective_share_pct:.1f}%</b><br/>
				<span style="color:#aaa;">{source_note}</span>
			</div>
		</div>
		{f'<table style="width:100%;border-collapse:collapse;margin-top:10px;font-size:13px;border-top:1px solid #e0e6ed;"><thead><tr style="color:#888;font-size:11px;text-transform:uppercase;"><td style="padding:6px 8px;">Category</td><td style="padding:6px 8px;text-align:right;">Allocated</td><td style="padding:6px 8px;text-align:right;">% of total</td></tr></thead><tbody>{cats}</tbody></table>' if lines else ''}
	</div>
	"""


@frappe.whitelist()
def get_indirect_summary(estimate_name):
	"""Render the read-only aggregated summary for Section H."""
	doc = frappe.get_doc("Implementation Estimate", estimate_name)
	if not doc.indirect_costs:
		return (
			"<p style='color:#888;margin:8px 0;'>"
			"No indirect costs loaded yet. "
			"Click <b>Actions → Load Indirect Costs from Books</b> to pull live averages."
			"</p>"
		)
	dur = max(int(doc.project_duration_months or 1), 1)
	company_monthly_sum = sum(float(r.monthly_total_cost or 0) for r in doc.indirect_costs)
	total_allocated     = sum(float(r.allocated_amount or 0)   for r in doc.indirect_costs)
	effective_share_pct = (total_allocated / (company_monthly_sum * dur) * 100) if (company_monthly_sum * dur) else 0

	# Group by category
	by_cat = {}
	for r in doc.indirect_costs:
		cat = r.category or "Other"
		by_cat[cat] = by_cat.get(cat, 0) + float(r.allocated_amount or 0)
	lines = sorted(by_cat.items(), key=lambda x: -x[1])

	return _summary_html(
		title="Indirect Cost Allocation",
		lines=lines,
		total_allocated=total_allocated,
		dur=dur,
		company_monthly_sum=company_monthly_sum,
		effective_share_pct=effective_share_pct,
		source_note=f"{len(doc.indirect_costs)} lines from books (EWMA over 6 mo)",
	)


@frappe.whitelist()
def get_infrastructure_summary(estimate_name):
	"""Render the read-only aggregated summary for Section I."""
	doc = frappe.get_doc("Implementation Estimate", estimate_name)
	if not doc.infrastructure_costs:
		return (
			"<p style='color:#888;margin:8px 0;'>"
			"No infrastructure costs added yet. Add rows manually below."
			"</p>"
		)
	dur = max(int(doc.project_duration_months or 1), 1)
	company_monthly_sum = sum(float(r.total_monthly_company_cost or 0) for r in doc.infrastructure_costs)
	total_allocated     = sum(float(r.allocated_amount or 0)            for r in doc.infrastructure_costs)
	effective_share_pct = (total_allocated / (company_monthly_sum * dur) * 100) if (company_monthly_sum * dur) else 0

	by_cat = {}
	for r in doc.infrastructure_costs:
		cat = r.category or "Other"
		by_cat[cat] = by_cat.get(cat, 0) + float(r.allocated_amount or 0)
	lines = sorted(by_cat.items(), key=lambda x: -x[1])

	return _summary_html(
		title="Infrastructure Cost Allocation",
		lines=lines,
		total_allocated=total_allocated,
		dur=dur,
		company_monthly_sum=company_monthly_sum,
		effective_share_pct=effective_share_pct,
		source_note=f"{len(doc.infrastructure_costs)} shared assets",
	)


@frappe.whitelist()
def check_team_capacity(estimate_name):
	"""
	Return an HTML table showing each team member's capacity utilization
	considering this estimate PLUS every Won estimate they're on.

	Only **Won** estimates count as real commitments. Draft / Under Review /
	Approved estimates are still in negotiation and may never materialise,
	so they're excluded to avoid inflating the conflict count.
	"""
	from frappe.utils import getdate, add_months, nowdate

	doc = frappe.get_doc("Implementation Estimate", estimate_name)
	if not doc.team_members:
		return "<p style='color:#888;margin:8px 0;'>Add team members to see capacity check.</p>"

	MONTHLY_HOURS_CAP = 22 * 6  # same constant as elsewhere
	this_dur     = max(int(doc.project_duration_months or 1), 1)
	this_start   = getdate(doc.enquiry_date or nowdate())
	this_end     = add_months(this_start, this_dur)

	# Sum same-employee rows on THIS estimate (only active ones)
	this_alloc = {}
	for r in doc.team_members:
		if not r.employee or not r.is_active_in_current_version: continue
		this_alloc.setdefault(r.employee, {'hours': 0, 'role': r.role, 'name': r.employee})
		this_alloc[r.employee]['hours'] += r.allocated_hours or 0

	if not this_alloc:
		return "<p style='color:#888;margin:8px 0;'>Add team members to see capacity check.</p>"

	# Pull every team member from every other WON estimate.
	# Draft / Under Review / Approved / Revision Requested / On Hold are
	# excluded — they're not real commitments until the deal is Won.
	rows = frappe.db.sql("""
		SELECT
			ie.name AS estimate, ie.client_name, ie.status,
			ie.project_duration_months, ie.enquiry_date,
			tm.employee, tm.allocated_hours
		FROM `tabImplementation Estimate` ie
		INNER JOIN `tabTeam Composition` tm ON tm.parent = ie.name
		WHERE ie.name != %(self)s
		  AND ie.status = 'Won'
		  AND tm.is_active_in_current_version = 1
		  AND tm.employee IN %(emps)s
		  AND tm.allocated_hours > 0
	""", {
		"self": estimate_name,
		"emps": tuple(this_alloc.keys()),
	}, as_dict=True)

	def overlap_hours(other_start, other_dur, other_total_hours):
		"""How many of `other`'s hours fall inside THIS estimate's window."""
		o_start = getdate(other_start or nowdate())
		o_end   = add_months(o_start, max(int(other_dur or 1), 1))
		overlap_start = max(o_start, this_start)
		overlap_end   = min(o_end, this_end)
		days_overlap = (overlap_end - overlap_start).days
		if days_overlap <= 0: return 0
		other_total_days = (o_end - o_start).days or 30
		return other_total_hours * (days_overlap / other_total_days)

	# Aggregate per employee
	commitments = {emp: {'overlap_hours': 0, 'estimates': []} for emp in this_alloc}
	for r in rows:
		if r.employee not in commitments: continue
		oh = overlap_hours(r.enquiry_date, r.project_duration_months, r.allocated_hours or 0)
		commitments[r.employee]['overlap_hours'] += oh
		commitments[r.employee]['estimates'].append({
			'estimate':         r.estimate,
			'client':           r.client_name,
			'status':           r.status,
			'allocated':        float(r.allocated_hours or 0),
			'overlap_in_window': round(oh, 1),
		})

	# Resolve employee display names
	emp_names = dict(frappe.db.sql(
		"SELECT name, employee_name FROM `tabEmployee` WHERE name IN %(emps)s",
		{"emps": tuple(this_alloc.keys())}
	))

	# Build the table HTML
	window_capacity = MONTHLY_HOURS_CAP * this_dur
	rows_html = []
	for emp, info in this_alloc.items():
		this_h     = info['hours']
		others_h   = commitments[emp]['overlap_hours']
		total_h    = this_h + others_h
		util_pct   = (total_h / window_capacity * 100) if window_capacity > 0 else 0

		if util_pct >= 100:
			color, icon, label = "#e74c3c", "🔴", "OVER"
		elif util_pct >= 85:
			color, icon, label = "#f39c12", "⚠️", "AT CAP"
		elif util_pct >= 65:
			color, icon, label = "#f1c40f", "⚡", "BUSY"
		else:
			color, icon, label = "#27ae60", "✅", "OK"

		# Detail of other estimates
		others = commitments[emp]['estimates']
		if others:
			details_html = "<ul style='margin:4px 0 0;padding-left:20px;font-size:12px;'>"
			for o in sorted(others, key=lambda x: -x['overlap_in_window']):
				details_html += (f"<li>{frappe.utils.escape_html(o['estimate'])} — "
				                 f"{frappe.utils.escape_html(o['client'] or '?')} "
				                 f"<span style='color:#888'>({o['status']})</span>: "
				                 f"{o['overlap_in_window']:.0f} hrs in window "
				                 f"<span style='color:#888'>(of {o['allocated']:.0f} total)</span></li>")
			details_html += "</ul>"
		else:
			details_html = "<span style='color:#888;font-size:12px;'>No other open commitments.</span>"

		emp_display = emp_names.get(emp, emp)
		bar_width = min(util_pct, 100)
		rows_html.append(f"""
		<tr style="border-bottom:1px solid #eee;">
			<td style="padding:8px;vertical-align:top;">
				<b>{frappe.utils.escape_html(emp_display)}</b>
				<br/><small style="color:#888;">{frappe.utils.escape_html(info['role'] or '')}</small>
			</td>
			<td style="padding:8px;text-align:right;vertical-align:top;">{this_h:,.0f}</td>
			<td style="padding:8px;text-align:right;vertical-align:top;">{others_h:,.0f}</td>
			<td style="padding:8px;text-align:right;vertical-align:top;"><b>{total_h:,.0f}</b></td>
			<td style="padding:8px;text-align:right;vertical-align:top;color:#888;">{window_capacity:,}</td>
			<td style="padding:8px;vertical-align:top;min-width:160px;">
				<div style="background:#ecf0f1;border-radius:4px;height:18px;position:relative;overflow:hidden;">
					<div style="background:{color};height:100%;width:{bar_width:.0f}%;"></div>
				</div>
				<div style="margin-top:2px;color:{color};font-weight:600;font-size:12px;">
					{util_pct:.0f}% — {icon} {label}
				</div>
			</td>
			<td style="padding:8px;vertical-align:top;">{details_html}</td>
		</tr>""")

	return f"""
	<div style="margin:8px 0;">
		<h6 style="margin:0 0 6px;">Team Capacity Check</h6>
		<small style="color:#888;">
			Window: {this_start} → {this_end} ({this_dur} month{'s' if this_dur != 1 else ''}).
			Capacity per employee = {MONTHLY_HOURS_CAP} hrs/mo × {this_dur} = {window_capacity:,} hrs.
			Counts overlapping hours from every non-Lost / non-Cancelled estimate.
		</small>
		<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;">
			<thead>
				<tr style="background:#2c3e50;color:white;">
					<th style="padding:8px;text-align:left;">Employee</th>
					<th style="padding:8px;text-align:right;">This est.</th>
					<th style="padding:8px;text-align:right;">Other</th>
					<th style="padding:8px;text-align:right;">Total</th>
					<th style="padding:8px;text-align:right;">Capacity</th>
					<th style="padding:8px;">Utilization</th>
					<th style="padding:8px;text-align:left;">Conflicts</th>
				</tr>
			</thead>
			<tbody>{''.join(rows_html)}</tbody>
		</table>
	</div>
	"""


def _clean(v):
	"""Strip empty/None-as-string values that pollute display."""
	if v is None:
		return ""
	v = str(v).strip()
	return "" if v.lower() in ("none", "null") else v


@frappe.whitelist()
def get_client_contact(client_type, client_name, contact_person=None):
	"""Return contact info for the picked Customer or Lead.

	Lookup chain for **Customer** (first non-empty wins):
	  1. The explicitly-passed `contact_person` Contact, if any
	  2. The Customer's `customer_primary_contact` (the official primary)
	  3. Any Contact linked to the Customer via Dynamic Link
	  4. The Customer record's own `mobile_no` / `email_id` fields (no Contact at all)

	For **Lead** — leads don't use the Contact doctype; everything is inline:
	  `lead_name`, `email_id`, `mobile_no` come straight off the Lead.

	Returns:
	  {
	    "contact_person":     "<Contact name or empty>",
	    "contact_full_name":  "...",
	    "contact_email":      "...",
	    "contact_mobile_no":  "...",
	    "source":             "primary" | "linked" | "customer_direct" | "lead" | "explicit",
	  }
	"""
	result = {
		"contact_person":    "",
		"contact_full_name": "",
		"contact_email":     "",
		"contact_mobile_no": "",
		"source":            "",
	}
	if not client_name:
		return result

	# ── Lead path ─────────────────────────────────────────────────────────
	if client_type == "Lead":
		lead = frappe.db.get_value(
			"Lead", client_name,
			["lead_name", "email_id", "mobile_no"],
			as_dict=True,
		)
		if lead:
			result["contact_full_name"] = _clean(lead.get("lead_name"))
			result["contact_email"]     = _clean(lead.get("email_id"))
			result["contact_mobile_no"] = _clean(lead.get("mobile_no"))
			result["source"]            = "lead"
		return result

	# ── Customer path ─────────────────────────────────────────────────────
	contact_name = _clean(contact_person)
	source = "explicit" if contact_name else ""

	if not contact_name:
		# Step 2: prefer the official primary contact
		primary = frappe.db.get_value(
			"Customer", client_name, "customer_primary_contact"
		)
		if primary:
			contact_name = primary
			source = "primary"

	if not contact_name:
		# Step 3: any Contact linked via Dynamic Link
		contact_name = frappe.db.get_value(
			"Dynamic Link",
			{"link_doctype": "Customer", "link_name": client_name, "parenttype": "Contact"},
			"parent",
		)
		if contact_name:
			source = "linked"

	if contact_name and frappe.db.exists("Contact", contact_name):
		contact = frappe.db.get_value(
			"Contact", contact_name,
			["full_name", "first_name", "last_name", "email_id", "mobile_no"],
			as_dict=True,
		)
		if contact:
			# Prefer Contact.full_name (auto-built); fall back to first+last with
			# "None"-as-string sanitisation.
			name = _clean(contact.get("full_name"))
			if not name:
				name = " ".join(filter(None, [_clean(contact.get("first_name")),
				                              _clean(contact.get("last_name"))]))
			result["contact_person"]    = contact_name
			result["contact_full_name"] = name
			result["contact_email"]     = _clean(contact.get("email_id"))
			result["contact_mobile_no"] = _clean(contact.get("mobile_no"))
			result["source"]            = source or "linked"
			return result

	# Step 4: no Contact found — fall back to Customer-level mobile/email/name
	cust = frappe.db.get_value(
		"Customer", client_name,
		["customer_name", "mobile_no", "email_id"],
		as_dict=True,
	)
	if cust:
		result["contact_full_name"] = _clean(cust.get("customer_name"))
		result["contact_email"]     = _clean(cust.get("email_id"))
		result["contact_mobile_no"] = _clean(cust.get("mobile_no"))
		result["source"]            = "customer_direct"

	return result


@frappe.whitelist()
def get_employee_hourly_cost(employee):
	"""
	Derive an employee's internal hourly cost.

	Lookup order (first non-zero wins):
	  1. Employee.ctc                  — primary. TBO uses `ctc` as the MONTHLY
	     salary, not annual (verified against the values in the live data).
	     Salary Structure Assignment and Salary Slips aren't consistently
	     populated in this site, so CTC on the Employee master is the source
	     of truth.
	  2. Salary Structure Assignment.base (monthly) — fallback for legacy
	     records that pre-date the CTC-on-Employee workflow.
	  3. Avg gross_pay of last 3 submitted Salary Slips — secondary fallback.

	Returns: {hourly_cost, monthly_salary, source}
	Divisor: 22 working days × 6 hrs/day = 132 hrs/month (matches the
	project-duration and capacity-check formulas).
	"""
	MONTHLY_HOURS = 22 * 6
	monthly = 0.0
	source = ""

	# 1. Monthly CTC from Employee master
	ctc = frappe.db.get_value("Employee", employee, "ctc")
	if ctc and float(ctc) > 0:
		monthly = float(ctc)
		source = f"Employee CTC (₹{float(ctc):,.0f}/mo)"

	# 2. Salary Structure Assignment fallback
	if not monthly:
		ssa = frappe.db.sql("""
			SELECT base
			FROM `tabSalary Structure Assignment`
			WHERE employee = %s AND docstatus = 1
			ORDER BY from_date DESC
			LIMIT 1
		""", employee, as_dict=True)
		if ssa and ssa[0].base:
			monthly = float(ssa[0].base)
			source = "Salary Structure Assignment"

	# 3. Salary Slips fallback
	if not monthly:
		slips = frappe.db.sql("""
			SELECT gross_pay
			FROM `tabSalary Slip`
			WHERE employee = %s AND docstatus = 1
			ORDER BY start_date DESC
			LIMIT 3
		""", employee, as_dict=True)
		if slips:
			vals = [float(s.gross_pay or 0) for s in slips]
			if any(vals):
				monthly = sum(vals) / len(vals)
				source = f"Avg of last {len(slips)} Salary Slip(s)"

	if monthly:
		return {
			"hourly_cost": round(monthly / MONTHLY_HOURS, 2),
			"monthly_salary": round(monthly, 2),
			"source": source,
		}

	return {"hourly_cost": 0, "monthly_salary": 0,
	        "source": "No salary data — fill in CTC on the Employee record (or add a Salary Structure Assignment)"}


@frappe.whitelist()
def get_scenario_data(docname):
	"""Return scenario comparison table data for the JS renderer + report.

	Base row must equal Section K's Grand Total Cost exactly. To enforce that:
	- team cost = team_cost_total × multiplier (scaled actual team cost, not
	  base_hours × blended which can drift when team allocation differs from scope).
	- non_team includes total_support_cost so all five cost buckets are summed.
	"""
	doc = frappe.get_doc("Implementation Estimate", docname)
	team_cost_total = doc.team_cost_total or 0
	non_team = (
		(doc.direct_cost_total or 0)
		+ (doc.indirect_cost_total or 0)
		+ (doc.infrastructure_cost_total or 0)
		+ (doc.total_support_cost or 0)
	)
	price = doc.recommended_price or 0
	base_hours = doc.grand_total_hours or 0
	custom_pct = (doc.scenario_custom_pct or 100) / 100

	scenarios = {}
	for key, mult in {**SCENARIO_MULTIPLIERS, "custom": custom_pct}.items():
		hrs = round(base_hours * mult, 1)
		team_cost = round(team_cost_total * mult, 2)
		total_cost = round(team_cost + non_team, 2)
		profit = round(price - total_cost, 2)
		margin = round(profit / price * 100, 1) if price else 0
		scenarios[key] = {
			"hours": hrs,
			"team_cost": team_cost,
			"total_cost": total_cost,
			"gross_profit": profit,
			"margin_pct": margin,
			"status": "Profit" if profit >= 0 else "Loss",
		}
	return scenarios
