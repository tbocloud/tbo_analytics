# `tbo_analytics` — Production Roadmap

**From pre-sales estimator to full project lifecycle intelligence platform.**

This document maps the business problems TBO faces across the full life of a project — from the first enquiry to the post-mortem — and proposes a concrete Frappe implementation to close the loop. Read this when you want to know what to build next, why it matters in business terms, and how to build it in Frappe.

> **Today** the app is strong on **one stage**: pre-sales estimation. After a deal moves to Won, the app goes dark.
>
> **Tomorrow** the app should be strong on **six stages**: lead pipeline, estimation, negotiation, execution, completion, and post-mortem learning. Each stage produces signal that feeds the next.

Companion to: [FIELDS.md](FIELDS.md), [USAGE.md](USAGE.md), [COST_ESTIMATION_IDEAS.md](COST_ESTIMATION_IDEAS.md), [INDIRECT_COST_ALLOCATION.md](INDIRECT_COST_ALLOCATION.md), [PRICING_FLOW_ANALYSIS.md](PRICING_FLOW_ANALYSIS.md), [CHANGES.md](CHANGES.md). This doc is the umbrella; those are detail dives on specific themes.

---

# Part A — Strategic Framing

## 1. Executive Summary

| Today | Tomorrow |
|---|---|
| One DocType (Implementation Estimate) does great pre-sales math. | A lifecycle platform: Lead → Estimate → Project In Flight → Closure → Lessons → Better next estimate. |
| 6 reports, 1 dashboard, all centred on the Estimate. | 8 new reports, 2 new dashboards covering pipeline, project health, profitability, resource utilisation. |
| `custom_module_tag` and `custom_actual_hours_logged` referenced defensively in code but **not actually provisioned**, so feedback loops silently no-op. | Custom fields installed via fixture; the existing weekly historical-average job and the two estimate-vs-actual reports start producing real data on day one. |
| Sales Order created on Won but never confirmed, never linked back to invoices, never closed. | Project status workflow drives invoicing, profitability snapshotting, and lessons capture at the right moments. |
| Capacity check is per-estimate only. | Cross-project resource heat-map shows who's over-allocated this quarter at a portfolio level. |

**The one-line thesis:** every project produces data. The current app captures none of it after Won. Capture it, feed it back to the estimator, and within 6 months estimates become measurably more accurate. The technical work is mostly DocType schema, hooks, and reports — not net-new algorithms.

**The expected business value at each stage:**

| Stage | Business value of fixing it |
|---|---|
| Lead/Pipeline | Forecast revenue 1 quarter out, spot dry pipeline before it hurts payroll. |
| Estimation | Already strong; sharpens further when feedback loop closes. |
| Negotiation | Win/loss analytics tell you which price bands actually close. |
| Execution | Catch over-runs in week 1 instead of month 3. Reduce schedule slips by 30-50%. |
| Completion | Real profitability per project + per customer; defensible margin reporting to leadership. |
| Post-mortem | Every project makes the next one cheaper to estimate. Compounding accuracy. |

---

## 2. The Project Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                       │
│  ① LEAD            ② ESTIMATION      ③ NEGOTIATION    ④ EXECUTION                    │
│  ┌──────┐         ┌──────────┐      ┌─────────┐      ┌────────────┐                  │
│  │ Lead │  ───→   │ Estimate │ ───→ │ Quote   │ ───→ │ Project    │                  │
│  │ /    │  qual.  │ Draft →  │ rev. │ Sent →  │ Won  │ In Flight  │  ───→            │
│  │ Enq. │         │ Approved │      │ Won     │      │            │                  │
│  └──────┘         └──────────┘      └─────────┘      └────────────┘                  │
│      │                 │                  │               │                          │
│      │                 │                  │               ▼                          │
│      │                 │                  │           ⑤ COMPLETION                  │
│      │                 │                  │           ┌────────────┐                 │
│      │                 │                  │           │ Delivery + │                 │
│      │                 │                  │           │ Invoicing  │  ───→           │
│      │                 │                  │           └────────────┘                 │
│      │                 │                  │                  │                       │
│      ▼                 ▼                  ▼                  ▼                       │
│  ⑥ LEARNING — every signal here feeds back into estimating the next deal             │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Stage definitions

| # | Stage | Doctype today | Frappe gap |
|---|---|---|---|
| **①** | **Lead / Pipeline** | (none in tbo_analytics) | A Lead-to-Estimate qualification step doesn't exist. If you use Frappe CRM, it's not bridged. |
| **②** | **Estimation** | Implementation Estimate (Draft, Under Review, Revision Requested) | **Strong**. Cost model, pricing, scenarios, sensitivity, Monte Carlo, capacity check all live. |
| **③** | **Negotiation & Win** | Implementation Estimate (Approved, Won) | Custom price field exists. Win/Loss reasons not captured. Sales Order created but stays Draft. |
| **④** | **Project In Flight** | ERPNext Project + Tasks (linked but untracked) | **Major gap.** No status workflow on Project, no in-flight health snapshot, no risk alerts. |
| **⑤** | **Completion** | (Project marked Completed manually) | **Major gap.** No closure form, no profitability snapshot, no link from Sales Invoice back to project review. |
| **⑥** | **Post-mortem & Learning** | Weekly `update_historical_averages()` only | **Major gap.** Numerical feedback only; no causal capture ("why did this overrun?"). |

### The data flow

Today (linear, one-shot):
```
Modules → Cost → Price → Won → Project created → ☠ (silence)
```

Target (closed loop):
```
Modules → Cost → Price → Won → Project In Flight → Completion Review → Lessons
   ↑                                                                       │
   └───────────── feeds back to historical_avg + reasons ←─────────────────┘
```

The closure → feedback step is the single biggest missing arrow.

---

## 3. Business Problems by Stage

For each stage, the problems are framed as **real pain stories** — user role, frequency, business cost.

