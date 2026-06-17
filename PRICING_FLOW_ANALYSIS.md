# Pricing → Profitability Flow — Analysis

An audit of how `tbo_analytics` takes a project's cost and turns it into a price + profitability picture for the client. Read this when you want to understand **how the loop works end-to-end today** and **where the user experience is rough**.

This is an analysis document. **No code changes are proposed for execution here.** Anything called out as a "refinement" is a recommendation only; the existing `COST_ESTIMATION_IDEAS.md` is where future code work lives.

---

## Executive Summary

The price-setting → profitability-analysis loop is **functionally complete**. Cost calculation, three pricing bands (Floor / Standard / Premium), a custom-price override, scenario analysis (Optimistic / Base / Pessimistic / Custom %), sensitivity matrix (±10/25/50% on each driver), break-even hours, 1000-run Monte Carlo with P10/P50/P90 + loss probability, and multi-currency quoting with FX-buffer hedging are all live in Sections K and L of the Implementation Estimate form.

The rough edge isn't math or missing capability. It's **UX clarity**: the band picker and the custom-price override live in the same column real-estate with conflicting visibility rules, and there's no explicit *"which pricing mode am I in?"* signpost. A user can switch modes mid-negotiation without realising, and the rich assessment widget (LOSS / DANGER / HEALTHY / PREMIUM+ banner) only fires for the custom-price path — band selection has no equivalent visual.

The biggest payoff for the next iteration is therefore not a new feature but a **dedicated price-strategy toggle** that makes the two pricing modes explicit and gives each mode its own assessment panel.

---

## 1. The Loop Today

### 1.1 Where it lives on the form

```
[A. Client Details]
[B. Module Selection]            ← drives grand_total_hours
[C. Custom Module Requests]      ← drives grand_total_hours
[D. Integration Requirements]    ← drives grand_total_hours
[E. Team Composition]            ← drives team_cost_total + blended_hourly_rate
[F. Team Revision History]
[G. Direct Costs]                ← drives direct_cost_total
[H. Indirect Costs]              ← drives indirect_cost_total (driver-based allocation)
[I. Infrastructure & Shared]     ← drives infrastructure_cost_total
─────────────────────────────────────────────────────────
[J. Estimation Summary]          ← grand_total_hours, project_duration_months, blended_hourly_rate
[K. Pricing & Profitability]     ← the price-setting half of the loop
[L. Scenario Analysis]           ← the profitability-analysis half
```

### 1.2 Section K — setting the price

| Step | Field(s) | Behaviour |
|---|---|---|
| 1. Target margin | `target_margin_pct` (default 30) | User picks the gross margin they want to clear. |
| 2. Cost roll-up | `team_cost_total`, `direct_cost_total`, `indirect_cost_total`, `infrastructure_cost_total`, `grand_total_cost` | Read-only, computed from sections E–I. |
| 3. Band derivation | `floor_price`, `standard_price`, `premium_price` | `floor = cost × 1.10`; `standard = cost / (1 − margin%)`; `premium = standard × 1.25`. |
| 4. **Mode A — Pick a band** | `recommended_band` (Standard / Conservative / Premium) | Selecting a band sets `recommended_price` = the matching band price. |
| 5. **Mode B — Type a custom price** | `use_custom_price` + `custom_price` | Tick the check, type the negotiated INR figure; `recommended_price` = `custom_price`. The `recommended_band` field is hidden by `depends_on: !use_custom_price`. |
| 6. Custom-mode assessment | `custom_price_assessment_html` | A banner that classifies the typed price as **LOSS / DANGER / BELOW TARGET / HEALTHY / PREMIUM+** + a comparison table vs each band. **Only shown when `use_custom_price = 1`.** |
| 7. Derived metrics | `margin_at_recommended`, `price_per_hour`, `amc_suggested` | Recomputed on every change to cost, margin, band, or custom price. |
| 8. Multi-currency mirror | `quoting_currency`, `quoting_rate`, `quoting_rate_date`, `fx_buffer_pct`, and `*_quoting` mirror fields | If the customer's currency ≠ INR, every band + the recommended price gets converted; FX buffer applied to `recommended_price_quoting` only. Toggle `display_view` (INR Only / Quoting Only / Both) controls visibility. |

