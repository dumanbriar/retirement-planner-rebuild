"""Authoritative tax / benefit parameters used by the projection engine.

Every constant in this file is traceable to a primary source, cited inline.
The engine's base parameter year is 2026. Amounts that are indexed by law
are grown from these 2026 values using the plan's assumed inflation rate
(the IRS actually indexes with chained CPI rounded to $25/$50 increments;
using the plan inflation assumption instead is a documented modeling
assumption surfaced in the UI and the Excel workbook).

Amounts that are NOT indexed by statute (Social Security taxability
thresholds, NIIT thresholds) are held fixed in nominal terms, which is a
material and often-overlooked real-world effect.
"""

BASE_YEAR = 2026

# ---------------------------------------------------------------------------
# Federal ordinary income tax brackets, tax year 2026.
# Source: IRS Rev. Proc. 2025-32 (released Oct 9, 2025), reflecting the
# rate structure made permanent by the One Big Beautiful Bill Act of 2025
# (P.L. 119-21). Tuples are (top_of_bracket, rate); the last bracket is
# unbounded.
# ---------------------------------------------------------------------------
FEDERAL_BRACKETS = {
    "single": [
        (12_400, 0.10),
        (50_400, 0.12),
        (105_700, 0.22),
        (201_775, 0.24),
        (256_225, 0.32),
        (640_600, 0.35),
        (float("inf"), 0.37),
    ],
    "mfj": [
        (24_800, 0.10),
        (100_800, 0.12),
        (211_400, 0.22),
        (403_550, 0.24),
        (512_450, 0.32),
        (768_700, 0.35),
        (float("inf"), 0.37),
    ],
}

# Standard deduction, tax year 2026.
# Source: Rev. Proc. 2025-32; base amounts set by OBBBA sec. 70102.
STANDARD_DEDUCTION = {"single": 16_100, "mfj": 32_200}

# Additional standard deduction for age 65+, tax year 2026 (per person for
# MFJ; single amount applies to the unmarried filer).
# Source: Rev. Proc. 2025-32; IRC sec. 63(f).
ADDITIONAL_STD_DEDUCTION_65 = {"single": 2_050, "mfj": 1_650}

# "Senior bonus" deduction: $6,000 per individual age 65+, tax years
# 2025-2028 only, phased out at 6% of MAGI above $75,000 (single) /
# $150,000 (MFJ). Source: OBBBA sec. 70103 (new IRC sec. 151(d)(6)).
SENIOR_BONUS_DEDUCTION = 6_000
SENIOR_BONUS_LAST_YEAR = 2028
SENIOR_BONUS_PHASEOUT_START = {"single": 75_000, "mfj": 150_000}
SENIOR_BONUS_PHASEOUT_RATE = 0.06

# ---------------------------------------------------------------------------
# Long-term capital gains / qualified dividend brackets, tax year 2026.
# (top_of_0%_bracket, top_of_15%_bracket); 20% above.
# Source: Rev. Proc. 2025-32; IRC sec. 1(h), 1(j)(5).
# ---------------------------------------------------------------------------
LTCG_BRACKETS = {
    "single": (49_450, 545_500),
    "mfj": (98_900, 613_700),
}

# Net Investment Income Tax: 3.8% on net investment income above MAGI
# thresholds that are NOT inflation-indexed. Source: IRC sec. 1411.
NIIT_RATE = 0.038
NIIT_THRESHOLD = {"single": 200_000, "mfj": 250_000}

# ---------------------------------------------------------------------------
# Social Security benefit taxation (IRC sec. 86; IRS Pub. 915 worksheet).
# Provisional-income thresholds are fixed by statute and NOT indexed.
# ---------------------------------------------------------------------------
SS_TAX_THRESHOLD_1 = {"single": 25_000, "mfj": 32_000}
SS_TAX_THRESHOLD_2 = {"single": 34_000, "mfj": 44_000}

