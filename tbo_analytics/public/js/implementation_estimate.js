// Copyright (c) 2026, tbo and contributors
// For license information, please see license.txt

// ─── Helpers ───────────────────────────────────────────────────────────────

function fmt_currency(val) {
	if (!val && val !== 0) return "—";
	return "₹" + parseFloat(val).toLocaleString("en-IN", {
		minimumFractionDigits: 0,
		maximumFractionDigits: 0
	});
}

function fmt_hours(val) {
	if (!val && val !== 0) return "—";
	return parseFloat(val).toLocaleString("en-IN") + " hrs";
}

function resolve_final_hours(ai_val, manual_val) {
	if (manual_val && manual_val > 0) return manual_val;
	if (ai_val && ai_val > 0) return ai_val;
	return 0;
}

// ─── Contact auto-fetch helpers ────────────────────────────────────────────

function _clear_contact_fields(frm) {
	frm.set_value("contact_full_name", "");
	frm.set_value("contact_email", "");
	frm.set_value("contact_mobile_no", "");
}

// Auto-fetch industry from the linked Customer or Lead. Only fills if the field
// is currently empty so a deliberate manual override isn't clobbered when the
// client is re-saved.
function _fetch_industry(frm) {
	if (!frm.doc.client_type || !frm.doc.client_name) return;
	if (frm.doc.industry) return;   // respect manual override
	frappe.db.get_value(frm.doc.client_type, frm.doc.client_name, "industry").then(r => {
		const v = r && r.message && r.message.industry;
		if (v) frm.set_value("industry", v);
	});
}

// Restrict the contact_person picker to Contacts linked to the current Customer.
// Frappe's built-in `Contact` Link query supports passing `link_doctype` + `link_name`
// filters via the standard contact_query method.
function scope_contact_person_picker(frm) {
	if (!frm.set_query) return;
	frm.set_query("contact_person", () => {
		if (frm.doc.client_type === "Customer" && frm.doc.client_name) {
			return {
				query: "frappe.contacts.doctype.contact.contact.contact_query",
				filters: { link_doctype: "Customer", link_name: frm.doc.client_name },
			};
		}
		return {};   // empty filter for Lead (Contact picker hidden by depends_on anyway)
	});
}

function _fetch_contact(frm) {
	frappe.call({
		method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.get_client_contact",
		args: {
			client_type: frm.doc.client_type,
			client_name: frm.doc.client_name,
			contact_person: frm.doc.contact_person || null,
		},
	}).then(r => {
		const d = r.message || {};
		// If the server resolved a Contact (Customer path), populate the Link field.
		// Setting it programmatically does fire the contact_person handler — but
		// set_value short-circuits when the value is unchanged, so re-fetching once
		// is the worst case (acceptable, < 100ms round-trip).
		if (d.contact_person && d.contact_person !== frm.doc.contact_person) {
			frm.set_value("contact_person", d.contact_person);
		}
		frm.set_value("contact_full_name", d.contact_full_name || "");
		frm.set_value("contact_email", d.contact_email || "");
		frm.set_value("contact_mobile_no", d.contact_mobile_no || "");
		if (d.contact_full_name) {
			const src_label = ({
				primary:         "primary contact",
				linked:          "linked contact",
				customer_direct: "Customer record",
				lead:            "Lead record",
				explicit:        "selected contact",
			})[d.source] || "contact";
			frappe.show_alert({
				message: `Contact: ${d.contact_full_name} (from ${src_label})`,
				indicator: "blue",
			}, 4);
		}
	});
}

// ─── Main Form Handlers ────────────────────────────────────────────────────

frappe.ui.form.on("Implementation Estimate", {

	refresh(frm) {
		try { setup_custom_buttons(frm); } catch (e) { console.error("tbo_analytics: setup_custom_buttons failed", e); }
		try { update_scenario_table(frm); } catch (e) { console.error("tbo_analytics: update_scenario_table failed", e); }
		try { set_field_descriptions(frm); } catch (e) { console.error("tbo_analytics: set_field_descriptions failed", e); }
		try { add_quick_add_direct_costs(frm); } catch (e) { console.error("tbo_analytics: add_quick_add_direct_costs failed", e); }
		try { update_team_capacity(frm); } catch (e) { console.error("tbo_analytics: update_team_capacity failed", e); }
		try { update_indirect_summary(frm); } catch (e) { console.error("tbo_analytics: update_indirect_summary failed", e); }
		try { update_infrastructure_summary(frm); } catch (e) { console.error("tbo_analytics: update_infrastructure_summary failed", e); }
		try { update_sensitivity_table(frm); } catch (e) { console.error("tbo_analytics: update_sensitivity_table failed", e); }
		try { update_custom_price_assessment(frm); } catch (e) { console.error("tbo_analytics: update_custom_price_assessment failed", e); }
		try { render_monte_carlo_placeholder(frm); } catch (e) { console.error("tbo_analytics: render_monte_carlo_placeholder failed", e); }
		try { verify_linked_project(frm); } catch (e) { console.error("tbo_analytics: verify_linked_project failed", e); }
		try { scope_contact_person_picker(frm); } catch (e) { console.error("tbo_analytics: scope_contact_person_picker failed", e); }
		try { update_team_allocation_summary(frm); } catch (e) { console.error("tbo_analytics: update_team_allocation_summary failed", e); }
	},

	onload(frm) {
		// Set default recommended_band if empty
		if (!frm.doc.recommended_band) {
			frm.set_value("recommended_band", "Standard");
		}
	},

	company_size(frm)            { recalc_all(frm); },
	data_migration_required(frm) { recalc_all(frm); },

	// Child-row add/remove → re-aggregate hours so dashboards update without saving.
	module_selections_remove(frm)        { recalc_hour_totals(frm); },
	custom_module_requests_remove(frm)   { recalc_hour_totals(frm); },
	integration_requirements_remove(frm) { recalc_hour_totals(frm); },
	target_margin_pct(frm)       { recalc_pricing(frm); },
	recommended_band(frm)        { recalc_pricing(frm); },
	use_custom_price(frm)        { recalc_pricing(frm); update_custom_price_assessment(frm); invalidate_monte_carlo(frm); },
	custom_price(frm)            { recalc_pricing(frm); update_custom_price_assessment(frm); invalidate_monte_carlo(frm); },
	scenario_custom_pct(frm)     { update_scenario_table(frm); },

	// Client Type drives whether the Client picker lists Leads or Customers.
	// Clear the picked value and contact fields when the type changes.
	client_type(frm) {
		if (frm.doc.client_name) frm.set_value("client_name", null);
		frm.set_value("contact_person", null);
		_clear_contact_fields(frm);
	},

	client_name(frm) {
		// Clear previous contact info, then auto-fetch from the new client
		frm.set_value("contact_person", null);
		_clear_contact_fields(frm);
		if (frm.doc.client_name) {
			_fetch_contact(frm);
			_fetch_industry(frm);
		}
	},

	contact_person(frm) {
		// Re-fetch using the explicitly selected contact
		_clear_contact_fields(frm);
		if (frm.doc.client_name) _fetch_contact(frm);
	},

	// On adding a new Direct Cost row, seed Duration from the project's duration
	// so the user sees a sensible number immediately. They can override per row.
	direct_costs_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.project_duration_months && frm.doc.project_duration_months) {
			frappe.model.set_value(cdt, cdn, "project_duration_months", frm.doc.project_duration_months);
		}
	},


	// Post Go-Live Support — recompute cost when any support input changes.
	monthly_support_hours(frm)   { recalc_all_costs(frm); },
	support_duration_months(frm) { recalc_all_costs(frm); },
	support_hourly_rate(frm)     { recalc_all_costs(frm); },

	// ── Real-time client-side cost roll-up (complementary to server-side) ──
	// Called after any child table edit to keep totals live without save.
});

// ─── Module Selection child table ──────────────────────────────────────────

