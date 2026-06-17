# Implementation Estimate — Field Reference

Every field in the **Implementation Estimate** doctype and its 8 child tables. For each field: type, source, formula (if calculated), and when it runs.

> **Convention used below:**
> - **Manual** = user types it.
> - **Auto-fetch** = filled from another record (rate card, master, etc.) by client JS the moment a foreign-key field is picked.
> - **Calculated** = derived inside the controller's `before_save` pipeline ([implementation_estimate.py:37-42](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py#L37-L42)) and **also** updated client-side on every relevant change for live UX.
> - **Read-only** = the user can't type into it; only the controller writes to it.

The controller's pipeline runs in five fixed phases every save:

```
before_save
   ├── 1. calculate_ai_estimates()      ← Section 2 below
   ├── 2. calculate_final_hours()       ← Section 3
   ├── 3. calculate_costs()             ← Section 4
   ├── 4. calculate_pricing()           ← Section 5
   └── 5. calculate_break_even()        ← Section 6
```

---

## 1. Master fields — Section A (Client Details)

| Field | Type | Source | Notes |
|---|---|---|---|
| `naming_series` | Select | Default `EST-.YYYY.-####` | Auto-numbered, e.g. `EST-2026-0017`. Set once. |
| `status` | Select / Workflow | Manual + workflow buttons | States: Draft → Under Review → Approved → Won / Lost. Plus Revision Requested, On Hold. Drives the workflow transitions. |
| `client_name` | Link → Customer | Manual | Required. Drives the Project + Sales Order link on Won. |
| `contact_person` | Link → Contact | Manual | Optional. |
| `industry` | Link → Industry Type | Manual | Optional but powers reporting. |
| `company_size` | Select | Manual | **Feeds the hours formula** — see §2.1 below. Values: Micro / Small / Medium / Large / Enterprise. |
| `number_of_users` | Int | Manual | Informational. |
| `number_of_companies` | Int | Manual, default 1 | Informational. |
| `current_system` | Data | Manual | E.g. "Tally", "SAP". |
| `project_type` | Select | Manual | Fresh / Upgrade / Add-on / Re-implementation. Informational. |
| `client_technical_level` | Select | Manual | None / Basic / Intermediate / Advanced. Informational. |
| `enquiry_date` | Date | Default = Today | |
| `expected_go_live` | Date | Manual | Used by the auto-created Project's `expected_end_date` when status → Won. |
| `assigned_pre_sales` | Link → User | Manual | Receives the in-app notification when status → Won. |
| `data_migration_required` | Check | Manual | **Feeds the hours formula** — adds 1.15× multiplier to every module's hours. |
| `migration_years` | Int | Manual (visible only when `data_migration_required = 1`) | Informational, doesn't feed the math today. |
| `pre_sales_notes` | Text Editor | Manual | |

---

## 2. Hour estimation logic — `calculate_ai_estimates()`

This is the most important math in the controller. It runs before every save and populates the **AI hours** on every Module Selection, Custom Module Request, and Integration Requirement row.

### 2.1 Module Selection rows

```
ai_estimated_hours  =  base_hours
                       × complexity_multiplier
                       × company_size_factor
                       × migration_factor
```

| Component | Source / Values |
|---|---|
| `base_hours` | `ERP Module Master.historical_avg_hours` if non-zero (learned from past projects). Else falls back to `base_hours_complexity_2` for C2 rows, `base_hours_complexity_1` for C1 rows. |
| `complexity_multiplier` | `1.6` if `complexity` contains `"2"`, else `1.0`. |
| `company_size_factor` | Micro→0.8, Small→1.0, Medium→1.2, Large→1.4, Enterprise→1.7. Defaults to 1.0 if blank. |
| `migration_factor` | `1.15` if `data_migration_required = 1`, else `1.0`. |

### 2.2 Customization sub-block on a Module Selection row

Only computed when `customization_required = 1`:

```
customization_ai_hours  =  base_customization_hours[customization_type]
                           × complexity_multiplier
```
 aa
| `customization_type` | Base hours |
|---|---:|
| Custom Field | 4 |
| Custom Form | 16 |
| Workflow | 12 |
| Custom Report | 10 |
| Print Format | 10 |
| API / Integration | 24 |
| Other | 8 |

