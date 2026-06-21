"""Plan orchestration: resolves the Roth-conversion strategy, optionally
optimizes Social Security claiming ages, runs sensitivity scenarios, and
assembles the full PlanResult.

The "optimizer" is deliberately transparent rather than a black-box LP:
it exhaustively evaluates a small, explainable strategy space (bracket-fill
Roth conversion levels x claiming-age grid) and reports every candidate it
considered, so an advisor can see exactly why the chosen strategy won.
The objective is ending after-tax wealth in today's dollars (tax-deferred
and HSA balances discounted at the heir tax rate; taxable assumed to
receive a basis step-up under IRC sec. 1014).
"""
from __future__ import annotations

import copy

from ..models import (Account, AccountType, AccountVehicle,
                      ContributionSplitCell, ConversionStrategy, PlanInput,
                      PlanResult, SensitivityRow, SSGridCell, StrategyComparison)
from . import constants as C
from .engine import Simulator

FILL_STRATEGIES = [ConversionStrategy.none, ConversionStrategy.fill_10,
                   ConversionStrategy.fill_12, ConversionStrategy.fill_22,
                   ConversionStrategy.fill_24]

# Traditional-vs-Roth split candidates: fraction of the contribution budget
# routed to Roth. A small, explainable grid (like the bracket-fill levels).
SPLIT_LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]


def _run(plan: PlanInput, strategy: ConversionStrategy,
         claim_ages: list[int] | None = None):
    sim = Simulator(plan, strategy=strategy, claim_ages=claim_ages)
    rows, metrics = sim.run()
    return sim, rows, metrics


def resolve_strategy(plan: PlanInput, claim_ages: list[int] | None = None
                     ) -> tuple[ConversionStrategy, list[StrategyComparison]]:
    requested = plan.assumptions.roth_conversion_strategy
    candidates = FILL_STRATEGIES if requested == ConversionStrategy.auto else [requested]
    comparisons: list[StrategyComparison] = []
    best, best_val = candidates[0], float("-inf")
    for s in candidates:
        _, rows, m = _run(plan, s, claim_ages)
        total_conv = sum(r.roth_conversion for r in rows)
        comparisons.append(StrategyComparison(
            strategy=s.value, ending_after_tax_real=m.ending_after_tax_real,
            lifetime_taxes_real=m.lifetime_taxes_real,
            total_converted=total_conv, depletion_age=m.depletion_age))
        # success first, then after-tax terminal wealth
        val = (0 if m.depleted else 1e15) + m.ending_after_tax_real
        if val > best_val:
            best, best_val = s, val
    if requested != ConversionStrategy.auto:
        # in fixed mode, still show the alternative fill levels for context
        for s in FILL_STRATEGIES:
            if s == requested:
                continue
            _, rows, m = _run(plan, s, claim_ages)
            comparisons.append(StrategyComparison(
                strategy=s.value, ending_after_tax_real=m.ending_after_tax_real,
                lifetime_taxes_real=m.lifetime_taxes_real,
                total_converted=sum(r.roth_conversion for r in rows),
                depletion_age=m.depletion_age))
    return best, comparisons


def optimize_ss(plan: PlanInput, strategy: ConversionStrategy
                ) -> tuple[list[int], list[SSGridCell]]:
    """Exhaustive claiming-age grid (62-70 per person with a benefit)."""
    persons = plan.persons
    ranges = []
    for p in persons:
        if p.ss_monthly_at_fra > 0:
            lo = max(62, p.current_age)  # cannot claim in the past
            ranges.append(list(range(lo, 71)))
        else:
            ranges.append([p.ss_claim_age])
    combos = [[a] for a in ranges[0]]
    if len(ranges) == 2:
        combos = [[a, b] for a in ranges[0] for b in ranges[1]]
    grid: list[SSGridCell] = []
    best, best_val = None, float("-inf")
    for ages in combos:
        _, _, m = _run(plan, strategy, ages)
        grid.append(SSGridCell(claim_ages=ages,
                               ending_after_tax_real=m.ending_after_tax_real,
                               depletion_age=m.depletion_age))
        val = (0 if m.depleted else 1e15) + m.ending_after_tax_real
        if val > best_val:
            best, best_val = ages, val
    return best or [p.ss_claim_age for p in persons], grid


def _retirement_budget(plan: PlanInput, owner: int) -> float:
    """A person's combined Traditional + Roth annual contribution budget."""
    return sum(a.annual_contribution for a in plan.accounts if a.owner == owner
               and a.type in (AccountType.tax_deferred, AccountType.roth))


