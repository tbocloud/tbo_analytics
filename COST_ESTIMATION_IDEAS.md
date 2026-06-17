# Advanced Cost Estimation — Ideas for `tbo_analytics`

> **Scope:** `tbo_analytics` is the **Implementation Estimate** app for **ERP / ERPNext / Frappe-based engagements only**. Digital Marketing, video shoots, content production etc. are separate business lines that don't go through this form. The ideas below treat ERP projects as the unit of estimation. Other departments' costs are still relevant — they show up as company-wide overhead that gets allocated to ERP projects via §1's auto-allocator.

The current app asks the user to **type in** direct/indirect/infrastructure cost rows from memory. That's fine for a v1 but produces guesses, not estimates. Below are concrete upgrades — each grounded in data you already have in the `tbo` site (GL, Timesheets, Salary Slips, Projects, Sales Invoices).

Ordered roughly **highest impact + lowest effort first.**

---

## 1. Pull indirect cost from the books, don't ask the user to type it

**Problem today.** The Indirect Costs table (Section H) asks the user to type `monthly_total_cost` and `project_share_pct` for every overhead line. They guess. The guess is usually 30–40% off from the books reality.

**Idea.** A "Load from books" button that:
1. Queries the last 6 months of GL entries against every `Indirect Expenses - TBO` leaf account.
2. Averages each account's monthly spend (`total / months`).
3. Pre-fills one Indirect Cost row per category with the real monthly figure.
4. Auto-computes `project_share_pct` using the **activity-based** formula:

   ```
   project_share_pct = (project's allocated_hours / company's avg monthly active hours) × 100
   ```

   Where `company's avg monthly active hours` comes from the last 3 months of submitted Timesheets.

**Why better.** The user can't accidentally under-allocate. The estimate's indirect cost matches what'll actually hit the books. No more "we forgot to include depreciation" misses.

**Implementation sketch.**
- New whitelisted method `pull_indirect_from_books(company, lookback_months=6)` → returns list of `(category, account, monthly_avg)`.
- New custom button on Section H: *"Load from books (last 6 months)"*.
- Use the same chart-of-accounts walk we built in `notebooks/expense_analysis.ipynb` §2.
- For `project_share_pct`, query: `SELECT AVG(hours_per_month) FROM tabTimesheet` to get the denominator.

**Tunables to expose.** Lookback window (3/6/12 months), exclude HR Expense subtree toggle, allocation basis (labour hours vs headcount vs project count).

---

## 2. ERP-archetype direct cost templates

**Problem today.** The Direct Cost quick-add buttons offer the same 5 presets (Frappe Cloud, Claude AI, SMS, WhatsApp, Domain) to every estimate. But a fresh multi-module ERPNext build needs Frappe Cloud sized for production + staging, GST API credits, integration tooling, and a one-time setup; a small Add-on customisation might need only a developer cloud account; an Upgrade project usually needs only a temporary staging server and a Tally-import tool.

**Idea — templates keyed off the existing `project_type` field.**

You already have `project_type` on the master with options `Fresh / Upgrade / Add-on / Re-implementation`. Use it as the dispatch key.

Plus a second dimension that matters for ERP work: **scale band** — Single-module / Standard (3-7 modules) / Comprehensive (8+ modules) / Industry-vertical (Healthcare / Education / Manufacturing / POS-Retail). Derive automatically from `module_selections` count + module categories.

A new `Direct Cost Template` DocType:

| Field | Type | Notes |
|---|---|---|
| `template_name` | Data | "Fresh Standard ERPNext", "Fresh Comprehensive", "Add-on", "Upgrade", "Re-implementation", "Industry Vertical" |
| `project_type` | Select | Mirrors master: Fresh / Upgrade / Add-on / Re-implementation. Blank = applies to all. |
| `scale_band` | Select | Single-module / Standard / Comprehensive / Industry vertical. Blank = applies to all. |
| `requires_integration` | Check | Template applies only when integrations are present. |
| `requires_migration` | Check | Template applies only when data_migration_required = 1. |
| `is_active` | Check | |
| `notes` | Text Editor | When to use this template + what's typically included |
| **`lines` (child table)** | Table → Direct Cost Template Line | The actual cost rows to load |