### 2.3 Custom Module Request rows

A separate formula because custom modules have no master:

```
ai_estimated_hours  =  base
                     + integration_add  (if needs_integration)
                     + report_count × per_report_hours  (if needs_reports)

where:
   base               = 48 if complexity == "2" else 24
   integration_add    = 32 if complexity == "2" else 16
   per_report_hours   = 12 if complexity == "2" else 8
```

### 2.4 Integration Requirement rows

```
ai_estimated_hours  =  Integration Type Master.base_hours_c2   if complexity == "2"
                     else Integration Type Master.base_hours_c1
```

No company-size or migration multiplier — integrations are scope-only.

---

## 3. Final hours resolution — `calculate_final_hours()`

The pattern is the same everywhere: **leader override wins, AI is the fallback.**

```
def resolve(ai_value, leader_value):
    return leader_value if leader_value > 0 else ai_value
```

### Per row totals

| DocType | Formula |
|---|---|
| Module Selection | `final_hours = resolve(ai_estimated_hours, leader_estimated_hours)` <br> `customization_final_hours = resolve(customization_ai_hours, customization_manual_hours)` <br> `total_module_hours = final_hours + customization_final_hours` |
| Custom Module Request | `final_hours = resolve(ai_estimated_hours, leader_estimated_hours)` <br> `total_hours = final_hours + integration_hours + report_hours` |
| Integration Requirement | `final_hours = resolve(ai_estimated_hours, manual_hours)` |

### Roll-ups on the master

```
total_modules_hours        = SUM(total_module_hours)  for is_included = 1 rows only
total_custom_modules_hours = SUM(total_hours)         across all custom_module_requests
total_integration_hours    = SUM(final_hours)         across all integration_requirements
grand_total_hours          = total_modules_hours
                           + total_custom_modules_hours
                           + total_integration_hours
```

---

## 4. Cost calculation — `calculate_costs()`

Order matters here: team cost first, then duration (which the other cost types need), then direct/indirect/infra.

### 4.1 Team cost (per Team Composition row)

```
For each member where is_active_in_current_version = 1:
    total_cost = hourly_cost × allocated_hours

team_cost_total      = SUM(total_cost)
total_allocated_hrs  = SUM(allocated_hours)
blended_hourly_rate  = team_cost_total / total_allocated_hrs     (0 if total = 0)
```

#### Where `hourly_cost` comes from (Team Composition)

When you pick an **Employee** in the row, the client script ([implementation_estimate.js](tbo_analytics/public/js/implementation_estimate.js) `employee` handler) calls the server method [`get_employee_hourly_cost`](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py):

```
1. Salary Structure Assignment (most recent active) → base
2. Salary Slip (last 3 submitted) → average gross_pay
3. None → 0 (toast tells user to set up HRMS data)

hourly_cost = monthly_amount / (22 × 6)     # 22 working days × 6 hrs/day = 132 hrs/month
```

The 132 divisor matches the project-duration formula (§4.2), so cost and duration use a consistent assumption.

### 4.2 Project duration

```
team_size        = count of active team_members
daily_cap        = team_size × 6 × 22         # hours of work the team can absorb per month
duration_months  = CEIL(grand_total_hours / daily_cap)
                   (clamped to ≥ 1)
```

Used by every duration-dependent cost row (direct + indirect + infra).

### 4.3 Direct cost rows

```
For each direct_costs row:
    project_duration_months = duration_months   (written back to the row)
    total_cost = monthly_cost                  if is_one_time = 1
               = monthly_cost × duration_months otherwise

direct_cost_total = SUM(total_cost)
```

### 4.4 Indirect cost rows

```
For each indirect_costs row:
    project_duration_months = duration_months
    allocated_amount = monthly_total_cost
                     × (project_share_pct / 100)
                     × duration_months

indirect_cost_total = SUM(allocated_amount)
```

`allocation_method` is informational only today — every row uses the formula above regardless of which method is picked. (Reserved field for future per-row method dispatch.)

### 4.5 Infrastructure cost rows

