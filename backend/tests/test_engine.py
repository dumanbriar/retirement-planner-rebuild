"""Hand-verified test cases for the projection engine.

Every expected value here was computed by hand from the cited statutory
formulas so the engine is checked against the law, not against itself.
"""
import math

import pytest

from app.engine import constants as C
from app.engine import socialsecurity as ss
from app.engine.engine import Simulator
from app.engine.planner import build_plan
from app.engine.taxes import (TaxYearInput, aca_applicable_pct, aca_subsidy,
                              compute_taxes, irmaa_tier,
                              taxable_social_security)
from app.models import (Account, AccountType, Assumptions, ConversionStrategy,
                        Liability, Person, PlanInput)


# ----------------------------------------------------------- federal tax
def test_mfj_ordinary_tax_2026():
    # MFJ, $100,000 ordinary income, 2026, both under 65.
    # taxable = 100,000 - 32,200 = 67,800
    # tax = 24,800*.10 + (67,800-24,800)*.12 = 2,480 + 5,160 = 7,640
    r = compute_taxes(TaxYearInput(year=2026, filing_status="mfj", inflation=0.025,
                                   ordinary_income=100_000, ss_benefits=0,
                                   qualified_dividends=0, realized_ltcg=0))
    assert math.isclose(r.taxable_income, 67_800, abs_tol=0.01)
    assert math.isclose(r.federal_tax, 7_640, abs_tol=0.01)
    assert r.marginal_rate == 0.12


def test_single_tax_with_ltcg_stacking_2026():
    # Single, $60,000 ordinary + $30,000 LTCG, under 65.
    # deductions 16,100 -> taxable 73,900; ordinary taxable 43,900, gains 30,000
    # ordinary tax = 12,400*.10 + (43,900-12,400)*.12 = 1,240 + 3,780 = 5,020
    # gains stack 43,900-73,900; 0% to 49,450 covers 5,550; rest 24,450 @15% = 3,667.50
    r = compute_taxes(TaxYearInput(year=2026, filing_status="single", inflation=0.025,
                                   ordinary_income=60_000, ss_benefits=0,
                                   qualified_dividends=0, realized_ltcg=30_000))
    assert math.isclose(r.taxable_income, 73_900, abs_tol=0.01)
    assert math.isclose(r.ltcg_tax, 24_450 * 0.15, abs_tol=0.01)
    assert math.isclose(r.federal_tax, 5_020 + 3_667.50, abs_tol=0.01)


def test_senior_bonus_and_additional_deduction():
    # MFJ both 65+, 2026, MAGI under phaseout: std 32,200 + 2*1,650 + 2*6,000
    r = compute_taxes(TaxYearInput(year=2026, filing_status="mfj", inflation=0.025,
                                   ordinary_income=80_000, ss_benefits=0,
                                   qualified_dividends=0, realized_ltcg=0,
                                   ages_65_plus=2))
    assert math.isclose(r.deductions, 32_200 + 3_300 + 12_000, abs_tol=0.01)


def test_senior_bonus_expires_after_2028():
    r = compute_taxes(TaxYearInput(year=2029, filing_status="mfj", inflation=0.0,
                                   ordinary_income=80_000, ss_benefits=0,
                                   qualified_dividends=0, realized_ltcg=0,
                                   ages_65_plus=2))
    assert math.isclose(r.deductions, 32_200 + 3_300, abs_tol=0.01)


def test_niit():
    # Single, MAGI 250k incl. 60k investment income: NIIT on min(60k, 50k)
    r = compute_taxes(TaxYearInput(year=2026, filing_status="single", inflation=0.0,
                                   ordinary_income=190_000, ss_benefits=0,
                                   qualified_dividends=20_000, realized_ltcg=40_000))
    assert math.isclose(r.niit, 0.038 * 50_000, abs_tol=0.01)


# -------------------------------------------------- social security taxation
def test_ss_taxation_worksheet_mid_tier():
    # MFJ: SS 40,000, other AGI 20,000 -> provisional 40,000
    # over t1 (32k) but under t2 (44k): min(.5*8,000, .5*40,000) = 4,000
    assert math.isclose(taxable_social_security(40_000, 20_000, "mfj"), 4_000, abs_tol=0.01)