### Stage ① — Lead / Pipeline

| Problem | Who hurts | How often | Cost |
|---|---|---|---|
| Pre-sales has no visibility into how many leads are in flight at each stage. They prioritise by gut feel. | Pre-sales Lead | Daily | Misallocated effort; deals slip through cracks. |
| Leadership can't forecast revenue 3 months out. They guess. | Sales Manager / Founders | Monthly | Bad hiring decisions, cash flow surprises. |
| The win rate is not known by customer segment, project type, or band. | Sales Manager | Quarterly | Pricing decisions made without data; lose deals on price when value would have closed them. |
| No clear "average deal cycle time" → can't promise clients realistic timelines from enquiry. | Pre-sales | Per deal | Over-promised start dates, eroded trust. |

### Stage ② — Estimation

| Problem | Who hurts | How often | Cost |
|---|---|---|---|
| Junior pre-sales staff don't know what a "complex" module looks like. Estimates vary wildly between people for the same scope. | Pre-sales Lead | Weekly | Inconsistent quotes; loss of credibility with repeat clients. |
| "AI estimate" uses base hours from ERP Module Master that nobody has reviewed in 12 months. | All pre-sales | Every estimate | Systematic over/under-estimation on certain module types. |
| When the client asks "why this number?" pre-sales can't show the breakdown of how much is hosting vs labour vs overhead. | Pre-sales | Per quote conversation | Loss of pricing power; client haggles on the wrong line items. |
| Custom-price negotiation lacks an assessment for the **band path** (only custom-price has the LOSS/DANGER/HEALTHY widget today). | Sales Manager | Per negotiated deal | See [PRICING_FLOW_ANALYSIS.md](PRICING_FLOW_ANALYSIS.md). |

### Stage ③ — Negotiation & Win

| Problem | Who hurts | How often | Cost |
|---|---|---|---|
| The reason a deal was Lost isn't recorded. Was it price? Timeline? Scope? Competitor? | Sales Manager | Per lost deal | No corrective action possible; same mistake repeats. |
| Won deals at Floor price aren't flagged for leadership oversight. They should be — they're the riskiest deals. | Sales Manager | Per low-margin win | Bad deals slip through. |
| The Sales Order created on Won is left in Draft forever. The client is told a price but no SO is ever confirmed. | Accounts | Per won deal | Invoicing delays; revenue recognition confusion. |
| FX rate snapshot is taken at estimate time but currency moves before invoice. No FX P&L attribution. | Finance | Per foreign-currency deal | Margin erosion silently absorbed by company. |

### Stage ④ — Execution (Project In Flight)

| Problem | Who hurts | How often | Cost |
|---|---|---|---|
| **PMs only know a project is overrunning when it's already 50% over.** No early signal. | Project Manager | Per project | Schedule slips become irrecoverable; client communication late and reactive. |
| Burn rate (hours logged ÷ days elapsed) not computed automatically per project. | PM, Delivery Head | Weekly | PMs spend half a day each Monday in spreadsheets. |
| When a module's actuals exceed estimate by 30%, nobody flags it until the variance report runs (if it runs). | PM | Per overrun module | Estimating gets less accurate over time, not more. |
| Scope changes mid-project ("the client also wants WhatsApp integration") aren't tracked anywhere structured. | PM, Pre-sales | 2-3× per project | Effective margin collapses silently; no change-order conversation with client. |
| Resource over-allocation across projects isn't visible. The capacity check works per-estimate only. | Delivery Head | Quarterly | Star employees burn out; junior staff sit idle. |

### Stage ⑤ — Completion

| Problem | Who hurts | How often | Cost |
|---|---|---|---|
| When a project finishes, no closure form is filled. The Project record sits in "Open" forever. | PM | Every project | Backlog of zombie projects clutters dashboards; metrics polluted. |
| **No profitability snapshot at delivery.** Recommended price was X; what did the project actually cost? Nobody runs the report. | Finance, Founders | Per completed project | Leadership runs on a feeling, not data. Can't tell which segments are actually profitable. |
| Sales Invoice generation is manual and disconnected from project state. | Accounts | Per invoice | Days-Sales-Outstanding creeps up; client follow-ups slip. |
| AMC contracts ("Suggested AMC = 18% of recommended_price") aren't actually created. The system suggests it but never books it. | Sales | Per Won deal | Recurring revenue invisible; renewal conversations forgotten. |

### Stage ⑥ — Post-mortem & Learning

| Problem | Who hurts | How often | Cost |
|---|---|---|---|
| The weekly `update_historical_averages()` job updates a number but nobody knows what happened in those projects to produce that number. | Estimating team | Weekly | Numerical feedback without causal feedback = slow improvement. |
| "Why did the Hydrotech project overrun by 40%?" — nobody captured the reason at the time. Now it's lost. | PM, Pre-sales Lead | Per significant variance | No institutional memory; same mistake repeats with the next client. |
| Lessons from finished projects aren't reusable. A new pre-sales person can't say "show me how we estimated similar healthcare verticals." | Pre-sales Lead | Per new project | Knowledge stays in heads of senior staff; bottleneck. |
| Estimate accuracy trend isn't visible. Are we getting better? Worse? In which areas? | Founders | Quarterly | Capital allocation decisions made on hunch. |

---

## 4. Capability Themes (the solution map)

Nine themes, each addressing a slice of the lifecycle. Two columns are key: **business value** (why) and **lifecycle stages** (where it lands).

