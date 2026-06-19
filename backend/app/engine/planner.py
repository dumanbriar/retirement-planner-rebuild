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

from ..models import (ConversionStrategy, PlanInput, PlanResult,
                      SensitivityRow, SSGridCell, StrategyComparison)
from . import constants as C
from .engine import Simulator

FILL_STRATEGIES = [ConversionStrategy.none, ConversionStrategy.fill_10,
                   ConversionStrategy.fill_12, ConversionStrategy.fill_22,
                   ConversionStrategy.fill_24]


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
    return [
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
        {"label": "Withdrawal order", "value": "cash > taxable > tax-deferred > Roth > HSA",
         "kind": "modeled", "source": "Conventional tax-efficient sequencing; HSA reserved "
                   "for qualified medical first (tax-free per IRC sec. 223)."},
        {"label": "Roth conversion strategy", "value": a.roth_conversion_strategy.value,
         "kind": "modeled", "source": "Bracket-fill conversions; 'auto' exhaustively "
                   "compares fill levels on ending after-tax wealth."},
        {"label": "Pre-retirement tax treatment", "value": f"{fpct(a.pre_retirement_tax_rate)} flat",
         "kind": "assumed", "source": "Wages are not modeled. Dividend drag at 15%; cash "
                   "interest and pre-retirement RMD/SS inflows taxed at this flat rate."},
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


def build_plan(plan: PlanInput) -> PlanResult:
    claim_ages = [p.ss_claim_age for p in plan.persons]
    strategy, comparisons = resolve_strategy(plan, claim_ages)

    ss_grid: list[SSGridCell] = []
    if plan.assumptions.optimize_ss_claiming and \
            any(p.ss_monthly_at_fra > 0 for p in plan.persons):
        claim_ages, ss_grid = optimize_ss(plan, strategy)
        # re-resolve the conversion strategy under the optimized claim ages
        strategy, comparisons = resolve_strategy(plan, claim_ages)

    sim, rows, metrics = _run(plan, strategy, claim_ages)
    sens = sensitivity_scenarios(plan, strategy, claim_ages)

    return PlanResult(metrics=metrics, years=rows, sensitivity=sens,
                      conversion_comparison=comparisons, ss_grid=ss_grid,
                      warnings=sim.warnings,
                      assumption_notes=assumption_notes(plan))