frappe.ui.form.on("Module Selection", {

	module(frm, cdt, cdn) {
		recompute_module_ai_hours(frm, cdt, cdn);
	},

	complexity(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const grid = frm.fields_dict && frm.fields_dict["module_selections"] && frm.fields_dict["module_selections"].grid;
		if (grid && grid.get_row) {
			const grid_row = grid.get_row(cdn);
			if (grid_row && grid_row.row) {
				grid_row.row.toggleClass("complex-row", complexity_mult(row.complexity) > 1.5);
			}
		}
		if (row.module) {
			recompute_module_ai_hours(frm, cdt, cdn);
		}
		if (row.customization_required) {
			recompute_customization_hours(row, cdt, cdn);
			update_row_final_hours(frm, cdt, cdn);
		}
	},

	leader_estimated_hours(frm, cdt, cdn) {
		update_row_final_hours(frm, cdt, cdn);
	},

	customization_required(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		recompute_customization_hours(row, cdt, cdn);
		update_row_final_hours(frm, cdt, cdn);
	},

	// Legacy single-Select — kept hidden but still wired up in case anything reads it.
	customization_type(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		recompute_customization_hours(row, cdt, cdn);
		update_row_final_hours(frm, cdt, cdn);
	},

	// One handler per Customization Type Check — all recompute the row's hours.
	cust_custom_field(frm, cdt, cdn)     { _cust_changed(frm, cdt, cdn); },
	cust_custom_form(frm, cdt, cdn)      { _cust_changed(frm, cdt, cdn); },
	cust_workflow(frm, cdt, cdn)         { _cust_changed(frm, cdt, cdn); },
	cust_custom_report(frm, cdt, cdn)    { _cust_changed(frm, cdt, cdn); },
	cust_print_format(frm, cdt, cdn)     { _cust_changed(frm, cdt, cdn); },
	cust_api_integration(frm, cdt, cdn)  { _cust_changed(frm, cdt, cdn); },
	cust_other(frm, cdt, cdn)            { _cust_changed(frm, cdt, cdn); },

	customization_manual_hours(frm, cdt, cdn) {
		update_row_final_hours(frm, cdt, cdn);
	},

	is_included(frm, cdt, cdn) {
		recalc_hour_totals(frm);
	},
});

// Shared helper for the 7 Customization Type Check handlers.
function _cust_changed(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	recompute_customization_hours(row, cdt, cdn);
	update_row_final_hours(frm, cdt, cdn);
}

// Float complexity ∈ [1.0, 2.0]. Clamps out-of-range values. Mirror of the Python helper.
function complexity_mult(c) {
	const v = parseFloat(c);
	if (isNaN(v)) return 1.0;
	return Math.max(1.0, Math.min(v, 2.0));
}

// Multi-check model: each ticked Customization Type contributes its hours.
const CUSTOMIZATION_FLAG_HOURS = {
	cust_custom_field:     4,
	cust_custom_form:     16,
	cust_workflow:        12,
	cust_custom_report:   10,
	cust_print_format:    10,
	cust_api_integration: 24,
	cust_other:            8,
};
const CUSTOMIZATION_LEGACY_TO_FLAG = {
	"Custom Field":      "cust_custom_field",
	"Custom Form":       "cust_custom_form",
	"Workflow":          "cust_workflow",
	"Custom Report":     "cust_custom_report",
	"Print Format":      "cust_print_format",
	"API / Integration": "cust_api_integration",
	"Other":             "cust_other",
};

function recompute_customization_hours(row, cdt, cdn) {
	if (!row.customization_required) {
		frappe.model.set_value(cdt, cdn, "customization_ai_hours", 0);
		return;
	}

	// Sum hours across every ticked flag.
	let base = 0;
	for (const [flag, hrs] of Object.entries(CUSTOMIZATION_FLAG_HOURS)) {
		if (row[flag]) base += hrs;
	}

	// Legacy fallback: if no flags ticked but the old single-Select has a value,
	// flip the corresponding flag and use its hours. Python's calculate_ai_estimates
	// also does this on save, so the migration sticks.
	if (base === 0 && row.customization_type) {
		const target = CUSTOMIZATION_LEGACY_TO_FLAG[row.customization_type];
		if (target) {
			frappe.model.set_value(cdt, cdn, target, 1);
			base = CUSTOMIZATION_FLAG_HOURS[target] || 0;
		}
	}

	const cmult = complexity_mult(row.complexity);
	frappe.model.set_value(cdt, cdn, "customization_ai_hours", Math.round(base * cmult * 10) / 10);
}

function recompute_module_ai_hours(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.module) return;
	frappe.db.get_doc("ERP Module Master", row.module).then(m => {
		const cmult  = complexity_mult(row.complexity);
		const weight = cmult - 1.0;   // 0.0 at cmult=1.0, 1.0 at cmult=2.0
		const size_f = { Micro: 0.8, Small: 1.0, Medium: 1.2, Large: 1.4, Enterprise: 1.7 }[frm.doc.company_size] || 1.0;
		const mig_f  = frm.doc.data_migration_required ? 1.15 : 1.0;
		// Base: historical avg if set, else linear interpolation between c1 and c2 base hours
		const base = m.historical_avg_hours
			|| ((1 - weight) * (m.base_hours_complexity_1 || 0) + weight * (m.base_hours_complexity_2 || 0))
			|| 0;
		frappe.model.set_value(cdt, cdn, "ai_estimated_hours",
			Math.round(base * cmult * size_f * mig_f * 10) / 10);
		update_row_final_hours(frm, cdt, cdn);
	});
}

function update_row_final_hours(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const fh = resolve_final_hours(row.ai_estimated_hours, row.leader_estimated_hours);
	const cfh = resolve_final_hours(row.customization_ai_hours, row.customization_manual_hours);
	frappe.model.set_value(cdt, cdn, "final_hours", fh);
	frappe.model.set_value(cdt, cdn, "customization_final_hours", cfh);
	frappe.model.set_value(cdt, cdn, "total_module_hours", Math.round((fh + cfh) * 10) / 10);
	recalc_hour_totals(frm);
}

// ─── Team Composition child table ──────────────────────────────────────────

frappe.ui.form.on("Team Composition", {

	employee(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.employee) {
			recalc_team_cost(frm, cdt, cdn);    // row cleared → still need to refresh totals
			return;
		}
		frappe.call({
			method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.get_employee_hourly_cost",
			args: { employee: row.employee },
		}).then(r => {
			const data = r.message || {};
			if (data.hourly_cost) {
				frappe.model.set_value(cdt, cdn, "hourly_cost", data.hourly_cost);
				if (data.source) {
					frappe.show_alert({
						message: `${row.employee}: ₹${data.hourly_cost}/hr (from ${data.source})`,
						indicator: "blue",
					}, 4);
				}
			} else {
				frappe.show_alert({
					message: `No salary data for ${row.employee}. Set a Salary Structure Assignment in HRMS.`,
					indicator: "orange",
				}, 6);
			}
			// Always re-cost the row + propagate to dashboards, even when set_value above
			// short-circuits (e.g. new employee happens to have the same hourly rate).
			recalc_team_cost(frm, cdt, cdn);
			debounce_capacity_check(frm);
			update_team_allocation_summary(frm);
		});
	},

	allocated_hours(frm, cdt, cdn) {
		recalc_team_cost(frm, cdt, cdn);
		debounce_capacity_check(frm);
		update_team_allocation_summary(frm);
	},

	hourly_cost(frm, cdt, cdn) {
		recalc_team_cost(frm, cdt, cdn);
	},

	is_active_in_current_version(frm, cdt, cdn) {
		recalc_all_costs(frm);
		debounce_capacity_check(frm);
		update_team_allocation_summary(frm);
	},
});

// ─── Custom Module Request child table — live recalc ──────────────────────

frappe.ui.form.on("Custom Module Request", {
	complexity(frm, cdt, cdn)              { _recalc_custom_module(frm, cdt, cdn); },
	leader_estimated_hours(frm, cdt, cdn)  { _recalc_custom_module(frm, cdt, cdn); },
	needs_integration(frm, cdt, cdn)       { _recalc_custom_module(frm, cdt, cdn); },
	integration_hours(frm, cdt, cdn)       { _recalc_custom_module(frm, cdt, cdn); },
	needs_reports(frm, cdt, cdn)           { _recalc_custom_module(frm, cdt, cdn); },
	report_hours(frm, cdt, cdn)            { _recalc_custom_module(frm, cdt, cdn); },
	needs_dashboards(frm, cdt, cdn)        { _recalc_custom_module(frm, cdt, cdn); },
	dashboard_hours(frm, cdt, cdn)         { _recalc_custom_module(frm, cdt, cdn); },
});

function _recalc_custom_module(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const fh = resolve_final_hours(row.ai_estimated_hours, row.leader_estimated_hours);
	let total = fh;
	if (row.needs_integration) total += (row.integration_hours || 0);
	if (row.needs_reports)     total += (row.report_hours     || 0);
	if (row.needs_dashboards)  total += (row.dashboard_hours  || 0);
	frappe.model.set_value(cdt, cdn, "final_hours", fh);
	frappe.model.set_value(cdt, cdn, "total_hours", Math.round(total * 10) / 10);
	recalc_hour_totals(frm);
}

// ─── Integration Requirement child table — live recalc ─────────────────────