**Direct Cost Template Line** child:
| Field | Type | Notes |
|---|---|---|
| `cost_item` | Data | "Frappe Cloud — Production tier", "Frappe Cloud — Staging", "Claude AI API", "Tally Migration Tool", "GST API Credits", "SMS Gateway", "Domain & SSL" |
| `category` | Select | Hosting / Software License / Third-party API / Tools / Travel / Other |
| `vendor` | Data | Default vendor — editable per estimate |
| `default_monthly_cost` | Currency | Pre-fill |
| `is_one_time` | Check | Pre-fill |
| `notes` | Small Text | |

### Suggested seed templates for TBO

| Template | When it applies | Typical lines |
|---|---|---|
| **Fresh Standard ERPNext** | `project_type=Fresh` AND 3-7 modules | Frappe Cloud Production (₹5k/mo), Frappe Cloud Staging (₹2k/mo), Domain + SSL (₹500 one-time), GST API Credits (₹500/mo), SMS Gateway (₹500/mo) |
| **Fresh Comprehensive ERPNext** | `project_type=Fresh` AND 8+ modules | Above + Email Service (₹1.5k/mo), Backup storage (₹1k/mo), WhatsApp API (₹1.5k/mo) |
| **Fresh w/ Migration** | `project_type=Fresh` AND `data_migration_required=1` | Above + Tally / Excel migration tool (₹4k one-time), Data cleaning sandbox (₹3k/mo for 2 mo) |
| **Add-on / Customisation** | `project_type=Add-on` | Developer Frappe Cloud account (₹2k/mo), nothing else — the customer already has hosting |
| **Upgrade** | `project_type=Upgrade` | Staging server (₹3k/mo for project duration), Backup storage (₹500/mo), Code-diff tooling (₹500 one-time) |
| **Re-implementation** | `project_type=Re-implementation` | Same as Fresh Standard + parallel production env (₹5k/mo for 1 mo cut-over) |
| **Industry vertical (Healthcare / Education)** | A vertical module is selected | Above + Compliance-specific cloud add-on (₹2k/mo), Vertical training sandbox (₹1.5k/mo) |
| **+Integration add-on** | One per integration type, layered on top | WhatsApp (₹1.5k/mo), Biometric SDK license (₹800/mo), Payment gateway (depends), Government portal credits (₹500/mo) |

### Flow on the form

1. User fills Section A (client + `project_type` + `data_migration_required`) and Section B (module selection).
2. **Auto-derive `scale_band`** in JS:
   - 1 module → Single-module
   - 2-7 → Standard
   - 8+ → Comprehensive
   - Any module from `category in (Healthcare, Education, POS)` → Industry vertical
3. **Button "Load standard direct costs"** appears above Section G.
4. On click: server finds every active `Direct Cost Template` matching the project's profile (project_type, scale_band, requires_integration, requires_migration), unions their lines, dedups by `cost_item`, prepends to `direct_costs`.
5. User can edit, delete, or add more rows. Standard direct cost flow.

**Why better.** Pre-sales doesn't remember which Frappe Cloud tier to quote, whether to include GST API credits, what migration tooling costs. The catalogue evolves: as you complete more projects, you add lines that turned out to matter. Cost catalogue becomes institutional knowledge instead of tribal memory.

### Bonus — auto-suggest from past Won projects

Once you have 5+ Won estimates with matching `project_type` + `scale_band`, surface a "Past projects of this profile billed these direct costs:" widget showing the **median** monthly cost per `cost_item` from those Wons. Treat the templates as the starting catalogue; treat past actuals as the calibration.

```python
# Pseudocode for the suggestion query
SELECT cost_item, MEDIAN(monthly_cost) AS typical_monthly, COUNT(*) AS seen_in_n_projects
FROM `tabDirect Cost Item` dci
INNER JOIN `tabImplementation Estimate` ie ON dci.parent = ie.name
WHERE ie.status = 'Won'
  AND ie.project_type = :pt
  AND <scale_band condition>
GROUP BY cost_item
HAVING seen_in_n_projects >= 3
ORDER BY typical_monthly DESC
```

---

## 3. Multi-currency native estimates

**Problem today.** Everything is INR. But TBO bills 152 invoices in SAR, 56 in AED, 6 in QAR, 2 in USD — about 70% of revenue is foreign-currency. Today, when pre-sales builds an estimate for a KSA client, they have to mentally divide by ~22 to express it in SAR.