def test_ss_taxation_85_percent_cap():
    # high income: capped at 85% of benefits
    assert math.isclose(taxable_social_security(40_000, 200_000, "mfj"),
                        34_000, abs_tol=0.01)


def test_ss_taxation_zero_below_threshold():
    assert taxable_social_security(20_000, 10_000, "mfj") == 0.0


# ----------------------------------------------------------- SS claiming
def test_claiming_factor_fra67():
    # born 1960+: FRA 67. Claim at 62 -> 36*5/9% + 24*5/12% = 20%+10% = 30% cut
    assert math.isclose(ss.claiming_factor(1970, 62), 0.70, abs_tol=1e-9)
    # claim at 70 -> 36 months * 2/3% = 24% bonus
    assert math.isclose(ss.claiming_factor(1970, 70), 1.24, abs_tol=1e-9)
    assert math.isclose(ss.claiming_factor(1970, 67), 1.00, abs_tol=1e-9)


def test_claiming_factor_fra66():
    # born 1954: FRA 66; claim at 62 -> 36*5/9 + 12*5/12 = 20% + 5% = 25% cut
    assert math.isclose(ss.claiming_factor(1954, 62), 0.75, abs_tol=1e-9)


def test_spousal_factor():
    # FRA 67, claim 62: 36*25/36% + 24*5/12% = 25% + 10% = 35% cut
    assert math.isclose(ss.spousal_factor(1970, 62), 0.65, abs_tol=1e-9)


# ------------------------------------------------------------------- RMD
def test_rmd_start_age():
    assert C.rmd_start_age(1955) == 73
    assert C.rmd_start_age(1959) == 73
    assert C.rmd_start_age(1960) == 75


def test_rmd_factor_values():
    assert C.rmd_factor(73) == 26.5
    assert C.rmd_factor(80) == 20.2
    assert C.rmd_factor(95) == 8.9


# ------------------------------------------------------------- healthcare
def test_irmaa_tiers_2026():
    assert irmaa_tier(150_000, "mfj", 2026, 0.025) == 0
    assert irmaa_tier(218_001, "mfj", 2026, 0.025) == 1
    assert irmaa_tier(800_000, "mfj", 2026, 0.025) == 5


def test_aca_cliff_2026():
    assert aca_applicable_pct(4.5) is None
    assert math.isclose(aca_applicable_pct(3.5), 0.0996, abs_tol=1e-6)
    # subsidy: 200% FPL couple => MAGI = 2*21,150 = 42,300; pct 6.60%
    fpl2 = C.FPL_FIRST_PERSON + C.FPL_PER_ADDITIONAL
    sub = aca_subsidy(2.0 * fpl2, 2, 20_000, 2026, 0.025)
    assert math.isclose(sub, 20_000 - 0.0660 * 2.0 * fpl2, abs_tol=1.0)


# -------------------------------------------------------------- full plan
def couple_plan(**kw) -> PlanInput:
    defaults = dict(
        persons=[
            Person(name="Sam", current_age=55, retirement_age=65, death_age=92,
                   ss_monthly_at_fra=2800, ss_claim_age=67),
            Person(name="Alex", current_age=53, retirement_age=63, death_age=94,
                   ss_monthly_at_fra=1900, ss_claim_age=67),
        ],
        accounts=[
            Account(name="Sam 401(k)", type=AccountType.tax_deferred, owner=0,
                    balance=850_000, annual_contribution=30_000, expected_return=0.06),
            Account(name="Alex 403(b)", type=AccountType.tax_deferred, owner=1,
                    balance=310_000, annual_contribution=15_000, expected_return=0.06),
            Account(name="Roth IRA", type=AccountType.roth, owner=0,
                    balance=120_000, annual_contribution=7_000, expected_return=0.065),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=400_000, cost_basis=250_000, annual_contribution=12_000,
                    expected_return=0.06),
            Account(name="HSA", type=AccountType.hsa, owner=0,
                    balance=45_000, annual_contribution=8_300, expected_return=0.05),
            Account(name="HY Savings", type=AccountType.cash, owner=0,
                    balance=60_000, annual_contribution=0, expected_return=0.04),
        ],
        annual_spending=96_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.fill_12),
    )
    defaults.update(kw)
    return PlanInput(**defaults)