def _current_household_split(plan: PlanInput) -> float:
    """Household-wide current Roth fraction = total Roth contributions / total
    Traditional+Roth contribution budget across all persons."""
    total = sum(_retirement_budget(plan, i) for i in range(len(plan.persons)))
    if total <= 0:
        return 0.0
    roth = sum(a.annual_contribution for a in plan.accounts
               if a.type == AccountType.roth)
    return roth / total


def apply_split(plan: PlanInput, roth_pct: list[float]) -> PlanInput:
    """Return a deepcopy with each person's Traditional/Roth contributions
    reallocated to `roth_pct`. The split is applied within each vehicle bucket
    (employer / IRA) so per-vehicle totals — and therefore the applicable
    contribution limits — are preserved."""
    p2 = copy.deepcopy(plan)
    for i in range(len(p2.persons)):
        pct = roth_pct[i]
        for vehicle in (AccountVehicle.employer, AccountVehicle.ira):
            td = [a for a in p2.accounts if a.owner == i
                  and a.type == AccountType.tax_deferred
                  and a.limit_vehicle() == vehicle]
            roth = [a for a in p2.accounts if a.owner == i
                    and a.type == AccountType.roth
                    and a.limit_vehicle() == vehicle]
            budget = sum(a.annual_contribution for a in td + roth)
            if budget <= 0:
                continue
            roth_amt = budget * pct
            like = (td or roth)[0]
            roth_home = roth[0] if roth else _synth(p2, i, AccountType.roth, vehicle, like)
            td_home = td[0] if td else _synth(p2, i, AccountType.tax_deferred, vehicle, like)
            for a in td + roth:
                a.annual_contribution = 0.0
            roth_home.annual_contribution = roth_amt
            td_home.annual_contribution = budget - roth_amt
    return p2


def _synth(plan: PlanInput, owner: int, type_: AccountType,
           vehicle: AccountVehicle, like: Account) -> Account:
    """Add a zero-balance sibling account so a person can hold the other side
    of a split they don't currently have (mirrors the engine's auto-added
    surplus account)."""
    label = "Roth" if type_ == AccountType.roth else "Traditional"
    acct = Account(name=f"{label} ({vehicle.value}, optimizer)", type=type_,
                   owner=owner, vehicle=vehicle, balance=0.0,
                   annual_contribution=0.0, expected_return=like.expected_return)
    plan.accounts.append(acct)
    return acct


def optimize_contribution_split(
        plan: PlanInput, strategy: ConversionStrategy, claim_ages: list[int]
) -> tuple[list[float], list[ContributionSplitCell]]:
    """Suggest the household-wide Traditional-vs-Roth contribution split.

    A couple files jointly, so only the household's total Roth fraction matters
    (a dollar in either spouse's Roth is identical to the household). We search
    a single percentage applied uniformly to both spouses rather than an
    independent per-person grid. Each candidate is a full re-simulation; the
    objective is ending after-tax wealth (success first). The household's
    current allocation is included for context.

    Returns (suggested split as a single-element [household_pct], cells). This
    is ADVISORY: build_plan does not apply it to the projection. The returned
    list has one element regardless of the number of persons.
    """
    n = len(plan.persons)
    if sum(_retirement_budget(plan, i) for i in range(n)) <= 0:
        return [], []
    current = round(_current_household_split(plan), 4)

    def score(m) -> float:
        return (0 if m.depleted else 1e15) + m.ending_after_tax_real

    cells: list[ContributionSplitCell] = []
    # the user's actual allocation — matches the headline projection
    _, _, m_cur = _run(plan, strategy, claim_ages)
    cells.append(ContributionSplitCell(
        roth_pct=[current], ending_after_tax_real=m_cur.ending_after_tax_real,
        lifetime_taxes_real=m_cur.lifetime_taxes_real,
        depletion_age=m_cur.depletion_age, is_current=True))
    best, best_val = [current], score(m_cur)

    for pct in SPLIT_LEVELS:
        if abs(pct - current) < 0.005:
            continue  # the current cell already represents this household %
        _, _, m = _run(apply_split(plan, [pct] * n), strategy, claim_ages)
        cells.append(ContributionSplitCell(
            roth_pct=[round(pct, 4)], ending_after_tax_real=m.ending_after_tax_real,
            lifetime_taxes_real=m.lifetime_taxes_real, depletion_age=m.depletion_age,
            is_current=False))
        if score(m) > best_val:
            best, best_val = [round(pct, 4)], score(m)
    return best, cells