| # | Theme | Business value | Stages |
|---|---|---|---|
| **A** | **Pipeline & funnel forecasting** | Predict bookings 1–3 months out. Spot dry pipeline before it hurts payroll. | ①, ② |
| **B** | **Estimate accuracy calibration** | Close the learning loop. Every completed project makes the next one's estimate sharper. | ②, ⑥ |
| **C** | **Project health monitoring** | Detect over-runs in week 1 not month 3. Burn rate vs schedule + automated risk flags. | ④ |
| **D** | **Post-completion profitability** | Real margin per project + per customer. Defensible leadership reporting. | ⑤, ⑥ |
| **E** | **Cross-project resource intelligence** | Stop over-booking star employees and under-utilising juniors at the portfolio level. | ④, ① (capacity forecasting) |
| **F** | **Customer lifetime value** | Identify high-LTV vs marginal customers; pricing power for repeats. | ②, ⑥ |
| **G** | **Lessons learned / knowledge capture** | Causal record: why projects went well or badly. Reusable across pre-sales staff. | ⑤, ⑥ |
| **H** | **Multi-currency, tax & cash flow reality** | Track FX P&L attribution; tax-aware pricing; DSO monitoring. | ③, ⑤ |
| **I** | **Change management (scope creep tracking)** | Convert mid-project scope changes into formal Change Requests with client sign-off. | ④ |

Each capability maps to specific DocTypes, custom fields, scheduler jobs, reports, and hooks in Part B below.

---

# Part B — Frappe Implementation Blueprint

This part is the build-out: what to create, where in the file tree, with what fields. The schemas below are sketches — final field lists may shift during implementation, but the structure should hold.

## 5. New DocTypes

Seven new DocTypes. Two are **child tables** (live inside parents); five are **masters** (standalone records).

### 5.1 `Project Health Snapshot` (master) — capability **C**

One row per active project per week. Time-series of in-flight health. Powers the Delivery dashboard.

```
DocType: Project Health Snapshot
Module: tbo analytics

Fields:
  project                  Link → Project              (required, indexed)
  estimate                 Link → Implementation Estimate (auto-fetched from project)
  snapshot_date            Date                        (required, indexed)
  estimated_hours          Float                       (auto-fetched from estimate)
  actual_hours_to_date     Float                       (auto-computed from Timesheet)
  pct_consumed             Float                       (= actual / estimated × 100)
  days_elapsed             Int                         (today − project.expected_start_date)
  total_duration_days      Int                         (expected_end − expected_start)
  pct_time_elapsed         Float                       (days_elapsed / total_duration × 100)
  burn_rate_daily          Float                       (actual_hours / days_elapsed)
  projected_end_date       Date                        (today + remaining_hours / burn_rate)
  days_ahead_or_behind     Int                         (projected_end − expected_end)
  status_flag              Select  On Track / At Risk / Overrun
  health_note              Small Text                  (auto-generated, e.g. "32 hrs over with 15 days left")
  by                       Link → User                 (snapshot author; usually System)
```

Generated weekly by scheduler. Read by Delivery dashboard. Old snapshots retained for trend analysis.

### 5.2 `Project Completion Review` (master, submittable) — capabilities **D**, **G**

The closure form. One per finished project. Captures the lessons + signs off the profitability snapshot.

```
DocType: Project Completion Review
Module: tbo analytics
is_submittable: 1
autoname: PCR-.YYYY.-####

Sections:
  A. Project Identity
     project              Link → Project              (required, unique)
     estimate             Link → Implementation Estimate (auto-fetched)
     completion_date      Date                        (default today)
     reviewer             Link → User                 (default session user)

  B. Actuals vs Estimate (read-only, computed)
     estimated_hours, actual_hours, hours_variance_pct
     estimated_cost,  actual_cost,  cost_variance_pct
     recommended_price, realised_revenue, margin_at_estimate, realised_margin
     duration_estimated_months, duration_actual_months

  C. Per-module variance (child table — Estimate Variance Record, §5.3)
     variance_breakdown   Table → Estimate Variance Record

  D. Lessons (free text)
     what_went_well       Text Editor
     what_went_badly      Text Editor
     surprise_findings    Text Editor   "Things we did not anticipate"
     client_feedback      Text Editor   "What the client told us"

  E. Root-cause tags (multi-select)
     causes_of_variance   Table → Variance Cause Tag (a child with a single Select field, options:
                                                       Scope creep, Skill gap, Client delay,
                                                       Tech blocker, External integration delay,
                                                       Over-optimistic estimate, Estimating tool gap,
                                                       Resource turnover, Other)

  F. Outcome
     final_status         Select  Profitable / Break-even / Loss / Strategic write-off
     recommend_for_repeat Check   "Would we take this customer again?"
     amc_signed           Check   "AMC contract was signed for this client"
     amc_value            Currency
```

On submit, this DocType triggers two things:
1. A row in `Customer Profitability Summary` for this customer (§5.7)
2. An entry in `Estimate Variance Record` per module that contributes to the historical_avg refresh

### 5.3 `Estimate Variance Record` (child of Project Completion Review) — capability **B**

Per-module estimated-vs-actual record with causal tag. The structured signal that feeds the estimator.

```
DocType: Estimate Variance Record
istable: 1
Parent: Project Completion Review (variance_breakdown)

Fields:
  source_type        Select  Module / Custom Module / Integration  (required)
  source_identifier  Data                                          (the module name, integration name, etc.)
  estimated_hours    Float
  actual_hours       Float
  variance_hours     Float    (= actual − estimated)
  variance_pct       Float
  primary_cause      Link → Variance Cause Tag (or Select; same options as §5.2 E)
  cause_notes        Small Text
```

### 5.4 `Pipeline Forecast Snapshot` (master) — capability **A**

Weekly snapshot of funnel state. Time-series enables conversion-rate-by-cohort and revenue forecasting.

```
DocType: Pipeline Forecast Snapshot
Module: tbo analytics

Fields:
  snapshot_date           Date         (indexed)
  draft_count             Int
  under_review_count      Int
  approved_count          Int
  won_count_this_week     Int
  lost_count_this_week    Int
  total_pipeline_value    Currency     (sum of recommended_price for Draft/Under Review/Approved)
  weighted_pipeline_value Currency     (each estimate × stage probability — Draft 10%, Under Review 30%,
                                        Approved 60%, Sent to Client 80%)
  avg_cycle_days          Float        (avg time Draft → Won/Lost for cohort closed this week)
  win_rate_pct            Float        (won / (won + lost) × 100, trailing 30 days)
  forecast_revenue_30d    Currency
  forecast_revenue_90d    Currency
```