**Idea.** Add two fields on the master:

| Field | Type | Notes |
|---|---|---|
| `quoting_currency` | Link → Currency | Default = customer's billing currency. Drives the Section K price display. |
| `fx_buffer_pct` | Float | Default 5%. Padding added to recommended price to hedge FX exposure for the project duration. |

The math under the hood stays in INR (company currency), but Section K renders both:

```
Standard Price : ₹4,50,000  (SAR 18,367 @ 24.50)
Floor Price    : ₹2,80,000  (SAR 11,428 @ 24.50)
... with fx_buffer applied
```

`conversion_rate` pulled from `tabCurrency Exchange` at estimate time. Auto-pads recommended_price by `1 + fx_buffer_pct/100` when `quoting_currency != company_currency`.

**Why better.** No mental arithmetic for KSA/UAE clients. Pricing notes can explicitly state the SAR figure that goes into the quote document.

---

## 4. Live capacity check — "can the team actually do this?"

**Problem today.** Section E lets you allocate 500 hours to an employee in Phase 1, with no indication that the employee already has 800 hours committed to other projects. You build an estimate the team can't deliver.

**Idea.** New widget under Section E: **"Team capacity over project duration"**.

For each row in `team_members`:
1. Query timesheets + other open Implementation Estimates' team allocations for this employee.
2. Compute committed_hours per month for the next `project_duration_months`.
3. Compare against the employee's monthly capacity (132 hrs).
4. Show a red badge if `committed_hours + allocated_hours > 132 × duration`.

```
Senior Developer — Vinod
  Capacity     : 132 hrs/month × 4 months = 528 hrs
  Committed    : 410 hrs (Hydrotech, Calicut, Champion)
  This project : 200 hrs   ← OVER by 82 hrs
```

**Why better.** Catches over-commitment at estimate-time, not 2 months into delivery. Drives realistic team composition.

**Implementation sketch.**
- New whitelisted method `get_team_capacity(employee, start_date, end_date)` returns `(committed_hours, capacity_hours, headroom)`.
- Renders an inline HTML widget under team_members table.
- Same logic could power a portfolio-level **Resource Heatmap dashboard**: rows = employees, columns = next 6 months, cell colour by utilisation.

---

## 5. Predictive overrun model — learn from past variance

**Problem today.** The Pessimistic scenario uses a flat 1.30× multiplier. But for TBO specifically, the historical estimate-vs-actual variance is different per module and per team:
- HR & Payroll projects have averaged 1.55× overrun
- Standard CRM has averaged 1.10×
- First-time clients have averaged 1.40× regardless of module

**Idea.** Compute per-module and per-segment overrun coefficients from the *Estimate vs Actual Hours* report we already have:

```python
overrun_by_module = (completed_estimates
                       .merge(actual_hours_by_project)
                       .assign(ratio = actuals/estimated)
                       .groupby('module')['ratio'].mean())
```

Display them as a new column in the Module Selection table — **"Historical overrun ×"**.

Use them automatically to compute a **fourth scenario**: *"Data-driven Pessimistic"* = grand_total_hours × weighted_avg(per_module_overrun).

**Why better.** The pessimistic scenario stops being a guess and becomes "what we historically actually delivered vs estimate". You can defend pricing in a sales call with: *"We've never delivered a Manufacturing module within 1.4× the estimate. Our pessimistic price reflects that."*

**Threshold for activating.** Need ≥ 5 completed projects with the module before the coefficient is shown.

---

## 6. Sensitivity analysis — "what costs me the most if it changes?"

**Problem today.** The Scenario table flexes hours only. But cost can blow up from blended rate (a senior leaves, juniors take over) or duration (a 4-month project drags to 7).

**Idea.** A new **Sensitivity Section** below Scenario Analysis:

| Variable | −10% | Base | +10% | +25% | +50% |
|---|---:|---:|---:|---:|---:|
| Hours | margin 38% | **30%** | 22% | 10% | −5% |
| Blended rate | margin 36% | **30%** | 24% | 15% | 0% |
| Duration (months) | margin 33% | **30%** | 27% | 23% | 15% |
| Recommended price | margin 22% | **30%** | 37% | 45% | 55% |

Each cell = the net margin if you bump that single variable by that % while holding all others constant.