def sensitivity_scenarios(plan: PlanInput, strategy: ConversionStrategy,
                          claim_ages: list[int]) -> list[SensitivityRow]:
    def perturbed(mutate) -> PlanInput:
        p2 = copy.deepcopy(plan)
        mutate(p2)
        return p2

    def shift_returns(p: PlanInput, delta: float):
        for acc in p.accounts:
            acc.expected_return = max(-0.10, min(0.20, acc.rate() + delta))

    scenarios = [
        ("All returns -1%", "returns", "-1%", lambda p: shift_returns(p, -0.01)),
        ("All returns +1%", "returns", "+1%", lambda p: shift_returns(p, +0.01)),
        ("All returns -2%", "returns", "-2%", lambda p: shift_returns(p, -0.02)),
        ("Inflation +1%", "inflation", "+1%",
         lambda p: setattr(p.assumptions, "inflation",
                           min(0.10, p.assumptions.inflation + 0.01))),
        ("Spending +10%", "spending", "+10%",
         lambda p: setattr(p, "annual_spending", p.annual_spending * 1.10)),
        ("Spending -10%", "spending", "-10%",
         lambda p: setattr(p, "annual_spending", p.annual_spending * 0.90)),
        ("Retire 2 years earlier", "retirement_age", "-2 yrs",
         lambda p: [setattr(x, "retirement_age",
                            max(x.current_age + 1, x.retirement_age - 2))
                    for x in p.persons]),
        ("Retire 2 years later", "retirement_age", "+2 yrs",
         lambda p: [setattr(x, "retirement_age", min(80, x.retirement_age + 2))
                    for x in p.persons]),
        ("Social Security cut 23% in 2034", "social_security", "-23%",
         "SS_CUT"),
        ("Live to 100", "longevity", "to 100",
         lambda p: [setattr(x, "death_age", 100) for x in p.persons]),
    ]

    out: list[SensitivityRow] = []
    for label, param, delta, mutate in scenarios:
        if mutate == "SS_CUT":
            # OASI trust-fund depletion scenario: 2024 SSA Trustees Report
            # projects ~23% across-the-board cut at depletion (2033-2035).
            p2 = copy.deepcopy(plan)
            for x in p2.persons:
                x.ss_monthly_at_fra *= 0.77
            ca = claim_ages
        else:
            p2 = perturbed(mutate)
            ca = [min(max(claim_ages[i], 62), 70) for i in range(len(claim_ages))]
        try:
            _, _, m = _run(p2, strategy, ca)
            out.append(SensitivityRow(
                label=label, parameter=param, delta=delta,
                ending_net_worth_real=m.ending_net_worth_real,
                nest_egg_real=m.nest_egg_at_retirement_real,
                depletion_age=m.depletion_age, success=m.success))
        except Exception:
            continue
    return out


