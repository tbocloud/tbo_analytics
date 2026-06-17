# Indirect Cost Allocation — How to Attribute Company Overhead to a New Project

Deep-dive companion to [COST_ESTIMATION_IDEAS.md](COST_ESTIMATION_IDEAS.md) §1.

The hard question isn't *what* the company's indirect cost is — that's in your GL. The hard question is **how much of it should this specific project bear**. There's no single right answer; it depends on the cost driver. This doc covers the standard framework, the driver mapping for TBO's actual chart of accounts, the math, worked examples, and the implementation sketch.

---

## 1. The framework — every indirect line has a cost driver

For each indirect GL account `a`:

```
historical_monthly_avg(a) = average monthly spend on account `a` over the last N months
                            (pulled live from `tabGL Entry`)

project_share(a) = f(project_intensity, company_intensity)
                   where the "intensity" is whatever drives that specific cost

project_monthly_contribution(a) = historical_monthly_avg(a) × project_share(a)

project_total_allocation(a) = project_monthly_contribution(a) × project_duration_months
```

The trick is **picking the right intensity** (cost driver) per account. Rent doesn't grow with project hours; it grows with headcount. Marketing doesn't grow with headcount; it grows with revenue.

---

## 2. The five cost drivers you need

For TBO's chart of accounts, five drivers cover ~95% of indirect categories.

| # | Driver | Project's intensity | Company's intensity (benchmark) | When to use it |
|---|---|---|---|---|
| **A** | **Headcount** | `team_size` (count of active `team_members`) | `company_headcount` (active `tabEmployee` for this company) | Costs scale with number of people occupying the office, owning a laptop, drinking coffee. |
| **B** | **Labour Hours** | `monthly_project_hours = grand_total_hours / duration_months` | `company_avg_monthly_hours` (avg of last 3 months of submitted Timesheet hours) | Costs scale with how busy the team is — IT load, cloud usage, support tickets generated. |
| **C** | **Project Count** | `1` (this project) | `company_active_projects` (count of `Project` where `status='Open'`) | Fixed costs spread across all active engagements — audit, compliance, accounting service. |
| **D** | **Revenue** | `project_monthly_revenue = recommended_price / duration_months` | `company_avg_monthly_revenue` (avg `base_grand_total` from `tabSales Invoice` over last 6 months) | Costs scale with the size of the business — sales, marketing, bank charges, taxes. |
| **E** | **Fixed Pct** | `user_provided_pct / 100` | n/a | Escape hatch: the user knows better, just types the % directly. |

The share formula per driver:

```
A. Headcount    : share = team_size / company_headcount
B. Labour Hours : share = monthly_project_hours / company_avg_monthly_hours
C. Project Count: share = 1 / company_active_projects
D. Revenue      : share = project_monthly_revenue / company_avg_monthly_revenue
E. Fixed Pct    : share = user_pct / 100
```

---

## 3. Driver assignment for TBO's actual indirect accounts

Walking through your chart of accounts (`Indirect Expenses - TBO` subtree from `expense_analysis.ipynb`):