# ---------------------------------------------------------------------------
# Social Security claiming-age rules.
# Full retirement age by birth year: SSA, https://www.ssa.gov/benefits/retirement/planner/agereduction.html
# Early-claiming reduction: 5/9 of 1% per month for the first 36 months
# before FRA, 5/12 of 1% per month beyond 36 (SSA; 42 U.S.C. 402(q)).
# Delayed retirement credits: 2/3 of 1% per month (8%/yr) up to age 70 for
# beneficiaries born 1943+ (SSA; 42 U.S.C. 402(w)).
# Spousal benefit: up to 50% of the worker's PIA, reduced 25/36 of 1% per
# month for the first 36 months early, 5/12 of 1% beyond; spousal benefits
# earn no delayed credits (SSA).
# ---------------------------------------------------------------------------
def full_retirement_age_months(birth_year: int) -> int:
    """FRA expressed in months of age (e.g. 67y -> 804)."""
    if birth_year <= 1954:
        return 66 * 12
    if birth_year >= 1960:
        return 67 * 12
    return 66 * 12 + (birth_year - 1954) * 2


# ---------------------------------------------------------------------------
# Required Minimum Distributions.
# Beginning age: 73 for those born 1951-1959, 75 for those born 1960+
# (SECURE 2.0 Act of 2022, sec. 107; the 1959 drafting ambiguity is
# resolved to 73 per IRS proposed regs REG-103529-23, July 2024).
# ---------------------------------------------------------------------------
def rmd_start_age(birth_year: int) -> int:
    if birth_year <= 1950:
        return 72  # pre-SECURE 2.0; already in pay status for such ages
    if birth_year <= 1959:
        return 73
    return 75


# IRS Uniform Lifetime Table (Table III), effective for distribution years
# 2022+. Source: IRS Pub. 590-B (2024), Appendix B; Treas. Reg. 1.401(a)(9)-9.
UNIFORM_LIFETIME_TABLE = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0,
    79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0,
    86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
    93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8, 98: 7.3, 99: 6.8,
    100: 6.4, 101: 6.0, 102: 5.6, 103: 5.2, 104: 4.9, 105: 4.6, 106: 4.3,
    107: 4.1, 108: 3.9, 109: 3.7, 110: 3.5, 111: 3.4, 112: 3.3, 113: 3.1,
    114: 3.0, 115: 2.9, 116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3, 120: 2.0,
}


def rmd_factor(age: int) -> float:
    if age < 72:
        raise ValueError("No uniform-table factor below age 72")
    return UNIFORM_LIFETIME_TABLE[min(age, 120)]


# ---------------------------------------------------------------------------
# Medicare Part B, calendar year 2026.
# Standard monthly premium $202.90. Source: CMS press release / fact sheet,
# "2026 Medicare Parts A & B Premiums and Deductibles" (Nov 2025).
# IRMAA tiers: statutory cost-share multiples of the standard premium
# (1.4x / 2.0x / 2.6x / 3.2x / 3.4x per 42 U.S.C. 1395r(i)). MAGI
# thresholds below are the 2026 values (indexed annually); MAGI is measured
# with a TWO-YEAR lookback, which the engine models explicitly.
# ---------------------------------------------------------------------------
MEDICARE_PART_B_MONTHLY = 202.90
IRMAA_MULTIPLIERS = (1.0, 1.4, 2.0, 2.6, 3.2, 3.4)
IRMAA_THRESHOLDS = {
    "single": (109_000, 137_000, 171_000, 205_000, 500_000),
    "mfj": (218_000, 274_000, 342_000, 410_000, 750_000),
}
MEDICARE_AGE = 65

# ---------------------------------------------------------------------------
# ACA premium tax credit, plan year 2026 (post-ARPA-enhancement schedule:
# the enhanced credits expired after 2025, restoring the 400% FPL cliff).
# Applicable-percentage table: Rev. Proc. 2025-25 (IRC sec. 36B(b)(3)(A)).
# Segments are (fpl_pct_floor, fpl_pct_ceil, pct_at_floor, pct_at_ceil),
# linearly interpolated; no credit above 400% FPL.
# ---------------------------------------------------------------------------
ACA_APPLICABLE_PCT = [
    (0.0, 1.33, 0.0210, 0.0210),
    (1.33, 1.50, 0.0314, 0.0419),
    (1.50, 2.00, 0.0419, 0.0660),
    (2.00, 2.50, 0.0660, 0.0844),
    (2.50, 3.00, 0.0844, 0.0996),
    (3.00, 4.00, 0.0996, 0.0996),
]
ACA_CLIFF_FPL = 4.00

# Federal poverty guidelines (48 contiguous states), 2025 guidelines, which
# govern 2026 ACA coverage. Source: HHS, 90 FR (Jan 2025): $15,650 for one
# person + $5,500 per additional person.
FPL_FIRST_PERSON = 15_650
FPL_PER_ADDITIONAL = 5_500

