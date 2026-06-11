"""Social Security benefit math.

The advisor supplies each person's estimated monthly benefit at full
retirement age (the PIA from an SSA statement), in today's dollars. The
engine applies the statutory claiming-age adjustment and inflates by the
plan's inflation assumption as a COLA proxy (SSA COLAs track CPI-W; PIA
estimates for those under 60 are wage-indexed — using one inflation
assumption for both is a documented simplification).

Sources: SSA early-retirement reduction and delayed retirement credit
formulas (42 U.S.C. 402(q), 402(w)); spousal benefits (42 U.S.C. 402(b)).
"""
from __future__ import annotations

from . import constants as C


def claiming_factor(birth_year: int, claim_age: int) -> float:
    """Multiplier on PIA for claiming at `claim_age` (whole years)."""
    fra_m = C.full_retirement_age_months(birth_year)
    claim_m = claim_age * 12
    if claim_m >= fra_m:
        months_late = min(claim_m, 70 * 12) - fra_m
        return 1.0 + months_late * (2 / 3) / 100
    months_early = fra_m - claim_m
    first = min(months_early, 36)
    rest = months_early - first
    return 1.0 - first * (5 / 9) / 100 - rest * (5 / 12) / 100


def spousal_factor(birth_year: int, claim_age: int) -> float:
    """Reduction applied to the 50%-of-PIA spousal benefit when the spouse
    claims before their own FRA. No delayed credits on spousal benefits."""
    fra_m = C.full_retirement_age_months(birth_year)
    claim_m = claim_age * 12
    if claim_m >= fra_m:
        return 1.0
    months_early = fra_m - claim_m
    first = min(months_early, 36)
    rest = months_early - first
    return 1.0 - first * (25 / 36) / 100 - rest * (5 / 12) / 100


def annual_benefit_todays_dollars(own_pia_monthly: float, birth_year: int,
                                  claim_age: int,
                                  spouse_pia_monthly: float | None = None,
                                  spouse_has_claimed: bool = False) -> float:
    """Own benefit, topped up to the spousal benefit when 50% of the
    spouse's PIA exceeds the claimant's own PIA (and the spouse has filed).
    Returned in today's dollars; the engine applies COLA inflation."""
    own = own_pia_monthly * claiming_factor(birth_year, claim_age)
    if spouse_pia_monthly and spouse_has_claimed:
        spousal_base = max(0.0, 0.5 * spouse_pia_monthly - own_pia_monthly)
        own += spousal_base * spousal_factor(birth_year, claim_age)
    return own * 12