frappe.ui.form.on("Integration Requirement", {
	complexity(frm, cdt, cdn)    { _recalc_integration(frm, cdt, cdn); },
	manual_hours(frm, cdt, cdn)  { _recalc_integration(frm, cdt, cdn); },
});

function _recalc_integration(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const fh = resolve_final_hours(row.ai_estimated_hours, row.manual_hours);
	frappe.model.set_value(cdt, cdn, "final_hours", fh);
	recalc_hour_totals(frm);
}

let _capacity_check_timer = null;
function debounce_capacity_check(frm) {
	if (_capacity_check_timer) clearTimeout(_capacity_check_timer);
	_capacity_check_timer = setTimeout(() => update_team_capacity(frm), 500);
}

// "Hours to Allocate" widget — sits above the Team Composition table.
// Shows Total needed (from grand_total_hours) vs Allocated (Σ allocated_hours
// for active rows) + a Remaining bar + per-bucket module breakdown. PM uses
// this to split hours fairly across the team without scrolling to Section J.
function update_team_allocation_summary(frm) {
	const field = frm.fields_dict && frm.fields_dict["team_allocation_summary_html"];
	if (!field || !field.$wrapper) return;

	const total      = parseFloat(frm.doc.grand_total_hours) || 0;
	const t_mod      = parseFloat(frm.doc.total_modules_hours) || 0;
	const t_custom   = parseFloat(frm.doc.total_custom_modules_hours) || 0;
	const t_integr   = parseFloat(frm.doc.total_integration_hours) || 0;

	const active = (frm.doc.team_members || []).filter(r => r.is_active_in_current_version);
	const allocated = active.reduce((sum, r) => sum + (parseFloat(r.allocated_hours) || 0), 0);
	const remaining = total - allocated;

	if (total <= 0) {
		field.$wrapper.html(`
			<div style="padding:10px 14px;background:#f5f5f5;border-left:3px solid #888;color:#777;font-size:13px;margin-bottom:8px;">
				Add modules / customs / integrations in Sections B–D first to see hours to allocate.
			</div>`);
		return;
	}

	const pct = total > 0 ? Math.min(100, Math.round(allocated / total * 1000) / 10) : 0;
	const status_colour =
		remaining < 0 ? "#e74c3c" :              // over-allocated
		remaining === 0 ? "#27ae60" :            // exactly matched
		pct >= 80 ? "#2980b9" :                  // close
		"#f39c12";                                // significantly under
	const status_label =
		remaining < 0 ? `OVER-ALLOCATED by ${fmt_hours(Math.abs(remaining))}` :
		remaining === 0 ? "FULLY ALLOCATED" :
		`${fmt_hours(remaining)} REMAINING`;

	// Bucket rows — only show buckets that have hours
	const buckets = [
		{ label: "Modules (Section B)",       hrs: t_mod,    color: "#3498db" },
		{ label: "Custom Modules (Section C)", hrs: t_custom, color: "#9b59b6" },
		{ label: "Integrations (Section D)",   hrs: t_integr, color: "#1abc9c" },
	].filter(b => b.hrs > 0);

	const bucket_rows = buckets.map(b => `
		<tr>
			<td style="padding:4px 10px;color:${b.color};font-weight:600;">${b.label}</td>
			<td style="padding:4px 10px;text-align:right;font-weight:600;">${fmt_hours(b.hrs)}</td>
			<td style="padding:4px 10px;text-align:right;color:#888;">${(total > 0 ? (b.hrs/total*100).toFixed(1) : 0)}%</td>
		</tr>
	`).join("");

	// Team allocation breakdown — who's been given what
	const team_rows = active.length ? active.map(r => {
		const a = parseFloat(r.allocated_hours) || 0;
		const p = total > 0 ? (a / total * 100).toFixed(1) : 0;
		const name = r.employee_name || r.employee || "(unnamed)";
		return `
			<tr>
				<td style="padding:4px 10px;">${name} <span style="color:#888;">(${r.role || "—"})</span></td>
				<td style="padding:4px 10px;text-align:right;">${fmt_hours(a)}</td>
				<td style="padding:4px 10px;text-align:right;color:#888;">${p}%</td>
			</tr>`;
	}).join("") : `<tr><td colspan="3" style="padding:8px 10px;color:#aaa;font-style:italic;">No active team members yet — add rows below.</td></tr>`;

	field.$wrapper.html(`
		<div style="margin:6px 0 10px;padding:14px;background:#f8f9fa;border-radius:6px;border:1px solid #dde2e8;">
		  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;">
			<div style="flex:1;min-width:240px;">
				<div style="font-size:11px;color:#666;text-transform:uppercase;margin-bottom:2px;">Total Hours Needed</div>
				<div style="font-size:30px;font-weight:700;line-height:1;color:#2c3e50;">${fmt_hours(total)}</div>
				<div style="font-size:12px;color:#888;margin-top:4px;">From Sections B + C + D</div>
			</div>
			<div style="flex:1;min-width:240px;">
				<div style="font-size:11px;color:#666;text-transform:uppercase;margin-bottom:2px;">Allocated</div>
				<div style="font-size:30px;font-weight:700;line-height:1;color:${status_colour};">${fmt_hours(allocated)}</div>
				<div style="font-size:12px;color:${status_colour};font-weight:600;margin-top:4px;">${status_label}</div>
			</div>
			<div style="flex:2;min-width:280px;">
				<div style="font-size:11px;color:#666;text-transform:uppercase;margin-bottom:4px;">Coverage</div>
				<div style="background:#e0e6ed;border-radius:8px;height:18px;overflow:hidden;position:relative;">
					<div style="background:${status_colour};height:100%;width:${pct}%;transition:width 0.3s;"></div>
					<div style="position:absolute;top:0;left:0;width:100%;text-align:center;line-height:18px;font-size:11px;font-weight:600;color:#fff;text-shadow:0 0 2px rgba(0,0,0,0.4);">${pct}%</div>
				</div>
			</div>
		  </div>
		  <div style="display:flex;gap:16px;margin-top:14px;flex-wrap:wrap;">
			<div style="flex:1;min-width:280px;background:#fff;border:1px solid #e0e6ed;border-radius:4px;padding:8px;">
				<div style="font-size:11px;color:#666;text-transform:uppercase;padding:4px 10px;border-bottom:1px solid #eee;">Scope Breakdown</div>
				<table style="width:100%;border-collapse:collapse;font-size:13px;">${bucket_rows || '<tr><td style="padding:8px;color:#aaa;">No scope yet</td></tr>'}</table>
			</div>
			<div style="flex:1;min-width:280px;background:#fff;border:1px solid #e0e6ed;border-radius:4px;padding:8px;">
				<div style="font-size:11px;color:#666;text-transform:uppercase;padding:4px 10px;border-bottom:1px solid #eee;">Team Allocation</div>
				<table style="width:100%;border-collapse:collapse;font-size:13px;">${team_rows}</table>
			</div>
		  </div>
		</div>
	`);
}

function update_team_capacity(frm) {
	const field = frm.fields_dict && frm.fields_dict["team_capacity_html"];
	if (!field || !field.$wrapper) return;
	if (frm.is_new()) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Save the estimate to enable cross-estimate capacity checks.</p>");
		return;
	}
	if (!(frm.doc.team_members || []).length) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Add team members to see capacity check.</p>");
		return;
	}
	frappe.call({
		method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.check_team_capacity",
		args: { estimate_name: frm.doc.name },
	}).then(r => {
		if (r.message) field.$wrapper.html(r.message);
	}).catch(() => {});
}

function update_indirect_summary(frm) {
	const field = frm.fields_dict && frm.fields_dict["indirect_summary_html"];
	if (!field || !field.$wrapper) return;
	if (frm.is_new()) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Save first — then Actions → Load Indirect Costs from Books.</p>");
		return;
	}
	if (!(frm.doc.indirect_costs || []).length) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>No indirect costs loaded. Click Actions → Load Indirect Costs from Books.</p>");
		return;
	}
	frappe.call({
		method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.get_indirect_summary",
		args: { estimate_name: frm.doc.name },
	}).then(r => {
		if (r.message) field.$wrapper.html(r.message);
	}).catch(() => {});
}

function update_infrastructure_summary(frm) {
	const field = frm.fields_dict && frm.fields_dict["infrastructure_summary_html"];
	if (!field || !field.$wrapper) return;
	if (frm.is_new()) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Save first — then add infrastructure cost rows.</p>");
		return;
	}
	if (!(frm.doc.infrastructure_costs || []).length) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>No infrastructure costs added yet.</p>");
		return;
	}
	frappe.call({
		method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.get_infrastructure_summary",
		args: { estimate_name: frm.doc.name },
	}).then(r => {
		if (r.message) field.$wrapper.html(r.message);
	}).catch(() => {});
}

