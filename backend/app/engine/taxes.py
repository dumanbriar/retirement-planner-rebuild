"""Federal & state tax computation for a single plan year.

Methodology notes (also surfaced in the Excel workbook):
- Bracket thresholds, the standard deduction, LTCG breakpoints and IRMAA
  thresholds are 2026 statutory values (see constants.py for citations)
  indexed forward at the plan's assumed inflation rate. Exception: the top
  IRMAA income threshold ($500k single / $750k MFJ) is statutorily fixed
  (42 U.S.C. §1395r(i)(3)(C)) and is never indexed here.
- Social Security provisional-income thresholds and the NIIT MAGI
  thresholds are NOT indexed, per statute.
- Qualified dividends, realized long-term gains, AND cash interest are
  all net investment income under IRC §1411 and are included in the NIIT base.
- ACA premium tax credit (IRC §36B) requires MAGI ≥ 100% FPL; no PTC is
  modeled for below-poverty-line years. See aca_subsidy() for details.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as C


def _infl(base: float, year: int, inflation: float) -> float:
    return base * (1 + inflation) ** (year - C.BASE_YEAR)


@dataclass
class TaxYearInput:
    year: int
    filing_status: str            # "single" | "mfj"
    inflation: float
    # ordinary income components (nominal $)
    ordinary_income: float        # TD withdrawals + conversions + interest + pensions + non-medical HSA
    ss_benefits: float            # gross Social Security received
    # preferential-rate income
    qualified_dividends: float
    realized_ltcg: float
    # cash interest: already in ordinary_income for AGI; tracked separately
    # so it can be included in the NIIT net-investment-income base (IRC §1411)
    interest: float = 0.0
    ages_65_plus: int = 0         # count of filers 65+ this year
    state_rate: float = 0.0


@dataclass
class TaxYearResult:
    taxable_ss: float = 0.0
    agi: float = 0.0
    magi: float = 0.0             # AGI (no tax-exempt interest modeled)
    aca_magi: float = 0.0         # AGI + nontaxable SS (IRC sec. 36B(d)(2)(B))
    deductions: float = 0.0
    taxable_income: float = 0.0
    federal_tax: float = 0.0
    ltcg_tax: float = 0.0
    niit: float = 0.0
    state_tax: float = 0.0
    total: float = 0.0
    marginal_rate: float = 0.0


def taxable_social_security(ss: float, other_agi: float, status: str) -> float:
    """IRS Pub. 915 worksheet (IRC sec. 86). Thresholds are not indexed."""
    if ss <= 0:
        return 0.0
    provisional = other_agi + 0.5 * ss
    t1 = C.SS_TAX_THRESHOLD_1[status]
    t2 = C.SS_TAX_THRESHOLD_2[status]
    if provisional <= t1:
        return 0.0
    if provisional <= t2:
        return min(0.5 * (provisional - t1), 0.5 * ss)
    tier1 = min(0.5 * (t2 - t1), 0.5 * ss)
    return min(0.85 * (provisional - t2) + tier1, 0.85 * ss)


def _bracket_tax(taxable: float, brackets: list, scale: float) -> tuple[float, float]:
    """Tax and marginal rate. Thresholds scaled by `scale`
    (inflation indexing from the 2026 base year)."""
    tax = 0.0
    lower = 0.0
    marginal = brackets[0][1]
    for top, rate in brackets:
        top_s = top * scale if top != float("inf") else top
        if taxable > lower:
            amt = min(taxable, top_s) - lower
            tax += amt * rate
            marginal = rate
        if taxable <= top_s:
            break
        lower = top_s
    return tax, marginal


def compute_taxes(inp: TaxYearInput) -> TaxYearResult:
    r = TaxYearResult()
    status = inp.filing_status
    scale = (1 + inp.inflation) ** (inp.year - C.BASE_YEAR)

    pref_income = inp.qualified_dividends + max(0.0, inp.realized_ltcg)
    other_agi = inp.ordinary_income + pref_income
    r.taxable_ss = taxable_social_security(inp.ss_benefits, other_agi, status)
    r.agi = other_agi + r.taxable_ss
    r.magi = r.agi
    r.aca_magi = r.agi + (inp.ss_benefits - r.taxable_ss)

    # deductions: standard + 65+ additional + OBBBA senior bonus (2025-2028)
    ded = C.STANDARD_DEDUCTION[status] * scale
    ded += C.ADDITIONAL_STD_DEDUCTION_65[status] * scale * inp.ages_65_plus
    if inp.year <= C.SENIOR_BONUS_LAST_YEAR and inp.ages_65_plus:
        bonus = C.SENIOR_BONUS_DEDUCTION * inp.ages_65_plus
        phaseout = max(0.0, r.magi - C.SENIOR_BONUS_PHASEOUT_START[status]) * C.SENIOR_BONUS_PHASEOUT_RATE
        ded += max(0.0, bonus - phaseout)
    r.deductions = ded
    r.taxable_income = max(0.0, r.agi - ded)

    # split taxable income: preferential income stacks on top of ordinary
    pref_taxable = min(pref_income, r.taxable_income)
    ord_taxable = r.taxable_income - pref_taxable

    ord_tax, marginal = _bracket_tax(ord_taxable, C.FEDERAL_BRACKETS[status], scale)

    # LTCG/QDI stacked at 0/15/20 (IRC sec. 1(h))
    zero_top, fifteen_top = (b * scale for b in C.LTCG_BRACKETS[status])
    g = pref_taxable
    in_zero = max(0.0, min(ord_taxable + g, zero_top) - ord_taxable)
    in_fifteen = max(0.0, min(ord_taxable + g, fifteen_top) - max(ord_taxable, zero_top))
    in_twenty = max(0.0, g - in_zero - in_fifteen)
    r.ltcg_tax = in_fifteen * 0.15 + in_twenty * 0.20

    r.federal_tax = ord_tax + r.ltcg_tax
    r.marginal_rate = marginal

    # NIIT: 3.8% on net investment income above unindexed MAGI threshold
    # NII includes dividends, realized gains, AND interest (IRC §1411)
    nii = inp.qualified_dividends + max(0.0, inp.realized_ltcg) + inp.interest
    excess = max(0.0, r.magi - C.NIIT_THRESHOLD[status])
    r.niit = C.NIIT_RATE * min(nii, excess)

    r.state_tax = inp.state_rate * r.taxable_income
    r.total = r.federal_tax + r.niit + r.state_tax
    return r


# ----------------------------- healthcare ---------------------------------

def irmaa_tier(magi_two_years_prior: float, status: str, year: int, inflation: float) -> int:
    """0-5; thresholds 0-3 are indexed; top threshold is statutorily fixed."""
    thresholds = C.IRMAA_THRESHOLDS[status]
    tier = 0
    for i, t in enumerate(thresholds):
        # last tier ($500k single / $750k MFJ) is fixed (42 U.S.C. §1395r(i)(3)(C))
        scaled = t if i == len(thresholds) - 1 else _infl(t, year, inflation)
        if magi_two_years_prior > scaled:
            tier = i + 1
    return tier


def medicare_part_b_annual(tier: int, year: int, healthcare_inflation: float) -> tuple[float, float]:
    """(standard annual premium, IRMAA surcharge) for one person."""
    std = _infl(C.MEDICARE_PART_B_MONTHLY * 12, year, healthcare_inflation)
    total = std * C.IRMAA_MULTIPLIERS[tier]
    return std, total - std


def aca_applicable_pct(fpl_ratio: float) -> float | None:
    """Required contribution % of MAGI; None above the 400% FPL cliff.
    2026 schedule per Rev. Proc. 2025-25 (post-ARPA-expiry)."""
    if fpl_ratio > C.ACA_CLIFF_FPL:
        return None
    for lo, hi, p_lo, p_hi in C.ACA_APPLICABLE_PCT:
        if fpl_ratio <= hi or (lo, hi) == (3.00, 4.00):
            if fpl_ratio < lo:
                return p_lo
            if hi == lo:
                return p_lo
            f = (fpl_ratio - lo) / (hi - lo) if hi > lo else 0.0
            return p_lo + f * (p_hi - p_lo)
    return None


def aca_subsidy(aca_magi: float, household_size: int, benchmark_annual: float,
                year: int, inflation: float) -> float:
    """Premium tax credit = benchmark - applicable%(FPL ratio) * MAGI,
    floored at 0; zero above 400% FPL (2026 cliff). FPL indexed at the
    plan inflation assumption."""
    fpl = _infl(C.FPL_FIRST_PERSON + C.FPL_PER_ADDITIONAL * (household_size - 1), year, inflation)
    ratio = aca_magi / fpl if fpl > 0 else 99
    if ratio < 1.0:
        # below 100% FPL → no PTC (IRC §36B(c)(1)(A)); household may qualify
        # for Medicaid (expansion states) or face a coverage gap. Not modeled.
        return 0.0
    pct = aca_applicable_pct(ratio)
    if pct is None:
        return 0.0
    return max(0.0, benchmark_annual - pct * aca_magi)
