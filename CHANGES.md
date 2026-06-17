# tbo_analytics — Change Log & Open Items

Date: 2026-06-01
Scope: post-audit of `guide.md` vs current build, bug fixes, and permission relaxation.

---

## 1. What was audited

The spec in [guide.md](guide.md) was checked against the actual build under [tbo_analytics/](tbo_analytics/). Roughly 95% of the spec is implemented:

- All 12 DocTypes (master + 11 children) — present
- Main controller [implementation_estimate.py](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py) — AI estimation, costs, pricing, scenarios, break-even, team-version snapshot
- Server handlers [handlers.py](tbo_analytics/tbo_analytics/handlers.py) — before_save / on_submit / on_update_after_submit / Won → Project+Tasks+SO
- Scheduled jobs [tasks.py](tbo_analytics/tbo_analytics/tasks.py) — historical averages, time-coverage cache
- Client script [implementation_estimate.js](tbo_analytics/public/js/implementation_estimate.js) — recalc, scenario table, quick-add, status buttons
- 6 reports (py + js + json)
- Workflow fixture, Dashboard + Dashboard Chart fixtures
- Bootstrap script [bootstrap_doctypes.py](bootstrap_doctypes.py)
- Hooks correctly registered (`doc_events`, `scheduler_events`, `doctype_js`, `fixtures`)

---

## 2. Bugs fixed