| Account | Suggested driver | Why |
|---|---|---|
| Office Rent | **A. Headcount** | Office sized for the team. |
| Business Park Rent | **A. Headcount** | Same. |
| Workspace Rent | **A. Headcount** | Same. |
| Electricity Charges | **A. Headcount** | Office-wide, person-shared. |
| OFFICE WATER CHARGES | **A. Headcount** | |
| Telephone & Internet Charges | **A. Headcount** | Per-seat use. |
| Cleaning Supplies, Cleaning & Wastage | **A. Headcount** | Per-seat. |
| Office Expenses, Office Maintenance, Office Setup, Office stationery | **A. Headcount** | Per-seat. |
| Laptop Rental, Laptop Servicing | **A. Headcount** | One laptop per person. |
| Employee Welfare, Employee Entertainment | **A. Headcount** | Per-person. |
| Food Expenses, Staff Accommodation | **A. Headcount** | Per-person. |
| Staff Birthday Celebration, TBO Celebrations, Festival Expenses | **A. Headcount** | Per-person culture cost. |
| Recruitment and Training Expenses | **A. Headcount** | Grows with team size. |
| Depreciation | **A. Headcount** | Equipment depreciation scales with team. |
| Cloud Service Exp. | **B. Labour Hours** | Cloud load scales with active work. |
| Frappe Cloud Expense | **B. Labour Hours** or **C. Project Count** | Depends — usually per project. |
| Domain Expense | **C. Project Count** | One per active engagement. |
| Auditing Fee, Accounting and Filing Charges | **C. Project Count** | Fixed-ish across the firm. |
| GST Filing Fee, TDS Filing Fee, ITR Filing Fee | **C. Project Count** | Fixed. |
| Legal Expenses, Professional Charges, Consulting Charge | **C. Project Count** | |
| FINANCE ADVISORY CHARGES | **C. Project Count** | |
| Documentation Charges | **C. Project Count** | |
| Marketing Expenses, Meta Ad Expense | **D. Revenue** | Scales with business volume. |
| TBO Promotion Expenses, TBO Website | **D. Revenue** | Brand investment scales with revenue. |
| Brokerage, Commission on Sales | **D. Revenue** | Definitionally per-deal. |
| Bank Charges | **D. Revenue** | Transaction-volume driven. |
| GST Expense | **D. Revenue** | Tax on output. |
| Exchange Gain/Loss, Unrealized Exchange Gain/Loss | **D. Revenue** | FX exposure scales with foreign revenue. |
| Income tax expense | **D. Revenue** | Tax on profit (proxy). |
| Travel Expense - Local, Travelling Expense Director | **C. Project Count** | Per-engagement client visits. |
| Fuel Expense | **C. Project Count** | |
| Daily Allowance - Director | **C. Project Count** | |
| Client Entertainment, Client Shoot Exp. | **C. Project Count** | Per-client cost. |
| Late Fee, Interest & Fines, Write Off, Miscellaneous | **E. Fixed Pct** (default 0.5%) | Uncontrollable, small. |
| HR Expense subtree (Basic Salary, Allowances, per-employee, Partners Salary) | **EXCLUDED** | Already attributed to projects via timesheet × hourly_cost in direct labour. Allocating again = double-counting. |
| Stock Expenses subtree (COGS, Customs Duty, Stock Adjustment) | **EXCLUDED** (or D. Revenue if you treat them as cost-of-revenue) | Inventory accounts — only relevant if the project involves physical goods. |

> **The HR exclusion is critical.** TBO's per-employee salary accounts (~₹70L lifetime) are in Indirect Expenses in the books, but in the estimator we already capture labour cost via `hourly_cost × allocated_hours`. Allocating those salary accounts as overhead too would double-count by 60% of total spend. The auto-allocation must skip them.

---

## 4. Worked example — a 4-month, 4-person estimate

**The project being estimated:**

| Input | Value |
|---|---:|
| `team_size` | 4 |
| `duration_months` (from §4.2 in FIELDS.md) | 4 |
| `grand_total_hours` | 700 |
| `monthly_project_hours` | 175 (= 700/4) |
| `recommended_price` | ₹6,00,000 |
| `monthly_project_revenue` | ₹1,50,000 (= 6L/4) |

**Company benchmarks** (pulled live from books):

| Benchmark | Value | Source |
|---|---:|---|
| `company_headcount` | 106 | `SELECT COUNT(*) FROM tabEmployee WHERE status='Active' AND company='TBO…'` |
| `company_avg_monthly_hours` | 3,800 | avg of last 3 months SUM(`tabTimesheet Detail.hours`) for submitted timesheets |
| `company_active_projects` | 17 | count(`tabProject WHERE status='Open'`) — or use the *forecastable* count (≥6 active months, ≥50 hrs) from the canonicalization notebook |
| `company_avg_monthly_revenue` | ₹8,30,000 | avg of last 6 months SUM(`tabSales Invoice.base_grand_total`) |

**Per-driver project share:**

```
A. Headcount     share = 4 / 106              = 3.77%
B. Labour Hours  share = 175 / 3,800           = 4.61%
C. Project Count share = 1 / 17                = 5.88%
D. Revenue       share = 1,50,000 / 8,30,000   = 18.07%
```

**Sample allocations** (illustrative monthly averages from your GL):

