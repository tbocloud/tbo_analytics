# tbo_analytics — How the App Works

A practical walkthrough of what this app does, the day-to-day workflow, and how to use it. For the technical spec see [guide.md](guide.md); for recent bug fixes and open items see [CHANGES.md](CHANGES.md).

---

## 1. What this app is, in one paragraph

It's an **internal ERPNext implementation estimator**. Pre-sales opens one Implementation Estimate per client lead, ticks the modules they need, the app auto-estimates hours from history, you assign a team, plug in your overhead costs, and the app produces the minimum price you can quote without losing money — plus best-case, worst-case, and break-even numbers. The output is reviewed and approved inside the team; nothing is sent to the client from this app. When you mark a deal Won, the app auto-creates the Project, Tasks, and a draft Sales Order so delivery can start immediately.

---

## 2. One-time setup (do this before using the app)

These three things need to exist in your site before creating your first estimate. **No manual rate-card maintenance** — internal cost is derived from each employee's HRMS salary.

| What | Where | Why |
|---|---|---|
| **ERP Module Master** records | Auto-loaded from [fixtures/erp_module_master.json](tbo_analytics/fixtures/erp_module_master.json) — 13 modules pre-seeded (Accounts, Sales, Manufacturing, HR, etc.) | The list of ERPNext modules a client can choose, with their base hours per complexity. |
| **Integration Type Master** records | Auto-loaded from [fixtures/integration_type_master.json](tbo_analytics/fixtures/integration_type_master.json) — WhatsApp, biometric, payment gateways, etc. | The catalogue of external integrations. |
| **Employee + Salary Structure Assignment** (HRMS) | Already in HRMS | Source of the hourly cost. When you pick an employee in Team Composition, the app reads their active Salary Structure Assignment and computes `hourly_cost = monthly_base / (22 × 6)`. If no SSA, it falls back to the last 3 Salary Slips' average gross pay. |

Run once after install:
```
bench --site erp.hydrotech migrate
bench --site erp.hydrotech clear-cache
```

That's it — no Rate Card setup required to get started.

### How the hourly cost is derived

When an Employee is picked in Section E (Team Composition), the app calls the server method [`get_employee_hourly_cost`](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py) which tries, in order:

1. **Salary Structure Assignment** — most recent active one for that employee, takes the `base` field (monthly basic).
2. **Salary Slip** — if no SSA, averages `gross_pay` from the last 3 submitted Salary Slips.

The result is divided by `22 × 6 = 132` working hours/month (matching the project-duration formula elsewhere in the app). A toast notification confirms which source was used, e.g. *"₹757/hr (from Salary Structure Assignment)"*. If neither source has data, you'll see an orange warning asking you to set up a Salary Structure Assignment in HRMS.

---

## 3. The end-to-end workflow

```
   ┌──────────────────────────────────────────────────────────────────┐
   │  PRE-SALES                                                       │
   │  ────────                                                        │
   │  1. New Implementation Estimate                                  │
   │  2. Fill Client Details                                          │
   │  3. Tick modules → app fills AI hours                            │
   │  4. Add custom modules + integrations if needed                  │
   │  5. Build the team (employees + allocated hours)                 │
   │  6. Add direct / indirect / infrastructure costs                 │
   │  7. App computes Recommended Price + scenarios                   │
   │  8. Submit for Review                                            │
   └──────────────────────────────────────────────────────────────────┘
                                  ↓
   ┌──────────────────────────────────────────────────────────────────┐
   │  REVIEW (internal)                                               │
   │  ─────────────────                                               │
   │  9.  Reviewer Approves (or Requests Revision)                    │
   │  10. Once the client commits (offline) → Mark Won / Mark Lost    │
   └──────────────────────────────────────────────────────────────────┘
                                  ↓  (on Won)
   ┌──────────────────────────────────────────────────────────────────┐
   │  AUTO (no human action)                                          │
   │  ───────────────────────                                         │
   │  • Project is created and linked to the Customer                 │
   │  • One Task per module / custom module / integration             │
   │  • Draft Sales Order is created with Recommended Price           │
   │  • PM and pre-sales get a notification                           │
   └──────────────────────────────────────────────────────────────────┘
                                  ↓
   ┌──────────────────────────────────────────────────────────────────┐
   │  DELIVERY                                                        │
   │  ────────                                                        │
   │  • Team logs Timesheets against the Project                      │
   │  • Time Coverage Tracker report shows % consumed / on-track      │
   │  • After project ends, Estimate vs Actual feeds back into the    │
   │    historical_avg_hours of each module → next estimate is better │
   └──────────────────────────────────────────────────────────────────┘
```