# HSA: withdrawals for qualified medical expenses are tax-free at any age;
# non-medical withdrawals are ordinary income plus a 20% additional tax
# before age 65 (IRC sec. 223(f)). Medicare premiums are HSA-qualified
# after 65; ACA marketplace premiums generally are not (IRS Pub. 969).
HSA_PENALTY_RATE = 0.20
HSA_PENALTY_END_AGE = 65

# Early-withdrawal additional tax on tax-deferred accounts before 59.5
# (IRC sec. 72(t)). The engine applies it to tax-deferred withdrawals taken
# before the owner's age-60 year (whole-year model) and flags it in output.
EARLY_WITHDRAWAL_PENALTY = 0.10
EARLY_WITHDRAWAL_AGE = 60  # whole-year approximation of 59.5, documented

# ---------------------------------------------------------------------------
# Freshness metadata: when each constant group was last verified against its
# primary source, and how often it is expected to change.
# update_cycle values:
#   "annual-october"  — IRS Rev. Proc., typically released each October
#   "annual-november" — CMS Medicare announcement, each November
#   "annual-january"  — HHS FPL guidelines, each January
#   "annual-may"      — IRS ACA applicable-% Rev. Proc., each spring
#   "legislative"     — changes only when Congress acts; never auto-stale
# When you update a constant, update last_updated to today's ISO date and
# update the review_url to point at the specific document you used.
# ---------------------------------------------------------------------------
CONSTANT_METADATA: dict[str, dict[str, str]] = {
    "federal_brackets": {
        "last_updated": "2025-10-09",
        "update_cycle": "annual-october",
        "review_url": "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    },
    "standard_deduction": {
        "last_updated": "2025-10-09",
        "update_cycle": "annual-october",
        "review_url": "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    },
    "ltcg_brackets": {
        "last_updated": "2025-10-09",
        "update_cycle": "annual-october",
        "review_url": "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    },
    "irmaa_thresholds": {
        "last_updated": "2025-11-01",
        "update_cycle": "annual-november",
        "review_url": "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-and-deductibles",
    },
    "medicare_part_b": {
        "last_updated": "2025-11-01",
        "update_cycle": "annual-november",
        "review_url": "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-and-deductibles",
    },
    "fpl": {
        "last_updated": "2025-01-22",
        "update_cycle": "annual-january",
        "review_url": "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
    },
    "aca_applicable_pct": {
        "last_updated": "2025-05-01",
        "update_cycle": "annual-may",
        "review_url": "https://www.irs.gov/pub/irs-drop/rp-25-25.pdf",
    },
    "rmd_ages": {
        "last_updated": "2024-07-01",
        "update_cycle": "legislative",
        "review_url": "https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs",
    },
    "uniform_lifetime_table": {
        "last_updated": "2022-01-01",
        "update_cycle": "legislative",
        "review_url": "https://www.irs.gov/pub/irs-tege/uniform_rmd_wksht.pdf",
    },
    "senior_bonus": {
        "last_updated": "2025-07-04",
        "update_cycle": "legislative",
        "review_url": "https://www.congress.gov/bill/119th-congress/house-bill/1",
    },
}


def constants_freshness(today=None) -> list[dict]:
    """Return per-group freshness records with computed staleness flags.

    `today` can be overridden (accepts datetime.date) for testing.
    """
    from datetime import date as _date
    if today is None:
        today = _date.today()
    _CYCLE_MONTH = {
        "annual-october": 10,
        "annual-november": 11,
        "annual-january": 1,
        "annual-may": 5,
    }
    results = []
    for key, meta in CONSTANT_METADATA.items():
        lu = _date.fromisoformat(meta["last_updated"])
        cycle = meta["update_cycle"]
        stale = False
        if cycle in _CYCLE_MONTH:
            month = _CYCLE_MONTH[cycle]
            # Due date is the review month of the year after last_updated
            due_year = lu.year + 1
            due_day = 15 if month == 1 else 1
            due = _date(due_year, month, due_day)
            stale = today >= due
        results.append({
            "key": key,
            "last_updated": meta["last_updated"],
            "update_cycle": cycle,
            "review_url": meta["review_url"],
            "stale": stale,
        })
    return results