### 5.5 `Resource Utilisation Snapshot` (master) — capability **E**

Weekly per-employee allocation across all open projects. Drives the resource heat-map.

```
DocType: Resource Utilisation Snapshot
Module: tbo analytics

Fields:
  snapshot_date            Date              (indexed)
  employee                 Link → Employee   (indexed)
  employee_name            Data              (denormalised for display)
  department               Link → Department
  capacity_hours_this_week Float             (default 132 / 4 = 33)
  committed_hours_this_week Float            (sum of overlapping allocations across all open estimates + projects)
  utilisation_pct          Float
  status                   Select  Under / OK / Busy / Over
  open_estimates_list      Text              (comma-separated estimate names contributing)
```

Composite index: `(snapshot_date, employee)` for fast time-series queries.

### 5.6 `Change Request` (master, submittable) — capability **I**

Captures mid-project scope changes. Linked to Project; creates an addendum to Implementation Estimate.

```
DocType: Change Request
Module: tbo analytics
is_submittable: 1
autoname: CR-{project}-.####

Fields:
  project                  Link → Project (required)
  estimate                 Link → Implementation Estimate (auto-fetched)
  requested_date           Date  (default today)
  requested_by             Link → User
  client_contact           Link → Contact

  description              Text Editor   (what the client is asking for)
  business_justification   Text Editor

  modules_affected         Table → Change Request Module Line  (child: module + delta_hours)
  estimated_added_hours    Float         (sum from child table)
  estimated_added_cost     Currency      (computed: added_hours × blended_hourly_rate)
  pricing_treatment        Select  Absorbed / Charged Separately / Free Goodwill
  added_price              Currency      (0 if absorbed)
  client_approval_status   Select  Pending / Approved / Rejected
  client_approval_date     Date
  notes                    Text Editor
```

On approval, optionally appends new rows to the linked Estimate's `module_selections` or `custom_module_requests`.

### 5.7 `Customer Profitability Summary` (master, one record per customer) — capabilities **D**, **F**

Refreshed nightly by scheduler. Lifetime profitability per customer.

```
DocType: Customer Profitability Summary
Module: tbo analytics

Fields:
  customer                       Link → Customer  (unique, required)
  customer_name                  Data             (denormalised)
  first_engagement_date          Date
  last_engagement_date           Date
  total_estimates_created        Int
  total_estimates_won            Int
  win_rate_pct                   Float
  total_projects_completed       Int
  lifetime_revenue               Currency  (sum base_grand_total from Sales Invoices, company-currency)
  lifetime_direct_cost           Currency
  lifetime_overhead_allocated    Currency
  lifetime_realised_margin       Currency  (revenue − total cost)
  lifetime_margin_pct            Float
  avg_project_size_hours         Float
  avg_project_margin_pct         Float
  ltv_tier                       Select  Platinum / Gold / Silver / Bronze / Watch
                                          (rule-based: Platinum > ₹50L lifetime, Gold > ₹20L, Silver > ₹5L,
                                           Watch = avg margin < 10%)
  next_action_recommended        Select  Upsell AMC / Repeat engagement / Renegotiate pricing / Disengage
  notes                          Text Editor
```

---

## 6. Custom Fields on Standard ERPNext DocTypes

Standard ERPNext doctypes need our app's custom fields. **All to be provisioned as a `Custom Field` fixture** in `tbo_analytics/fixtures/custom_field.json` so they install automatically via `bench migrate`.

> **Naming convention:** prefix new fields with `custom_tba_` (TBO Analytics) to avoid collision with existing custom fields from sibling apps (e.g. Project already has `custom_lead`, `custom_project_manager` from `tbo_smart`). Exception: the two fields the existing code already references (`custom_module_tag`, `custom_actual_hours_logged`) — keep their current names so the existing handlers and tasks work unchanged.

### On `Task`

| Field | Type | Purpose | Notes |
|---|---|---|---|
| `custom_module_tag` | Link → ERP Module Master | Tags a delivery Task back to the originating estimate module. | **Already referenced by code** — Phase 1 must add this. |
| `custom_tba_origin_estimate` | Link → Implementation Estimate | Direct link from Task to the estimate that created it. | Helps the post-mortem variance report. |
| `custom_tba_overrun_reason` | Select | Why this Task went over hours. | Same options as `Variance Cause Tag` (§5.2). |

### On `Project`

| Field | Type | Purpose | Notes |
|---|---|---|---|
| `custom_actual_hours_logged` | Float | Sum of Timesheet hours against this project, refreshed by scheduler. | **Already referenced** — Phase 1 must add. |
| `custom_tba_estimate_link` | Link → Implementation Estimate | Project ↔ Estimate two-way link. | Standard ERPNext has no Estimate doctype to link to. |
| `custom_tba_health_status` | Select | On Track / At Risk / Overrun / On Hold | Updated daily by scheduler. |
| `custom_tba_last_snapshot_date` | Date | Last time Project Health Snapshot ran for this project. | |
| `custom_tba_completion_review` | Link → Project Completion Review | Two-way link once the closure form is submitted. | |

### On `Timesheet Detail`

| Field | Type | Purpose | Notes |
|---|---|---|---|
| `custom_tba_phase` | Select | Phase 1 / Phase 2 / Phase 3 | Categorise time-logged by deployment wave. |
| `custom_tba_module_tag` | Link → ERP Module Master | Module this hour was spent on (helpful when one Task spans multiple modules). | Optional; falls back to Task.custom_module_tag. |

### On `Sales Invoice`

Standard ERPNext already has `project` (Link → Project). **No new field needed** at header level.