function recalc_team_cost(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "total_cost",
		Math.round((row.hourly_cost || 0) * (row.allocated_hours || 0) * 100) / 100);
	recalc_all_costs(frm);
}

// ─── Direct Cost Item ──────────────────────────────────────────────────────

frappe.ui.form.on("Direct Cost Item", {
	// Share-of-company helpers: when both are set, auto-derive monthly_cost.
	total_monthly_company_cost(frm, cdt, cdn) { recalc_direct_row(frm, cdt, cdn, true); },
	project_share_pct(frm, cdt, cdn)          { recalc_direct_row(frm, cdt, cdn, true); },
	// Direct inputs to the row total.
	monthly_cost(frm, cdt, cdn)               { recalc_direct_row(frm, cdt, cdn, false); },
	is_one_time(frm, cdt, cdn)                { recalc_direct_row(frm, cdt, cdn, false); },
	project_duration_months(frm, cdt, cdn)    { recalc_direct_row(frm, cdt, cdn, false); },
});

// Live row recompute. When `from_share` is true, the trigger came from a share
// helper field — we (re)derive monthly_cost from Total Monthly × Share %. When
// false, monthly_cost was edited directly and we leave it alone.
function recalc_direct_row(frm, cdt, cdn, from_share) {
	const row = locals[cdt][cdn];
	const t_co  = parseFloat(row.total_monthly_company_cost) || 0;
	const share = parseFloat(row.project_share_pct) || 0;

	if (from_share && t_co > 0 && share > 0) {
		const monthly = Math.round(t_co * share / 100 * 100) / 100;
		// Set monthly_cost via the model so the field re-renders and triggers downstream events.
		frappe.model.set_value(cdt, cdn, "monthly_cost", monthly);
		return;   // the monthly_cost change will re-fire this function with from_share=false
	}

	const row_dur = parseInt(row.project_duration_months, 10) || frm.doc.project_duration_months || 1;
	const monthly = parseFloat(row.monthly_cost) || 0;
	const total = row.is_one_time ? monthly : monthly * row_dur;
	frappe.model.set_value(cdt, cdn, "total_cost", Math.round(total * 100) / 100);
	recalc_all_costs(frm);
}

// ─── Indirect Cost Item ────────────────────────────────────────────────────

frappe.ui.form.on("Indirect Cost Item", {
	monthly_total_cost(frm, cdt, cdn)  { recalc_indirect_row(frm, cdt, cdn); },
	project_share_pct(frm, cdt, cdn)   { recalc_indirect_row(frm, cdt, cdn); },
	indirect_costs_remove(frm)         { recalc_all_costs(frm); },
});

function recalc_indirect_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const dur = frm.doc.project_duration_months || 1;
	const amt = (row.monthly_total_cost || 0) * ((row.project_share_pct || 0) / 100) * dur;
	frappe.model.set_value(cdt, cdn, "allocated_amount", Math.round(amt * 100) / 100);
	recalc_all_costs(frm);
}

// ─── Infrastructure Cost Item ──────────────────────────────────────────────

frappe.ui.form.on("Infrastructure Cost Item", {
	total_monthly_company_cost(frm, cdt, cdn) { recalc_infra_row(frm, cdt, cdn); },
	company_total_employees(frm, cdt, cdn)    { recalc_infra_row(frm, cdt, cdn); },
	project_team_size(frm, cdt, cdn)          { recalc_infra_row(frm, cdt, cdn); },
	project_duration_months(frm, cdt, cdn)    { recalc_infra_row(frm, cdt, cdn); },
	split_method(frm, cdt, cdn)               { recalc_infra_row(frm, cdt, cdn); },
	allocated_amount(frm)                     { recalc_all_costs(frm); },   // manual override
	infrastructure_costs_remove(frm)          { recalc_all_costs(frm); },
});

function recalc_infra_row(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const total = row.total_monthly_company_cost || 0;
	const dur   = row.project_duration_months || frm.doc.project_duration_months || 1;
	let amt = 0;
	const method = row.split_method || "Per Head";
	if (method === "Per Head" && (row.company_total_employees || 0) > 0) {
		amt = total / row.company_total_employees * (row.project_team_size || 0) * dur;
	} else if (method === "Fixed Amount") {
		amt = total * dur;
	} else {
		// Default fallback: per-head if numbers exist, else just monthly × duration
		amt = (row.company_total_employees || 0) > 0
			? total / row.company_total_employees * (row.project_team_size || 0) * dur
			: total * dur;
	}
	frappe.model.set_value(cdt, cdn, "allocated_amount", Math.round(amt * 100) / 100);
	recalc_all_costs(frm);
}

// ─── Aggregation helpers ───────────────────────────────────────────────────

function recalc_hour_totals(frm) {
	let mod_hrs = 0, cust_hrs = 0, int_hrs = 0;
	(frm.doc.module_selections || []).forEach(r => {
		if (r.is_included) mod_hrs += (r.total_module_hours || 0);
	});
	(frm.doc.custom_module_requests || []).forEach(r => { cust_hrs += (r.total_hours || 0); });
	(frm.doc.integration_requirements || []).forEach(r => { int_hrs += (r.final_hours || 0); });

	frm.set_value("total_modules_hours",       Math.round(mod_hrs * 10) / 10);
	frm.set_value("total_custom_modules_hours", Math.round(cust_hrs * 10) / 10);
	frm.set_value("total_integration_hours",   Math.round(int_hrs * 10) / 10);
	frm.set_value("grand_total_hours", Math.round((mod_hrs + cust_hrs + int_hrs) * 10) / 10);

	recalc_all_costs(frm);
}

function recalc_all_costs(frm) {
	// Team cost
	const active = (frm.doc.team_members || []).filter(r => r.is_active_in_current_version);
	let team_cost = 0, total_alloc = 0;
	active.forEach(r => {
		team_cost  += (r.total_cost || 0);
		total_alloc += (r.allocated_hours || 0);
	});

	const blended = total_alloc > 0 ? Math.round(team_cost / total_alloc * 100) / 100 : 0;

	// Duration — bottleneck-driven (matches the Python controller).
	// Use the longest individual workload to set the timeline; fall back to the
	// average if no allocations have been made yet.
	const team_size = active.length;
	const grand_hrs = frm.doc.grand_total_hours || 0;
	const MONTHLY_HOURS = 6 * 22;  // 132
	const loads = active.map(r => r.allocated_hours || 0);
	const max_load = loads.length ? Math.max(...loads) : 0;

	let dur = 1;
	if (max_load > 0) {
		const bottleneck_mo = max_load / MONTHLY_HOURS;
		const avg_mo_if_pooled = team_size > 0 ? (grand_hrs / (team_size * MONTHLY_HOURS)) : 0;
		dur = Math.max(Math.ceil(bottleneck_mo), Math.ceil(avg_mo_if_pooled), 1);
	} else if (team_size > 0 && grand_hrs > 0) {
		dur = Math.max(Math.ceil(grand_hrs / (team_size * MONTHLY_HOURS)), 1);
	}

	// Direct costs — respect per-row duration override (falls back to project dur)
	let direct_total = 0;
	(frm.doc.direct_costs || []).forEach(r => {
		const row_dur = parseInt(r.project_duration_months, 10) || dur;
		const t = r.is_one_time ? (r.monthly_cost || 0) : (r.monthly_cost || 0) * row_dur;
		direct_total += t;
	});

	// Indirect costs
	let indirect_total = 0;
	(frm.doc.indirect_costs || []).forEach(r => {
		indirect_total += (r.monthly_total_cost || 0) * ((r.project_share_pct || 0) / 100) * dur;
	});

	// Infra costs — sum of per-row allocated_amount (recomputed live by recalc_infra_row)
	let infra_total = 0;
	(frm.doc.infrastructure_costs || []).forEach(r => { infra_total += (r.allocated_amount || 0); });

	// Post Go-Live Support — folded into grand_total_cost so pricing sees it.
	const supp_hrs   = (frm.doc.monthly_support_hours || 0) * (frm.doc.support_duration_months || 0);
	const supp_rate  = frm.doc.support_hourly_rate || blended;
	const supp_cost  = Math.round(supp_hrs * supp_rate * 100) / 100;

	const grand_cost = Math.round((team_cost + direct_total + indirect_total + infra_total + supp_cost) * 100) / 100;

	frm.set_value("team_cost_total",          Math.round(team_cost * 100) / 100);
	frm.set_value("direct_cost_total",        Math.round(direct_total * 100) / 100);
	frm.set_value("indirect_cost_total",      Math.round(indirect_total * 100) / 100);
	frm.set_value("total_support_hours",         Math.round(supp_hrs * 10) / 10);
	frm.set_value("total_support_cost",          supp_cost);
	frm.set_value("support_cost_in_grand_total", supp_cost);   // Section K mirror
	frm.set_value("infrastructure_cost_total",   Math.round(infra_total * 100) / 100);
	frm.set_value("grand_total_cost",            grand_cost);
	frm.set_value("blended_hourly_rate",         blended);
	frm.set_value("project_duration_months",     dur);

	recalc_pricing(frm);

	// Refresh the dashboard-style summary widgets live so the user sees the new
	// indirect / infrastructure / scenario / sensitivity totals without saving.
	try { update_indirect_summary(frm); } catch (e) {}
	try { update_infrastructure_summary(frm); } catch (e) {}
	try { update_scenario_table(frm); } catch (e) {}
	try { update_sensitivity_table(frm); } catch (e) {}
}