```
For each infrastructure_costs row:
    project_team_size       = team_size
    project_duration_months = duration_months

    if split_method == "Per Head" and company_total_employees > 0:
        allocated_amount = total_monthly_company_cost
                         × (team_size / company_total_employees)
                         × duration_months

    elif split_method == "By Project Count":
        proj_count = count(Project where status='Open') or 1
        allocated_amount = total_monthly_company_cost / proj_count × duration_months

    elif split_method == "Fixed Amount":
        allocated_amount = (left as user-entered value)

    else:
        allocated_amount = 0

infrastructure_cost_total = SUM(allocated_amount)
```

### 4.6 Grand total cost

```
grand_total_cost = team_cost_total
                 + direct_cost_total
                 + indirect_cost_total
                 + infrastructure_cost_total
```

---

## 5. Pricing & profitability — `calculate_pricing()`

Section K. Runs after `calculate_costs()` so `grand_total_cost` is fresh.

### 5.1 The three price bands

```
margin = target_margin_pct  (default 30)

floor_price     = grand_total_cost × 1.10                # absolute minimum: covers 10% buffer
standard_price  = grand_total_cost / (1 − margin/100)    # delivers the target margin
                  (if margin >= 100, fallback = grand_total_cost × 2 to avoid divide-by-zero)
premium_price   = standard_price × 1.25                  # +25% over standard
```

### 5.2 Recommended price = band picker

```
band = recommended_band  (default "Standard")

if band == "Conservative": recommended_price = floor_price
if band == "Premium":      recommended_price = premium_price
otherwise:                  recommended_price = standard_price
```

### 5.3 Derived headline metrics

```
margin_at_recommended  = (recommended_price − grand_total_cost) / recommended_price × 100
price_per_hour         = recommended_price / grand_total_hours
amc_suggested          = recommended_price × 0.18      # standard 18% annual maintenance
```

| Field | What it means |
|---|---|
| `floor_price` | Absolute minimum quote you can offer without losing money. |
| `standard_price` | Default quote at target margin. |
| `premium_price` | Premium positioning (urgency, scarcity, brand value). |
| `recommended_price` | What the form actually proposes — driven by the band. |
| `margin_at_recommended` | The gross margin % the recommended price delivers. |
| `price_per_hour` | Sanity check — keep it within the market band for ERPNext implementation. |
| `amc_suggested` | Suggested annual maintenance contract figure. 18% of project value. |
| `pricing_notes` | Free-text justification for the chosen band. |

---

## 6. Scenario analysis + break-even — `calculate_break_even()` + `get_scenario_data()`

Section L is rendered in two parts.

### 6.1 The four scenarios (rendered as the HTML table on the form)

Built by `get_scenario_data(docname)` and rendered by the client script's `update_scenario_table(frm)`. Both call the same math:

```
For each scenario (Optimistic / Base / Pessimistic / Custom):
    hours        = grand_total_hours × multiplier
    team_cost    = hours × blended_hourly_rate
    total_cost   = team_cost + direct_cost_total + indirect_cost_total + infrastructure_cost_total
    gross_profit = recommended_price − total_cost
    margin_pct   = gross_profit / recommended_price × 100
    status       = "Profit"  if gross_profit ≥ 0
                   "Loss"    otherwise
```

| Scenario | Multiplier | Reading |
|---|---:|---|
| Optimistic | **0.85** | Team is sharp, requirements are clear, no rework. |
| Base | **1.00** | Reality matches the estimate. |
| Pessimistic | **1.30** | Requirements drift, third-party delays, junior team. |
| Custom | `scenario_custom_pct / 100` | Whatever % the user types into `scenario_custom_pct` — instant what-if. |

The whole table re-renders client-side every time the user changes hours, rates, costs, or the custom %.

### 6.2 Break-even hours

How long can the team take before the project tips into loss?

```
non_team_cost      = direct_cost_total + indirect_cost_total + infrastructure_cost_total
break_even_hours   = (recommended_price − non_team_cost) / blended_hourly_rate
break_even_pct     = break_even_hours / grand_total_hours × 100
break_even_note    = "You break even if the team takes up to {break_even_hours} hours
                      ({break_even_pct}% of the estimate). Beyond that, the project is at a loss."
```