### 1.3 Section L — analysing the price

| Widget | Field | What it shows |
|---|---|---|
| Scenario table | `scenario_table_html` | 4 rows — Optimistic (0.85× hours), Base, Pessimistic (1.30×), and a Custom % set by `scenario_custom_pct`. Each shows hours, team cost, total cost, gross profit, margin, profit/loss status. |
| Sensitivity matrix | `sensitivity_table_html` | 4 variables × 7 flex levels (−50, −25, −10, Base, +10, +25, +50). Cells colour-coded by margin band. Tells the user which assumption is most fragile. |
| Monte Carlo card | `monte_carlo_html` | Button-triggered. 1000 sims using triangular distributions on hours, blended rate, non-team cost. Returns P10/P50/P90 cost + profit, mean, **probability of net loss**, 25-bin histogram. |
| Break-even | `break_even_hours`, `break_even_pct`, `break_even_note` | "You break even if the team takes up to X hours (Y% of estimate). Beyond that the project is at a loss." |

### 1.4 The two halves wired together

The bridge between K and L is the **client-side recalc_pricing** function in [implementation_estimate.js:342](tbo_analytics/public/js/implementation_estimate.js#L342). Every time the user changes margin, picks a different band, ticks `use_custom_price`, types into `custom_price`, or edits any cost row, this function:

1. Recomputes Floor / Standard / Premium from cost + margin.
2. Resolves `recommended_price` (custom price wins; band price otherwise).
3. Recomputes margin, price-per-hour, AMC, break-even, all `*_quoting` mirror fields.
4. Calls `update_scenario_table()`, `update_sensitivity_table()`, `update_custom_price_assessment()` so the whole right-hand side of the page stays in sync.

The server-side equivalent is [`calculate_pricing()` in implementation_estimate.py:241](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py#L241) — runs on every save, applies the exact same formulas, and persists the same fields. The JS is for *live* feedback; the Python is *truth of record*.

The Monte Carlo widget breaks this rule on purpose: it's button-triggered (server round-trip), and any price change calls [`invalidate_monte_carlo()` at js:645](tbo_analytics/public/js/implementation_estimate.js#L645), resetting the card to its placeholder so users know the prior result is stale.

---

## 2. Deep-dive: the mixed band-picker + custom-price UI

This is the focal pain point. The audit found that the same physical column in Section K hosts two distinct pricing modes with conflicting visibility rules, and only one of the two modes gets the rich assessment widget.

### 2.1 Visibility rules today

Looking at the relevant fields in [implementation_estimate.json](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.json):

| Field | Line | Visibility rule |
|---|---|---|
| `recommended_band` | json:426 | Hidden when `use_custom_price = 1` (via `depends_on: eval:!doc.use_custom_price`) |
| `use_custom_price` | json:434 | Always visible (the toggle itself) |
| `custom_price` | json:441 | Hidden when `use_custom_price = 0` (`depends_on: eval:doc.use_custom_price==1`) |
| `custom_price_assessment_html` | json:448 | Hidden when `use_custom_price = 0` (same `depends_on`) |

So on the screen, the column animates:

```
use_custom_price = 0   →   shows: recommended_band ▼
                                   (nothing else)

use_custom_price = 1   →   shows: ☑ Use Custom Price
                                   custom_price [    ]
                                   ┌──────────────────────────┐
                                   │ ✅ HEALTHY — Margin 33.4% │
                                   │ vs Floor:    −7.2%       │
                                   │ vs Standard: −6.4%       │
                                   │ vs Premium: −25.3%       │
                                   └──────────────────────────┘
```

### 2.2 Why this is confusing

Three concrete problems with the current state:

1. **No explicit mode signpost.** When you open an estimate, there's no header that says "You're in BAND MODE" or "You're in NEGOTIATED-PRICE MODE". The mode is implicit in whether one tiny checkbox is ticked. New users have to deduce this by trial and error.

2. **The assessment widget is asymmetric.** Pick Premium band → no visual feedback at all about whether that price is healthy. Type the *same number* into `custom_price` → suddenly a green "HEALTHY" banner with a comparison table. Same outcome economically, completely different on-screen experience.

3. **Silent mode-flip risk.** A negotiation often goes: pre-sales picks Standard → client pushes back → pre-sales ticks `use_custom_price` and types a lower number. There's no "are you switching mode?" prompt; the `recommended_band` field just vanishes. If the user later unticks the checkbox the band re-appears at whatever it was set to before — but `recommended_price` has now flipped back to the band amount silently. Easy to mis-quote.

### 2.3 What "good" looks like

A single explicit mode toggle at the top of the pricing block, with each mode getting its own self-contained panel + matching assessment widget. Sketch:

```
┌─ K. Pricing & Profitability ────────────────────────────────────────────────┐
│  Cost: ₹4.50L                                                                │
│                                                                              │
│  Pricing Strategy:    ● Pick a Band      ○ Negotiated Price                  │
│  ────────────────────────────────────────────────────────────────────────    │
│                                                                              │
│   (BAND MODE — radio selection, each option shows its margin)               │
│                                                                              │
│      ○ Conservative  ₹4.95L   (10% margin — safety floor)                    │
│      ● Standard       ₹6.43L  (30% margin — your target)        ← selected   │
│      ○ Premium        ₹8.03L  (44% margin — value pricing)                   │
│                                                                              │
│   Recommended Price: ₹6.43L                                                  │
│   ┌──────────────────────────────────────────────────────┐                   │
│   │ ✅ HEALTHY — 30% margin, exactly on target.          │ ← NEW: band       │
│   │ Standard band — typical for ERP projects with        │   gets its own    │
│   │ documented scope.                                    │   assessment      │
│   └──────────────────────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────────┘

  ─ OR if user picks ○ Negotiated Price ─

┌─ K. Pricing & Profitability ────────────────────────────────────────────────┐
│  Cost: ₹4.50L                                                                │
│                                                                              │
│  Pricing Strategy:    ○ Pick a Band      ● Negotiated Price                  │
│  ────────────────────────────────────────────────────────────────────────    │
│                                                                              │
│   (CUSTOM MODE — type your price, see assessment)                            │
│                                                                              │
│   Negotiated Price (INR):  [  ₹5,35,000  ]                                   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────┐                   │
│   │ ✅ HEALTHY — Margin 15.9%                            │                   │
│   │ Between Floor and Standard.                          │                   │
│   │ vs Floor (₹4.95L)     +8.1%                          │                   │
│   │ vs Standard (₹6.43L)  −16.8%                         │                   │
│   │ vs Premium (₹8.03L)   −33.4%                         │                   │
│   │                                                       │                   │
│   │ 💡 To hit your 30% target, try ₹6.43L                │ ← NEW: helper     │
│   └──────────────────────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

Key differences from today:

- **One Radio at the top makes the mode obvious.** Switching is deliberate; the UI doesn't quietly reshape.
- **In Band Mode, each band radio option shows its price + margin inline** — so the user is comparing three concrete options visually instead of seeing prices in a separate left-hand column.
- **Band Mode also gets an assessment widget** that says, e.g., *"Standard band — typical for ERP projects with documented scope"* or *"Conservative band — 10% margin only, expect overruns to wipe profit"*. The widget reads from the same `update_custom_price_assessment` logic, parameterised so it works for both modes.
- **Custom Mode adds a one-line suggestion** *"To hit your 30% target, try ₹X"* (already half-done — the data is there, just not surfaced) so the user can see the gap to their target without doing math.

### 2.4 What stays the same

This refinement is purely UX. None of the math changes:

- `calculate_pricing()` in the controller would still derive Floor / Standard / Premium identically.
- The `recommended_price` field stays the source of truth that downstream widgets (scenarios, sensitivity, Monte Carlo, break-even, Sales Order generation) read from.
- All formulas in `FIELDS.md` §5 stay valid.

The change is presentation only: one new radio field at the top of Section K, conditional rendering of two sub-panels, and reusing the existing assessment widget for both modes.

---

## 3. The Other Refinement Gaps (briefer)

These are real but less acute than the mixed-UI problem. Listed in priority order.

### 3.1 Tables render even when empty

Section L's scenario / sensitivity / Monte Carlo widgets all render on every form refresh, even when `grand_total_cost = 0` or `recommended_price = 0`. The widgets gracefully show "Fill cost + pricing to see…" messages, but the visual clutter on a fresh estimate is heavy — three big boxes saying "fill me in" before the user has even entered modules.

**Recommendation:** wrap each widget render in `if (frm.doc.grand_total_cost > 0 && frm.doc.recommended_price > 0)` so they appear only when there's something meaningful to show. The widgets stay functional, just hide their boxes until ready.

### 3.2 Monte Carlo invalidation is silent

When the user changes `recommended_price` (or any input that affects it), [`invalidate_monte_carlo()` at js:645](tbo_analytics/public/js/implementation_estimate.js#L645) re-renders the Monte Carlo card to its placeholder state. That's correct behaviour — the prior P10/P50/P90 numbers no longer reflect the current price.

But the visual change is subtle: the histogram + summary boxes disappear and the placeholder "Run Monte Carlo (1000 sims)" button comes back. If the user had glanced at the result a minute earlier and then changed something, they might not notice the panel quietly reset.

**Recommendation:** when invalidation fires and a previous result existed, show a yellow banner *"⚠️ Simulation is stale — price changed since last run."* with the Re-run button beside it. This is a one-line addition to `invalidate_monte_carlo()`.

### 3.3 Quoting currency ambiguity at Sales Order generation

If `display_view = "INR Only"` and the user marks the estimate Won, the auto-created Sales Order uses `quoting_currency` + `quoting_rate` + the buffered `recommended_price_quoting` per [handlers.py](tbo_analytics/tbo_analytics/handlers.py). The user might have been reading INR figures on the form the whole time and not realise the SO is denominated in SAR / AED / USD.

**Recommendation:** before the Won transition, prompt with a confirmation: *"This SO will be created in SAR at ₹/SAR 24.50, line rate SAR 26,936 (INR ₹6,42,500 incl. 5% FX buffer). Confirm?"* Lets the user catch a mismatched display vs quote currency.

### 3.4 No "suggest a better price" helper in DANGER mode

Today's `custom_price_assessment_html` widget tells the user the price is bad (LOSS / DANGER / BELOW TARGET) but doesn't suggest a number. Negotiation cycles get longer because the user has to compute the target price themselves.

**Recommendation:** in the assessment banner, when the price falls below the target margin band, append *"To hit your 30% target, try ₹X (Standard). To meet the floor minimum, try ₹Y."* The numbers are already in `floor_price` and `standard_price` — just surface them.

---

## 4. What's NOT Recommended Here

These are deliberately out of scope so the reader knows the audit was opinionated, not exhaustive:

| Out of scope | Why not |
|---|---|
| NPV / IRR / payback period | Adds financial sophistication but TBO's typical engagement is 3–6 months — discounted-cashflow math adds clutter without changing decisions at this duration. Worth revisiting if engagements stretch beyond 12 months. |
| Milestone-based cashflow modelling | Useful for fixed-fee contracts with staged payments, but the existing Sales Order + Project Invoicing already covers this if the user uses Frappe's milestone billing. Not something this app should duplicate. |
| Deferred AMC revenue calculation | `amc_suggested` is already shown as a one-line annual figure. Modelling its present value over 3–5 years is finance not estimation. |
| Deal-comparison view (multiple estimates side-by-side) | The Report Builder and the existing "Profitability Scenarios" report cover side-by-side comparisons across multiple estimates. The form is the wrong place to surface portfolio comparisons. |
| Win-probability modelling | Belongs in a CRM Lead/Opportunity workflow, not in the cost estimator. Anchoring pricing to a probabilistic win rate would conflate scope estimation with sales pipeline modelling. |
| Margin-floor enforcement / approval workflow | Would require a per-role permission system on `custom_price`. The audit found the existing workflow (Draft → Under Review → Approved) is already in place — adding a margin-threshold guard there is a 2-line change but belongs to permissions tightening, not the estimation loop. |

These are all reasonable ideas; they're just not what this app needs next.

---

## 5. Reading Guide

If you want to verify any claim in this document, every reference points to a real file + line range.

### Section K layout (JSON)

[`implementation_estimate.json`](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.json):

| Field | Line |
|---|---|
| `section_k` (Section break) | 372 |
| `display_view` (INR Only / Quoting Only / Both toggle) | 378 |
| `recommended_band` | 426 |
| `use_custom_price` | 434 |
| `custom_price` | 441 |
| `custom_price_assessment_html` | 448 |
| `quoting_currency`, `quoting_rate`, `quoting_rate_date`, `fx_buffer_pct` | 453, 460, 467, 475 |
| `section_l` | 578 |
| `scenario_table_html` | 588 |
| `sensitivity_table_html` | 593 |
| `monte_carlo_html` | 599 |

### Server-side controller methods (Python)

[`implementation_estimate.py`](tbo_analytics/tbo_analytics/doctype/implementation_estimate/implementation_estimate.py):

| Method | Line |
|---|---|
| `calculate_ai_estimates` | 51 |
| `calculate_final_hours` | 125 |
| `calculate_costs` (incl. driver-based indirect allocation) | 142 |
| `calculate_pricing` (band + custom override resolution) | 241 |
| `calculate_break_even` | 293 |
| `save_team_version` | 317 |
| `run_monte_carlo` (whitelisted) | 349 |
| `check_team_capacity` (whitelisted) | 444 |
| `get_quoting_exchange_rate` (whitelisted, with fallback chain) | 604 |
| `get_customer_default_currency` (whitelisted) | 642 |
| `get_employee_hourly_cost` (whitelisted, HRMS lookup) | 651 |

### Client-side functions (JS)

[`implementation_estimate.js`](tbo_analytics/public/js/implementation_estimate.js):

| Function | Line |
|---|---|
| `recalc_pricing` (live recomputation hub) | 342 |
| `update_scenario_table` | 403 |
| `update_sensitivity_table` | 465 |
| `update_custom_price_assessment` | 567 |
| `invalidate_monte_carlo` | 645 |
| `render_monte_carlo_placeholder` | 657 |
| `run_monte_carlo` | 682 |
| `build_monte_carlo_html` | 717 |
| `apply_display_view` | 807 |
| `fetch_quoting_rate` | 822 |
| `load_indirect_from_books` | 844 |

### Related documents in the repo root

| File | Coverage |
|---|---|
| [`FIELDS.md`](FIELDS.md) | Canonical field reference + 5-step controller pipeline formulas. Cite this for any math claim. |
| [`USAGE.md`](USAGE.md) | End-to-end workflow guide for new users. |
| [`COST_ESTIMATION_IDEAS.md`](COST_ESTIMATION_IDEAS.md) | Roadmap of estimation improvements — the mixed-UI refinement above would live here as a new entry. |
| [`INDIRECT_COST_ALLOCATION.md`](INDIRECT_COST_ALLOCATION.md) | Deep-dive on the 5-driver indirect cost allocation framework. |
| [`CHANGES.md`](CHANGES.md) | Bug-fix log and audit history. |

---

## Closing Note

The pricing → profitability loop has all the parts. What it needs is one explicit mode toggle to remove a class of user confusion, and three smaller polish items (empty-state suppression, Monte Carlo staleness flag, quoting-currency confirmation) that each fix a single concrete misuse risk. None require a refactor of the underlying math. The next iteration is a UX iteration, not an algorithmic one.