function recalc_pricing(frm) {
	const cost = frm.doc.grand_total_cost || 0;
	if (!cost) return;
	const margin = frm.doc.target_margin_pct || 30;
	const floor   = Math.round(cost * 1.10);
	const std     = Math.round(margin < 100 ? cost / (1 - margin / 100) : cost * 2);
	const premium = Math.round(std * 1.25);

	let rec = std;
	if (frm.doc.recommended_band === "Conservative") rec = floor;
	else if (frm.doc.recommended_band === "Premium")  rec = premium;

	// Custom price override
	if (frm.doc.use_custom_price && (frm.doc.custom_price || 0) > 0) {
		rec = frm.doc.custom_price;
	}

	const margin_at = rec > 0 ? Math.round((rec - cost) / rec * 100 * 10) / 10 : 0;

	frm.set_value("floor_price",            floor);
	frm.set_value("standard_price",         std);
	frm.set_value("premium_price",          premium);
	frm.set_value("recommended_price",      rec);
	frm.set_value("margin_at_recommended",  margin_at);
	frm.set_value("price_per_hour", frm.doc.grand_total_hours ? Math.round(rec / frm.doc.grand_total_hours) : 0);
	frm.set_value("amc_suggested",  Math.round(rec * 0.15));

	// Break-even — support cost treated as a fixed reservation (subtract from price).
	const non_team = (frm.doc.direct_cost_total || 0) + (frm.doc.indirect_cost_total || 0) + (frm.doc.infrastructure_cost_total || 0) + (frm.doc.total_support_cost || 0);
	const blended = frm.doc.blended_hourly_rate || 0;
	if (blended > 0 && rec > 0) {
		const beh = Math.round((rec - non_team) / blended * 10) / 10;
		const bepct = frm.doc.grand_total_hours ? Math.round(beh / frm.doc.grand_total_hours * 1000) / 10 : 0;
		frm.set_value("break_even_hours", beh);
		frm.set_value("break_even_pct",   bepct);
		frm.set_value("break_even_note",
			`You break even if the team takes up to ${beh} hrs (${bepct}% of estimate). Beyond that, the project is at a loss.`);
	}

	update_scenario_table(frm);
	update_sensitivity_table(frm);
	update_custom_price_assessment(frm);
}

function recalc_all(frm) {
	recalc_hour_totals(frm);
}

// ─── Scenario Table ────────────────────────────────────────────────────────

function update_scenario_table(frm) {
	const field = frm.fields_dict && frm.fields_dict["scenario_table_html"];
	if (!field || !field.$wrapper) return;

	// Source numbers from Section K so Base row equals Grand Total Cost exactly.
	// Scaling team_cost_total (actual sum from Team Composition) by the multiplier,
	// not hours × blended — those can drift when team allocation differs from scope.
	const base_hrs        = frm.doc.grand_total_hours       || 0;
	const team_cost_total = frm.doc.team_cost_total         || 0;
	const non_team        = (frm.doc.direct_cost_total       || 0)
	                      + (frm.doc.indirect_cost_total     || 0)
	                      + (frm.doc.infrastructure_cost_total || 0)
	                      + (frm.doc.total_support_cost     || 0);   // include support
	const price      = frm.doc.recommended_price || 0;
	const custom_pct = ((frm.doc.scenario_custom_pct || 100) / 100);

	const scenarios = [
		{ label: "Optimistic", mult: 0.85, color: "#27ae60" },
		{ label: "Base",       mult: 1.00, color: "#2980b9" },
		{ label: "Pessimistic",mult: 1.30, color: "#e67e22" },
		{ label: `Custom (${frm.doc.scenario_custom_pct || 100}%)`, mult: custom_pct, color: "#8e44ad" },
	];

	const rows = scenarios.map(s => {
		const hrs   = Math.round(base_hrs * s.mult * 10) / 10;
		const tcost = Math.round(team_cost_total * s.mult);
		const tot   = Math.round(tcost + non_team);
		const profit= Math.round(price - tot);
		const margin= price > 0 ? Math.round(profit / price * 1000) / 10 : 0;
		const ok    = profit >= 0;
		return `
			<td style="text-align:right">${fmt_hours(hrs)}</td>
			<td style="text-align:right">${fmt_currency(tcost)}</td>
			<td style="text-align:right">${fmt_currency(tot)}</td>
			<td style="text-align:right;color:${ok ? "#27ae60":"#e74c3c"};font-weight:600">${fmt_currency(profit)}</td>
			<td style="text-align:right;color:${ok ? "#27ae60":"#e74c3c"};font-weight:600">${margin}%</td>
			<td style="text-align:center;font-weight:600">${ok ? "✅ Profit" : "❌ Loss"}</td>
		`;
	});

	const header = [
		["Scenario",     "left"],
		["Hours",        "right"],
		["Team Cost",    "right"],
		["Total Cost",   "right"],
		["Gross Profit", "right"],
		["Margin %",     "right"],
		["Status",       "center"],
	];
	const html = `
		<style>
			.scenario-tbl { width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; table-layout:fixed; }
			.scenario-tbl th { background:#2c3e50; color:#fff; padding:8px 12px; }
			.scenario-tbl td { padding:7px 12px; border-bottom:1px solid #eee; }
			.scenario-tbl tr:nth-child(even) { background:#f8f9fa; }
		</style>
		<table class="scenario-tbl">
			<thead><tr>${header.map(([h, a]) => `<th style="text-align:${a}">${h}</th>`).join("")}</tr></thead>
			<tbody>
				${scenarios.map((s, i) => `
					<tr>
						<td style="font-weight:600;color:${s.color};text-align:left">${s.label}</td>
						${rows[i]}
					</tr>
				`).join("")}
			</tbody>
		</table>
	`;

	field.$wrapper.html(html);
}

// ─── Sensitivity Table ─────────────────────────────────────────────────────
// For each of {hours, blended rate, duration, recommended price}, show what the
// net margin becomes if you flex JUST that variable by ±10/25/50%. Highlights
// which assumption matters most.