def test_full_plan_runs_and_is_consistent():
    plan = couple_plan()
    sim = Simulator(plan, strategy=ConversionStrategy.fill_12)
    rows, metrics = sim.run()
    assert rows[0].year == C.BASE_YEAR
    # both retire in 2036 (Sam 65, Alex 63)
    assert metrics.retirement_year == 2036
    # accounting identity per account-year
    for y in rows:
        for ac in y.accounts:
            recon = (ac.start_balance + ac.contribution - ac.withdrawal
                     - ac.conversion_out + ac.conversion_in + ac.growth)
            assert math.isclose(recon, ac.end_balance, abs_tol=0.5), \
                f"{y.year} {ac.name}: {recon} != {ac.end_balance}"
    # taxable basis never exceeds balance (within rounding) or goes negative
    for y in rows:
        for ac in y.accounts:
            if ac.cost_basis is not None:
                assert ac.cost_basis >= -0.01
    # Sam is born 1971 -> SECURE 2.0 RMD age is 75 -> first RMD year 2046
    rmd_years = [y.year for y in rows if y.rmd_total > 0]
    assert rmd_years and min(rmd_years) == 2046
    # RMD magnitude check: prior-year TD balance / uniform factor at 75 (24.6)
    y2046 = next(y for y in rows if y.year == 2046)
    prior = next(y for y in rows if y.year == 2045)
    prior_td_sam = sum(ac.end_balance for ac in prior.accounts
                       if ac.type == AccountType.tax_deferred and ac.owner == 0)
    assert math.isclose(y2046.rmd_by_person[0], prior_td_sam / 24.6, rel_tol=1e-6)


def test_conversions_fill_but_do_not_exceed_bracket():
    plan = couple_plan()
    sim = Simulator(plan, strategy=ConversionStrategy.fill_12)
    rows, _ = sim.run()
    conv_years = [y for y in rows if y.roth_conversion > 1000]
    assert conv_years, "expected some Roth conversions in low-income years"
    for y in conv_years:
        # ordinary taxable income should not exceed the 12% bracket top
        scale = (1 + plan.assumptions.inflation) ** (y.year - C.BASE_YEAR)
        top = C.FEDERAL_BRACKETS[y.filing_status][1][0] * scale
        pref = min(y.dividends + max(0.0, y.realized_gains), y.taxable_income)
        assert y.taxable_income - pref <= top + 1.0, f"{y.year}"


def test_survivor_files_single():
    plan = couple_plan()
    sim = Simulator(plan, strategy=ConversionStrategy.none)
    rows, _ = sim.run()
    # Sam dies at 92 (2063); Alex (death 94 in 2067) survives
    after = [y for y in rows if y.year >= 2064]
    assert after and all(y.filing_status == "single" for y in after)
    # survivor keeps the larger benefit (Sam's)
    y2064 = after[0]
    y2063 = next(y for y in rows if y.year == 2063)
    assert y2064.ss_total > 0
    assert y2064.ss_total < y2063.ss_total  # one benefit, not two


def test_depletion_flagged_when_spending_too_high():
    plan = couple_plan(annual_spending=400_000)
    sim = Simulator(plan, strategy=ConversionStrategy.none)
    rows, metrics = sim.run()
    assert metrics.depleted and metrics.depletion_age is not None


def test_single_person_plan():
    plan = PlanInput(
        persons=[Person(name="Jo", current_age=60, retirement_age=65, death_age=90,
                        ss_monthly_at_fra=2400, ss_claim_age=70)],
        accounts=[Account(name="IRA", type=AccountType.tax_deferred, owner=0,
                          balance=900_000, annual_contribution=10_000),
                  Account(name="Brokerage", type=AccountType.taxable, owner=0,
                          balance=300_000, cost_basis=200_000)],
        annual_spending=70_000)
    result = build_plan(plan)
    assert result.metrics.retirement_year == 2031
    assert all(y.filing_status == "single" for y in result.years)
    # SS starts at 70 with delayed credits: 2400*12*1.24 in today's $
    y_claim = next(y for y in result.years if y.year == 2036)
    infl = (1 + plan.assumptions.inflation) ** (2036 - 2026)
    assert math.isclose(y_claim.ss_total, 2400 * 12 * 1.24 * infl, rel_tol=1e-6)