---

## 4. Filling the form, section by section

The Implementation Estimate doctype is one long form split into 12 sections (A–L). Open one and fill them in roughly this order.

### Section A — Client Details
Pick the Customer (required). Set Company Size, Project Type, expected go-live date. Tick **Data Migration Required** if relevant — this adds a 15% hour multiplier to every module.

### Section B — Module Selection
Click **Add Row**, pick a module from the dropdown (e.g. "Accounts"), and the app auto-fills:

- **AI Estimated Hours** (read-only): `historical_avg × complexity × company_size × migration_factor`
- **Final Hours**: the leader override if you typed one, else the AI value

Per row you can:
- Set **Complexity** to 1 or 2 (2 = +60% multiplier, row turns yellow)
- Override the AI estimate with **Leader Estimated Hours**
- Tick **Customization Required** → reveals a customization sub-section where you pick the type (Custom Field, Custom Form, Workflow, etc.) and the app adds the customization hours

### Section C — Custom Module Requests
For modules ERPNext doesn't have out of the box (e.g. "Vehicle Maintenance Tracker"). Each row captures: business purpose, functional description, technical approach, complexity, optional integration & reports. AI hours = `24 or 48 (by complexity) + 16/32 integration + 8/12 per report`.

### Section D — Integration Requirements
WhatsApp, biometric devices, payment gateways, etc. Pick the type, the app fetches the base hours from Integration Type Master.

### Section E — Team Composition
Add one row per team member. Pick the Employee → the app derives **hourly_cost** from their HRMS salary (`monthly_base / 132`). Set **Allocated Hours** manually. Cost per row = `hourly_cost × allocated_hours`.

A toast tells you the source — "Salary Structure Assignment" or "Avg of last 3 Salary Slips". If you see *"No salary data"*, set up a Salary Structure Assignment for that employee in HRMS.

### Section F — Team Revision History
Optional. Click **Actions → Save Team as Version** any time the team composition changes. The app snapshots the current team into a JSON history. You can then run the *Team Revision Comparison* report to see V1 vs V2 vs Current side-by-side. Useful for "what if we swap a senior for a junior?" scenarios.

### Section G — Direct Costs
Quick-add buttons above the table for common items (Frappe Cloud Hosting, Claude API, SMS Gateway, etc.). Tick **One-time Cost** for things like Domain & SSL. Total = `monthly_cost × project_duration_months` (or just `monthly_cost` if one-time).

### Section H — Indirect Costs
Overhead allocated to this project (HR cost, accountant, office rent share). For each, enter your full monthly cost and the % allocated to this project. Allocated amount = `monthly × share% × duration`.

### Section I — Infrastructure & Shared Costs
Laptops, electricity, internet, etc. Choose a split method:
- **Per Head**: `total × (project_team_size / company_headcount) × duration`
- **By Project Count**: `total / active_projects × duration`
- **Fixed Amount**: enter the number directly

### Sections J–L are all computed — read-only