**Why better.** Tells leadership which assumption is the most fragile. If the table shows hours and rate move the needle 8pp each, but duration moves it only 3pp, then the conversation is "lock the rate" — not "fix the duration".

**Implementation.** Pure computation over the existing P&L formulas — no new DB queries. Render as an HTML table like the current Scenario block.

---

## 7. Customer pricing memory

**Problem today.** Every estimate starts from zero. Pre-sales has no idea what TBO charged this customer last time, or what hourly rate the customer agreed to.

**Idea.** A new **"Customer history"** collapsible section on the master that auto-loads on `client_name` change:

```
PRIME INSTITUTIONS INDIA LLP — Pricing history
─────────────────────────────────────────────
Last 5 estimates:
  EST-2025-0042   Won    ₹1.8L    @ ₹450/hr   400 hrs   Margin 35%
  EST-2025-0028   Won    ₹2.4L    @ ₹420/hr   570 hrs   Margin 32%
  EST-2024-0091   Lost   ₹3.1L    @ ₹460/hr   670 hrs   Margin 38%   ← lost on price
  EST-2024-0067   Won    ₹1.5L    @ ₹400/hr   375 hrs   Margin 28%
  EST-2024-0050   Won    ₹2.0L    @ ₹430/hr   465 hrs   Margin 30%

Avg accepted hourly rate: ₹425/hr
Suggested ceiling      : ₹450/hr (lost above this)
```

Plus a one-click "Match last accepted rate" button that nudges `target_margin_pct` so `price_per_hour` lands near the historical avg.

**Why better.** Stops you over-quoting a price-sensitive customer or under-quoting a flush one. The "lost above this" line is gold for repeat clients.

---

## 8. Activity-Based Costing (ABC) — proper indirect allocation

**Problem today.** The Indirect Costs table uses a single flat `project_share_pct` per row. So "Office Rent" gets the same % as "Recruitment Expenses" even though they're driven by very different things.

**Idea.** Add a `cost_driver` field to each indirect/infrastructure row:

| Cost driver | Allocation formula |
|---|---|
| Headcount | row × (project_team_size / company_total_employees) |
| Labour Hours | row × (project_hours / company_total_hours in period) |
| Project Count | row × (1 / count(active projects)) |
| Revenue Share | row × (project_revenue / company_revenue in period) |
| Fixed % | row × user_pct |

Office Rent → Headcount. Marketing → Revenue Share. Recruitment → grows with team size. Cloud infra → Labour Hours. Legal → Project Count.

The controller dispatches by `cost_driver` instead of treating every row identically.

**Why better.** A 2-person project doesn't get allocated the same office rent as a 10-person project. The allocation reflects what actually consumes that overhead. This is textbook Activity-Based Costing, the standard method for services firms.

**Implementation.** A 5-branch `if/elif` in `calculate_costs()` per row. No new tables.

---

## 9. Risk-adjusted estimate (Monte Carlo)

**Problem today.** The 3 scenarios (Optimistic / Base / Pessimistic) are deterministic. Real projects have probability distributions, not single numbers.

**Idea.** A new "Risk-adjusted estimate" button that runs 1000 Monte Carlo simulations:

```
For each module:
   Sample hours from a triangular distribution (best, likely, worst)
   Sample complexity multiplier from a beta distribution
For each cost row:
   Sample monthly cost from a normal distribution (current ±15%)
Run 1000 times, compute distributions of:
   - grand_total_cost
   - net_profit at recommended_price
```

Display the **P10 / P50 / P90** for total cost and profit:

```
Grand Total Cost
  P10 (best case)    : ₹8.2L
  P50 (median)       : ₹10.4L
  P90 (worst case)   : ₹14.1L

Probability of net loss at standard pricing: 22%
```

**Why better.** Leadership thinks in probability. "22% chance of net loss" is a much more actionable signal than "Pessimistic case shows loss". A go/no-go decision becomes a risk decision.

**Implementation.** Pure Python (NumPy) in a whitelisted method. Renders as a chart in a new HTML widget.

---

## 10. Smart hourly cost — gross + benefits + occupancy

**Problem today.** Hourly cost = `monthly_basic / 132`. This misses:
- Allowances (housing, travel, special) — already in `gross_pay` but the SSA fallback uses `base` only
- Employer-side contributions (PF, ESI, gratuity provision)
- Annualised leave + holidays (so the divisor of 132 is too high — real productive hours/month ≈ 110)
- Bench time when an employee is paid but not project-billable