def assumption_notes(plan: PlanInput) -> list[dict[str, str]]:
    a = plan.assumptions
    def fpct(v):
        s = f"{v * 100:g}%"
        return s
    notes = [
        {"label": "Base parameter year", "value": str(C.BASE_YEAR),
         "kind": "modeled",
         "source": "All statutory amounts are 2026 values; see per-item sources below."},
        {"label": "General inflation", "value": fpct(a.inflation), "kind": "assumed",
         "source": "User assumption. Used for spending, COLAs, and indexing of tax "
                   "brackets/deductions/IRMAA thresholds (the IRS actually uses chained "
                   "CPI rounded to $25/$50 steps)."},
        {"label": "Healthcare inflation", "value": fpct(a.healthcare_inflation),
         "kind": "assumed", "source": "User assumption applied to premiums and OOP costs."},
        {"label": "Federal brackets & standard deduction", "value": "2026 statutory",
         "kind": "modeled", "source": "IRS Rev. Proc. 2025-32; OBBBA (P.L. 119-21) made "
                   "TCJA rates permanent. Indexed forward at assumed inflation."},
        {"label": "LTCG/qualified dividend brackets", "value": "0/15/20% stacking",
         "kind": "modeled", "source": "IRC sec. 1(h); 2026 breakpoints per Rev. Proc. 2025-32."},
        {"label": "Social Security taxation", "value": "Pub. 915 worksheet",
         "kind": "modeled", "source": "IRC sec. 86. Thresholds ($25k/$34k single, "
                   "$32k/$44k MFJ) are NOT inflation-indexed, by statute."},
        {"label": "SS claiming adjustments", "value": "exact monthly formula",
         "kind": "modeled", "source": "42 U.S.C. 402(q)/(w): 5/9% & 5/12% monthly early "
                   "reduction; 2/3%/month delayed credits to 70. Spousal: 50% of PIA, "
                   "reduced 25/36%/month if early."},
        {"label": "SS COLA", "value": fpct(a.inflation), "kind": "assumed",
         "source": "Plan inflation used as COLA proxy (actual COLA tracks CPI-W)."},
        {"label": "RMDs", "value": "start 73 (born 1951-59) / 75 (1960+)",
         "kind": "modeled", "source": "SECURE 2.0 sec. 107; IRS Uniform Lifetime Table, "
                   "Pub. 590-B."},
        {"label": "Medicare Part B + IRMAA", "value": "$202.90/mo 2026 base",
         "kind": "modeled", "source": "CMS 2026 announcement; IRMAA multipliers per "
                   "42 U.S.C. 1395r(i) with 2-year MAGI lookback (modeled explicitly)."},
        {"label": "ACA premium credit (pre-65)", "value": "2026 schedule w/ 400% FPL cliff",
         "kind": "estimated", "source": "Rev. Proc. 2025-25 applicable percentages; "
                   "2025 HHS poverty guidelines. Benchmark premium is a user estimate. "
                   "IRC §36B(c)(1)(A) requires MAGI ≥ 100% FPL for any PTC; when projected "
                   "MAGI falls below this threshold, no subsidy is modeled (household may "
                   "qualify for Medicaid in expansion states). This can materially affect "
                   "strategy comparisons for early retirees funded from Roth/basis/cash."},
        {"label": "ACA below-poverty-line years", "value": "no PTC modeled",
         "kind": "estimated",
         "source": "IRC §36B(c)(1)(A) requires MAGI ≥ 100% FPL for PTC eligibility. "
                   "Low-MAGI pre-65 years show $0 ACA subsidy in the audit workbook; "
                   "actual coverage depends on state Medicaid expansion status."},
        {"label": "NIIT", "value": "3.8% on dividends, gains & interest over $200k/$250k MAGI",
         "kind": "modeled",
         "source": "IRC sec. 1411. Thresholds NOT indexed, by statute. Net investment "
                   "income includes qualified dividends, realized capital gains, and cash "
                   "interest (all investment income under §1411(c))."},
        {"label": "Future home purchase", "value": "mortgage + down payment at start age",
         "kind": "estimated",
         "source": "A liability with a start age models a future purchase: the mortgage "
                   "and a one-time down payment begin that year. Amounts are entered as "
                   "the literal (nominal) dollar values at the purchase date — the actual "
                   "loan and down payment expected — not today's dollars. The home itself "
                   "is NOT modeled as an asset, so net worth "
                   "reflects only the new debt and the cash spent — it understates reality "
                   "by roughly the property's value. Pre-retirement mortgage payments are "
                   "assumed covered by (unmodeled) wages, as with existing debts; the down "
                   "payment is always drawn from the portfolio."},
        {"label": "Withdrawal order", "value": "cash > taxable > tax-deferred > Roth > HSA",
         "kind": "modeled", "source": "Conventional tax-efficient sequencing; HSA reserved "
                   "for qualified medical first (tax-free per IRC sec. 223)."},
        {"label": "Roth conversion strategy", "value": a.roth_conversion_strategy.value,
         "kind": "modeled", "source": "Bracket-fill conversions; 'auto' exhaustively "
                   "compares fill levels on ending after-tax wealth."},
        {"label": "Roth vs. Traditional contributions",
         "value": "split suggested (advisory)" if a.optimize_contribution_split
                  else "as entered",
         "kind": "modeled",
         "source": "The projection always models the contributions you entered. "
                   "When enabled, a single household Traditional/Roth split (the "
                   "couple files jointly, so only the household ratio matters) is "
                   "compared across levels on ending after-tax wealth and the best "
                   "is shown as a suggestion — it is NOT applied to the projection "
                   "('invest the tax savings': the Traditional deduction, valued "
                   "at the real marginal bracket from salary, is reinvested in a "
                   "taxable account). Contribution caps are vehicle-aware per "
                   "person — IRC sec. 402(g) elective-deferral for 401(k)/403(b), "
                   "IRC sec. 219 for IRAs (2026 values indexed at the inflation "
                   "assumption) — and over-limit inputs are flagged, not capped. "
                   "Roth IRA contributions above the MAGI phase-out are allowed "
                   "but flagged as requiring a backdoor Roth; the pro-rata rule "
                   "(IRC sec. 408(d)(2)) on existing pre-tax IRA balances and "
                   "FICA are not modeled."},
        {"label": "Pre-retirement income tax (with salary)",
         "value": "modeled from wages" if any(p.salary > 0 for p in plan.persons)
                  else "not entered (flat-rate drag only)",
         "kind": "modeled",
         "source": "When salaries are entered, working-year federal/state income "
                   "tax is computed on wages plus pre-retirement inflows (less "
                   "Traditional deferrals) using the same tax engine as "
                   "retirement; wage tax is assumed paid from wages and does not "
                   "draw down the portfolio. Dividend/cash-interest drag still "
                   "applies separately. Wages grow at the inflation assumption."},
        {"label": "Pre-retirement tax treatment",
         "value": f"{fpct(a.pre_retirement_tax_rate)} flat drag",
         "kind": "assumed",
         "source": "The flat pre-retirement rate applies to the annual cash-"
                   "interest drag and (when no salary is entered) to pre-retirement "
                   "RMD/SS inflows; the dividend drag is a separate 15%. When a "
                   "salary is entered, working-year income tax and those inflows are "
                   "modeled with the full tax engine instead — see 'Pre-retirement "
                   "income tax (with salary)'."},
        {"label": "Heir tax rate (terminal valuation)", "value": fpct(a.heir_tax_rate),
         "kind": "assumed", "source": "Discount on inherited tax-deferred/HSA dollars; "
                   "taxable assets assume basis step-up (IRC sec. 1014)."},
        {"label": "Return timing", "value": "annual, start-of-year flows",
         "kind": "modeled", "source": "Deterministic annual compounding; income recognized "
                   "on start-of-year balances. No return volatility (see sensitivity)."},
        {"label": "Roth pre-59½ withdrawals", "value": "treated as contribution basis",
         "kind": "estimated",
         "source": "Roth withdrawals before age 59½ are modeled as returning contribution "
                   "basis (no tax/penalty), per IRC §72(t)(2)(A)(i). Ordering rules for "
                   "contributions vs. conversions vs. earnings are not tracked per-layer. "
                   "This is optimistic for large earnings pools; Roth is last in the "
                   "withdrawal waterfall so this edge rarely applies."},
    ]
    # Attach freshness metadata (last_updated, stale, review_url) to matched notes
    _NOTE_KEY_MAP = {
        "Federal brackets & standard deduction": "federal_brackets",
        "LTCG/qualified dividend brackets": "ltcg_brackets",
        "Medicare Part B + IRMAA": "medicare_part_b",
        "ACA premium credit (pre-65)": "aca_applicable_pct",
        "RMDs": "rmd_ages",
        "Roth vs. Traditional contributions": "contribution_limits",
    }
    freshness = {f["key"]: f for f in C.constants_freshness()}
    for note in notes:
        key = _NOTE_KEY_MAP.get(note["label"])
        if key and key in freshness:
            f = freshness[key]
            note["last_updated"] = f["last_updated"]
            note["stale"] = "true" if f["stale"] else "false"
            note["review_url"] = f["review_url"]
    return notes