| Field | Type | Purpose | Notes |
|---|---|---|---|
| `custom_tba_estimate_link` | Link → Implementation Estimate | Direct invoice → estimate link. | Optional convenience; project link already chains through. |

### On `Lead` (if Frappe CRM Lead doctype is in use)

| Field | Type | Purpose | Notes |
|---|---|---|---|
| `custom_tba_estimate_link` | Link → Implementation Estimate | Lead → Estimate when one is created from the lead. | Powers the funnel analytics. |

### Fixture file structure

```json
[
  {
    "doctype": "Custom Field",
    "dt": "Task",
    "fieldname": "custom_module_tag",
    "fieldtype": "Link",
    "options": "ERP Module Master",
    "label": "Module Tag (tbo_analytics)",
    "insert_after": "project"
  },
  {
    "doctype": "Custom Field",
    "dt": "Project",
    "fieldname": "custom_actual_hours_logged",
    "fieldtype": "Float",
    "label": "Actual Hours Logged (tbo_analytics)",
    "read_only": 1,
    "insert_after": "actual_time"
  },
  ...
]
```

Add the fixture file path to `hooks.py`:

```python
fixtures = [
    {"dt": "Custom Field", "filters": [["fieldname", "like", "custom_tba_%"]]},
    {"dt": "Custom Field", "filters": [["fieldname", "in", ["custom_module_tag", "custom_actual_hours_logged"]]]},
    ...
]
```

---

## 7. Workflows to Add

Two new workflows, similar in shape to the existing Implementation Estimate workflow.

### 7.1 Project Status Workflow