function update_sensitivity_table(frm) {
	const field = frm.fields_dict && frm.fields_dict["sensitivity_table_html"];
	if (!field || !field.$wrapper) return;

	const team_cost = frm.doc.team_cost_total         || 0;
	const direct    = frm.doc.direct_cost_total       || 0;
	const indirect  = frm.doc.indirect_cost_total     || 0;
	const infra     = frm.doc.infrastructure_cost_total || 0;
	const support   = frm.doc.total_support_cost      || 0;
	const price     = frm.doc.recommended_price       || 0;
	const non_team  = direct + indirect + infra + support;   // include support so base_cost == grand_total_cost
	const base_cost = team_cost + non_team;

	if (!price || !base_cost) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Fill team + costs + pricing to see sensitivity.</p>");
		return;
	}

	const flexes = [-50, -25, -10, 0, 10, 25, 50];
	const margin = (p, c) => (p > 0 ? (p - c) / p * 100 : 0);

	const rows = [
		{
			label: "Team cost (hours × rate)",
			tip:   "If team takes more/fewer hours OR blended rate shifts (a senior leaves, juniors fill in). Either flex multiplies team_cost the same way.",
			calc: (f) => margin(price, team_cost * (1 + f/100) + non_team),
		},
		{
			label: "Project duration",
			tip:   "If timeline extends/compresses (non-team costs scale with duration; team cost fixed by hours)",
			calc: (f) => margin(price, team_cost + non_team * (1 + f/100)),
		},
		{
			label: "Recommended price",
			tip:   "If client negotiates price up/down (cost stays the same)",
			calc: (f) => margin(price * (1 + f/100), base_cost),
		},
	];

	const colorize = (m) => {
		if (m >= 25)  return "#27ae60";  // strong green
		if (m >= 15)  return "#2ecc71";  // green
		if (m >= 0)   return "#f39c12";  // orange
		return "#e74c3c";                 // red
	};

	let html = `
		<style>
			.sens-tbl { width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }
			.sens-tbl th { background:#2c3e50; color:#fff; padding:8px 12px; text-align:center; }
			.sens-tbl td { padding:7px 12px; border-bottom:1px solid #eee; text-align:right; }
			.sens-tbl td.label { text-align:left; }
			.sens-tbl td.base  { background:#ecf0f1; font-weight:600; }
			.sens-tbl tr:nth-child(even) td:not(.base) { background:#f8f9fa; }
			.sens-tbl .tip { color:#888; font-weight:normal; font-size:11px; font-style:italic; }
		</style>
		<table class="sens-tbl">
			<thead><tr><th style="text-align:left;">Flex this →</th>
	`;
	flexes.forEach(f => {
		const cls  = f === 0 ? "base" : "";
		const sign = f > 0 ? "+" : "";
		const lbl  = f === 0 ? "Base" : `${sign}${f}%`;
		html += `<th class="${cls}">${lbl}</th>`;
	});
	html += `</tr></thead><tbody>`;

	rows.forEach(row => {
		html += `<tr><td class="label"><b>${row.label}</b><br/><span class="tip">${row.tip}</span></td>`;
		flexes.forEach(f => {
			const m   = row.calc(f);
			const cls = f === 0 ? "base" : "";
			const wt  = f === 0 ? 700 : 500;
			html += `<td class="${cls}" style="color:${colorize(m)};font-weight:${wt};">${m.toFixed(1)}%</td>`;
		});
		html += `</tr>`;
	});

	html += `
			</tbody>
		</table>
		<small style="color:#888;margin-top:6px;display:block;">
			Each cell = net margin % if you flex ONLY that variable. Compare row spreads — the variable with the widest swing is your biggest exposure.
			<span style="color:#27ae60;font-weight:600;">≥15% green</span>,
			<span style="color:#f39c12;font-weight:600;">0–15% orange</span>,
			<span style="color:#e74c3c;font-weight:600;">&lt;0% red</span>.
		</small>
	`;

	field.$wrapper.html(html);
}

// ─── Custom Price Assessment ───────────────────────────────────────────────
// When user ticks "Use Custom Price" and types a number, show where it sits
// relative to floor / standard / premium, and what margin it delivers.


function update_custom_price_assessment(frm) {
	const field = frm.fields_dict && frm.fields_dict["custom_price_assessment_html"];
	if (!field || !field.$wrapper) return;
	if (!frm.doc.use_custom_price) { field.$wrapper.html(""); return; }

	const cp      = parseFloat(frm.doc.custom_price) || 0;
	const cost    = parseFloat(frm.doc.grand_total_cost) || 0;
	const floor   = parseFloat(frm.doc.floor_price) || 0;
	const std     = parseFloat(frm.doc.standard_price) || 0;
	const premium = parseFloat(frm.doc.premium_price) || 0;

	if (!cp || !cost) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Type a custom price to see assessment.</p>");
		return;
	}

	const margin     = (cp - cost) / cp * 100;
	const vs_floor   = floor   > 0 ? (cp / floor   - 1) * 100 : 0;
	const vs_std     = std     > 0 ? (cp / std     - 1) * 100 : 0;
	const vs_premium = premium > 0 ? (cp / premium - 1) * 100 : 0;

	let banner;
	if (cp < cost) {
		banner = {bg: "#c0392b", icon: "🛑", title: "LOSS",
		          msg: `Custom price ${fmt_currency(cp)} is BELOW total cost ${fmt_currency(cost)}. You're losing ${fmt_currency(cost-cp)} per project.`};
	} else if (cp < floor) {
		banner = {bg: "#e74c3c", icon: "🔴", title: "DANGER",
		          msg: `Custom price ${fmt_currency(cp)} is BELOW floor ${fmt_currency(floor)}. Margin only ${margin.toFixed(1)}% — no buffer for overruns.`};
	} else if (cp < std) {
		banner = {bg: "#f39c12", icon: "⚠️", title: "BELOW TARGET",
		          msg: `Margin ${margin.toFixed(1)}% is under your target. Custom price is between floor and standard.`};
	} else if (cp <= premium) {
		banner = {bg: "#27ae60", icon: "✅", title: "HEALTHY",
		          msg: `Margin ${margin.toFixed(1)}%. Custom price sits between standard and premium — strong position.`};
	} else {
		banner = {bg: "#16a085", icon: "💎", title: "PREMIUM+",
		          msg: `Margin ${margin.toFixed(1)}%. Custom price is ABOVE premium — make sure scope/value justifies it.`};
	}

	const cmp = (pct) => {
		const c = pct >= 0 ? "#27ae60" : "#e74c3c";
		const s = pct >= 0 ? "+" : "";
		return `<span style="color:${c};font-weight:600;">${s}${pct.toFixed(1)}%</span>`;
	};

	field.$wrapper.html(`
		<div style="margin:6px 0;padding:10px;background:${banner.bg};color:white;border-radius:4px;">
			<b>${banner.icon} ${banner.title} — Margin ${margin.toFixed(1)}%</b>
			<div style="font-size:13px;margin-top:4px;">${banner.msg}</div>
		</div>
		<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:6px;">
			<tr style="border-bottom:1px solid #eee;">
				<td style="padding:4px 8px;color:#888;">Floor</td>
				<td style="padding:4px 8px;text-align:right;">${fmt_currency(floor)}</td>
				<td style="padding:4px 8px;text-align:right;">${cmp(vs_floor)}</td>
			</tr>
			<tr style="border-bottom:1px solid #eee;">
				<td style="padding:4px 8px;color:#888;">Standard</td>
				<td style="padding:4px 8px;text-align:right;">${fmt_currency(std)}</td>
				<td style="padding:4px 8px;text-align:right;">${cmp(vs_std)}</td>
			</tr>
			<tr style="border-bottom:1px solid #eee;">
				<td style="padding:4px 8px;color:#888;">Premium</td>
				<td style="padding:4px 8px;text-align:right;">${fmt_currency(premium)}</td>
				<td style="padding:4px 8px;text-align:right;">${cmp(vs_premium)}</td>
			</tr>
			<tr style="background:#ecf0f1;">
				<td style="padding:6px 8px;"><b>Custom Price</b></td>
				<td style="padding:6px 8px;text-align:right;"><b>${fmt_currency(cp)}</b></td>
				<td style="padding:6px 8px;text-align:right;color:#666;">→ ${margin.toFixed(1)}% margin</td>
			</tr>
		</table>
		<p style="font-size:11px;color:#888;margin-top:6px;">
			Scenarios, sensitivity & break-even already use this price. Re-run Monte Carlo (Section L) to refresh loss probability.
		</p>
	`);
}

function invalidate_monte_carlo(frm) {
	// When price changes, the previous Monte Carlo result is stale.
	const field = frm.fields_dict && frm.fields_dict["monte_carlo_html"];
	if (!field || !field.$wrapper) return;
	// Reset to the placeholder so user knows to re-run
	render_monte_carlo_placeholder(frm);
}

// ─── Monte Carlo ───────────────────────────────────────────────────────────
// On refresh we show a placeholder button. User clicks → server runs 1000 sims
// → results render with summary + histogram.

function render_monte_carlo_placeholder(frm) {
	const field = frm.fields_dict && frm.fields_dict["monte_carlo_html"];
	if (!field || !field.$wrapper) return;
	if (frm.is_new()) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Save the estimate first — Monte Carlo runs against the saved cost + price.</p>");
		return;
	}
	if (!frm.doc.recommended_price || !frm.doc.grand_total_cost) {
		field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Fill cost + price to enable Monte Carlo simulation.</p>");
		return;
	}
	field.$wrapper.html(`
		<div style="margin:8px 0;padding:12px;background:#f8f9fa;border-radius:4px;border:1px solid #ddd;">
			<b>Risk-adjusted Estimate</b>
			<p style="margin:6px 0 10px;color:#555;font-size:13px;">
				1000 Monte Carlo simulations using triangular distributions on hours (0.85×–1.30×),
				blended rate (0.95×–1.15×), and non-team cost (0.90×–1.25×).
				Returns P10 / P50 / P90 cost + probability of net loss.
			</p>
			<button class="btn btn-primary btn-sm" id="mc-run-btn">Run Monte Carlo (1000 sims)</button>
		</div>
	`);
	field.$wrapper.find("#mc-run-btn").on("click", () => run_monte_carlo(frm));
}