| # | Severity | File | Fix |
|---|---|---|---|
| 1 | Migration would crash | [fixtures/dashboard.json](tbo_analytics/fixtures/dashboard.json) | Dashboard referenced chart `"Won Estimates - Margin Distribution"` that doesn't exist. Repointed to the existing `"Won Estimates - Revenue by Client"`. |
| 2 | Workflow editors wrong (later opened up — see §3) | [fixtures/workflow.json](tbo_analytics/fixtures/workflow.json) | Several states had `allow_edit: System Manager` where spec required Sales Manager. |
| 3 | Silent dead code | [public/js/implementation_estimate.js:61-73](tbo_analytics/public/js/implementation_estimate.js#L61-L73) | `complexity` handler used `frappe.ui.form.on` (a registry fn) as a truthy guard then called a nonexistent `frappe.ui.form.trigger(...)`. AI hours never recalculated when complexity flipped 1↔2. Extracted [`recompute_module_ai_hours()`](tbo_analytics/public/js/implementation_estimate.js#L102-L117) called by both `module` and `complexity` handlers. Also now picks `base_hours_complexity_2` for C2 when no historical avg (was always falling back to C1). |
| 4 | Wrong formula | [report/time_coverage_tracker/time_coverage_tracker.py:53-72](tbo_analytics/tbo_analytics/report/time_coverage_tracker/time_coverage_tracker.py#L53-L72) | `daily_burn = actual / date_diff(today, est_end_date)` divided by *days remaining*, not days *since project start*. Future end dates produced negative/garbage projections. Now uses `start_date` (or `creation` date as fallback). |
| 5 | SQL injection | reports below | F-string `WHERE` clauses with user filters → parameterized with `%(name)s`. |
|   |   | [ai_vs_leader_estimate.py](tbo_analytics/tbo_analytics/report/ai_vs_leader_estimate/ai_vs_leader_estimate.py) |   |
|   |   | [profitability_scenarios.py](tbo_analytics/tbo_analytics/report/profitability_scenarios/profitability_scenarios.py) |   |
|   |   | [time_coverage_tracker.py](tbo_analytics/tbo_analytics/report/time_coverage_tracker/time_coverage_tracker.py) |   |
| 6 | Wrong API signature | [handlers.py:151](tbo_analytics/tbo_analytics/handlers.py#L151) | `frappe.publish_realtime("msgprint", msg, user=user)` — positional args didn't match the API. Now uses `event=` / `message=` kwargs so Won-status notifications actually fire. |
| 7 | Dead code | [public/js/implementation_estimate.js:412-420](tbo_analytics/public/js/implementation_estimate.js#L412-L420) | "Save Team as Version" button fired `get_scenario_data` and discarded the result before the real call. Removed. |

---

## 3. Permissions opened up

Per request: every authenticated user gets full access via the built-in `All` role. Role-specific gating will be applied later.

- [Implementation Estimate](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.json) — `All` gets create/read/write/delete/submit/cancel/amend/share/print/export. `System Manager` kept for admin clarity.
- [Workflow](tbo_analytics/fixtures/workflow.json) — every state's `allow_edit` and every transition's `allowed` set to `All`.
- All 6 reports — single `All` role.
- Masters ([ERP Module Master](tbo_analytics/tbo_analytics/doctype/erp_module_master/erp_module_master.json), [Integration Type Master](tbo_analytics/tbo_analytics/doctype/integration_type_master/integration_type_master.json), [Rate Card](tbo_analytics/tbo_analytics/doctype/rate_card/rate_card.json)) — `All` upgraded from read-only to full CRUD.

To re-tighten later, the original role mapping is documented in [guide.md §14](guide.md).

---

## 4. To apply these changes

```
bench --site erp.hydrotech migrate
bench --site erp.hydrotech clear-cache
bench restart   # or `bench start` in dev
```

---

## 5. Spec items not yet built

These are in [guide.md](guide.md) but missing from the codebase — pure additions, not bugs.

### 5.1 Project Health dashboard (spec §11, Dashboard 2)

Spec calls for 6 charts (time coverage heatmap, at-risk projects, team utilisation, estimate-vs-actual trend, AI-vs-leader accuracy, cost overrun tracker). Only Dashboard 1 ("Implementation Overview") exists.

Effort: 1–2 hours. Wire as another entry in [fixtures/dashboard.json](tbo_analytics/fixtures/dashboard.json) with new chart definitions in [fixtures/dashboard_chart.json](tbo_analytics/fixtures/dashboard_chart.json).

### 5.2 Custom fields on `Task` and `Project`

Code expects these for the closed-loop estimation feedback, but no Custom Field DocType records are provisioned:

- `Task.custom_module_tag` — used by [tasks.py:34](tbo_analytics/tbo_analytics/tasks.py#L34) for historical averaging and by [handlers.py:72](tbo_analytics/tbo_analytics/handlers.py#L72) when auto-creating tasks
- `Project.custom_actual_hours_logged` — used by [handlers.py:183](tbo_analytics/tbo_analytics/handlers.py#L183) and [tasks.py:73](tbo_analytics/tbo_analytics/tasks.py#L73)

The code is defensive (`if frappe.db.has_column(...)`) so nothing crashes, but the features silently no-op until the fields are created. Two options:

1. Add a `Custom Field` fixture for both — auto-installs on `bench migrate`.
2. Document them as manual setup steps.

### 5.3 Status-change email notifications (spec §9)

Auto-project creation works ([handlers.py:49](tbo_analytics/tbo_analytics/handlers.py#L49)), but email notifications on status transitions aren't wired. Frappe Notification DocType fixtures would handle this declaratively.

### 5.4 Inline revision comparison HTML widget (spec §8.5)

Spec shows a small V1-vs-V2 cost-diff widget rendered below the team_revisions table. Currently you only get the Team Revision Comparison *report* — no on-form widget.

### 5.5 "Go-live feasibility" warning (spec §12, item 5)

A client-script warning when `expected_go_live` is sooner than `project_duration_months` would allow. Not implemented in [implementation_estimate.js](tbo_analytics/public/js/implementation_estimate.js).

---

## 6. Smaller follow-ups (cosmetic / hygiene)

- [implementation_estimate.json:89](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.json#L89) — `naming_series` options has a trailing `\n` which adds a blank dropdown entry.
- DocField JSONs use a `"placeholder"` key on Float fields (e.g. `ai_estimated_hours`). Frappe doesn't honour this in JSON schema — placeholder text is silently dropped. The spec wants `"Auto-calculated"` to render in-grid; this needs to be set via JS using `grid.fields_map[fieldname].df.placeholder` in the form `refresh`. The currently-unused helper `set_ai_field_placeholders()` mentioned in the spec was never implemented.
- [handlers.py:10](tbo_analytics/tbo_analytics/handlers.py#L10) — `now_datetime` import is unused.
- [bootstrap_doctypes.py](bootstrap_doctypes.py) — works as a one-time setup tool but isn't discoverable. Either delete (since `bench migrate` does the same job now that fixtures are wired) or add a header comment explaining when to run it.
- [implementation_estimate.js:277-278](tbo_analytics/public/js/implementation_estimate.js#L277-L278) — client-side aggregation sums `r.allocated_amount` for infra rows but never sets `infrastructure_cost_total`; that field stays whatever the server last computed. Causes a brief drift between client/server until next save. Minor.

---

## 7. Recommended next step

If the immediate goal is to put the app in front of users:

1. Provision the two custom fields (5.2) — they unlock historical-average feedback, which is the entire point of the AI estimation getting smarter over time.
2. Project Health dashboard (5.1) — second-most-used view per the spec.

5.2 is the only one that materially affects whether the system works as designed; everything else is polish.