- **J. Estimation Summary** — total hours, project duration in months, blended hourly rate
- **K. Pricing & Profitability** — Floor / Standard / Premium prices, your chosen **Recommended Band** drives the Recommended Price, plus margin %, price-per-hour, and suggested 18% AMC
- **L. Scenario Analysis** — Optimistic (85% hrs), Base (100%), Pessimistic (130%), and a Custom % you can type in. Plus break-even hours and a one-line interpretation.

---

## 5. The status / workflow

Seven states. Internal only — nothing in this app is sent to the client. Buttons appear in the form header depending on current state.

```
   Draft ──Submit for Review──→ Under Review ──Approve──→ Approved ─┬─Mark Won──→ Won
                                       │                            └─Mark Lost─→ Lost
                                       └─Request Revision─→ Revision Requested
                                                                │
                                                                └─Resubmit─→ Under Review

   Draft / Under Review / Revision Requested / Approved ──Put on Hold──→ On Hold ──Resume──→ Draft
```

Currently every user can perform every transition — role gating was deliberately removed (see [CHANGES.md §3](CHANGES.md)). Re-tighten later by editing [fixtures/workflow.json](tbo_analytics/fixtures/workflow.json).

---

## 6. What happens automatically

| Trigger | What runs | File |
|---|---|---|
| **Any save** | Re-runs AI estimation, recalculates all hours/costs/pricing/break-even | [implementation_estimate.py:37-42](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py#L37-L42) (`before_save`) |
| **Status → Won** | Creates Project + Tasks (one per module/custom/integration) + draft Sales Order, links them back | [handlers.py:49](tbo_analytics/tbo_analytics/handlers.py#L49) |
| **Timesheet submitted** | Updates `custom_actual_hours_logged` on the linked Project (if the field exists — see [CHANGES.md §5.3](CHANGES.md)) | [handlers.py:154](tbo_analytics/tbo_analytics/handlers.py#L154) |
| **Every week (scheduler)** | Recalculates each ERP Module Master's `historical_avg_hours` from completed tasks of the last 24 months | [tasks.py:13](tbo_analytics/tbo_analytics/tasks.py#L13) |
| **Every week (scheduler)** | Refreshes time-coverage cache on all linked Projects | [tasks.py:50](tbo_analytics/tbo_analytics/tasks.py#L50) |

---

## 7. Custom buttons on the form

Under the **Actions** menu (top right):

- **Recalculate AI Estimates** — forces a save, which re-runs the whole estimation engine. Useful after editing a Rate Card or a Module Master while the form is open.
- **Save Team as Version** — prompts for a "reason for change", snapshots the team into `team_revisions`.

Under the **Workflow** menu (only shows when relevant):

- **Submit for Review** / **Approve** / **Request Revision** / **Mark Won** / **Mark Lost** — depending on current status.

---

## 8. Reports

All under **Desk → Build → Reports** (or search "Report" in the awesome bar):

| Report | What it answers |
|---|---|
| **Time Coverage Tracker** | For every active project: % of estimated hours consumed, projected end date, on-track / at-risk / overrun flag. The day-to-day operational view. |
| **Estimate vs Actual Hours** | Post-project view: for a finished estimate, which modules took longer than estimated and by how much. Feeds the weekly historical-average refresh. |
| **Profitability Scenarios** | Optimistic / Base / Pessimistic profit for one or many estimates. Leadership uses this for go/no-go pricing decisions. |
| **Project Cost Breakdown** | Itemised cost view for a single estimate — every team member, every direct/indirect/infra line, the grand total, the recommended price, the AMC. |
| **Team Revision Comparison** | V1 vs V2 vs Current team composition side-by-side, with cost delta. |

---

## 9. Dashboards

Under **Desk → Dashboards**:

- **Implementation Overview** — pipeline by status (donut), revenue pipeline by status (bar), estimates created per month (line), won estimates revenue by client (bar).

A *Project Health* dashboard is in the spec but not yet built (see [CHANGES.md §5.1](CHANGES.md)).

---

## 10. A typical 5-minute walkthrough

If you want to demo the app to someone, this is the shortest happy path:

1. Pick any employee that has a **Salary Structure Assignment** in HRMS — note their name. (If none exists, create one for that employee first.)
2. **Implementation Estimate → New**.
3. Section A: pick any Customer, Company Size = Medium.
4. Section B: Add Row → Module = "Accounts", Complexity = 1. Watch the AI hours auto-fill (≈ 96 hrs = 80 base × 1.0 × 1.2 size × 1.0).
5. Section E: Add Row → Employee = the one from step 1, Role = Senior Developer. The hourly_cost auto-fills from their salary and a toast confirms the source. Set Allocated Hours = 96.
6. Section H/I: skip for the demo.
7. **Save**. Scroll down — you'll see Recommended Price, Floor / Standard / Premium, and the scenario table populated.
8. Click **Actions → Save Team as Version**, reason = "initial". Now you have V1 snapshotted.
9. Change the employee's allocated_hours to 120, save, then save as V2. Run the *Team Revision Comparison* report to see the diff.
10. Click **Submit for Review → Approve → Mark Won**. A Project, Tasks, and draft Sales Order are auto-created and linked at the bottom of the form.

---

## 11. Where to look when something doesn't add up

| Symptom | Likely cause |
|---|---|
| AI hours show 0 for a module | The ERP Module Master record has no `base_hours_complexity_1/2` and no `historical_avg_hours`. Open the master, fill the base hours. |
| Team cost is 0 | The Employee has no Salary Structure Assignment and no recent Salary Slips. Set up an SSA in HRMS for that employee. |
| Recommended Price is 0 | Grand Total Cost is 0 → likely no team yet, or no allocated hours, or hourly_cost wasn't fetched. |
| "Mark Won" didn't create a project | Check **Error Log** in the Desk. Most common cause: the customer link is broken, or the Sales Order item code `"ERPNext Implementation"` doesn't exist as an Item. The estimate is still marked Won. |
| Time Coverage Tracker shows nothing | Either no projects linked yet, or no Timesheets logged against them with `docstatus = 1`. |
| Historical averages never update | Tasks need a `custom_module_tag` Custom Field — not yet provisioned. See [CHANGES.md §5.3](CHANGES.md). |

---

## 12. The mental model in one diagram

```
   ┌──────────────────────────────────────────────────────────┐
   │  INPUT (per estimate, manual)                            │
   │    • Modules ticked                                      │
   │    • Company size, migration flag                        │
   │    • Team members + allocated hours                      │
   │    • Direct / indirect / infra cost items                │
   │    • Target margin %                                     │
   └──────────────────────────────────────────────────────────┘
                                ↓
   ┌──────────────────────────────────────────────────────────┐
   │  KNOWLEDGE BASE (shared, grows over time)                │
   │    • ERP Module Master.historical_avg_hours              │
   │      (updated weekly from completed projects)            │
   │    • Rate Card (your internal cost per hour)             │
   │    • Integration Type Master (catalogue)                 │
   └──────────────────────────────────────────────────────────┘
                                ↓
   ┌──────────────────────────────────────────────────────────┐
   │  ENGINE (on every save)                                  │
   │    AI hours → final hours → grand total hours            │
   │      → project duration → all costs                      │
   │      → recommended price + scenarios + break-even        │
   └──────────────────────────────────────────────────────────┘
                                ↓
   ┌──────────────────────────────────────────────────────────┐
   │  OUTPUT                                                  │
   │    • Recommended price for the proposal                  │
   │    • Three profit scenarios                              │
   │    • Break-even hours                                    │
   │    • Auto-created Project + Tasks + Sales Order on Won   │
   │    • Reports + Dashboard for portfolio-level view        │
   └──────────────────────────────────────────────────────────┘
```

The whole point: every estimate you close (Won + later marked done with actual hours) makes the next estimate's AI numbers slightly more accurate, because `historical_avg_hours` gets recomputed weekly from real task actuals.