function run_monte_carlo(frm) {
	const field = frm.fields_dict["monte_carlo_html"];
	if (frm.is_new()) {
		field.$wrapper.html("<p style='color:#e74c3c;margin:8px 0;'>Save the estimate first.</p>");
		return;
	}
	field.$wrapper.html("<p style='color:#888;margin:8px 0;'>Running 1000 simulations…</p>");

	frappe.call({
		method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.run_monte_carlo",
		args: { estimate_name: frm.doc.name, n_runs: 1000 },
	}).then(r => {
		const d = r.message || {};
		if (d.error) {
			field.$wrapper.html(`<p style='color:#e74c3c;margin:8px 0;'>${d.error}</p>`);
			return;
		}
		field.$wrapper.html(build_monte_carlo_html(d));
		field.$wrapper.find("#mc-rerun-btn").on("click", () => run_monte_carlo(frm));
	}).catch((err) => {
		const msg = (err && err.message) || "see browser console";
		field.$wrapper.html(`<p style='color:#e74c3c;margin:8px 0;'>Monte Carlo failed: ${msg}</p>`);
	});
}

function fmt_inr(v) {
	if (v === null || v === undefined) return "—";
	const n = Math.abs(parseFloat(v));
	const sign = parseFloat(v) < 0 ? "−" : "";
	if (n >= 1e7) return `${sign}₹${(n/1e7).toFixed(2)}cr`;
	if (n >= 1e5) return `${sign}₹${(n/1e5).toFixed(2)}L`;
	if (n >= 1e3) return `${sign}₹${(n/1e3).toFixed(1)}k`;
	return `${sign}₹${n.toFixed(0)}`;
}

function build_monte_carlo_html(d) {
	const loss_color = d.prob_loss_pct >= 30 ? "#e74c3c"
	                 : d.prob_loss_pct >= 10 ? "#f39c12"
	                 : "#27ae60";
	const loss_label = d.prob_loss_pct >= 30 ? "HIGH RISK"
	                 : d.prob_loss_pct >= 10 ? "MODERATE RISK"
	                 : "LOW RISK";

	// Histogram — inline CSS bars
	const max_count = Math.max(...d.histogram, 1);
	let hist_rows = "";
	d.histogram.forEach((cnt, i) => {
		const centre = d.histogram_bins[i];
		const w = (cnt / max_count * 100).toFixed(0);
		const bar_color = centre >= 0 ? "#27ae60" : "#e74c3c";
		hist_rows += `
			<tr>
				<td style="padding:2px 8px;text-align:right;font-size:11px;color:#555;width:80px;">${fmt_inr(centre)}</td>
				<td style="padding:2px 0;">
					<div style="background:${bar_color};height:14px;width:${w}%;border-radius:2px;"></div>
				</td>
				<td style="padding:2px 6px;text-align:right;font-size:11px;color:#888;width:40px;">${cnt}</td>
			</tr>`;
	});

	return `
		<div style="margin:8px 0;">
			<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:stretch;">
				<!-- Probability of loss -->
				<div style="flex:1;min-width:220px;padding:14px;background:${loss_color};color:white;border-radius:6px;">
					<div style="font-size:11px;text-transform:uppercase;opacity:0.85;">Probability of Net Loss</div>
					<div style="font-size:36px;font-weight:700;margin-top:4px;line-height:1;">${d.prob_loss_pct}%</div>
					<div style="font-size:13px;margin-top:6px;opacity:0.95;">${loss_label} — out of ${d.n_runs} sims</div>
				</div>
				<!-- Cost distribution -->
				<div style="flex:2;min-width:300px;padding:14px;background:#ecf0f1;border-radius:6px;">
					<div style="font-size:12px;color:#666;font-weight:600;margin-bottom:6px;">Total Cost Distribution</div>
					<div style="display:flex;justify-content:space-between;font-size:13px;">
						<div><div style="color:#888;font-size:11px;">P10 (lucky)</div><b>${fmt_inr(d.cost_p10)}</b></div>
						<div><div style="color:#888;font-size:11px;">P50 (median)</div><b>${fmt_inr(d.cost_p50)}</b></div>
						<div><div style="color:#888;font-size:11px;">P90 (unlucky)</div><b>${fmt_inr(d.cost_p90)}</b></div>
					</div>
					<div style="margin-top:6px;padding-top:6px;border-top:1px solid #ccc;font-size:12px;color:#666;">
						Base (deterministic) cost: <b>${fmt_inr(d.base_cost)}</b> · Mean of sims: ${fmt_inr(d.cost_mean)}
					</div>
				</div>
				<!-- Profit distribution -->
				<div style="flex:2;min-width:300px;padding:14px;background:#ecf0f1;border-radius:6px;">
					<div style="font-size:12px;color:#666;font-weight:600;margin-bottom:6px;">Net Profit Distribution</div>
					<div style="display:flex;justify-content:space-between;font-size:13px;">
						<div><div style="color:#888;font-size:11px;">P10 (worst)</div><b style="color:${d.profit_p10<0?'#e74c3c':'#27ae60'}">${fmt_inr(d.profit_p10)}</b></div>
						<div><div style="color:#888;font-size:11px;">P50 (median)</div><b style="color:${d.profit_p50<0?'#e74c3c':'#27ae60'}">${fmt_inr(d.profit_p50)}</b></div>
						<div><div style="color:#888;font-size:11px;">P90 (best)</div><b style="color:${d.profit_p90<0?'#e74c3c':'#27ae60'}">${fmt_inr(d.profit_p90)}</b></div>
					</div>
					<div style="margin-top:6px;padding-top:6px;border-top:1px solid #ccc;font-size:12px;color:#666;">
						Base profit @ price ${fmt_inr(d.price)}: <b>${fmt_inr(d.base_profit)}</b>
					</div>
				</div>
			</div>

			<!-- Histogram -->
			<div style="margin-top:14px;padding:12px;background:#fff;border:1px solid #ddd;border-radius:6px;">
				<div style="font-weight:600;font-size:13px;margin-bottom:6px;">Profit Distribution (${d.n_runs} sims) — red = loss, green = profit</div>
				<table style="width:100%;border-collapse:collapse;">${hist_rows}</table>
			</div>

			<div style="margin-top:8px;display:flex;justify-content:space-between;align-items:center;">
				<small style="color:#888;">
					Hours flex 0.85×–1.30× · Rate flex 0.95×–1.15× · Non-team flex 0.90×–1.25×
				</small>
				<button class="btn btn-default btn-xs" id="mc-rerun-btn">Re-roll (new random seed)</button>
			</div>
		</div>
	`;
}

// ─── Linked project self-heal ──────────────────────────────────────────────
// Runs on every refresh. If the linked project was renamed via Frappe's standard
// rename action, the Link field updates automatically — nothing for us to do.
// If it was deleted (or renamed outside of Frappe), the server checks the Project's
// `notes` for the recovery tag we wrote at creation and either re-links or clears
// the pointer. Reload the form so the Create Project button reappears when needed.
const _verify_link_seen = new Set();
function verify_linked_project(frm) {
	if (frm.is_new() || !frm.doc.linked_project) return;
	const key = `${frm.doc.name}::${frm.doc.linked_project}`;
	if (_verify_link_seen.has(key)) return;  // already checked this combo this session
	_verify_link_seen.add(key);

	frappe.call({
		method: "tbo_analytics.tbo_analytics.doctype.implementation_estimate.implementation_estimate.verify_or_relink_project",
		args: { estimate_name: frm.doc.name },
	}).then(r => {
		const out = r.message || {};
		if (out.status === "renamed") {
			frappe.show_alert({
				message: __(`Linked project updated to ${out.linked_project} (original was renamed/deleted).`),
				indicator: "blue",
			}, 8);
			frm.reload_doc();
		} else if (out.status === "missing") {
			frappe.show_alert({
				message: __("Linked project no longer exists — link cleared. Use Create Project to make a new one."),
				indicator: "orange",
			}, 10);
			frm.reload_doc();
		}
	}).catch(() => {});
}

// ─── Custom Buttons ─────────────────────────────────────────────────────────