def test_build_plan_full_pipeline():
    plan = couple_plan(assumptions=Assumptions(
        roth_conversion_strategy=ConversionStrategy.auto,
        optimize_ss_claiming=False))
    result = build_plan(plan)
    assert result.metrics.success
    assert len(result.sensitivity) >= 8
    assert len(result.conversion_comparison) == 5
    assert result.assumption_notes
    # auto must do at least as well as doing nothing
    by_name = {c.strategy: c for c in result.conversion_comparison}
    chosen = by_name[result.metrics.chosen_conversion_strategy]
    assert chosen.ending_after_tax_real >= by_name["none"].ending_after_tax_real - 1


def test_excel_workbook_builds():
    from app.engine.excel import build_workbook
    plan = couple_plan()
    result = build_plan(plan)
    data = build_workbook(plan, result)
    assert data[:2] == b"PK"  # valid zip/xlsx
    import io

    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data))
    assert {"Summary", "Assumptions", "Accumulation", "Retirement",
            "Account Detail", "Strategies", "Sensitivity"} <= set(wb.sheetnames)


# --------------------------------------------------------- C1: ACA below FPL
def test_aca_below_fpl_returns_zero():
    # below 100% FPL → no PTC (IRC §36B(c)(1)(A)); must return 0, not benchmark
    assert aca_subsidy(5_000, 1, 20_000, 2026, 0.025) == 0.0
    assert aca_subsidy(0, 2, 15_000, 2026, 0.025) == 0.0


# --------------------------------------------------------- M6: NIIT + interest
def test_niit_includes_interest():
    # Single, ordinary_income=205k (which already includes 10k interest), no divs/gains.
    # MAGI=205k; excess over $200k=5k; NII=10k interest; NIIT = 3.8% * min(10k, 5k) = 190.
    # Without the fix (interest excluded from NII): NII=0 → NIIT=0. This case proves it.
    r = compute_taxes(TaxYearInput(year=2026, filing_status="single", inflation=0.025,
                                   ordinary_income=205_000, ss_benefits=0,
                                   qualified_dividends=0, realized_ltcg=0,
                                   interest=10_000))
    assert math.isclose(r.niit, C.NIIT_RATE * 5_000, abs_tol=0.01)


def test_niit_interest_only():
    # Single, $210k ordinary income + $5k interest, no divs/gains
    # NII = 5k interest; excess = 210k+5k - 200k = 15k; NIIT on min(5k, 15k) = 5k
    r = compute_taxes(TaxYearInput(year=2026, filing_status="single", inflation=0.025,
                                   ordinary_income=210_000, ss_benefits=0,
                                   qualified_dividends=0, realized_ltcg=0,
                                   interest=5_000))
    assert math.isclose(r.niit, C.NIIT_RATE * 5_000, abs_tol=0.01)


# --------------------------------------------------------- M7: IRMAA top tier
def test_irmaa_top_tier_not_indexed():
    # top single threshold is fixed at $500k regardless of year
    # At 2.5% inflation for 10 years, $500k would become ~$641k if indexed;
    # but the statutory cap is fixed so $490k stays in tier 4 and $510k hits tier 5
    assert irmaa_tier(490_000, "single", 2036, 0.025) == 4
    assert irmaa_tier(510_000, "single", 2036, 0.025) == 5
    # top MFJ threshold fixed at $750k
    assert irmaa_tier(740_000, "mfj", 2036, 0.025) == 4
    assert irmaa_tier(760_000, "mfj", 2036, 0.025) == 5


# --------------------------------------------------------- M2: death vs retirement
def test_death_age_le_retirement_age_raises():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Person(name="Test", current_age=50, retirement_age=70, death_age=65)

    with pytest.raises(ValidationError):
        Person(name="Test", current_age=50, retirement_age=70, death_age=70)


def test_death_age_gt_retirement_age_ok():
    p = Person(name="Test", current_age=50, retirement_age=65, death_age=90)
    assert p.death_age > p.retirement_age