| Indirect account | Monthly avg | Driver | Share | Monthly contribution | × 4 months = Total |
|---|---:|---|---:|---:|---:|
| Business Park Rent | ₹65,000 | A | 3.77% | ₹2,452 | **₹9,810** |
| Office Rent | ₹15,000 | A | 3.77% | ₹566 | ₹2,264 |
| Electricity | ₹4,500 | A | 3.77% | ₹170 | ₹679 |
| Telephone & Internet | ₹2,200 | A | 3.77% | ₹83 | ₹332 |
| Cleaning Supplies | ₹1,800 | A | 3.77% | ₹68 | ₹272 |
| Laptop Rental | ₹13,500 | A | 3.77% | ₹509 | ₹2,038 |
| Depreciation | ₹30,000 | A | 3.77% | ₹1,132 | ₹4,528 |
| Recruitment & Training | ₹6,000 | A | 3.77% | ₹226 | ₹906 |
| Employee Welfare + Food | ₹4,500 | A | 3.77% | ₹170 | ₹679 |
| Cloud Service Exp. | ₹2,000 | B | 4.61% | ₹92 | ₹369 |
| Frappe Cloud Expense | ₹3,500 | C | 5.88% | ₹206 | ₹824 |
| Domain Expense | ₹800 | C | 5.88% | ₹47 | ₹188 |
| Auditing Fee | ₹2,500 | C | 5.88% | ₹147 | ₹588 |
| Accounting & Filing | ₹2,000 | C | 5.88% | ₹118 | ₹471 |
| GST/TDS/ITR Filing | ₹3,000 | C | 5.88% | ₹176 | ₹706 |
| Legal + Professional | ₹2,500 | C | 5.88% | ₹147 | ₹588 |
| Marketing + Meta Ad | ₹4,000 | D | 18.07% | ₹723 | ₹2,891 |
| TBO Promotion | ₹3,000 | D | 18.07% | ₹542 | ₹2,168 |
| Bank Charges | ₹1,500 | D | 18.07% | ₹271 | ₹1,084 |
| Exchange Gain/Loss | ₹2,000 | D | 18.07% | ₹361 | ₹1,446 |
| Travel + Fuel | ₹4,500 | C | 5.88% | ₹265 | ₹1,058 |
| Daily Allowance Director | ₹2,000 | C | 5.88% | ₹118 | ₹471 |
| **Total auto-allocated indirect** | | | | | **₹34,358** |

> **Compare with today's manual default.** Section H currently has the user type one line — say `monthly_total_cost = ₹30,000`, `project_share_pct = 10%` → allocates `30,000 × 0.10 × 4 = ₹12,000`. The auto-allocation produces ₹34,358 — **3× more, and broken down into 22 traceable lines** instead of one round-figure guess.

The estimate that comes out is more pessimistic about overhead, but it's defensible: every line traces back to a real GL average and a real cost driver.

---

## 5. Edge cases that must be handled