State machine for Project (extending ERPNext's default):

```
States                Allow Edit       doc_status
─────────────────────────────────────────────────
Draft                 PM, All          0
In Progress           PM, All          0
At Risk               PM, Delivery Hd  0
On Hold               PM               0
Completed             PM               0
Closed-Invoiced       Accounts         1   (after Sales Invoice submitted)
Closed-Reviewed       Delivery Head    1   (after Project Completion Review submitted)
Cancelled             Sales Mgr        2

Transitions
─────────────
Draft           → In Progress       (Won status on Estimate, automated)
In Progress     → At Risk           (daily scheduler flips it when burn > threshold)
At Risk         → In Progress       (PM acknowledges resolution)
In Progress     → On Hold           (PM manual)
On Hold         → In Progress       (PM resumes)
In Progress     → Completed         (PM manual — triggers prompt to file Completion Review)
Completed       → Closed-Invoiced   (auto when Sales Invoice for this project is submitted)
Closed-Invoiced → Closed-Reviewed   (auto when Project Completion Review is submitted)
* → Cancelled (Sales Mgr, requires reason)
```

### 7.2 Project Completion Review Workflow

```
States              Allow Edit         doc_status
─────────────────────────────────────────────────
Draft               Reviewer           0
Submitted           (none)             1   (locks data; triggers downstream snapshots)
```

### 7.3 Change Request Workflow

```
States              Allow Edit         doc_status
─────────────────────────────────────────────────
Logged              PM, Pre-sales      0
Approved            Sales Mgr          1   (auto-appends to Estimate if pricing != "Absorbed")
Rejected            Sales Mgr          1   (closed, no further action)
```

---

## 8. Scheduler Jobs to Add

Five new jobs in [tasks.py](tbo_analytics/tbo_analytics/tasks.py). Existing two (`update_historical_averages`, `refresh_time_coverage_cache`) stay; one is extended.

```python
# hooks.py — scheduler_events

scheduler_events = {
    "daily": [
        "tbo_analytics.tbo_analytics.tasks.refresh_project_health_status",     # NEW
    ],
    "weekly": [
        "tbo_analytics.tbo_analytics.tasks.update_historical_averages",        # existing
        "tbo_analytics.tbo_analytics.tasks.refresh_time_coverage_cache",       # existing
        "tbo_analytics.tbo_analytics.tasks.snapshot_project_health",           # NEW
        "tbo_analytics.tbo_analytics.tasks.snapshot_pipeline_forecast",        # NEW
        "tbo_analytics.tbo_analytics.tasks.snapshot_resource_utilisation",     # NEW
    ],
    "monthly": [
        "tbo_analytics.tbo_analytics.tasks.refresh_customer_profitability",    # NEW
        "tbo_analytics.tbo_analytics.tasks.feedback_loop_to_module_master",    # NEW — extends existing
    ],
}
```

### 8.1 `refresh_project_health_status()` (daily)

For every Project where `custom_tba_health_status` is not in (Completed, Closed-*, Cancelled):

```python
# Pseudocode
for project in active_projects:
    estimated = estimate.grand_total_hours
    actual    = sum(Timesheet Detail hours WHERE project = project.name AND ts.docstatus = 1)
    pct_consumed = actual / estimated * 100

    pct_time = (today - project.expected_start_date) / (project.expected_end_date - project.expected_start_date) * 100

    if pct_consumed >= 100 and pct_time < 100:
        new_status = "Overrun"
    elif pct_consumed >= 80 and pct_time < 50:
        new_status = "At Risk"           # burning fast, way before halftime
    elif pct_consumed - pct_time > 25:
        new_status = "At Risk"           # consumption running > 25 pp ahead of timeline
    else:
        new_status = "In Progress"

    if project.custom_tba_health_status != new_status:
        project.custom_tba_health_status = new_status
        project.save()
        # Optional: send email/notification to PM on transition to At Risk / Overrun
```

### 8.2 `snapshot_project_health()` (weekly)

Insert one `Project Health Snapshot` row per active project. Trends visible in dashboards over time.

### 8.3 `snapshot_pipeline_forecast()` (weekly)

```sql
INSERT INTO `tabPipeline Forecast Snapshot` (snapshot_date, draft_count, ..., weighted_pipeline_value, ...)
SELECT
    CURDATE(),
    COUNT(CASE WHEN status='Draft' THEN 1 END),
    COUNT(CASE WHEN status='Under Review' THEN 1 END),
    COUNT(CASE WHEN status='Approved' THEN 1 END),
    -- weekly win/loss
    COUNT(CASE WHEN status='Won' AND modified >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 END),
    COUNT(CASE WHEN status='Lost' AND modified >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) THEN 1 END),
    -- pipeline value
    SUM(CASE WHEN status IN ('Draft','Under Review','Approved') THEN recommended_price ELSE 0 END),
    -- probability-weighted
    SUM(CASE
        WHEN status='Draft'         THEN recommended_price * 0.10
        WHEN status='Under Review'  THEN recommended_price * 0.30
        WHEN status='Approved'      THEN recommended_price * 0.60
        ELSE 0 END),
    ...
FROM `tabImplementation Estimate`
WHERE company = (company name);
```

### 8.4 `snapshot_resource_utilisation()` (weekly)

For each active employee × current week, compute committed hours across all open estimates + projects, vs capacity = 33 hrs/week. Insert into `Resource Utilisation Snapshot`.

### 8.5 `refresh_customer_profitability()` (monthly)

Rebuild `Customer Profitability Summary` rows from scratch by walking Sales Invoices and Projects per customer. Slow but correctness over speed; nightly is fine.

### 8.6 `feedback_loop_to_module_master()` (monthly) — extends existing weekly job

Currently `update_historical_averages()` aggregates Task actuals by `custom_module_tag` and updates `ERP Module Master.historical_avg_hours`. Extension: also aggregate the **variance reasons** from `Estimate Variance Record` records of completed projects. Store as a new field on ERP Module Master:

```
ERP Module Master — add fields:
   common_overrun_causes   Long Text   (JSON: {"Scope creep": 12, "Skill gap": 4, ...})
   confidence_score        Float       (1.0 - stddev(variance%) / 100; bounded 0..1)
```

`confidence_score` becomes a new signal in the estimator — if a module has confidence_score < 0.5, show a yellow "ESTIMATE UNRELIABLE" badge in the estimate's Module Selection row.

---

## 9. New Reports

Eight new Script Reports. Each produces specific business insight.

### 9.1 Pipeline Funnel

| Column | Source |
|---|---|
| Stage | Estimate.status |
| Count | COUNT(*) |
| Total Value | SUM(recommended_price) |
| Weighted Value | SUM(recommended_price × stage_probability) |
| Avg Days in Stage | AVG(now() − Estimate.modified_at_last_status_change) |
| Conversion Rate to Next Stage | from historical Pipeline Forecast Snapshots |

Filters: date range, project type, customer.

### 9.2 Win/Loss Analysis

| Column | Notes |
|---|---|
| Customer segment | (manual tag or LTV tier) |
| Won count | |
| Lost count | |
| Win rate | won / (won + lost) |
| Avg Won price | |
| Avg Lost price | (negotiation rejection ceiling) |
| Top loss reason | Most common cause tag among Lost estimates (requires capturing loss reason — new field on Estimate) |

Suggested addition to **Implementation Estimate**: `custom_tba_lost_reason` Select field (Price / Timeline / Competitor / Internal Decision / Scope / Trust) — completed when status flips to Lost.

### 9.3 Project Health Dashboard (live)

Live view of all active projects:

| Column |
|---|
| Project |
| Client |
| Estimate ID |
| Start date / Expected end / Projected end |
| Estimated hrs / Actual / % consumed |
| Status flag (On Track / At Risk / Overrun) |
| PM |

Filters: status, PM, customer.

### 9.4 Estimate Accuracy Trend

For each completed project (Project Completion Review submitted):

| Column |
|---|
| Completion month |
| Module type |
| Estimated hrs |
| Actual hrs |
| Variance % |
| Trailing 3-month avg variance % |
| Trailing 12-month avg variance % |

Visualisation: line chart per module type showing variance % converging toward 0 (or not) over time.

### 9.5 Customer Profitability Ranking

Simple SELECT from `Customer Profitability Summary` ordered by `lifetime_realised_margin DESC`. Columns: rank, customer, projects done, lifetime revenue, margin, LTV tier, next action.

### 9.6 Resource Utilisation Heat-map

Pivot of `Resource Utilisation Snapshot`:

| Employee (row) | Wk 1 | Wk 2 | Wk 3 | Wk 4 | ... |
|---|---|---|---|---|---|

Cells colour-coded by utilisation %. Red > 100%, orange 85–100%, green 65–85%, grey < 65%.

### 9.7 Profitability Variance

Per completed project: estimated margin % vs realised margin %. Root-cause distribution:

| Column |
|---|
| Project |
| Customer |
| Estimated margin % |
| Realised margin % |
| Margin variance (pp) |
| Primary cause tag |
| Lessons summary (1-line excerpt) |

### 9.8 Module Calibration Report

For each row in ERP Module Master:

| Column |
|---|
| Module |
| Base hours C1 |
| Base hours C2 |
| Historical avg |
| Sample count |
| Confidence score |
| Suggested base hours (= historical_avg) |
| Drift % (historical avg vs base C1) |
| Common overrun causes |

Action column: "Apply suggestion" button that updates the master's base hours to match recent reality.

---

## 10. New Dashboards

Two new dashboards (each is a JSON fixture under `tbo_analytics/fixtures/dashboard.json` and `dashboard_chart.json`).

### 10.1 Sales / Leadership Dashboard

| Chart | Source |
|---|---|
| Pipeline funnel | Pipeline Forecast Snapshot (latest) |
| Win rate trend | Pipeline Forecast Snapshot — line over 12 months |
| Forecasted revenue 30/60/90 days | Pipeline Forecast Snapshot |
| Top customers by LTV | Customer Profitability Summary |
| Estimate accuracy trend | Estimate Accuracy Trend report |
| FX exposure | Sales Invoice grouped by currency (custom chart) |

### 10.2 Delivery / PM Dashboard

| Chart | Source |
|---|---|
| Projects at risk | Projects where custom_tba_health_status IN (At Risk, Overrun) |
| Burn-down per active project | Project Health Snapshot time-series |
| Team utilisation heat-map | Resource Utilisation Snapshot |
| Open Change Requests | Change Request where workflow_state = Logged |
| Days to next AMC renewal | Customer Profitability Summary where amc_signed = 1 |

---

## 11. New Hooks

Additions to `tbo_analytics/hooks.py`:

```python
doc_events = {
    # ... existing entries ...

    # NEW — Project status changes
    "Project": {
        "on_update": "tbo_analytics.tbo_analytics.handlers.on_project_update",
        "on_trash":  "tbo_analytics.tbo_analytics.handlers.on_project_trash",
    },

    # NEW — Sales Invoice submitted → close the project + update profitability
    "Sales Invoice": {
        "on_submit":  "tbo_analytics.tbo_analytics.handlers.on_invoice_submit",
        "on_cancel":  "tbo_analytics.tbo_analytics.handlers.on_invoice_cancel",
    },

    # NEW — Project Completion Review submitted → cascade snapshots + feedback
    "Project Completion Review": {
        "on_submit":  "tbo_analytics.tbo_analytics.handlers.on_completion_review_submit",
    },

    # NEW — Change Request approved → optionally append to Estimate
    "Change Request": {
        "on_submit":  "tbo_analytics.tbo_analytics.handlers.on_change_request_submit",
    },
}
```

The handlers themselves are described informally below. Each is ~30–50 lines of Python.

| Handler | What it does |
|---|---|
| `on_project_update` | If status moves to Completed, prompt the PM to file a Project Completion Review (toast or email notification). |
| `on_invoice_submit` | If Sales Invoice has `project` set and that project is Completed, flip project to Closed-Invoiced and update Customer Profitability Summary. |
| `on_completion_review_submit` | Cascade: generate the per-module Estimate Variance Records, append to `historical_avg_hours` feedback, flip Project to Closed-Reviewed, refresh Customer Profitability Summary. |
| `on_change_request_submit` | If approved and pricing != Absorbed, optionally append a row to the linked Estimate's module_selections or custom_module_requests (or just record the addendum). |

---

# Part C — Roadmap & Next Steps

## 12. Phased Rollout

Ordered by ROI. Each phase ends with something visibly useful in the Frappe Desk.

### Phase 1 — Unblock existing reports (1 week)

**Goal:** the two estimate-vs-actual reports that currently produce thin data start producing real data.

| Deliverable | File |
|---|---|
| Custom Field fixture for `custom_module_tag` (Task) and `custom_actual_hours_logged` (Project) | `tbo_analytics/fixtures/custom_field.json` (new) |
| Add fixture path to `hooks.py` so `bench migrate` installs it | `tbo_analytics/hooks.py` |
| Verify `update_historical_averages` and `refresh_time_coverage_cache` now run successfully | (no code change; just verify) |
| One paragraph in [USAGE.md](USAGE.md) explaining the new fields | |

Effort: **~3 hours**. Visible result: the existing Time Coverage Tracker + Estimate vs Actual Hours reports start showing real numbers for any project that has had a few timesheets logged.

### Phase 2 — Project In Flight visibility (2 weeks)

**Goal:** PMs see daily project health; over-runs surface in week 1.

| Deliverable |
|---|
| Custom fields on Project (`custom_tba_health_status`, `custom_tba_estimate_link`, `custom_tba_last_snapshot_date`) |
| New DocType: Project Health Snapshot |
| New scheduler job: `refresh_project_health_status` (daily) |
| New scheduler job: `snapshot_project_health` (weekly) |
| New Script Report: Project Health Dashboard (§9.3) |
| New Dashboard: Delivery / PM Dashboard (§10.2 — partial) |

Effort: **~10 working days**. Visible result: a delivery dashboard PMs check every morning.

### Phase 3 — Completion + Profitability Feedback Loop (3 weeks)

**Goal:** every finished project produces a Profitability snapshot and a lessons record that feeds the estimator.

| Deliverable |
|---|
| New DocType: Project Completion Review (submittable) |
| New child DocType: Estimate Variance Record |
| New child DocType: Variance Cause Tag (or use Select directly) |
| Project status workflow extended: Completed → Closed-Invoiced → Closed-Reviewed |
| Hook: `on_invoice_submit` flips project to Closed-Invoiced |
| Hook: `on_completion_review_submit` cascades into historical_avg + Customer Profitability |
| New Script Report: Profitability Variance (§9.7) |
| Extended scheduler job: `feedback_loop_to_module_master` (monthly) |
| Add `confidence_score` + `common_overrun_causes` fields to ERP Module Master |
| New Script Report: Module Calibration Report (§9.8) |
| Yellow "ESTIMATE UNRELIABLE" badge in Module Selection row when confidence_score < 0.5 |

Effort: **~15 working days**. Visible result: every closed project lands a row in Customer Profitability; the estimator starts highlighting unreliable modules.

### Phase 4 — Pipeline + LTV + Resource Intelligence (3 weeks)

**Goal:** leadership has revenue forecasting, win/loss analytics, customer LTV, and portfolio-level resource utilisation.

| Deliverable |
|---|
| New DocType: Pipeline Forecast Snapshot |
| New DocType: Customer Profitability Summary |
| New DocType: Resource Utilisation Snapshot |
| Scheduler jobs: `snapshot_pipeline_forecast` (weekly), `snapshot_resource_utilisation` (weekly), `refresh_customer_profitability` (monthly) |
| Add `custom_tba_lost_reason` field to Implementation Estimate |
| New Script Reports: Pipeline Funnel, Win/Loss Analysis, Customer Profitability Ranking, Resource Utilisation Heat-map (§9.1, 9.2, 9.5, 9.6) |
| New Dashboard: Sales / Leadership Dashboard (§10.1) |
| Add Change Request DocType + Workflow (§5.6) + hook |

Effort: **~15 working days**. Visible result: leadership dashboard with the three numbers every services firm wants — pipeline forecast, customer LTV, resource utilisation.

### Total effort

≈ **6–8 working weeks** for a single Frappe developer, broken into shippable phases. Each phase is independently valuable; you can stop after any of them without breaking what's been built.

---

## 13. What This Roadmap Does NOT Include

Deliberately out of scope:

| Out of scope | Why not |
|---|---|
| ML-driven estimation models | Premature — the historical_avg + variance-cause feedback in Phase 3 captures most of the value with much less complexity. ML becomes interesting only after 2+ years of clean data. |
| NPV / IRR / discounted cashflow | TBO's engagements are 3–9 months. Time-value-of-money math doesn't move decisions at that duration. |
| Predictive risk scoring | Same as ML — premature without 2 years of variance data. Phase 3's variance reasons are the prerequisite. |
| Lead-to-Estimate CRM funnel | If Frappe CRM is used as a sibling app, we should bridge to it (via `custom_tba_estimate_link` on Lead). We should NOT rebuild a Lead doctype here. |
| Mobile app / native UX | Frappe Desk is sufficient. Mobile-responsive web is good enough. |
| Multi-company consolidation | Single-company today. If multi-company becomes a need, every Currency / Cost field needs revisiting. |
| Detailed invoice / billing automation | The standard ERPNext Sales Invoice + Project flow covers this. We extend it, not replace it. |
| Customer-facing portal | The estimator is internal. Client-facing quote PDFs come from the existing Print Format infra (not in scope for this roadmap). |

---

## 14. Verification & Next Steps

### How to validate this roadmap

1. **Read top to bottom** — check that Parts A (business) and B (Frappe) tell the same story end-to-end.
2. **Pick one capability theme from Part B §4** — say, *"Project Health Monitoring"*. Trace it across §3 (the problem it addresses) → §5 (the DocType that holds the data) → §8 (the scheduler that populates it) → §9 (the report that surfaces it) → §10 (the dashboard that shows it). Confirm the chain is complete.
3. **Identify one stage where the business pain isn't strong enough to justify the work.** If you find one, that phase should drop in priority.
4. **Confirm the four phases match TBO's actual delivery capacity** — 6–8 weeks of one developer's time. If shorter, drop Phase 4 and revisit later.

### The first three concrete next steps

1. **Sanity-check Phase 1's custom field fixture** — confirm the field names `custom_module_tag` and `custom_actual_hours_logged` match exactly what the existing code references. Run `grep -rn "custom_module_tag\|custom_actual_hours_logged" tbo_analytics/`.
2. **Decide on `confidence_score` thresholds** — at what point should the estimator show "UNRELIABLE"? Default proposal: `< 0.5`. This is a business judgement call, not a technical one.
3. **Decide whether to attach Frappe CRM** — if TBO uses Frappe CRM for leads, Phase 4's pipeline forecasting becomes much more powerful by ingesting Lead-stage signal. If not, leave the Lead-Estimate bridge as a future item.

### When to revisit this roadmap

- After Phase 1 ships and the existing reports start producing real data — you'll know whether the data quality justifies Phase 3's heavier investment.
- After 6 months of Phase 3 data — at that point, ML-driven estimation becomes feasible and the "what's out of scope today" list should be reviewed.
- Whenever TBO doubles in headcount — the resource-utilisation themes (E) become much more valuable past ~25 people.

### Why the order matters

```
Phase 1  →  fixes silently-broken loops, unblocks existing reports     (1 wk)
Phase 2  →  PMs see project health daily                                (2 wks)
Phase 3  →  estimator improves itself; leadership sees real margins    (3 wks)
Phase 4  →  leadership forecasts revenue & resources                    (3 wks)
```

Phase 3 deliberately precedes Phase 4 because Phase 3's variance data makes Phase 4's forecasting trustworthy. Reversing the order produces forecasts that don't have variance-aware confidence intervals — pretty charts that don't help decisions.

---

## Appendix — Quick reference of new DocType names

```
Master:
  Project Health Snapshot
  Project Completion Review (submittable)
  Pipeline Forecast Snapshot
  Resource Utilisation Snapshot
  Change Request (submittable)
  Customer Profitability Summary

Child (table) DocTypes:
  Estimate Variance Record         (child of Project Completion Review)
  Variance Cause Tag               (child of Project Completion Review or generic)
  Change Request Module Line       (child of Change Request)
```

## Appendix — Quick reference of new custom fields

```
Task:
  custom_module_tag                (Link → ERP Module Master)  [Phase 1, name preserved]
  custom_tba_origin_estimate       (Link → Implementation Estimate)
  custom_tba_overrun_reason        (Select)

Project:
  custom_actual_hours_logged       (Float)                     [Phase 1, name preserved]
  custom_tba_estimate_link         (Link → Implementation Estimate)
  custom_tba_health_status         (Select)
  custom_tba_last_snapshot_date    (Date)
  custom_tba_completion_review     (Link → Project Completion Review)

Timesheet Detail:
  custom_tba_phase                 (Select)
  custom_tba_module_tag            (Link → ERP Module Master)

Sales Invoice:
  custom_tba_estimate_link         (Link → Implementation Estimate)

Implementation Estimate (extension):
  custom_tba_lost_reason           (Select)

ERP Module Master (extension):
  confidence_score                 (Float)
  common_overrun_causes            (Long Text, JSON)
```

---

**End of roadmap.** This document is opinionated about ordering and out-of-scope items but not prescriptive about implementation details — those land in code as each phase ships. The next action is Phase 1: scaffold the custom field fixture, run `bench migrate`, and watch the existing reports come alive.