def build_plan(plan: PlanInput) -> PlanResult:
    claim_ages = [p.ss_claim_age for p in plan.persons]
    strategy, comparisons = resolve_strategy(plan, claim_ages)

    ss_grid: list[SSGridCell] = []
    if plan.assumptions.optimize_ss_claiming and \
            any(p.ss_monthly_at_fra > 0 for p in plan.persons):
        claim_ages, ss_grid = optimize_ss(plan, strategy)
        # re-resolve the conversion strategy under the optimized claim ages
        strategy, comparisons = resolve_strategy(plan, claim_ages)

    # The contribution-split optimizer is ADVISORY: it suggests the best
    # household Traditional-vs-Roth split but does NOT change the modeled plan,
    # which always reflects the user's entered allocation. (SS claiming and Roth
    # conversions still apply, since those are plan parameters, not "your input
    # vs a suggestion".)
    contribution_split: list[ContributionSplitCell] = []
    chosen_split: list[float] = []
    no_salary = not any(p.salary > 0 for p in plan.persons)
    if plan.assumptions.optimize_contribution_split:
        chosen_split, contribution_split = optimize_contribution_split(
            plan, strategy, claim_ages)

    sim, rows, metrics = _run(plan, strategy, claim_ages)
    metrics.chosen_contribution_split = chosen_split
    sens = sensitivity_scenarios(plan, strategy, claim_ages)

    if plan.assumptions.optimize_contribution_split and contribution_split and no_salary:
        sim.warnings.append(
            "Traditional-vs-Roth optimization needs each working person's "
            "salary to value the Traditional deduction; with no salary entered "
            "the upfront tax benefit is ignored and the result favors Roth.")

    return PlanResult(metrics=metrics, years=rows, sensitivity=sens,
                      conversion_comparison=comparisons, ss_grid=ss_grid,
                      contribution_split=contribution_split,
                      warnings=sim.warnings,
                      assumption_notes=assumption_notes(plan))