### 5.1 The HR/salary exclusion
Already covered above — never allocate HR Expense or Partners Salary as overhead in the estimate, because they're captured in direct labour via timesheets. The auto-allocator must walk the chart of accounts and exclude:
- Every leaf under `HR Expense - TBO`
- Every leaf under `Partners Salary - TBO`
- Optionally: `Basic Salary`, `Housing Allowance`, `Other Allowance`, `Travel Allowance`, `Staff Incentive`, `Stipend` if they sit directly under Indirect Expenses (they appear to, in TBO's CoA)

### 5.2 Revenue-driver circularity
`Driver D` (Revenue) uses `monthly_project_revenue = recommended_price / duration_months`, but `recommended_price` depends on `grand_total_cost`, which includes the indirect cost we're computing. Circular.

**Resolution:** use `standard_price` instead — it's deterministic from `grand_total_cost` and `target_margin_pct`, both known at the time of allocation. Or iterate once: compute indirect with revenue=0 first, then recompute with revenue based on the resulting `standard_price`. Convergence is fast.

### 5.3 Months with zero activity
If `company_avg_monthly_hours` was computed from a 3-month window where one month had no timesheets (vacation, system downtime), the average is artificially low and the labour-hours share is inflated.

**Fix:** Use the **median**, not mean, of monthly hours. Or weight by number of working days in each month. Or compute over a longer window (6-12 months) to smooth out.

### 5.4 New company, no historical data
The auto-allocator needs at least 3 months of GL history per indirect account to produce a usable average. For accounts with fewer than that:
- Fall back to the **annualised** figure (e.g., for annual ITR Filing Fee, just take the one entry and divide by 12).
- Mark the row with a small ℹ️ tooltip: *"based on 1 month of data — review before saving"*.

### 5.5 Mismatched cost-center vs project-team alignment
If the project's team comes mostly from the ERPNext department but the office rent is shared with the Digital Marketing department too, the headcount-based share overestimates rent for an ERPNext-pure project.

**Two-stage allocation (advanced):**
1. First-stage: split each company-wide indirect across departments by departmental headcount.
2. Second-stage: from each department's pool, allocate to projects within that department by labour hours.

This needs department on every Indirect Cost row, which TBO already has via Cost Center. Not v1 critical but worth the upgrade later.

### 5.6 Project Count denominator
"Active projects" can mean many things:
- Status = Open (broad, but includes stalled ones)
- Has timesheet activity in the last 30 days (narrow but live)
- Has hours logged in the last 3 months (broader)
- The "forecastable" series from the canonicalization (≥6 active months, ≥50 hrs)

**Recommendation:** define `active_project` as "had ≥ 4 hours of timesheet activity in the last 60 days". That excludes stale/abandoned projects but includes anything currently being worked on.

### 5.7 New employees (hired but no historical hours)
`company_headcount` uses `tabEmployee.status='Active'`. If the company just hired 10 people who haven't logged any timesheets yet, the rent share for any given project drops 9% the day they're added. This is correct economically (office sized for the bigger team) but might surprise the user.

**Mitigation:** print the benchmarks in a banner above the auto-fill: *"Benchmarks: 106 active employees, 3,800 avg monthly hours, 17 active projects, ₹8.3L avg monthly revenue. Click "Refresh" to recompute."* So the user sees what's driving the numbers.

---

## 6. UI / UX flow

Section H gets a new button row above the table:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Indirect Costs                                                       │
│                                                                       │
│  [⚙ Load from books (last 6 months)]   [📊 Show benchmarks]          │
│  Lookback: ( 3m | ●6m | 12m )                                        │
│  Drivers:  (●default mapping | ◯let me pick per row)                 │
│                                                                       │
│  ───── auto-allocated 22 rows from 6 months of GL data ─────         │
│  [table rendered with category, monthly_total_cost, driver, share,   │
│   allocated_amount — all pre-filled, all editable]                   │
└─────────────────────────────────────────────────────────────────────┘
```

After clicking *Load from books*:
1. The current table is replaced (with a confirm prompt if there are existing rows).
2. Each row shows: `cost_item`, `monthly_total_cost` (avg from GL), `allocation_method` = driver name, `project_share_pct` (computed from the formula), `allocated_amount` (the result).
3. The user can edit any field — manually override the driver, change the share %, raise/lower the monthly cost. Recalc is instant.
4. A small "?" tooltip on each row explains: *"₹2,452/month = ₹65,000 × (4/106). Driver: Headcount. Source: average of 6 GL postings in the last 6 months."*

---

## 7. Implementation sketch

### 7.1 New Python file — `tbo_analytics/tbo_analytics/cost_allocator.py`

```python
import frappe
from frappe.utils import nowdate, add_months

# Driver enum — keep stable, used in the Indirect Cost Item.allocation_method field
DRIVER_HEADCOUNT     = 'Headcount'
DRIVER_LABOUR_HOURS  = 'Labour Hours'
DRIVER_PROJECT_COUNT = 'Project Count'
DRIVER_REVENUE       = 'Revenue'
DRIVER_FIXED_PCT     = 'Fixed Pct'

# Default driver per account (key = lowercased keyword-match against account_name)
DEFAULT_DRIVER_MAP = [
    ('rent',              DRIVER_HEADCOUNT),
    ('electricity',       DRIVER_HEADCOUNT),
    ('water',             DRIVER_HEADCOUNT),
    ('telephone',         DRIVER_HEADCOUNT),
    ('internet',          DRIVER_HEADCOUNT),
    ('office',            DRIVER_HEADCOUNT),
    ('cleaning',          DRIVER_HEADCOUNT),
    ('laptop',            DRIVER_HEADCOUNT),
    ('depreciation',      DRIVER_HEADCOUNT),
    ('food',              DRIVER_HEADCOUNT),
    ('staff',             DRIVER_HEADCOUNT),
    ('welfare',           DRIVER_HEADCOUNT),
    ('celebration',       DRIVER_HEADCOUNT),
    ('birthday',          DRIVER_HEADCOUNT),
    ('festival',          DRIVER_HEADCOUNT),
    ('recruitment',       DRIVER_HEADCOUNT),
    ('training',          DRIVER_HEADCOUNT),
    ('cloud',             DRIVER_LABOUR_HOURS),
    ('domain',            DRIVER_PROJECT_COUNT),
    ('audit',             DRIVER_PROJECT_COUNT),
    ('accounting',        DRIVER_PROJECT_COUNT),
    ('legal',             DRIVER_PROJECT_COUNT),
    ('professional',      DRIVER_PROJECT_COUNT),
    ('filing',            DRIVER_PROJECT_COUNT),
    ('consulting',        DRIVER_PROJECT_COUNT),
    ('travel',            DRIVER_PROJECT_COUNT),
    ('fuel',              DRIVER_PROJECT_COUNT),
    ('advisory',          DRIVER_PROJECT_COUNT),
    ('marketing',         DRIVER_REVENUE),
    ('promotion',         DRIVER_REVENUE),
    ('meta ad',           DRIVER_REVENUE),
    ('brokerage',         DRIVER_REVENUE),
    ('commission',        DRIVER_REVENUE),
    ('bank charge',       DRIVER_REVENUE),
    ('exchange',          DRIVER_REVENUE),
    ('gst expense',       DRIVER_REVENUE),
    ('income tax',        DRIVER_REVENUE),
    ('late fee',          DRIVER_FIXED_PCT),
    ('write off',         DRIVER_FIXED_PCT),
    ('miscellaneous',     DRIVER_FIXED_PCT),
]

# Account-name patterns that must NEVER be auto-allocated (already in direct labour)
EXCLUDED_PATTERNS = ['salary', 'allowance', 'incentive', 'stipend', 'partner']

def suggest_driver(account_name):
    n = account_name.lower()
    for pattern, driver in DEFAULT_DRIVER_MAP:
        if pattern in n:
            return driver
    return DRIVER_PROJECT_COUNT   # safe default for unknown lines

def is_excluded(account_name, parent_account):
    n = account_name.lower()
    if any(p in n for p in EXCLUDED_PATTERNS):
        return True
    if 'hr expense' in (parent_account or '').lower():
        return True
    if 'partners salary' in (parent_account or '').lower():
        return True
    return False


@frappe.whitelist()
def pull_indirect_lines(company, lookback_months=6):
    """Return one suggested Indirect Cost Item row per qualifying GL account."""
    cutoff = add_months(nowdate(), -int(lookback_months))

    # Pull every leaf account under Indirect Expenses with non-zero recent activity
    rows = frappe.db.sql("""
        SELECT
            a.name             AS account,
            a.account_name,
            a.parent_account,
            SUM(gl.debit - gl.credit) AS total_amount,
            COUNT(DISTINCT DATE_FORMAT(gl.posting_date, '%%Y-%%m')) AS active_months
        FROM `tabGL Entry` gl
        INNER JOIN `tabAccount` a ON a.name = gl.account
        WHERE gl.is_cancelled = 0
          AND gl.company = %(c)s
          AND a.root_type = 'Expense'
          AND a.is_group = 0
          AND gl.posting_date >= %(cutoff)s
        GROUP BY a.name, a.account_name, a.parent_account
        HAVING total_amount > 0
        ORDER BY total_amount DESC
    """, {'c': company, 'cutoff': cutoff}, as_dict=True)

    # Filter out HR/salary subtree and compute monthly avg + suggest driver
    result = []
    for r in rows:
        if is_excluded(r.account_name, r.parent_account):
            continue
        monthly_avg = float(r.total_amount) / max(int(r.active_months), 1)
        result.append({
            'account':           r.account,
            'cost_item':         r.account_name,
            'category':          _category_from_parent(r.parent_account),
            'monthly_total_cost': round(monthly_avg, 2),
            'allocation_method':  suggest_driver(r.account_name),
            'source':            f"avg of {r.active_months} mo from {cutoff} onward",
        })
    return result


@frappe.whitelist()
def get_company_benchmarks(company):
    """Pull live denominators for share calculations."""
    headcount = frappe.db.count('Employee', {'company': company, 'status': 'Active'})

    hours = frappe.db.sql("""
        SELECT AVG(monthly_hours) FROM (
            SELECT DATE_FORMAT(ts.start_date, '%%Y-%%m') AS m,
                   SUM(tsd.hours) AS monthly_hours
            FROM `tabTimesheet Detail` tsd
            INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
            WHERE ts.docstatus = 1 AND ts.company = %(c)s
              AND ts.start_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
            GROUP BY DATE_FORMAT(ts.start_date, '%%Y-%%m')
        ) t
    """, {'c': company})[0][0] or 0

    active_projects = frappe.db.sql("""
        SELECT COUNT(DISTINCT tsd.project)
        FROM `tabTimesheet Detail` tsd
        INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
        WHERE ts.docstatus = 1 AND ts.company = %(c)s
          AND ts.start_date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
          AND tsd.project IS NOT NULL AND tsd.project != ''
    """, {'c': company})[0][0] or 1

    revenue = frappe.db.sql("""
        SELECT SUM(base_grand_total) / 6
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND company = %(c)s
          AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
    """, {'c': company})[0][0] or 0

    return {
        'headcount':           int(headcount),
        'avg_monthly_hours':   float(hours),
        'active_projects':     int(active_projects),
        'avg_monthly_revenue': float(revenue),
    }
```

### 7.2 Controller update — `calculate_costs()`

Add a branch by `allocation_method` (`driver`) before the existing flat-pct formula:

```python
def _allocate_indirect_row(self, row, benchmarks):
    """Compute project_share_pct + allocated_amount based on the row's driver."""
    dur = self.project_duration_months
    team_size = len([r for r in self.team_members if r.is_active_in_current_version])
    monthly_hrs = (self.grand_total_hours or 0) / max(dur, 1)
    monthly_rev = (self.standard_price or 0) / max(dur, 1)

    if row.allocation_method == 'Headcount' and benchmarks['headcount']:
        share = team_size / benchmarks['headcount']
    elif row.allocation_method == 'Labour Hours' and benchmarks['avg_monthly_hours']:
        share = monthly_hrs / benchmarks['avg_monthly_hours']
    elif row.allocation_method == 'Project Count' and benchmarks['active_projects']:
        share = 1 / benchmarks['active_projects']
    elif row.allocation_method == 'Revenue' and benchmarks['avg_monthly_revenue']:
        share = monthly_rev / benchmarks['avg_monthly_revenue']
    else:   # 'Fixed Pct' or fallback — use whatever the user typed
        share = (row.project_share_pct or 0) / 100

    row.project_share_pct = round(share * 100, 2)
    row.project_duration_months = dur
    row.allocated_amount = round((row.monthly_total_cost or 0) * share * dur, 2)
```

### 7.3 Client JS — the button

```javascript
frm.add_custom_button(__('Load from books'), () => {
    frappe.call({
        method: 'tbo_analytics.tbo_analytics.cost_allocator.pull_indirect_lines',
        args: { company: frappe.defaults.get_user_default('Company'), lookback_months: 6 }
    }).then(r => {
        frm.clear_table('indirect_costs');
        for (const row of r.message) frm.add_child('indirect_costs', row);
        frm.refresh_field('indirect_costs');
        frm.save();
    });
}, __('Actions'));
```

---

## 8. Summary — the answer to "how do we identify project contribution?"

For each indirect cost line, attach a **cost driver** (Headcount / Labour Hours / Project Count / Revenue / Fixed Pct). The driver determines the formula. The formula's two inputs come from:

- **Project side**: team_size, monthly_project_hours, monthly_project_revenue — all computable from the estimate inputs.
- **Company side**: live benchmarks pulled from your books — `tabEmployee`, `tabTimesheet Detail`, `tabProject`, `tabSales Invoice`.

The share is mechanical from there. The user can override any line, but the **defaults** are principled instead of guessed — and they reconcile to the books because each line's monthly average comes from real GL data and each share's denominator is a real, current count.

The five drivers and the per-category mapping in §3 covers ~95% of TBO's indirect accounts out of the box. The remaining 5% — odd entries like `Charity` or `Daily Allowance Director` — get the default `Project Count` driver and can be overridden.

The single most important rule: **never auto-allocate HR Expense or Partners Salary**. They're labour, not overhead, and they're already captured by `hourly_cost × allocated_hours` on the team composition table. Allocating them again double-counts ~₹1 cr of TBO's expense base.
