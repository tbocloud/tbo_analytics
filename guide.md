# ERPNext Implementation Estimator — Frappe App Specification
### For: Antigravity Development Team
### Document type: Full Build Specification — Technical + Functional

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [App Structure](#2-app-structure)
3. [DocType Architecture](#3-doctype-architecture)
   - 3.1 Implementation Estimate (Master DocType)
   - 3.2 Client Details Section
   - 3.3 Module Selection (Child Table)
   - 3.4 Custom Module Request (Child Table)
   - 3.5 Integration Requirements (Child Table)
   - 3.6 Team Composition (Child Table)
   - 3.7 Team Revision History (Child Table)
   - 3.8 Direct Cost Items (Child Table)
   - 3.9 Indirect Cost Items (Child Table)
   - 3.10 Infrastructure & Shared Cost (Child Table)
   - 3.11 Supporting Masters
4. [Field-Level Specifications](#4-field-level-specifications)
5. [Hour Estimation Logic](#5-hour-estimation-logic)
6. [Cost Calculation Engine](#6-cost-calculation-engine)
7. [Profitability & Scenario Engine](#7-profitability--scenario-engine)
8. [Team Rearrangement Feature](#8-team-rearrangement-feature)
9. [Workflow & Approval](#9-workflow--approval)
10. [Reports](#10-reports)
11. [Dashboards](#11-dashboards)
12. [Client Scripts (UI Logic)](#12-client-scripts-ui-logic)
13. [Server Scripts & Hooks](#13-server-scripts--hooks)
14. [Permissions](#14-permissions)
15. [Build Sequence & Time Estimate](#15-build-sequence--time-estimate)

---

## 1. Project Overview

### What this app is

A Frappe/ERPNext custom app that allows an ERPNext implementation company to:

- Capture a new client's module requirements in a structured form
- Automatically estimate implementation hours (AI-assisted, with manual override)
- Build a team and assign hours per employee role
- Include all integration requirements (WhatsApp, biometric, mobile, website, etc.)
- Calculate full project cost — direct, indirect, and shared infrastructure
- Determine the minimum price needed for profitability
- Model scenarios — what happens if team takes longer than estimated
- Track ongoing progress vs. estimate in real time
- Rearrange team composition and compare cost impact (V1 vs V2)
- Generate rich reports and dashboards for leadership

### App name

```
erpnext_estimator
```

### Depends on

- `frappe` (core)
- `erpnext` (for Employee, Project, Task, Salary Slip links)
- `hrms` (for Employee Cost Rate)

---

## 2. App Structure

```
erpnext_estimator/
├── erpnext_estimator/
│   ├── __init__.py
│   ├── hooks.py
│   ├── doctype/
│   │   ├── implementation_estimate/
│   │   ├── module_selection/               ← child table
│   │   ├── custom_module_request/          ← child table
│   │   ├── integration_requirement/        ← child table
│   │   ├── team_composition/               ← child table
│   │   ├── team_revision/                  ← child table (stores V1/V2 snapshots)
│   │   ├── direct_cost_item/               ← child table
│   │   ├── indirect_cost_item/             ← child table
│   │   ├── infrastructure_cost_item/       ← child table
│   │   ├── erp_module_master/              ← supporting master
│   │   ├── rate_card/                      ← supporting master
│   │   └── integration_type_master/        ← supporting master
│   ├── report/
│   │   ├── estimate_vs_actual_hours/
│   │   ├── time_coverage_tracker/
│   │   ├── ai_vs_leader_estimate/
│   │   ├── profitability_scenarios/
│   │   └── project_cost_breakdown/
│   ├── dashboard/
│   │   ├── implementation_overview/
│   │   └── project_health/
│   ├── public/
│   │   └── js/
│   │       └── implementation_estimate.js  ← all client scripts
│   └── templates/
│       └── print_formats/
│           └── estimate_proposal.html
```

---

## 3. DocType Architecture

### 3.1 Implementation Estimate — Master DocType

This is the **central document**. One record per client engagement/proposal.

**Module:** `erpnext_estimator`
**Naming series:** `EST-.YYYY.-####`
**Is Submittable:** Yes
**Has Timeline:** Yes
**Track Changes:** Yes

**Sections layout (in order on the form):**

```
┌─────────────────────────────────────────────────────────┐
│  Section A: Client Details                              │
│  Section B: Module Selection           [Child Table]    │
│  Section C: Custom Module Requests     [Child Table]    │
│  Section D: Integration Requirements   [Child Table]    │
│  Section E: Team Composition           [Child Table]    │
│  Section F: Team Revision History      [Child Table]    │
│  Section G: Direct Costs               [Child Table]    │
│  Section H: Indirect Costs             [Child Table]    │
│  Section I: Infrastructure & Shared    [Child Table]    │
│  Section J: Estimation Summary         [Calculated]     │
│  Section K: Pricing & Profitability    [Calculated]     │
│  Section L: Scenario Analysis          [Calculated]     │
└─────────────────────────────────────────────────────────┘
```

---

### 3.2 Client Details Section (fields on master DocType)

| Field name | Type | Label | Notes |
|---|---|---|---|
| `client_name` | Link → Customer | Client Name | Required |
| `contact_person` | Link → Contact | Contact Person | |
| `industry` | Link → Industry Type | Industry | |
| `company_size` | Select | Company Size | Micro / Small / Medium / Large / Enterprise |
| `number_of_users` | Int | Number of Users | |
| `number_of_companies` | Int | Number of Legal Entities | Default 1 |
| `current_system` | Data | Current System | e.g. Tally, SAP, Excel |
| `data_migration_required` | Check | Data Migration Required | Triggers migration hours |
| `migration_years` | Int | Years of Data to Migrate | Visible only if migration checked |
| `project_type` | Select | Project Type | Fresh / Upgrade / Add-on / Re-implementation |
| `client_technical_level` | Select | Client Technical Level | None / Basic / Intermediate / Advanced |
| `expected_go_live` | Date | Expected Go-Live Date | |
| `pre_sales_notes` | Text Editor | Pre-Sales Notes | Free text, no character limit |
| `assigned_pre_sales` | Link → User | Assigned Pre-Sales | |
| `enquiry_date` | Date | Enquiry Date | Default today |
| `status` | Select (Workflow) | Status | Draft / Under Review / Approved / Won / Lost |

---

### 3.3 Module Selection — Child Table

**DocType name:** `Module Selection`
**Parent field:** `module_selections`

| Field name | Type | Label | Notes |
|---|---|---|---|
| `module` | Link → ERP Module Master | Module | Required |
| `is_included` | Check | Include | Default checked |
| `ai_estimated_hours` | Float | AI Estimated Hours | **Read-only. Placeholder: "Auto-calculated"** |
| `leader_estimated_hours` | Float | Leader Estimate (hrs) | Manual override by team lead |
| `final_hours` | Float | Final Hours | Read-only. = leader if set, else AI |
| `customization_required` | Check | Customization Needed | |
| `customization_type` | Select | Customization Type | Custom Field / Custom Form / Workflow / Report / Print Format / API / Other — visible only if customization checked |
| `customization_description` | Text Editor | Customization Details | Full notes field. Visible only if customization checked. Placeholder: "Describe what the client needs that standard ERPNext doesn't provide. Include workflows, fields, rules, and any screen mockups or references." |
| `customization_ai_hours` | Float | Customization AI Hours | **Read-only. Placeholder: "Auto-calculated"** |
| `customization_manual_hours` | Float | Customization Manual Hours | Manual override |
| `customization_final_hours` | Float | Customization Final Hours | Read-only. = manual if set, else AI |
| `complexity` | Select | Complexity | 1 — Standard / 2 — Complex |
| `complexity_notes` | Small Text | Complexity Notes | Why it's complex. Visible when complexity = 2 |
| `priority` | Select | Priority | Must Have / Should Have / Nice to Have / Future Phase |
| `phase` | Select | Phase | Phase 1 / Phase 2 / Phase 3 |
| `total_module_hours` | Float | Total Hours | Read-only. = final_hours + customization_final_hours |
| `row_notes` | Small Text | Notes | General notes for this module row |

> **Placeholder text behaviour:**
> - `ai_estimated_hours`: Shows grey placeholder text "Calculating…" when AI hasn't run yet, "N/A" if module has no historical data. Field is always read-only.
> - `customization_ai_hours`: Same behaviour.
> - `final_hours` and `customization_final_hours`: Read-only, no placeholder — computed automatically.

---

### 3.4 Custom Module Request — Child Table

**DocType name:** `Custom Module Request`
**Parent field:** `custom_module_requests`

| Field name | Type | Label | Notes |
|---|---|---|---|
| `module_name` | Data | Module Name | What the client calls it |
| `business_purpose` | Text Editor | Business Purpose | Why this is needed. Placeholder: "What business problem does this solve? What happens today without it?" |
| `functional_description` | Text Editor | Functional Description | Placeholder: "Describe inputs, process steps, outputs, user roles, automation rules, and any integration with other modules. This becomes the developer brief." |
| `technical_approach` | Text Editor | Technical Approach | Filled by Tech Lead. Placeholder: "New DocType / extend existing / custom script / integration?" |
| `complexity` | Select | Complexity | 1 — Simple / 2 — Complex |
| `ai_estimated_hours` | Float | AI Estimated Hours | **Read-only. Placeholder: "Auto-calculated from complexity"** |
| `leader_estimated_hours` | Float | Leader Hours | Manual override |
| `final_hours` | Float | Final Hours | Read-only. = leader if set, else AI |
| `needs_integration` | Check | Needs External Integration | |
| `integration_system` | Data | External System | Visible if needs_integration. e.g. Zoho, PayPal |
| `integration_hours` | Float | Integration Hours | Manual |
| `needs_reports` | Check | Custom Reports Needed | |
| `report_count` | Int | No. of Reports | Visible if needs_reports |
| `report_hours` | Float | Report Hours | Manual |
| `assumptions` | Text Editor | Assumptions | Placeholder: "List everything this estimate assumes — e.g. 'Client will provide API docs', 'Max 3 report templates'. These become contract clauses." |
| `risks` | Text Editor | Risks | Placeholder: "What could make this take longer? e.g. changing requirements, third-party delays, unclear workflow." |
| `open_questions` | Text Editor | Open Questions | Placeholder: "Questions that must be answered before finalising scope." |
| `phase` | Select | Phase | Phase 1 / Phase 2 / Phase 3 |
| `priority` | Select | Priority | Must Have / Should Have / Nice to Have |
| `total_hours` | Float | Total Hours | Read-only. = final_hours + integration_hours + report_hours |

---

### 3.5 Integration Requirements — Child Table

**DocType name:** `Integration Requirement`
**Parent field:** `integration_requirements`

| Field name | Type | Label | Notes |
|---|---|---|---|
| `integration_type` | Link → Integration Type Master | Integration Type | |
| `integration_name` | Data | Integration Name | e.g. "WhatsApp Business API via Twilio" |
| `direction` | Select | Direction | One-way (push) / One-way (pull) / Bidirectional / Real-time webhook |
| `description` | Text Editor | Description | Placeholder: "What data flows? Which ERPNext DocTypes are involved? What triggers the sync? What happens on failure?" |
| `third_party_provider` | Data | Third-party Provider | e.g. Twilio, AWS, Gupshup |
| `api_docs_available` | Check | API Docs Available | Affects estimate confidence |
| `ai_estimated_hours` | Float | AI Estimated Hours | **Read-only. Placeholder: "Auto-calculated"** |
| `manual_hours` | Float | Manual Hours | Override |
| `final_hours` | Float | Final Hours | Read-only |
| `complexity` | Select | Complexity | 1 — Standard / 2 — Complex |
| `phase` | Select | Phase | Phase 1 / Phase 2 / Phase 3 |
| `notes` | Small Text | Notes | |

**Integration Type Master pre-fill list:**
WhatsApp Business API, Biometric Device, Mobile App (Android), Mobile App (iOS), Website / Landing Page, Payment Gateway, SMS Gateway, Email Service, ERP-to-ERP Sync, Custom API, Barcode / QR Scanner, GPS / Location, E-commerce Platform, Accounting Software, Tally Import, Bank Feed, Government Portal (GST/TDS)

---

### 3.6 Team Composition — Child Table

**DocType name:** `Team Composition`
**Parent field:** `team_members`

| Field name | Type | Label | Notes |
|---|---|---|---|
| `employee` | Link → Employee | Employee | |
| `role` | Select | Role | See role list below |
| `rate_card` | Link → Rate Card | Rate Card | Auto-fetched from employee |
| `hourly_cost` | Currency | Hourly Cost (₹) | Auto-fetched. Read-only |
| `ai_suggested_hours` | Float | AI Suggested Hours | **Read-only. Placeholder: "Auto-allocated"** |
| `allocated_hours` | Float | Allocated Hours | **Manual. Required** |
| `total_cost` | Currency | Cost for This Employee | Read-only. = hourly_cost × allocated_hours |
| `modules_responsible` | Small Text | Modules / Tasks | Which modules this person handles |
| `notes` | Small Text | Notes | |
| `is_active_in_current_version` | Check | Active | For team revision: uncheck to exclude from V2 |

**Role list:**
Project Manager, Senior Functional Consultant, Junior Functional Consultant, Senior Developer, Junior Developer, QA / Tester, Business Analyst, DevOps Engineer, Project Coordinator, Support Engineer, Training Specialist, UX Designer, Data Migration Specialist

---

### 3.7 Team Revision History — Child Table

**DocType name:** `Team Revision`
**Parent field:** `team_revisions`

Stores snapshots of the team composition so V1 and V2 can be compared side by side.

| Field name | Type | Label | Notes |
|---|---|---|---|
| `version_label` | Data | Version | e.g. "V1 — Original", "V2 — After removing junior dev" |
| `revised_on` | Datetime | Revised On | Auto-set |
| `revised_by` | Link → User | Revised By | Auto-set |
| `team_snapshot` | JSON | Team Snapshot | Serialised team_members table at the time of revision |
| `total_team_cost` | Currency | Total Team Cost | Computed from snapshot |
| `total_hours` | Float | Total Hours | |
| `revision_reason` | Small Text | Reason for Change | |

> The "Save as Version" button (custom button on form) triggers a Server Script that serialises the current `team_members` child table into a JSON snapshot and appends a row here. The comparison report (Section 10) reads from this table.

---

### 3.8 Direct Cost Items — Child Table

**DocType name:** `Direct Cost Item`
**Parent field:** `direct_costs`

| Field name | Type | Label | Notes |
|---|---|---|---|
| `cost_item` | Data | Cost Item | e.g. "ERPNext Cloud Hosting (Frappe Cloud)" |
| `category` | Select | Category | Hosting / Software License / Third-party API / Tools / Travel / Other |
| `vendor` | Data | Vendor / Provider | |
| `monthly_cost` | Currency | Monthly Cost (₹) | |
| `project_duration_months` | Int | Duration (months) | Auto-fetched from estimate duration |
| `total_cost` | Currency | Total Cost | Read-only. = monthly × duration |
| `is_one_time` | Check | One-time Cost | If checked, total_cost = monthly_cost (no × months) |
| `notes` | Small Text | Notes | |

**Pre-fill suggestions (show as quick-add buttons on the form):**
- Frappe Cloud Hosting
- Claude AI API (if AI features used)
- SMS Gateway
- WhatsApp API
- Domain & SSL
- Third-party Integrations

---

### 3.9 Indirect Cost Items — Child Table

**DocType name:** `Indirect Cost Item`
**Parent field:** `indirect_costs`

Costs not directly billed to the project but consumed by it — overhead allocation.

| Field name | Type | Label | Notes |
|---|---|---|---|
| `cost_item` | Data | Cost Item | e.g. "HR Cost", "Accountant", "Office Admin" |
| `category` | Select | Category | HR & Admin / Finance / Management / Office / Utilities / Other |
| `monthly_total_cost` | Currency | Monthly Cost (₹) | Full monthly cost of this function in company |
| `allocation_method` | Select | Allocation Method | Per Head / By Hours / Fixed % / Manual |
| `project_share_pct` | Float | Project Share % | What % of this cost is allocated to this project |
| `project_duration_months` | Int | Duration (months) | Auto-fetched |
| `allocated_amount` | Currency | Allocated to Project | Read-only. = monthly × duration × share% |
| `notes` | Small Text | Notes | |

**Pre-fill suggestions:**
- HR Manager cost
- Accountant / Finance cost
- Office Rent (share)
- Electricity (share)
- Internet (share)
- Management overhead

---

### 3.10 Infrastructure & Shared Cost — Child Table

**DocType name:** `Infrastructure Cost Item`
**Parent field:** `infrastructure_costs`

Covers laptops, electricity, internet — shared assets that need project-wise splitting.

| Field name | Type | Label | Notes |
|---|---|---|---|
| `cost_item` | Data | Cost Item | e.g. "Laptop depreciation", "Electricity" |
| `category` | Select | Category | Laptop / Electricity / Internet / Equipment / Software / Other |
| `total_monthly_company_cost` | Currency | Total Monthly Company Cost | Full cost before splitting |
| `split_method` | Select | Split Method | Per Head / By Hours / By Project Count / Fixed Amount |
| `company_total_employees` | Int | Company Headcount | For per-head split |
| `project_team_size` | Int | Project Team Size | Auto-fetched from team_members count |
| `project_duration_months` | Int | Duration (months) | Auto-fetched |
| `allocated_amount` | Currency | Allocated to Project | Read-only. Calculated by split method |
| `notes` | Small Text | Notes | |

> **Electricity split example:**
> Company electricity = ₹30,000/month. Company has 20 employees. Project team = 4 people.
> Per-head split → ₹30,000 × (4/20) × project months = ₹6,000/month for 4-person team.

---

### 3.11 Supporting Masters

#### ERP Module Master

| Field | Type | Notes |
|---|---|---|
| `module_name` | Data (unique) | e.g. Accounts, Manufacturing |
| `module_code` | Data | ACC, MFG, etc. |
| `category` | Select | Finance / Operations / HR / CRM / Utility |
| `base_hours_complexity_1` | Float | Base hours at complexity 1 |
| `base_hours_complexity_2` | Float | Base hours at complexity 2 |
| `historical_avg_hours` | Float | Auto-updated by scheduled job |
| `historical_sample_count` | Int | How many completed projects fed this |
| `description` | Text Editor | What this module covers |
| `standard_task_templates` | Child Table | Task list for project creation |
| `is_active` | Check | |

#### Rate Card

| Field | Type | Notes |
|---|---|---|
| `role` | Select | Matches role list in Team Composition |
| `employee` | Link → Employee | Optional — for employee-specific rates |
| `hourly_cost` | Currency | Internal cost per hour |
| `effective_from` | Date | |
| `effective_to` | Date | Blank = current |
| `currency` | Link → Currency | Default INR |

#### Integration Type Master

Simple single-field master with `integration_type` (Data) and `base_hours` (Float), `description` (Text), `complexity_notes` (Small Text).

---

## 4. Field-Level Specifications

### Read-only AI fields — behaviour rules

Every AI-estimated hours field follows these rules without exception:

1. **Always read-only** — no direct editing by user
2. **Placeholder text** when empty: `"Auto-calculated"` (grey, italic)
3. **Populated by** a Server Script called on form save or on a "Recalculate AI Estimates" button click
4. **If no data is available** (new module, no historical projects): display `"N/A — set manually"` as placeholder, leave value as 0
5. **Manual override field sits next to it** and is always editable
6. **Final hours field** = manual override if set (not null, not 0), otherwise AI estimated hours

**Implementation in Client Script:**
```javascript
// For each AI hours field + its manual counterpart:
function resolve_final_hours(ai_val, manual_val) {
    if (manual_val && manual_val > 0) return manual_val;
    if (ai_val && ai_val > 0) return ai_val;
    return 0;
}
```

### Complexity field — 1 vs 2

| Value | Label | Meaning | Hour multiplier |
|---|---|---|---|
| 1 | Standard | Well-understood scope, clear requirements | 1.0× |
| 2 | Complex | Unclear requirements, non-standard business process, first-time implementation type | 1.6× |

When user selects complexity = 2:
- Show `complexity_notes` field (text field for explanation)
- AI hours field recalculates with 1.6× multiplier
- Yellow highlight on the row in the child table

---

## 5. Hour Estimation Logic

### 5.1 AI Estimation Source

The "AI estimation" in this app is **not a live API call** — it is a data-driven estimate pulled from:

1. `ERP Module Master.historical_avg_hours` (from completed ERPNext Projects)
2. Complexity multiplier (1.0× or 1.6×)
3. Company size modifier (larger companies = more configuration)
4. Data migration flag

This is fast, offline, and improves automatically as more projects complete.

> **Optional enhancement (Phase 2):** Add a button that calls the Anthropic Claude API with project context and returns an estimate. Store API-returned hours separately as `claude_api_hours`. The final hours logic remains the same.

### 5.2 Estimation formula per module row

```
ai_estimated_hours = (
    historical_avg_hours                     # from Module Master
    × complexity_multiplier                  # 1.0 or 1.6
    × company_size_factor                    # see table below
    × migration_factor                       # 1.0 or 1.15 if migration
)

customization_ai_hours = (
    base_customization_hours_by_type         # from lookup table
    × complexity_multiplier
)
```

**Company size factor:**

| Company size | Factor |
|---|---|
| Micro (<10) | 0.8 |
| Small (10–50) | 1.0 |
| Medium (50–200) | 1.2 |
| Large (200–1000) | 1.4 |
| Enterprise (1000+) | 1.7 |

**Base customization hours by type:**

| Type | Base hours |
|---|---|
| Custom Field (1–5 fields) | 4 |
| Custom Form | 16 |
| Workflow | 12 |
| Custom Report | 10 |
| Print Format | 10 |
| API / Integration | 24 |
| Other | 8 |

### 5.3 Custom module AI estimation

```
ai_estimated_hours = base_unit_hours × complexity_multiplier
    where:
        complexity 1 → base = 24 hours
        complexity 2 → base = 48 hours
    + integration_hours (if needs_integration)
    + (report_count × 10)  (if needs_reports)
```

### 5.4 Historical average updater (Scheduled Job — weekly)

```python
# hooks.py
scheduler_events = {
    "weekly": ["erpnext_estimator.tasks.update_historical_averages"]
}

# tasks.py
def update_historical_averages():
    # For each module in ERP Module Master:
    # Query completed Tasks where custom_module_tag = module
    # Calculate AVG(actual_time) from last 24 months
    # Update Module Master.historical_avg_hours
    # Log update with timestamp and sample count
    pass
```

---

## 6. Cost Calculation Engine

### 6.1 Team cost

```
team_cost = SUM(employee.hourly_cost × employee.allocated_hours)
            for all active employees in team_members
```

### 6.2 Direct costs

```
direct_cost_total = SUM(
    one_time items: cost_item.monthly_cost
    recurring items: cost_item.monthly_cost × project_duration_months
)
```

### 6.3 Indirect costs

```
indirect_cost_total = SUM(
    item.monthly_total_cost × (item.project_share_pct / 100) × project_duration_months
)
```

### 6.4 Infrastructure costs

```
infrastructure_cost_total = SUM(
    per_head method:
        item.total_monthly_company_cost
        × (project_team_size / company_total_employees)
        × project_duration_months

    by_project_count method:
        item.total_monthly_company_cost
        × (1 / active_project_count)   ← fetched from active Projects
        × project_duration_months

    fixed_amount method:
        item.allocated_amount
)
```

### 6.5 Grand total cost

```
grand_total_cost = team_cost
                 + direct_cost_total
                 + indirect_cost_total
                 + infrastructure_cost_total
```

### 6.6 Project duration

```
project_duration_months = CEIL(
    grand_total_hours / (team_size × 6 hours_per_day × 22 working_days)
)
```
Auto-calculated. Used in all duration-dependent cost fields.

---

## 7. Profitability & Scenario Engine

### 7.1 Pricing fields (Section K on form)

| Field | Type | Formula / Description |
|---|---|---|
| `target_margin_pct` | Float | Target gross margin %. Default 30. Editable. |
| `floor_price` | Currency | `grand_total_cost × 1.10` — absolute minimum |
| `standard_price` | Currency | `grand_total_cost / (1 - target_margin_pct/100)` |
| `premium_price` | Currency | `standard_price × 1.25` |
| `recommended_price` | Currency | System recommendation (see logic below) |
| `recommended_band` | Select | Conservative / Standard / Premium |
| `margin_at_recommended` | Float | `(recommended - cost) / recommended × 100` |
| `price_per_hour` | Currency | `recommended_price / grand_total_hours` |
| `amc_suggested` | Currency | `recommended_price × 0.18` (standard 18% AMC) |
| `pricing_notes` | Text Editor | Free text for pricing rationale |

### 7.2 Scenario Analysis (Section L on form)

Three scenarios are always computed and shown as a comparison table:

| Scenario | Hours assumption | Impact |
|---|---|---|
| **Optimistic** | Team completes in 85% of estimated hours | Best-case profit |
| **Base** | Team takes exactly estimated hours | Expected profit |
| **Pessimistic** | Team takes 130% of estimated hours | Worst-case loss/profit |

**Per-scenario computed fields:**

```
For each scenario:
    actual_hours = total_estimated_hours × scenario_multiplier
    actual_team_cost = actual_hours × blended_hourly_rate
    actual_total_cost = actual_team_cost + direct + indirect + infra
    gross_profit = recommended_price - actual_total_cost
    gross_margin = gross_profit / recommended_price × 100
    status = Profit / Break-even / Loss
```

**Display:** A 5-column table on the form (read-only, auto-updated):

```
┌────────────────┬────────────┬────────────┬────────────┐
│                │ Optimistic │    Base    │ Pessimistic│
├────────────────┼────────────┼────────────┼────────────┤
│ Hours          │   850      │  1,000     │  1,300     │
│ Team cost      │  ₹8.5L     │  ₹10L      │  ₹13L      │
│ Total cost     │  ₹10.2L    │  ₹12L      │  ₹15.2L    │
│ Gross profit   │  ₹4.8L     │  ₹3L       │  -₹0.2L    │
│ Margin %       │  32%       │  20%       │  -1.5%     │
│ Status         │  ✅ Profit │  ✅ Profit │  ❌ Loss   │
└────────────────┴────────────┴────────────┴────────────┘
```

A fourth column "Custom %" allows the user to input any multiplier (e.g. 150%, 200%) and see the impact immediately via client script.

### 7.3 Break-even analysis

```
break_even_hours = (recommended_price - direct - indirect - infra)
                   / blended_hourly_rate

break_even_pct_of_estimate = break_even_hours / total_estimated_hours × 100
```

Show as: "You break even if team takes up to X hours (Y% of estimate). Beyond that, the project is at a loss."

---

## 8. Team Rearrangement Feature

### 8.1 Concept

The team composition can be changed at any time (before or during the project). The system:

1. Keeps the **current team** in `team_members` child table (this is always the live version)
2. Every time a change is made and "Save as Version" is clicked, a snapshot is saved to `team_revisions`
3. Revisions are labelled V1, V2, V3, etc.
4. A comparison report (see Section 10) shows V1 vs V2 side by side

### 8.2 Save as Version button

- Custom button on Implementation Estimate form
- Appears after at least one team member is added
- On click: prompt for "Reason for change" → save snapshot

### 8.3 What happens when team changes

- `team_cost` recalculates instantly
- `grand_total_cost` recalculates
- `profitability_scenarios` recalculate
- `recommended_price` recalculates
- The form shows a banner: "Team was revised. Previous version saved as [V label]. See revision history."

### 8.4 Adding / removing employees

- **Add employee:** Add a row in `team_members`, set role and allocated hours → all costs update
- **Remove employee:** Uncheck `is_active_in_current_version` (soft remove) OR delete the row
- Soft remove is recommended — it keeps the employee visible in greyed-out state but excludes from cost calculations, and preserves the record for the revision comparison

### 8.5 Revision comparison (quick view on form)

Below `team_revisions` child table, a small HTML widget (using `frappe.ui.Dialog` or an inline Jinja block) shows:

```
V1 Total Cost: ₹12,40,000    Team: 5 people    Hours: 1,200
V2 Total Cost: ₹10,80,000    Team: 4 people    Hours: 1,050
Difference:    -₹1,60,000    -1 person         -150 hours
```

---

## 9. Workflow & Approval

### States

| State | Colour | Who can edit |
|---|---|---|
| Draft | Blue | Pre-Sales, Sales Manager |
| Under Review | Orange | Read-only (comments only) |
| Revision Requested | Red | Pre-Sales only |
| Approved | Green | No edits |
| Sent to Client | Purple | No edits |
| Won | Dark Green | No edits |
| Lost | Grey | No edits |
| On Hold | Yellow | Pre-Sales |

### Transitions

| From | Action | To | Role |
|---|---|---|---|
| Draft | Submit for Review | Under Review | Pre-Sales |
| Under Review | Approve | Approved | Sales Manager |
| Under Review | Request Revision | Revision Requested | Sales Manager |
| Revision Requested | Resubmit | Under Review | Pre-Sales |
| Approved | Send to Client | Sent to Client | Sales Manager |
| Sent to Client | Mark Won | Won | Sales Manager |
| Sent to Client | Mark Lost | Lost | Sales Manager |
| Any | Put on Hold | On Hold | Sales Manager |
| On Hold | Resume | Draft | Pre-Sales |

### On Won — auto project creation hook

When status → Won:
1. Create `Project` linked to Customer and Estimate
2. Create `Tasks` from Module Task Templates for each included module
3. Add `custom_module_tag` to each task (for historical averaging later)
4. Create `Sales Order` (draft) with recommended_price
5. Set `linked_project` and `linked_sales_order` on estimate
6. Send notification to Project Manager and Delivery Head

---

## 10. Reports

### Report 1: Time Coverage Tracker
**Type:** Script Report
**Purpose:** For each active project, show how much of the estimated time has been consumed and how much is left. This is the most-used operational report.

**Columns:**

| Column | Source |
|---|---|
| Project | tabProject |
| Linked Estimate | Implementation Estimate |
| Total Estimated Hours | estimate.grand_total_hours |
| Hours Logged (Actual) | SUM(tabTimesheet Detail.hours) for this project |
| Hours Remaining | estimated − actual |
| % Consumed | actual / estimated × 100 |
| Estimated End Date | project.expected_end_date |
| Projected End Date | today + (remaining / daily_burn_rate) |
| Days Ahead / Behind | projected − estimated end |
| Status Flag | On Track / At Risk / Overrun |

**Filters:** Project, Date range, Status flag, Client

**Visualisation:** Progress bar per project (% consumed), colour-coded by status flag.

---

### Report 2: AI Estimate vs Leader Estimate — Comparison
**Type:** Script Report
**Purpose:** Shows for every estimate, the difference between what the AI suggested and what the team lead manually set. Helps calibrate the AI model and identify where leads consistently over- or under-estimate.

**Columns:**

| Column | Notes |
|---|---|
| Estimate ID | |
| Client | |
| Module / Custom Module | |
| AI Estimated Hours | |
| Leader Estimated Hours | |
| Final Hours Used | |
| Difference (AI − Leader) | + means AI was higher |
| Variance % | |(AI − Leader)| / AI × 100 |
| Which was closer to Actual? | Post-project: compares both to actual |
| Actual Hours (post-project) | From Task actuals |

**Insight row at bottom:** "AI estimates were within 15% of actuals in 8 of 12 modules. Leader estimates were within 15% in 10 of 12. Leader estimates are more accurate for Manufacturing and HR modules."

**Filter:** Estimate, Module, Date range, Show only where AI and leader differ by > X%

---

### Report 3: Estimate vs Actual Hours (Post-project)
**Type:** Script Report
**Purpose:** After a project completes, compares what was estimated to what actually happened. Feeds back into Module Master for AI improvement.

**Columns:** Module, Estimated hours, Actual hours, Variance, Variance %, Over/Under, Notes from task

---

### Report 4: Profitability Scenarios Report
**Type:** Script Report
**Purpose:** Shows all three scenarios (Optimistic / Base / Pessimistic) for one or more estimates. Leadership uses this for go/no-go decisions and pricing approvals.

**Columns:** Estimate, Client, Scenario, Hours, Team Cost, Total Cost, Revenue, Gross Profit, Margin %, Status (Profit/Loss), Break-even Hours

**Chart:** Grouped bar chart — Revenue vs Cost for each scenario.

---

### Report 5: Project Cost Breakdown
**Type:** Script Report
**Purpose:** Full cost breakdown for a single estimate — every cost component itemised.

**Sections:**
- Team cost (by employee and role)
- Direct costs (by category)
- Indirect costs (by category)
- Infrastructure costs (by category)
- Grand total
- Recommended price
- Margin breakdown

---

### Report 6: Team Revision Comparison
**Type:** Script Report
**Purpose:** For an estimate with multiple team revisions, shows V1 vs V2 (and V3 etc.) side by side.

**Columns:** Version, Team Size, Employees, Total Allocated Hours, Total Team Cost, Grand Total Cost, Margin at Standard Price, Revision Date, Reason

---

## 11. Dashboards

### Dashboard 1: Implementation Overview (Sales/Pre-Sales view)

**Charts:**
1. **Pipeline by status** — Count of estimates by status (Draft / Under Review / Approved / Won / Lost) — Donut chart
2. **Revenue pipeline** — Sum of recommended_price by status — Bar chart
3. **Win rate** — Won / (Won + Lost) over last 12 months — Number card
4. **Average margin on won deals** — Number card
5. **Estimates by month** — Count of new estimates created per month — Line chart
6. **Top clients by pipeline value** — Horizontal bar

---

### Dashboard 2: Project Health (Delivery/PM view)

**Charts:**
1. **Time coverage heatmap** — All active projects, % of estimated hours consumed — Progress bars
2. **At-risk projects** — Projects where actual hours > 80% of estimate but % complete < 70% — Alert list
3. **Team utilisation** — Hours allocated vs hours logged per employee — Grouped bar
4. **Estimated vs actual hours trend** — Line chart comparing estimate accuracy over time
5. **AI vs leader estimate accuracy** — Which was closer to actuals in last 20 projects — Bar chart
6. **Cost overrun tracker** — Projects where actual cost is tracking above estimate — Number card with drill-down

---

## 12. Client Scripts (UI Logic)

### File: `public/js/implementation_estimate.js`

Key behaviours:

```javascript
frappe.ui.form.on('Implementation Estimate', {

    // 1. When company size or migration flag changes → recalculate AI hours
    company_size: function(frm) { recalculate_ai_hours(frm); },
    data_migration_required: function(frm) { recalculate_ai_hours(frm); },

    // 2. Recalculate all totals on any relevant field change
    refresh: function(frm) {
        recalculate_all_totals(frm);
        update_scenario_table(frm);
        show_revision_comparison(frm);
        set_ai_field_placeholders(frm);
        add_quick_add_buttons(frm);  // Direct cost quick-add
    },

    // 3. "Recalculate AI Estimates" button
    // 4. "Save as Version" button
    // 5. Go-live feasibility warning
    // 6. Scenario custom % field → update scenario table
});

frappe.ui.form.on('Module Selection', {
    complexity: function(frm, cdt, cdn) {
        // Highlight row yellow if complexity = 2
        // Show complexity_notes field
        // Recalculate ai_estimated_hours for that row
    },
    customization_required: function(frm, cdt, cdn) {
        // Show/hide customization fields
    },
    leader_estimated_hours: function(frm, cdt, cdn) {
        // Update final_hours = leader if set, else AI
        // Recalculate total_module_hours
        // Recalculate grand total
    },
    module: function(frm, cdt, cdn) {
        // Fetch base hours from ERP Module Master
        // Populate ai_estimated_hours
        // Set placeholder text
    }
});

frappe.ui.form.on('Team Composition', {
    employee: function(frm, cdt, cdn) {
        // Auto-fetch role and hourly_cost from Rate Card
        // Populate ai_suggested_hours based on role and total hours
    },
    allocated_hours: function(frm, cdt, cdn) {
        // Recalculate total_cost for this row
        // Recalculate grand total team cost
        // Recalculate all cost totals
        // Recalculate scenarios
    }
});
```

### Placeholder text implementation

```javascript
function set_ai_field_placeholders(frm) {
    const ai_fields = [
        'module_selections.ai_estimated_hours',
        'module_selections.customization_ai_hours',
        'custom_module_requests.ai_estimated_hours',
        'integration_requirements.ai_estimated_hours',
        'team_members.ai_suggested_hours'
    ];
    // Use frappe's grid API to set placeholder on each child table column
    // frm.fields_dict['module_selections'].grid.fields_map['ai_estimated_hours']
    //    .df.placeholder = 'Auto-calculated';
}
```

---

## 13. Server Scripts & Hooks

### hooks.py

```python
app_name = "erpnext_estimator"
app_title = "ERPNext Estimator"

doc_events = {
    "Implementation Estimate": {
        "before_save": "erpnext_estimator.handlers.calculate_ai_estimates",
        "on_submit":   "erpnext_estimator.handlers.validate_completeness",
        "on_update_after_submit": "erpnext_estimator.handlers.handle_status_change",
    },
    "Task": {
        "on_update": "erpnext_estimator.handlers.update_time_coverage",
    },
    "Timesheet": {
        "on_submit": "erpnext_estimator.handlers.update_time_coverage",
    }
}

scheduler_events = {
    "weekly": [
        "erpnext_estimator.tasks.update_historical_averages",
        "erpnext_estimator.tasks.refresh_time_coverage_cache",
    ]
}
```

### Key server-side handlers

**`calculate_ai_estimates(doc, method)`**
- Loops through `module_selections`
- For each row: fetches `historical_avg_hours` from ERP Module Master, applies complexity and company size multipliers
- Sets `ai_estimated_hours` on each row
- Does NOT overwrite `leader_estimated_hours`
- Updates `final_hours` = leader if set, else AI
- Recalculates all totals

**`handle_status_change(doc, method)`**
- When status → Won: creates Project, Tasks, Sales Order (as described in Section 9)

**`update_time_coverage(doc, method)`**
- When a Timesheet is submitted or a Task is updated, recalculates the time coverage cache for the linked project
- Updates a custom `actual_hours_logged` field on the Project
- Used by the Time Coverage Tracker report

**`update_historical_averages()`**
- Scheduled weekly
- Queries completed Tasks with `custom_module_tag` set
- Groups by module, calculates AVG(actual_time) for last 24 months
- Updates ERP Module Master records

---

## 14. Permissions

| Role | Create | Read | Write | Submit | Approve (workflow) | See Pricing |
|---|---|---|---|---|---|---|
| Pre-Sales | ✅ (own) | ✅ (own) | ✅ (own) | ✅ | ❌ | Standard price only |
| Sales Manager | ✅ | ✅ (all) | ✅ (all) | ✅ | ✅ | ✅ All |
| Delivery Head | ❌ | ✅ (all) | ❌ | ❌ | ✅ | ✅ All |
| Developer | ❌ | ✅ (linked project only) | ❌ | ❌ | ❌ | ❌ |
| Finance | ❌ | ✅ (all) | ❌ | ❌ | ❌ | ✅ All |
| System Manager | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 15. Build Sequence & Time Estimate

Build in this order to avoid dependency blocks:

| Phase | Tasks | Duration |
|---|---|---|
| **Phase 0** | Supporting masters (ERP Module Master, Rate Card, Integration Type Master). Fill with initial data. | 2–3 days |
| **Phase 1** | All child table DocTypes (Module Selection, Custom Module Request, Integration Requirement, Team Composition, Team Revision, Direct/Indirect/Infra cost items) | 3–4 days |
| **Phase 2** | Main DocType (Implementation Estimate) with all sections, fields, and layout | 2–3 days |
| **Phase 3** | Client scripts — auto-fetch, AI placeholder fields, real-time calculations, scenario table | 4–5 days |
| **Phase 4** | Server scripts — AI estimation engine, historical average updater, auto-project creation | 4–5 days |
| **Phase 5** | Workflow configuration + email notifications | 1–2 days |
| **Phase 6** | Reports (all 6) | 5–6 days |
| **Phase 7** | Dashboards (both) | 2–3 days |
| **Phase 8** | Print format (client-facing proposal PDF) | 1–2 days |
| **Phase 9** | UAT, bug fixes, data entry (module master, rate cards) | 3–4 days |
| **Phase 10** | Go-live, training, post-launch support | 2–3 days |
| **TOTAL** | With dedicated developer + consultant | **29–40 working days (6–8 weeks)** |

---

## Appendix A — Complexity 1 vs 2 — Per Module Reference

| Module | C1 base hours | C2 base hours | Notes |
|---|---|---|---|
| Accounts | 80 | 130 | Multi-company = always C2 |
| Inventory / Stock | 60 | 100 | Multi-warehouse = C2 |
| Purchase | 40 | 70 | |
| Sales | 50 | 85 | E-commerce integration = C2 |
| Manufacturing | 80 | 140 | Almost always C2 |
| HR & Payroll | 70 | 120 | Statutory compliance adds hours |
| CRM | 30 | 55 | |
| Projects Module | 20 | 40 | |
| Assets | 30 | 55 | |
| Quality | 25 | 45 | |
| POS / Retail | 40 | 75 | |
| Healthcare | 60 | 110 | Vertical — almost always C2 |
| Education | 55 | 100 | Vertical |

---

## Appendix B — Custom Module Base Hours by Complexity

| Complexity | Base hours | Integration add | Per report add |
|---|---|---|---|
| 1 — Simple | 24 | +16 | +8 per report |
| 2 — Complex | 48 | +32 | +12 per report |

---

## Appendix C — Integration Base Hours

| Integration type | C1 | C2 | Notes |
|---|---|---|---|
| WhatsApp Business API | 24 | 40 | Real-time = C2 |
| Biometric Device | 20 | 35 | Depends on device SDK |
| Mobile App (Android/iOS) | 40 | 80 | Per platform |
| Website integration | 20 | 40 | CMS type matters |
| Payment Gateway | 16 | 30 | Depends on provider |
| SMS Gateway | 8 | 16 | |
| ERP-to-ERP sync | 40 | 80 | Real-time = C2 |
| Tally import | 32 | 56 | Data quality dependent |
| Bank feed | 16 | 28 | |
| Government portal (GST/TDS) | 20 | 36 | |

---

## Appendix D — Scenario Multipliers (default)

| Scenario | Hours multiplier | Description |
|---|---|---|
| Optimistic | 0.85 | Team is experienced, requirements clear |
| Base | 1.00 | As estimated |
| Pessimistic | 1.30 | Requirement changes, team delays |
| Custom | User input | Any % the user wants to model |

These are editable defaults. The user can change them on the estimate form before running the scenario calculation.

---

*End of specification. Questions: contact the project owner before starting Phase 1.*