**Idea.** Add a `Loaded Cost Coefficient` field to Employee:

```
hourly_cost (loaded) = monthly_gross
                       × (1 + benefits_coefficient)       # employer-side adds ~10-15%
                       / (productive_hours_per_month)
                       × (1 + bench_multiplier)            # spread bench time across billable hours
```

`benefits_coefficient` per-company (default 0.12), `productive_hours_per_month` per-employee (default 110, override for part-time/contract), `bench_multiplier` derived from historical timesheet coverage:

```
bench_multiplier = 1 / avg_utilization_last_3_months
                 # If employee logs 70% of their hours to projects, multiplier = 1/0.70 = 1.43
```

**Why better.** The rate you bill the project for is the rate that needs to cover all the time the company is paying that person for. Today's `monthly_basic / 132` under-counts true cost-to-deliver by ~30–40%.

**Implementation sketch.**
- Extend `get_employee_hourly_cost()` with the new coefficients.
- Optional override per employee — most use the company default.
- Show the breakdown in a tooltip: "₹650/hr = ₹50k gross × 1.12 / 110 / 0.78"

---

## 11. Marginal cost view — "what does this project ADD?"

**Problem today.** The estimate shows the project's full allocated cost — including a share of rent, salary, etc. that the company pays whether the project happens or not.

**Idea.** Add a toggle on Section K: **"Marginal cost view"**.

In marginal mode, `grand_total_cost` excludes:
- Salary cost for employees who would be paid anyway (sunk cost)
- Fixed overhead (rent, salaries of partners, depreciation)

Only INCLUDES:
- Direct cost (freelancers, project-specific cloud)
- Variable overhead (cloud per use, project-specific software licenses)
- Opportunity cost (revenue this team would have earned on another project)

**Why better.** For pricing decisions on incremental projects (especially low-margin ones), marginal cost is the floor — not full cost. If you have free team capacity and a customer wants a quick add-on, marginal cost might be ₹50k while full-cost says ₹2L. Knowing both lets you negotiate.

---

## 12. Cost-center / dept rollup in Section K

**Problem today.** Section K shows total team cost as one number. But ERP projects at TBO are routinely cross-staffed — an ERPNext implementation might pull a UI designer from Digital Marketing for frontend work, an accountant from Accounts Service for the chart-of-accounts setup, and primary functional + dev resources from ERPNext dept. Each dept has different hourly costs.

**Idea.** Below `team_cost_total`, render an auto-breakdown by `tabEmployee.department` for the team members assigned to this ERP project:

```
Team Cost: ₹4.2L  (ERPNext implementation)
  ERPNext dept (Vinod, Sabhisha, Mohamed)        420 hrs × ₹650/hr = ₹2,73,000 (65%)
  Information Technology (Ajith)                 100 hrs × ₹680/hr = ₹68,000   (16%)
  Digital Marketing (Ali — UI design support)    100 hrs × ₹450/hr = ₹45,000   (11%)
  Accounts Service (Sajith — CoA setup)           80 hrs × ₹500/hr = ₹40,000   (10%)
  ───────
                                                 700 hrs            ₹4,26,000
```

**Why better.** Surfaces cross-dept resourcing at a glance. Lets pre-sales see if a project is over-reliant on borrowed people from other departments (a delivery risk) and lets finance internal-charge those departments correctly. Also drives the §23 "Department P&L" in the expense analysis notebook to reflect reality.

---

## 13. Auto-AMC pricing tier (replaces the flat 18%)

**Problem today.** AMC = `recommended_price × 0.18`. Same 18% whether the project is 5 modules or 20.

**Idea.** Tiered AMC based on:

```
amc_pct = base_amc                              # 12% baseline
        + 0.5 × count(integration_requirements)  # each integration adds 0.5%
        + 1.0 × count(custom_module_requests)    # each custom module adds 1%
        + (2 if complexity_score > threshold else 0)  # complex projects need more support
        + (3 if data_migration_required else 0)
        + (1.5 × number_of_users / 100)          # bigger user base = more support tickets
        — capped at 25%

amc_suggested = recommended_price × (amc_pct / 100)
```

Show the breakdown in a tooltip.

**Why better.** AMC under-prices simple deals and over-prices complex ones today. Tiered ties AMC to the actual support load the system will generate.