| Reading | What to do |
|---|---|
| `break_even_pct > 130%` | Comfortable margin — Pessimistic scenario still profitable. Standard pricing is safe. |
| `break_even_pct` 100–130% | Pessimistic scenario goes red. Push for Premium band or de-scope. |
| `break_even_pct < 100%` | Even the Base scenario loses money — re-cost or refuse. |

---

## 7. Auto-creation on status = Won — `handle_status_change()`

When status flips to Won (and the estimate isn't already linked to a project):

1. **Project** — created with `customer = client_name`, `expected_end_date = expected_go_live`, `estimated_costing = recommended_price`.
2. **Tasks** — one per Module Selection row (included ones only), one per customization sub-block, one per Custom Module Request, one per Integration Requirement. Each `exp_hours` = the row's `final_hours`.
3. **Sales Order** — draft, single line `"ERPNext Implementation"` at `recommended_price`. Created with `ignore_mandatory` to avoid blocking on item-master gaps.
4. **Back-links** — `linked_project` and `linked_sales_order` get filled on the estimate.
5. **Notification** — in-app realtime ping to `assigned_pre_sales` plus every team member with role = Project Manager.

---

## 8. Team revision snapshots — `save_team_version(reason)`

Whitelisted method, fired from the "Save Team as Version" custom button.

Every snapshot writes one row to `team_revisions`:

```
team_snapshot     = json.dumps([
    {employee, role, hourly_cost, allocated_hours, total_cost, is_active},
    …
])
total_team_cost   = SUM(total_cost) for active members
total_hours       = SUM(allocated_hours) for active members
version_label     = "V{N}"  where N = current revision count + 1
revised_on        = now()
revised_by        = current user
revision_reason   = user-entered note
```

The Team Revision Comparison report (Reports → tbo analytics) reads these snapshots to show V1 vs V2 vs Current side-by-side.

---

## 9. Child DocType field reference (every column, every type)

### 9.1 Module Selection

| Field | Type | Source | Notes |
|---|---|---|---|
| `module` | Link → ERP Module Master | Manual | Required. |
| `is_included` | Check, default 1 | Manual | Uncheck to leave a module in the row but exclude its hours from the totals. |
| `priority` | Select | Manual | Must Have / Should Have / Nice to Have / Future Phase. |
| `phase` | Select | Manual | Phase 1 / 2 / 3. |
| `complexity` | Select | Manual | `1 — Standard` (1.0×) or `2 — Complex` (1.6×). |
| `ai_estimated_hours` | Float | **Calculated** (§2.1) | Read-only. |
| `leader_estimated_hours` | Float | Manual | Override; wins if > 0. |
| `final_hours` | Float | **Calculated** (§3) | `leader_estimated_hours` if set else `ai_estimated_hours`. |
| `customization_required` | Check | Manual | Toggles visibility of the customization sub-block. |
| `customization_type` | Select | Manual | Drives `base_customization_hours` lookup (§2.2). |
| `customization_description` | Text Editor | Manual | |
| `customization_ai_hours` | Float | **Calculated** (§2.2) | Read-only. |
| `customization_manual_hours` | Float | Manual | Override. |
| `customization_final_hours` | Float | **Calculated** (§3) | |
| `total_module_hours` | Float | **Calculated** (§3) | `final_hours + customization_final_hours`. |
| `complexity_notes` | Small Text | Manual (visible only when complexity = 2) | Why this module is complex. |
| `row_notes` | Small Text | Manual | |

### 9.2 Custom Module Request

| Field | Type | Source | Notes |
|---|---|---|---|
| `module_name` | Data | Manual | Required. |
| `phase`, `priority`, `complexity` | Select | Manual | Same as Module Selection. |
| `ai_estimated_hours` | Float | **Calculated** (§2.3) | Read-only. |
| `leader_estimated_hours` | Float | Manual | Override. |
| `final_hours` | Float | **Calculated** (§3) | |
| `business_purpose`, `functional_description`, `technical_approach` | Text Editor | Manual | Becomes the developer brief on Won. |
| `needs_integration` | Check | Manual | Reveals integration_system + integration_hours. |
| `integration_system` | Data | Manual | E.g. "Zoho", "PayPal". |
| `integration_hours` | Float | Manual | Adds to `total_hours`. |
| `needs_reports` | Check | Manual | Reveals report_count + report_hours. |
| `report_count` | Int | Manual | Drives the per-report hours add in §2.3. |
| `report_hours` | Float | Manual | Adds to `total_hours`. |
| `total_hours` | Float | **Calculated** | `final_hours + integration_hours + report_hours`. |
| `assumptions`, `risks`, `open_questions` | Text Editor | Manual | These become contract clauses. |

### 9.3 Integration Requirement

| Field | Type | Source | Notes |
|---|---|---|---|
| `integration_type` | Link → Integration Type Master | Manual | Drives base hours lookup (§2.4). |
| `integration_name` | Data | Manual | E.g. "WhatsApp via Twilio". |
| `direction` | Select | Manual | One-way (push/pull) / Bidirectional / Real-time webhook. |
| `complexity` | Select | Manual | C1 / C2. |
| `phase` | Select | Manual | |
| `ai_estimated_hours` | Float | **Calculated** (§2.4) | Read-only. |
| `manual_hours` | Float | Manual | Override. |
| `final_hours` | Float | **Calculated** (§3) | |
| `third_party_provider` | Data | Manual | Twilio, AWS, Gupshup, etc. |
| `api_docs_available` | Check | Manual | Reduces uncertainty; tracked for reporting. |
| `description`, `notes` | Text Editor / Small Text | Manual | |

### 9.4 Team Composition

| Field | Type | Source | Notes |
|---|---|---|---|
| `employee` | Link → Employee | Manual | When picked, triggers `get_employee_hourly_cost`. |
| `role` | Select | Manual | Required. Project Manager, Senior Functional Consultant, etc. |
| `rate_card` | Link → Rate Card | (Reserved) | Legacy fallback — not consulted by the active salary-based hourly cost logic. |
| `hourly_cost` | Currency | **Auto-fetched** from HRMS via `get_employee_hourly_cost` | Read-only. See §4.1. |
| `ai_suggested_hours` | Float | (Reserved for future ML allocation) | Read-only, currently 0. |
| `allocated_hours` | Float | Manual | Required. Drives team cost + project duration. |
| `total_cost` | Currency | **Calculated** | `hourly_cost × allocated_hours`. |
| `is_active_in_current_version` | Check, default 1 | Manual | Uncheck to exclude from cost calculations without deleting the row. |
| `modules_responsible`, `notes` | Small Text | Manual | |

### 9.5 Team Revision

All fields populated by `save_team_version` — see §8.

### 9.6 Direct Cost Item

| Field | Type | Source | Notes |
|---|---|---|---|
| `cost_item` | Data | Manual / quick-add buttons | E.g. "Frappe Cloud Hosting". |
| `category` | Select | Manual | Hosting / Software License / Third-party API / Tools / Travel / Other. |
| `vendor` | Data | Manual | |
| `monthly_cost` | Currency | Manual | Required. |
| `project_duration_months` | Int | **Auto-fetched** from `duration_months` | Read-only. |
| `is_one_time` | Check | Manual | Switches the formula (§4.3). |
| `total_cost` | Currency | **Calculated** (§4.3) | |
| `notes` | Small Text | Manual | |

### 9.7 Indirect Cost Item

| Field | Type | Source | Notes |
|---|---|---|---|
| `cost_item` | Data | Manual | E.g. "HR Manager cost". |
| `category` | Select | Manual | HR & Admin / Finance / Management / Office / Utilities / Other. |
| `monthly_total_cost` | Currency | Manual | Required. Full monthly cost of this function. |
| `allocation_method` | Select | Manual | (Reserved, not yet branched). |
| `project_share_pct` | Float | Manual | The % of this overhead to attribute to this project. |
| `project_duration_months` | Int | **Auto-fetched** | Read-only. |
| `allocated_amount` | Currency | **Calculated** (§4.4) | |
| `notes` | Small Text | Manual | |

### 9.8 Infrastructure Cost Item

| Field | Type | Source | Notes |
|---|---|---|---|
| `cost_item` | Data | Manual | E.g. "Laptop depreciation", "Electricity". |
| `category` | Select | Manual | Laptop / Electricity / Internet / Equipment / Software / Other. |
| `total_monthly_company_cost` | Currency | Manual | Required. Full company-wide cost before splitting. |
| `split_method` | Select | Manual | Per Head / By Hours / By Project Count / Fixed Amount. Drives the formula in §4.5. |
| `company_total_employees` | Int | Manual | Used by Per Head split. |
| `project_team_size` | Int | **Auto-fetched** from team size | Read-only. |
| `project_duration_months` | Int | **Auto-fetched** | Read-only. |
| `allocated_amount` | Currency | **Calculated** (§4.5) | |
| `notes` | Small Text | Manual | |

---

## 10. Reading the form, top to bottom

The form layout mirrors the calculation pipeline — sections you fill in feed the sections below them, which are read-only.

```
[A. Client Details]            ← manual: client, size, migration flag
[B. Module Selection]          ← manual: pick modules, complexity drives AI hours
[C. Custom Module Requests]    ← manual: bespoke work
[D. Integration Requirements]  ← manual: WhatsApp, biometric, etc.
[E. Team Composition]          ← manual: who + how many hours
[F. Team Revision History]     ← auto-snapshotted via "Save as Version"
[G. Direct Costs]              ← manual + quick-add presets
[H. Indirect Costs]            ← manual
[I. Infrastructure & Shared]   ← manual
─────────── Below the line, everything is read-only & auto-calculated ───────────
[J. Estimation Summary]        ← total hours, project duration, blended rate
[K. Pricing & Profitability]   ← floor / standard / premium, recommended, margin
[L. Scenario Analysis]         ← optimistic / base / pessimistic + custom, break-even
[Linked Records]               ← project + sales order once Won
```

---

## 11. Where the math lives in code

| Behaviour | File | Function |
|---|---|---|
| Hour estimation (§2) | [implementation_estimate.py](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py) | `calculate_ai_estimates` |
| Hour roll-up (§3) | same | `calculate_final_hours` |
| Cost calc (§4) | same | `calculate_costs` |
| Pricing (§5) | same | `calculate_pricing` |
| Break-even (§6.2) | same | `calculate_break_even` |
| Scenario table (§6.1) — server | same | `get_scenario_data` |
| Scenario table (§6.1) — client | [implementation_estimate.js](tbo_analytics/public/js/implementation_estimate.js) | `update_scenario_table` |
| Hourly cost from HRMS (§4.1) | implementation_estimate.py | `get_employee_hourly_cost` |
| Won → Project + Tasks + SO (§7) | [handlers.py](tbo_analytics/tbo_analytics/handlers.py) | `handle_status_change`, `_create_project_from_estimate` |
| Snapshot (§8) | implementation_estimate.py | `save_team_version` |
| Live recalculation on every field edit | implementation_estimate.js | `recalc_hour_totals`, `recalc_all_costs`, `recalc_pricing`, `update_scenario_table` |

Constants in one place:

| Constant | File | Value |
|---|---|---|
| `COMPANY_SIZE_FACTORS` | implementation_estimate.py | Micro 0.8 / Small 1.0 / Medium 1.2 / Large 1.4 / Enterprise 1.7 |
| `CUSTOMIZATION_BASE_HOURS` | same | Custom Field 4 / Form 16 / Workflow 12 / Report 10 / Print 10 / API 24 / Other 8 |
| `SCENARIO_MULTIPLIERS` | same | Optimistic 0.85 / Base 1.00 / Pessimistic 1.30 |
| `MONTHLY_HOURS` | same | 22 × 6 = 132 (working days × hours/day) |
| Complexity multiplier | inline in `calculate_ai_estimates` | C2 → 1.6, C1 → 1.0 |
| Migration factor | inline | 1.15 if `data_migration_required` else 1.0 |
| Floor multiplier | `calculate_pricing` | × 1.10 |
| Premium multiplier | `calculate_pricing` | standard × 1.25 |
| AMC rate | `calculate_pricing` | recommended × 0.18 |