function load_all_overheads_from_books(frm) {
	// Pulls INDIRECT + INFRASTRUCTURE only. Direct Cost is fully manual now —
	// the COGS account aggregates all projects' direct spend, so allocating a
	// share of it to a new estimate would double-charge past clients. Use the
	// quick-add buttons above the Direct Cost table to add project-specific
	// direct rows yourself (Frappe Cloud, Claude AI, etc.).
	//
	// Behaviour for indirect + infra:
	// - Manual rows you added are NEVER touched. The pull only appends.
	// - Pulled rows are deduped by `cost_item` against what's already in the table
	//   so re-clicking the button doesn't create duplicates.
	// - To remove a pulled row, delete it manually. Re-clicking the button will
	//   re-add it. Easier workaround: set its driver to Fixed Pct with 0%.
	const company = frm.doc.company || frappe.defaults.get_user_default("Company");
	if (!company) {
		frappe.msgprint(__("No company found. Set a default company first."));
		return;
	}
	const fields = [
		{ label: __("Lookback (months)"), fieldname: "lookback_months", fieldtype: "Select",
		  options: "3\n6\n12", default: "6",
		  description: __("Pulls Indirect (GL non-salary lines + HR/Accounts/Sales-BD salary roll-up from Employee.ctc) + Infrastructure. Direct Cost is manual — add rows yourself above. Rows already in the table are never overwritten.") },
	];
	frappe.prompt(fields, (vals) => {
		frappe.call({
			method: "tbo_analytics.tbo_analytics.cost_allocator.pull_all_overhead",
			args: { company: company, lookback_months: vals.lookback_months },
			freeze: true,
			freeze_message: __("Pulling indirect (GL + overhead salaries) + infrastructure…"),
		}).then((r) => {
			const data  = r.message || {};
			const indir = (data.indirect || {}).rows || [];
			const infra = (data.infra    || {}).rows || [];

			if (!indir.length && !infra.length) {
				frappe.msgprint(__("No qualifying GL entries found in the lookback window."));
				return;
			}

			// Dedup helper: case-insensitive, trimmed cost_item match.
			const norm = s => (s || "").toString().trim().toLowerCase();
			const existing = (table) => new Set((frm.doc[table] || []).map(r => norm(r.cost_item)));
			const dedup = (rows, table) => {
				const have = existing(table);
				const added = [], skipped = [];
				for (const row of rows) {
					if (have.has(norm(row.cost_item))) {
						skipped.push(row.cost_item);
					} else {
						frm.add_child(table, row);
						added.push(row.cost_item);
						have.add(norm(row.cost_item));
					}
				}
				return { added, skipped };
			};

			const iRes = dedup(indir, "indirect_costs");
			const fRes = dedup(infra, "infrastructure_costs");

			frm.refresh_field("indirect_costs");
			frm.refresh_field("infrastructure_costs");

			const total_added   = iRes.added.length   + fRes.added.length;
			const total_skipped = iRes.skipped.length + fRes.skipped.length;
			const msg = total_skipped > 0
				? `Added ${total_added} new line(s). Skipped ${total_skipped} already in the table.`
				: `Added ${total_added} line(s) (${iRes.added.length} indirect + ${fRes.added.length} infra). All in INR.`;
			frappe.show_alert({ message: __(msg), indicator: total_added > 0 ? "green" : "blue" }, 7);

			if (total_added === 0) return;
			frm.dirty();
			frm.save().then(() => {
				update_indirect_summary(frm);
				update_infrastructure_summary(frm);
			});
		});
	}, __("Load Overheads from Books"), __("Load"));
}

function setup_custom_buttons(frm) {
	// ── Always-available buttons (work on new + saved estimates) ──

	// One button that pulls shared-direct + indirect + infrastructure in a single
	// round-trip. Replaces the prior three-button set. All values in INR (company base).
	frm.add_custom_button(__("Load Overheads from Books"), () => {
		load_all_overheads_from_books(frm);
	}, __("Actions"));

	// "Recalculate AI Estimates" — frm.save() works for both new and saved docs.
	frm.add_custom_button(__("Recalculate AI Estimates"), () => {
		frappe.confirm(
			"This will re-run the AI estimation engine and update all AI-estimated hour fields. Continue?",
			() => frm.save()
		);
	}, __("Actions"));

	// ── Saved-doc-only buttons (need a persisted doc / workflow state) ──
	if (frm.is_new()) return;

	// "Create Project" — explicit trigger for the Won → Project workflow.
	// The same call runs automatically on status change, but exposing it as a button
	// lets the user retry on failure and see errors instead of them being swallowed.
	if (frm.doc.status === "Won" && !frm.doc.linked_project) {
		frm.add_custom_button(__("Create Project"), () => {
			// Open a pre-filled new Project form. The back-link Custom Field
			// (custom_implementation_estimate) carries the estimate name through to
			// after_insert, which mirrors the link back to this estimate once the
			// user saves. No silent server insert — the user reviews everything first.
			const default_name = `${frm.doc.client_name || ""} — ERPNext Implementation (${frm.doc.name})`;
			const est_name = frm.doc.name;
			frappe.new_doc("Project", {
				project_name:                    default_name,
				customer:                        frm.doc.client_name,
				expected_start_date:             frappe.datetime.get_today(),
				expected_end_date:               frm.doc.expected_go_live,
				estimated_costing:               frm.doc.recommended_price,
				notes:                           `Created from Implementation Estimate ${est_name}`,
				custom_implementation_estimate:  est_name,
			});
			// Belt-and-braces: re-apply the back-link after the form has loaded.
			// Defends against the case where Project's doctype-meta cache is stale
			// (e.g., no bench restart since Custom Field install) and Frappe silently
			// drops unknown fields from the new_doc payload.
			setTimeout(() => {
				if (cur_frm && cur_frm.doc && cur_frm.doc.doctype === "Project"
				    && cur_frm.is_new()
				    && !cur_frm.doc.custom_implementation_estimate) {
					try { cur_frm.set_value("custom_implementation_estimate", est_name); } catch (e) {}
				}
			}, 600);
		}, __("Actions")).addClass("btn-primary");
	}

	// "Open Linked Project" — quick navigation once project exists.
	if (frm.doc.linked_project) {
		frm.add_custom_button(__("Open Linked Project"), () => {
			frappe.set_route("Form", "Project", frm.doc.linked_project);
		}, __("Actions"));
	}

	// Workflow transitions are driven exclusively by Frappe's built-in workflow
	// action button (top-right of the form). That button respects the role
	// restrictions defined in fixtures/workflow.json — Projects Manager sees
	// Submit for Review / Resubmit; Project Approver sees Approve / Request
	// Revision / Mark Won / Mark Lost / Put on Hold / Resume. We deliberately
	// don't add JS shortcuts here because they'd bypass the role check.
}

// ─── Quick-add Direct Cost Buttons ─────────────────────────────────────────

function add_quick_add_direct_costs(frm) {
	const field = frm.fields_dict && frm.fields_dict["direct_costs"];
	if (!field || !field.$wrapper) return;
	const presets = [
		{ cost_item: "Frappe Cloud Hosting", category: "Hosting", monthly_cost: 5000 },
		{ cost_item: "Claude AI API",         category: "Third-party API", monthly_cost: 2000 },
		{ cost_item: "SMS Gateway",           category: "Third-party API", monthly_cost: 500 },
		{ cost_item: "WhatsApp API",          category: "Third-party API", monthly_cost: 1500 },
		{ cost_item: "Domain & SSL",          category: "Hosting", monthly_cost: 200, is_one_time: 1 },
	];

	const $field = field.$wrapper;
	if ($field.find(".quick-add-btns").length) return;

	const $div = $(`<div class="quick-add-btns" style="margin:6px 0 2px;display:flex;flex-wrap:wrap;gap:6px;"></div>`);
	presets.forEach(p => {
		const $btn = $(`<button class="btn btn-xs btn-default">${p.cost_item}</button>`);
		$btn.on("click", () => {
			const row = frm.add_child("direct_costs", p);
			frm.refresh_field("direct_costs");
		});
		$div.append($btn);
	});
	$field.prepend($div);
}

// ─── Field descriptions ────────────────────────────────────────────────────

function set_field_descriptions(frm) {
	frm.set_df_property("grand_total_hours",    "description", "Sum of all module + custom module + integration hours");
	frm.set_df_property("project_duration_months","description", "Auto-calculated (bottleneck): max(employee allocated_hours) ÷ 132 hrs/month. Whoever has the most work sets the timeline.");
	frm.set_df_property("blended_hourly_rate",  "description", "Weighted average cost per hour across all active team members");
	frm.set_df_property("floor_price",          "description", "Grand Total Cost × 1.10 — absolute minimum");
	frm.set_df_property("standard_price",       "description", `Grand Total Cost ÷ (1 − Margin %)`);
	frm.set_df_property("amc_suggested",        "description", "Standard 15% of Recommended Price per year");
	frm.set_df_property("scenario_custom_pct",  "description", "Enter any % to model custom scenarios (e.g. 150 = team takes 1.5× estimated hours)");
}

// ─── CSS for complex rows ──────────────────────────────────────────────────

if (!document.getElementById("tbo-complex-row-style")) {
	const style = document.createElement("style");
	style.id = "tbo-complex-row-style";
	style.textContent = ".complex-row { background: #fff9e6 !important; }";
	document.head.appendChild(style);
}