---

## 14. "Estimate from text" — LLM-assisted module detection

**Problem today.** Pre-sales reads a 3-page client brief and manually clicks 8 modules + 4 integrations + writes 3 custom module rows. 30 minutes of clicking per estimate, easy to miss things.

**Idea.** A new "Paste client brief" textarea. On submit, calls the Anthropic API (`claude-haiku-4-5`):

```
Given this client brief, suggest:
- ERPNext modules to include (with complexity 1 or 2)
- Custom module requests (with business_purpose + functional_description)
- Integrations needed
- Any data migration or special requirements

Brief:
{user pasted text}

Return JSON matching this schema:
{modules: [...], custom_modules: [...], integrations: [...]}
```

The user reviews + confirms each suggestion before it's added to the form.

**Why better.** Pre-sales becomes about *reviewing* AI suggestions instead of *generating* them from scratch. Goes from 30 min/estimate to 8 min/estimate. The model also catches modules the human missed (Quality, Assets, etc. that come up implicitly in the brief).

**Implementation.**
- Use `anthropic` Python SDK in a whitelisted method.
- Cache: same brief → same suggestion. Avoid re-calling API on form refresh.
- Cost: ~$0.003 per estimate at Haiku pricing. Negligible.

---

## How these ideas interact

```
  Pull from books (1)
        │
        ▼
  ABC allocation (8) ── Sensitivity analysis (6)
        │                       │
        ▼                       ▼
  Marginal vs Full (11) ── Monte Carlo (9)
        │
        ▼
  Capacity check (4) ── Dept-aware direct (2)
        │                       │
        ▼                       ▼
  Customer memory (7) ── LLM brief parser (14)
                │
                ▼
        Multi-currency (3)
                │
                ▼
        Loaded hourly cost (10)
                │
                ▼
        Predictive overrun (5)
```

The chain runs roughly top-to-bottom — earlier items unlock or sharpen later ones.

---

## Suggested rollout order

If you build one per sprint:

| Sprint | What | Why first |
|---|---|---|
| 1 | **§1 — Pull indirect from books** | Biggest accuracy win for least code. One whitelisted method + one button. |
| 2 | **§3 — Multi-currency native** | Unblocks SAR/AED/QAR quotes. Critical for TBO's actual customer mix. |
| 3 | **§10 — Loaded hourly cost** | Fixes the under-counting of true labour cost across every estimate. |
| 4 | **§2 — Direct cost templates** | Speeds up estimate creation, surfaces best-practice line items. |
| 5 | **§8 — Activity-Based Costing** | The proper academic allocation method. Stops one-size-fits-all overhead. |
| 6 | **§4 — Live capacity check** | Catches over-commitment. Requires the team-allocation aggregation logic to be in place. |
| 7 | **§5 — Predictive overrun** | Needs the post-project actuals report to be running and tagged with `custom_module_tag` for ≥ 6 months first. |
| 8 | **§7 — Customer memory** + **§13 — Tiered AMC** | Both small, cosmetic but high-value polish items. |
| 9 | **§6 — Sensitivity** + **§11 — Marginal view** + **§12 — Dept rollup** | Visualisation upgrades. Build once data flows are solid. |
| 10 | **§14 — LLM brief parser** | A separate spike — needs Anthropic API key + Cost Center conversation with the user about per-estimate API cost. |
| 11 | **§9 — Monte Carlo** | The most academically elegant but lowest urgency. Build last when you want to upgrade to enterprise-grade. |

---

## What this needs from you (data hygiene)

A few items unlock most of these:

| Need | Used by | What it requires |
|---|---|---|
| Tag every Purchase Invoice with a `project` or `cost_center` | §1, §8 | Frappe field already exists — enforce it via a validation hook. |
| Tag every Sales Invoice with a `project` | §7, §11 | Same — `project` field is there, just unused. |
| `custom_module_tag` custom field on Task | §5 | One-line `Custom Field` fixture + populate in `handle_status_change`. |
| Salary Slip uses `gross_pay` not just `base` for cost decisions | §10 | Already in your data — switch the priority in `get_employee_hourly_cost`. |
| `expected_start_date` populated on every Project | §4 | Set automatically in `handle_status_change` when project is auto-created. |

These cost almost nothing to put in place but multiply the value of everything above.