# --------------------------------------------------------- M3: input caps
def test_accounts_max_length():
    from pydantic import ValidationError
    accts = [Account(name=f"IRA {i}", type=AccountType.tax_deferred,
                     owner=0, balance=10_000) for i in range(21)]
    with pytest.raises(ValidationError):
        PlanInput(
            persons=[Person(name="Jo", current_age=50, retirement_age=65, death_age=90)],
            accounts=accts,
            annual_spending=50_000,
        )


# ----------------------------------------------- future-dated liabilities
def _future_buyer(**kw) -> PlanInput:
    """A single 55-yo with ample liquidity to fund a future home purchase."""
    defaults = dict(
        persons=[Person(name="Pat", current_age=55, retirement_age=65, death_age=90,
                        ss_monthly_at_fra=2500, ss_claim_age=67)],
        accounts=[
            Account(name="401(k)", type=AccountType.tax_deferred, owner=0,
                    balance=600_000, annual_contribution=0, expected_return=0.05),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=500_000, cost_basis=500_000, annual_contribution=0,
                    expected_return=0.05),
            Account(name="Cash", type=AccountType.cash, owner=0, balance=200_000,
                    annual_contribution=0, expected_return=0.04),
        ],
        annual_spending=60_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none,
                                inflation=0.025),
    )
    defaults.update(kw)
    return PlanInput(**defaults)


def test_future_mortgage_dormant_then_activates():
    # Pat (55) buys at 70 (year 2041): $300k mortgage, no down payment.
    plan = _future_buyer(liabilities=[Liability(
        name="Future home", balance=300_000, interest_rate=0.05,
        annual_payment=24_000, start_age=70, down_payment=0)])
    sim = Simulator(plan, strategy=ConversionStrategy.none)
    rows, _ = sim.run()
    by_year = {y.year: y for y in rows}
    # dormant before purchase: contributes nothing to liabilities
    assert by_year[2040].total_liabilities == 0
    # active from the purchase year, grown to nominal dollars (>300k)
    scale = (1 + plan.assumptions.inflation) ** (2041 - C.BASE_YEAR)
    assert by_year[2041].total_liabilities > 300_000 * scale * 0.9
    # and it amortizes down thereafter
    assert by_year[2045].total_liabilities < by_year[2041].total_liabilities


def test_down_payment_withdrawn_from_portfolio():
    # Identical plans; one adds a $150k (today's $) down payment at age 70.
    base = _future_buyer()
    with_dp = _future_buyer(liabilities=[Liability(
        name="Future home", balance=0, interest_rate=0.0,
        annual_payment=0, start_age=70, down_payment=150_000)])
    m_base = Simulator(base, strategy=ConversionStrategy.none).run()[1]
    m_dp = Simulator(with_dp, strategy=ConversionStrategy.none).run()[1]
    # the down payment leaves the portfolio: ending real wealth is lower by
    # at least the today's-dollar down payment (it lost future growth too)
    assert (m_base.ending_net_worth_real - m_dp.ending_net_worth_real) >= 150_000 * 0.95


def test_purchase_year_records_home_purchase_outflow():
    plan = _future_buyer(liabilities=[Liability(
        name="Future home", balance=200_000, interest_rate=0.05,
        annual_payment=18_000, start_age=70, down_payment=100_000)])
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    by_year = {y.year: y for y in rows}
    scale = (1 + plan.assumptions.inflation) ** (2041 - C.BASE_YEAR)
    # the one-time outflow is the inflated down payment, only in the buy year
    assert math.isclose(by_year[2041].home_purchase, 100_000 * scale, rel_tol=1e-6)
    assert by_year[2040].home_purchase == 0
    assert by_year[2042].home_purchase == 0


def test_existing_liability_backward_compatible():
    # start_age=None must behave exactly like the pre-feature liability.
    liab = dict(name="Mortgage", balance=200_000, interest_rate=0.04,
                annual_payment=15_000)
    plan = _future_buyer(liabilities=[Liability(**liab)])
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    # active from year 1, no down-payment event ever
    assert rows[0].total_liabilities > 0
    assert all(y.home_purchase == 0 for y in rows)
