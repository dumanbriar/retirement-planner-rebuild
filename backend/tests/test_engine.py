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
from app.engine.planner import SPLIT_LEVELS, apply_split
from app.models import (Account, AccountType, AccountVehicle, Annuity,
                        Assumptions, ConversionStrategy, DistributionKind,
                        IncomeStream, InsurancePolicy, Liability, Person,
                        PlanInput, PrivateHolding)


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
    # accounting identity per account-year (generalized: distributions are
    # balance outflows for annuities/private holdings; 0 for ordinary accounts)
    for y in rows:
        for ac in y.accounts:
            recon = (ac.start_balance + ac.contribution - ac.withdrawal
                     - ac.distribution - ac.conversion_out + ac.conversion_in
                     + ac.growth)
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
            "Account Detail", "Strategies", "Legacy & Estate",
            "Sensitivity"} <= set(wb.sheetnames)


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
    # active from the purchase year at the literal $300k, amortized one year:
    # 300_000 * 1.05 - 24_000 = 291_000
    assert math.isclose(by_year[2041].total_liabilities, 291_000, abs_tol=1)
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
    # the down payment leaves the portfolio: a $150k nominal 2041 outflow is
    # worth less in today's dollars, but the real-wealth gap is still sizeable
    assert (m_base.ending_net_worth_real - m_dp.ending_net_worth_real) > 100_000


def test_purchase_year_records_home_purchase_outflow():
    plan = _future_buyer(liabilities=[Liability(
        name="Future home", balance=200_000, interest_rate=0.05,
        annual_payment=18_000, start_age=70, down_payment=100_000)])
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    by_year = {y.year: y for y in rows}
    # the one-time outflow is the literal down payment, only in the buy year
    assert math.isclose(by_year[2041].home_purchase, 100_000, abs_tol=0.01)
    assert by_year[2040].home_purchase == 0
    assert by_year[2042].home_purchase == 0


def _pre_retirement_buyer(**kw) -> PlanInput:
    """A 50-yo who retires at 65, so a purchase before 65 lands in accumulation
    (where the down payment competes with that year's contributions)."""
    defaults = dict(
        persons=[Person(name="Sam", current_age=50, retirement_age=65, death_age=90)],
        accounts=[
            Account(name="401(k)", type=AccountType.tax_deferred, owner=0,
                    balance=500_000, annual_contribution=20_000, expected_return=0.05),
            Account(name="Cash", type=AccountType.cash, owner=0, balance=5_000,
                    annual_contribution=0, expected_return=0.04),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=5_000, cost_basis=5_000, annual_contribution=0,
                    expected_return=0.05),
        ],
        annual_spending=40_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none,
                                inflation=0.025,
                                contributions_grow_with_inflation=False),
    )
    defaults.update(kw)
    return PlanInput(**defaults)


def test_pre_retirement_down_payment_raids_tax_advantaged_warns():
    # A $100k down payment at age 55 (2031) dwarfs cash+taxable (~$10k), so the
    # waterfall must raid the 401(k) — pre-59.5, so a penalty applies.
    plan = _pre_retirement_buyer(liabilities=[Liability(
        name="Future home", balance=0, interest_rate=0.0,
        annual_payment=0, start_age=55, down_payment=100_000)])
    sim = Simulator(plan, strategy=ConversionStrategy.none)
    rows, _ = sim.run()
    # the actionable plan-level warning fires exactly once
    raid = [w for w in sim.warnings if "down payment in 2031" in w]
    assert len(raid) == 1
    assert "tax-advantaged" in raid[0] and "not reduced" in raid[0]
    assert "early-withdrawal penalty" in raid[0]  # pre-59.5 raid is penalized
    # contributions are NOT reduced: the buy-year 401(k) contribution is still
    # the full entered $20k (growth-with-inflation is off in this fixture)
    buy = next(y for y in rows if y.year == 2031)
    k401 = next(a for a in buy.accounts if a.name == "401(k)")
    assert math.isclose(k401.contribution, 20_000, abs_tol=0.01)


def test_down_payment_covered_by_cash_raises_no_raid_warning():
    # Same purchase, but ample cash fully funds it — no tax-advantaged raid.
    plan = _pre_retirement_buyer(
        accounts=[
            Account(name="401(k)", type=AccountType.tax_deferred, owner=0,
                    balance=500_000, annual_contribution=20_000, expected_return=0.05),
            Account(name="Cash", type=AccountType.cash, owner=0, balance=300_000,
                    annual_contribution=0, expected_return=0.04),
        ],
        liabilities=[Liability(name="Future home", balance=0, interest_rate=0.0,
                               annual_payment=0, start_age=55, down_payment=100_000)])
    sim = Simulator(plan, strategy=ConversionStrategy.none)
    sim.run()
    assert not any("down payment in 2031" in w for w in sim.warnings)


def test_existing_liability_backward_compatible():
    # start_age=None must behave exactly like the pre-feature liability.
    liab = dict(name="Mortgage", balance=200_000, interest_rate=0.04,
                annual_payment=15_000)
    plan = _future_buyer(liabilities=[Liability(**liab)])
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    # active from year 1, no down-payment event ever
    assert rows[0].total_liabilities > 0
    assert all(y.home_purchase == 0 for y in rows)


# --------------------------------------------------- legacy foundation (Phase 1)
def _legacy_row(accounts, year=2063, liabilities=0.0):
    from app.models import YearRow
    return YearRow(year=year, ages=[None, None], phase="retirement",
                   filing_status="single", accounts=accounts,
                   total_liabilities=liabilities)


def test_settle_estate_dispatch_by_character_and_destination():
    # heir rate 24%. Four assets, one bequeathed to charity.
    from app.models import AccountYear
    sim = Simulator(couple_plan(), strategy=ConversionStrategy.none)
    accts = [
        AccountYear(name="401k", type=AccountType.tax_deferred, owner=0,
                    start_balance=100_000, contribution=0, withdrawal=0, growth=0,
                    end_balance=100_000, transfer_character="ird"),          # -> $76k
        AccountYear(name="Brokerage", type=AccountType.taxable, owner=0,
                    start_balance=100_000, contribution=0, withdrawal=0, growth=0,
                    end_balance=100_000, transfer_character="step_up"),      # -> $100k
        AccountYear(name="Roth", type=AccountType.roth, owner=0,
                    start_balance=50_000, contribution=0, withdrawal=0, growth=0,
                    end_balance=50_000, transfer_character="tax_free"),      # -> $50k
        AccountYear(name="IRA bequest", type=AccountType.tax_deferred, owner=0,
                    start_balance=20_000, contribution=0, withdrawal=0, growth=0,
                    end_balance=20_000, transfer_character="ird",
                    beneficiary="charity"),                                  # -> charity, $0 tax
    ]
    after_tax, legacy = sim.settle_estate(_legacy_row(accts))
    # IRD tax only on the $100k inherited 401(k): 100,000 * 0.24 = 24,000
    assert math.isclose(legacy.ird_tax, 24_000, abs_tol=0.01)
    # heirs receive 76,000 + 100,000 + 50,000 = 226,000
    assert math.isclose(legacy.to_heirs_net, 226_000, abs_tol=0.01)
    assert math.isclose(after_tax, 226_000, abs_tol=0.01)
    # charity receives the bequest tax-free (a charity pays no income tax on IRD)
    assert math.isclose(legacy.to_charity, 20_000, abs_tol=0.01)
    # every asset row reconciles: net == gross - tax
    for a in legacy.assets:
        assert math.isclose(a.net, a.gross - a.tax, abs_tol=0.01)


def test_settle_estate_subtracts_liabilities():
    from app.models import AccountYear
    sim = Simulator(couple_plan(), strategy=ConversionStrategy.none)
    accts = [AccountYear(name="Brokerage", type=AccountType.taxable, owner=0,
                         start_balance=300_000, contribution=0, withdrawal=0,
                         growth=0, end_balance=300_000, transfer_character="step_up")]
    after_tax, legacy = sim.settle_estate(_legacy_row(accts, liabilities=50_000))
    assert math.isclose(legacy.to_heirs_net, 250_000, abs_tol=0.01)
    assert math.isclose(after_tax, 250_000, abs_tol=0.01)


def test_settle_estate_reproduces_pre_refactor_terminal_formula():
    # Golden regression: ending_after_tax_real must equal the original inline
    # terminal calculation (TD/HSA discounted at heir rate, else full value,
    # minus liabilities) — the settle_estate extraction must be value-identical.
    plan = couple_plan()
    sim = Simulator(plan, strategy=ConversionStrategy.fill_12)
    rows, metrics = sim.run()
    last = rows[-1]
    expected = 0.0
    for x in last.accounts:
        if x.type in (AccountType.tax_deferred, AccountType.hsa):
            expected += x.end_balance * (1 - plan.assumptions.heir_tax_rate)
        else:
            expected += x.end_balance
    expected -= last.total_liabilities
    assert math.isclose(metrics.ending_after_tax_real,
                        expected / sim.infl(last.year), rel_tol=1e-9)


def test_legacy_result_wired_into_plan_and_reconciles():
    plan = couple_plan()
    result = build_plan(plan)
    legacy = result.legacy
    assert legacy is not None
    # ending_after_tax_real and net_to_heirs_real are the same quantity
    assert math.isclose(result.metrics.ending_after_tax_real,
                        result.metrics.net_to_heirs_real, rel_tol=1e-9)
    # to_heirs_net = sum(net of heir-bound assets) - liabilities; with no charity
    # bequests and no debt at death this equals gross - ird_tax
    assert math.isclose(legacy.to_heirs_net,
                        legacy.to_heirs_gross - legacy.ird_tax, abs_tol=1.0)
    assert legacy.to_charity == 0  # no bequests configured in the base plan


# ----------------------------------------- pension survivor (Phase 2)
def test_pension_survivor_continuation():
    # Sam (owner 0) holds a $40k/yr pension with a 50% survivor benefit. Sam
    # dies at 92 (2063); Alex survives to 2067. After Sam's death the benefit
    # continues to Alex at 50%.
    plan = couple_plan(income_streams=[IncomeStream(
        name="Sam pension", owner=0, annual_amount=40_000, start_age=65,
        cola=False, taxable=True, survivor_pct=0.5)])
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    by = {y.year: y for y in rows}
    assert math.isclose(by[2060].other_income, 40_000, abs_tol=1)  # both alive
    assert math.isclose(by[2063].other_income, 40_000, abs_tol=1)  # Sam alive at 92
    assert math.isclose(by[2064].other_income, 20_000, abs_tol=1)  # 50% to survivor
    assert math.isclose(by[2067].other_income, 20_000, abs_tol=1)  # still surviving


def test_income_stream_stops_at_death_without_survivor():
    # Backward-compat lock: default survivor_pct=0 reproduces prior behavior —
    # the stream stops entirely at the owner's death.
    plan = couple_plan(income_streams=[IncomeStream(
        name="Sam pension", owner=0, annual_amount=40_000, start_age=65,
        cola=False, taxable=True)])
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    by = {y.year: y for y in rows}
    assert math.isclose(by[2060].other_income, 40_000, abs_tol=1)
    assert by[2064].other_income == 0.0  # Sam dead -> nothing continues


# ------------------------------------------- whole-life insurance (Phase 3)
def _solo_with_policy(policy: InsurancePolicy, **kw) -> PlanInput:
    return PlanInput(
        persons=[Person(name="Pat", current_age=60, retirement_age=62, death_age=85,
                        ss_monthly_at_fra=2500, ss_claim_age=67)],
        accounts=[
            Account(name="401k", type=AccountType.tax_deferred, owner=0,
                    balance=1_200_000, annual_contribution=0, expected_return=0.05),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=300_000, cost_basis=200_000, annual_contribution=0,
                    expected_return=0.05),
        ],
        insurance_policies=[policy],
        annual_spending=60_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none),
        **kw)


def test_insurance_cash_value_grows_tax_deferred():
    pol = InsurancePolicy(name="WL", owner=0, annual_premium=0, cash_value=100_000,
                          cash_value_return=0.04, death_benefit=500_000,
                          premiums_paid_to_date=80_000)
    rows = Simulator(_solo_with_policy(pol), strategy=ConversionStrategy.none).run()[0]
    ins = next(a for a in rows[0].accounts if a.asset_class == "insurance")
    # 100,000 * 1.04 = 104,000, no annual tax drag (grows tax-deferred)
    assert math.isclose(ins.end_balance, 104_000, abs_tol=1)
    assert math.isclose(ins.growth, 4_000, abs_tol=1)


def test_insurance_premium_drawn_from_portfolio_in_retirement():
    pol = InsurancePolicy(name="WL", owner=0, annual_premium=12_000, cash_value=50_000,
                          cash_value_return=0.0, death_benefit=400_000)
    no_prem = InsurancePolicy(name="WL", owner=0, annual_premium=0, cash_value=50_000,
                              cash_value_return=0.0, death_benefit=400_000)
    m_base = Simulator(_solo_with_policy(no_prem), strategy=ConversionStrategy.none).run()[1]
    rows, m_with = Simulator(_solo_with_policy(pol), strategy=ConversionStrategy.none).run()
    # level premiums deplete the portfolio over retirement
    assert m_base.ending_net_worth_real - m_with.ending_net_worth_real > 50_000
    ret = next(r for r in rows if r.phase == "retirement")
    assert math.isclose(ret.premiums_paid, 12_000, abs_tol=1)


def test_insurance_death_benefit_paid_to_survivor_tax_free():
    pol = InsurancePolicy(name="Sam WL", owner=0, annual_premium=0, cash_value=0,
                          cash_value_return=0.0, death_benefit=300_000)
    with_pol = {y.year: y for y in
                Simulator(couple_plan(insurance_policies=[pol]),
                          strategy=ConversionStrategy.none).run()[0]}
    base = {y.year: y for y in
            Simulator(couple_plan(), strategy=ConversionStrategy.none).run()[0]}
    # Sam (owner 0) dies at 92 in 2063; the face is paid into Alex's portfolio in
    # 2064, income-tax-free, lifting assets by ~the death benefit vs the baseline.
    assert math.isclose(with_pol[2064].death_benefits_paid, 300_000, abs_tol=1)
    bump = with_pol[2064].total_assets - base[2064].total_assets
    assert 250_000 < bump < 360_000


def test_insurance_death_benefit_in_estate_income_tax_free():
    pol = InsurancePolicy(name="WL", owner=0, annual_premium=0, cash_value=40_000,
                          cash_value_return=0.0, death_benefit=500_000)
    result = build_plan(_solo_with_policy(pol))
    ins = next(a for a in result.legacy.assets if a.asset_class == "insurance")
    assert math.isclose(ins.gross, 500_000, abs_tol=1)  # death benefit, not cash value
    assert ins.tax == 0                                  # income-tax-free (IRC §101)
    assert ins.transfer_character == "tax_free"


# --------------------------------------------- deferred annuity (Phase 4)
def _solo_with_annuity(annuity: Annuity, **kw) -> PlanInput:
    return PlanInput(
        persons=[Person(name="Pat", current_age=60, retirement_age=62, death_age=85,
                        ss_monthly_at_fra=2500, ss_claim_age=67)],
        accounts=[Account(name="401k", type=AccountType.tax_deferred, owner=0,
                          balance=900_000, annual_contribution=0, expected_return=0.05)],
        annuities=[annuity],
        annual_spending=55_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none),
        **kw)


def test_annuity_exclusion_ratio_splits_payout():
    # basis 100k / balance 200k over 20 yrs -> $10k/yr payout, 50% excluded.
    ann = Annuity(name="SPDA", owner=0, balance=200_000, basis=100_000,
                  accumulation_return=0.0, annuitize_at_age=70, payout_years=20)
    sim = Simulator(_solo_with_annuity(ann), strategy=ConversionStrategy.none)
    sim.prepare_annuities(2036)  # Pat (born 1966) is 70 in 2036
    assert math.isclose(sim._annuity_payout, 10_000, abs_tol=1)
    assert math.isclose(sim._annuity_taxable, 5_000, abs_tol=1)   # gain portion
    a = sim.annuities[0]
    assert a.annuitized
    assert math.isclose(a.balance, 190_000, abs_tol=1)
    assert math.isclose(a.basis, 95_000, abs_tol=1)


def test_annuity_ird_taxes_gain_only_at_death():
    # held to death without annuitizing: heirs owe IRD on the GAIN only (§691/§72),
    # basis returns tax-free. 150k value, 90k basis, 24% heir rate -> 14,400.
    ann = Annuity(name="SPDA", owner=0, balance=150_000, basis=90_000,
                  accumulation_return=0.0, annuitize_at_age=90, payout_years=10)
    result = build_plan(_solo_with_annuity(ann))
    a = next(x for x in result.legacy.assets if x.asset_class == "annuity")
    assert math.isclose(a.gross, 150_000, abs_tol=1)
    assert math.isclose(a.tax, 60_000 * 0.24, abs_tol=1)
    assert a.transfer_character == "ird"


def test_future_annuity_purchase_funds_from_portfolio():
    # planned buy at 66: dormant before, then a $200k lump sum is drawn from the
    # portfolio and becomes the contract value with a full after-tax basis.
    ann = Annuity(name="Future SPDA", owner=0, annuitize_at_age=72, payout_years=20,
                  accumulation_return=0.0, purchase_age=66, purchase_amount=200_000)
    rows = Simulator(_solo_with_annuity(ann), strategy=ConversionStrategy.none).run()[0]
    by = {y.year: y for y in rows}
    # Pat (born 1966) is 66 in 2032.
    assert not any(a.asset_class == "annuity" for a in by[2031].accounts)  # dormant
    bought = [a for a in by[2032].accounts if a.asset_class == "annuity"]
    assert bought and math.isclose(bought[0].end_balance, 200_000, abs_tol=1)
    assert math.isclose(bought[0].cost_basis, 200_000, abs_tol=1)  # full basis
    # the lump sum came out of the portfolio accounts
    acct_2031 = sum(a.end_balance for a in by[2031].accounts if a.asset_class == "account")
    acct_2032 = sum(a.end_balance for a in by[2032].accounts if a.asset_class == "account")
    assert acct_2031 - acct_2032 > 150_000


def test_annuity_payout_exhausts_balance_over_term():
    # a 5-year payout from age 63 fully amortizes the balance to zero.
    ann = Annuity(name="SPDA", owner=0, balance=100_000, basis=100_000,
                  accumulation_return=0.0, annuitize_at_age=63, payout_years=5)
    rows = Simulator(_solo_with_annuity(ann), strategy=ConversionStrategy.none).run()[0]
    by = {y.year: y for y in rows}
    # Pat is 63 in 2029; payouts 2029-2033, each $20k, then exhausted.
    pay_years = [y for y in rows if y.legacy_distributions > 0]
    assert len(pay_years) == 5
    for y in pay_years:
        assert math.isclose(y.legacy_distributions, 20_000, abs_tol=1)
    ann_rows = [a for a in by[2034].accounts if a.asset_class == "annuity"]
    assert all(a.end_balance < 1 for a in ann_rows)  # exhausted after the term


def test_insurance_surrender_realizes_ordinary_gain():
    # cash value 180k over 120k of premiums paid -> 60k ordinary gain (IRC §72(e)).
    pol = InsurancePolicy(name="WL", owner=0, annual_premium=0, cash_value=180_000,
                          cash_value_return=0.0, death_benefit=500_000,
                          premiums_paid_to_date=120_000, surrender_at_age=70)
    sim = Simulator(_solo_with_policy(pol), strategy=ConversionStrategy.none)
    before = sim.surplus_account().balance
    sim.prepare_insurance(2036)  # Pat (born 1966) is 70 in 2036
    assert math.isclose(sim._ins_surrender_gain, 60_000, abs_tol=1)
    assert not sim.policies[0].active
    # the full cash value lands in the portfolio
    assert math.isclose(sim.surplus_account().balance - before, 180_000, abs_tol=1)
# --------------------------------------------- private holdings (Phase 5)
def _solo_with_holding(holding: PrivateHolding, **kw) -> PlanInput:
    return PlanInput(
        persons=[Person(name="Pat", current_age=60, retirement_age=62, death_age=85,
                        ss_monthly_at_fra=2500, ss_claim_age=67)],
        accounts=[
            Account(name="401k", type=AccountType.tax_deferred, owner=0,
                    balance=1_000_000, annual_contribution=0, expected_return=0.05),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=200_000, cost_basis=200_000, annual_contribution=0,
                    expected_return=0.05),
        ],
        private_holdings=[holding],
        annual_spending=60_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none),
        **kw)


def test_private_growth_and_distribution_hand_check():
    # value 500k @ 4%: growth 20,000; K-1 pays 20,000 out of it -> end 500,000.
    h = PrivateHolding(name="S-corp", owner=0, value=500_000, basis=200_000,
                       growth_rate=0.04, annual_distribution=20_000,
                       distribution_kind=DistributionKind.ordinary)
    rows = Simulator(_solo_with_holding(h), strategy=ConversionStrategy.none).run()[0]
    pr = next(a for a in rows[0].accounts if a.asset_class == "private")
    assert math.isclose(pr.start_balance, 500_000, abs_tol=0.01)
    assert math.isclose(pr.growth, 20_000, abs_tol=0.01)
    assert math.isclose(pr.distribution, 20_000, abs_tol=0.01)
    assert math.isclose(pr.end_balance, 500_000, abs_tol=0.01)
    # identity: start + contribution - withdrawal - distribution + growth = end
    recon = pr.start_balance + pr.contribution - pr.withdrawal \
        - pr.distribution + pr.growth
    assert math.isclose(recon, pr.end_balance, abs_tol=0.01)
    assert pr.transfer_character == "step_up"


def test_private_liquidity_event_realizes_ltcg():
    # No distributions; sale at 65 (2031). Value = 500k * 1.04^5 = 608,326.45
    # at the start of the sale year; LTCG = value - basis = 408,326.45.
    h = PrivateHolding(name="Startup", owner=0, value=500_000, basis=200_000,
                       growth_rate=0.04, annual_distribution=0, sale_age=65)
    rows = Simulator(_solo_with_holding(h), strategy=ConversionStrategy.none).run()[0]
    by = {y.year: y for y in rows}
    sale_value = 500_000 * 1.04 ** 5
    y31 = by[2031]
    pr = next(a for a in y31.accounts if a.asset_class == "private")
    assert math.isclose(pr.withdrawal, sale_value, rel_tol=1e-9)   # full proceeds
    assert pr.end_balance == 0
    assert math.isclose(y31.realized_gains, sale_value - 200_000, rel_tol=1e-6)
    assert y31.ltcg_tax > 0  # taxed through the 0/15/20% stack in retirement
    # gone the following year, and the proceeds joined the portfolio accounts
    assert not any(a.asset_class == "private" for a in by[2032].accounts)
    base = _solo_with_holding(PrivateHolding(name="none", owner=0, value=0))
    base_rows = Simulator(base, strategy=ConversionStrategy.none).run()[0]
    base31 = next(y for y in base_rows if y.year == 2031)
    acct_bump = (sum(a.end_balance for a in y31.accounts if a.asset_class == "account")
                 - sum(a.end_balance for a in base31.accounts if a.asset_class == "account"))
    assert acct_bump > 500_000  # proceeds (net of the LTCG tax) are in the portfolio


def test_private_step_up_at_death():
    # Held to death: passes with a basis step-up, no income tax (IRC §1014).
    # Pat dies at 85 (2051): 26 growth years 2026..2051 -> 500k * 1.04^26.
    h = PrivateHolding(name="Family LLC", owner=0, value=500_000, basis=100_000,
                       growth_rate=0.04)
    result = build_plan(_solo_with_holding(h))
    pr = next(a for a in result.legacy.assets if a.asset_class == "private")
    assert math.isclose(pr.gross, 500_000 * 1.04 ** 26, rel_tol=1e-9)
    assert pr.tax == 0
    assert pr.transfer_character == "step_up"


def test_private_spousal_transfer_steps_up_basis():
    # Sam (owner 0) dies at 92 (2063); Alex inherits the shares in 2064 with the
    # basis stepped up to the date-of-death value (IRC §1014).
    h = PrivateHolding(name="Shares", owner=0, value=300_000, basis=50_000,
                       growth_rate=0.03)
    rows = Simulator(couple_plan(private_holdings=[h]),
                     strategy=ConversionStrategy.none).run()[0]
    by = {y.year: y for y in rows}
    pr64 = next(a for a in by[2064].accounts if a.asset_class == "private")
    assert pr64.owner == 1
    # stepped-up basis == value at transfer == this year's starting value
    assert math.isclose(pr64.cost_basis, pr64.start_balance, abs_tol=0.5)
    assert math.isclose(pr64.start_balance, 300_000 * 1.03 ** 38, rel_tol=1e-9)


def test_private_accumulation_distribution_taxed_flat():
    # Before retirement the K-1 reinvests net of tax: ordinary at the 22% flat
    # rate (10,000 * 0.22 = 2,200), qualified at the 15% dividend rate (1,500).
    def plan_with(kind):
        return PlanInput(
            persons=[Person(name="Jo", current_age=50, retirement_age=65, death_age=90)],
            accounts=[Account(name="401k", type=AccountType.tax_deferred, owner=0,
                              balance=500_000, annual_contribution=0,
                              expected_return=0.05)],
            private_holdings=[PrivateHolding(
                name="K-1", owner=0, value=250_000, basis=250_000, growth_rate=0.05,
                annual_distribution=10_000, distribution_kind=kind)],
            annual_spending=50_000,
            assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none))
    for kind, expected_tax in ((DistributionKind.ordinary, 2_200.0),
                               (DistributionKind.qualified, 1_500.0)):
        rows = Simulator(plan_with(kind), strategy=ConversionStrategy.none).run()[0]
        y0 = rows[0]
        assert y0.phase == "accumulation"
        assert math.isclose(y0.total_tax, expected_tax, abs_tol=0.01), kind
        assert math.isclose(y0.legacy_distributions, 10_000, abs_tol=0.01)
        # the net distribution was reinvested into the portfolio
        assert math.isclose(y0.surplus_reinvested, 10_000 - expected_tax, abs_tol=0.01)


def test_private_qualified_k1_taxed_at_preferential_rates():
    # Same cash, different character: an ordinary K-1 must cost more federal tax
    # in retirement than a qualified one (which stacks at 0/15/20%).
    def with_kind(kind):
        h = PrivateHolding(name="K-1", owner=0, value=400_000, basis=400_000,
                           growth_rate=0.05, annual_distribution=25_000,
                           distribution_kind=kind)
        rows = Simulator(_solo_with_holding(h), strategy=ConversionStrategy.none).run()[0]
        return next(y for y in rows if y.phase == "retirement" and y.ages[0] == 70)
    ord_y = with_kind(DistributionKind.ordinary)
    qual_y = with_kind(DistributionKind.qualified)
    # both include the 25k in taxable income, but the qualified one pays less
    # (at this income much of it lands in the 0% LTCG bracket)
    assert ord_y.federal_tax > qual_y.federal_tax + 1_000


def test_private_holding_identity_and_full_plan():
    # Full-pipeline sanity with a distribution-paying holding: the accounting
    # identity holds every year and the workbook still builds.
    h = PrivateHolding(name="S-corp", owner=0, value=350_000, basis=150_000,
                       growth_rate=0.05, annual_distribution=12_000,
                       distribution_kind=DistributionKind.qualified)
    plan = couple_plan(private_holdings=[h])
    rows, m = Simulator(plan, strategy=ConversionStrategy.fill_12).run()
    for y in rows:
        for ac in y.accounts:
            recon = (ac.start_balance + ac.contribution - ac.withdrawal
                     - ac.distribution - ac.conversion_out + ac.conversion_in
                     + ac.growth)
            assert math.isclose(recon, ac.end_balance, abs_tol=0.5), \
                f"{y.year} {ac.name}"
    from app.engine.excel import build_workbook
    result = build_plan(plan)
    assert build_workbook(plan, result)[:2] == b"PK"


# -------------------------------- surplus reinvestment conservation (regression)
def test_no_phantom_surplus_from_rmds():
    # Regression: forced RMDs were double-counted as available resources in the
    # retirement surplus calc (once as rmd_total, once inside withdrawals_by_type),
    # minting phantom money in high-RMD years. Per-year wealth must be conserved:
    # end = start + growth - (spend+healthcare+tax+debt+home) + (ss+other).
    plan = PlanInput(
        persons=[Person(name="Rich", current_age=72, retirement_age=73, death_age=92,
                        ss_monthly_at_fra=3000, ss_claim_age=70)],
        accounts=[Account(name="Big 401k", type=AccountType.tax_deferred, owner=0,
                          balance=3_000_000, annual_contribution=0, expected_return=0.06),
                  Account(name="Brokerage", type=AccountType.taxable, owner=0,
                          balance=100_000, cost_basis=100_000, annual_contribution=0)],
        annual_spending=80_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none))
    rows, m = Simulator(plan, strategy=ConversionStrategy.none).run()
    ret = [y for y in rows if y.phase == "retirement"]
    assert any(y.rmd_total > 80_000 for y in ret)  # genuinely large forced RMDs
    assert not m.depleted
    for y in ret:
        start = sum(a.start_balance for a in y.accounts)
        growth = sum(a.growth for a in y.accounts)
        end = sum(a.end_balance for a in y.accounts)
        outflow = y.spend_goal + y.healthcare_cost + y.total_tax \
            + y.debt_payments + y.home_purchase
        inflow = y.ss_total + y.other_income
        assert math.isclose(end, start + growth - outflow + inflow,
                            rel_tol=0.01, abs_tol=1500), f"{y.year}"


def test_healthcare_cost_is_gross_not_netted_by_hsa():
    # Regression: healthcare_cost must report the TRUE (gross) cost of care, not
    # cost minus whatever the HSA paid tax-free — netting it produced an
    # artificial one-time jump the year the HSA ran dry, even though the real
    # cost grew smoothly the whole time. couple_plan() has an HSA that funds
    # medical costs for years, then depletes around 2060.
    plan = couple_plan()
    rows, m = Simulator(plan, strategy=ConversionStrategy.fill_12).run()
    ret = [y for y in rows if y.phase == "retirement"]

    # (a) whole-portfolio wealth conservation, using the now-gross healthcare
    # figure: end == start + growth - (spend+healthcare+tax+debt+home) + (ss+other).
    # This identity is HSA-blind by construction (it sums every account, so the
    # HSA's own balance draw-down is already captured on the start/end side) and
    # would NOT have held before the fix, when healthcare_cost quietly subtracted
    # the HSA's payment on the outflow side without a matching adjustment.
    for y in ret:
        start = sum(a.start_balance for a in y.accounts)
        growth = sum(a.growth for a in y.accounts)
        end = sum(a.end_balance for a in y.accounts)
        outflow = y.spend_goal + y.healthcare_cost + y.total_tax \
            + y.debt_payments + y.home_purchase
        inflow = y.ss_total + y.other_income
        assert math.isclose(end, start + growth - outflow + inflow,
                            rel_tol=0.01, abs_tol=1500), f"{y.year}"

    # (b) no artificial cliff the year the HSA empties: year-over-year healthcare
    # growth stays within normal inflation/IRMAA bounds (< 15%) every year,
    # including across the HSA-depletion boundary.
    by_year = {y.year: y for y in ret}
    for yr in sorted(by_year):
        prev = by_year.get(yr - 1)
        if prev is None or prev.healthcare_cost <= 0:
            continue
        growth_rate = by_year[yr].healthcare_cost / prev.healthcare_cost - 1
        assert growth_rate < 0.15, f"{yr}: healthcare cost jumped {growth_rate:.0%}"

    # (c) the HSA's medical payment is now visible as a funding source: in a
    # year the HSA pays medical costs, withdrawals_by_type["hsa"] must equal the
    # HSA account's own reported withdrawal (the same identity excel.py already
    # computes independently from AccountYear.withdrawal).
    hsa_paying_year = next(
        y for y in ret
        if any(a.type is not None and a.type.value == "hsa" and a.withdrawal > 0
               for a in y.accounts))
    hsa_acct_withdrawal = sum(a.withdrawal for a in hsa_paying_year.accounts
                              if a.type is not None and a.type.value == "hsa")
    assert math.isclose(hsa_paying_year.withdrawals_by_type.get("hsa", 0.0),
                        hsa_acct_withdrawal, abs_tol=0.01)

    # (d) golden lock: this is a pure reporting reclassification with zero effect
    # on actual cash flows or balances.
    assert math.isclose(m.ending_net_worth_real, 5_357_948.13, rel_tol=1e-6)
    assert math.isclose(m.lifetime_taxes_real, 510_261.87, rel_tol=1e-6)
    assert m.depletion_age is None and m.success


# --------------------------------- Roth-vs-Traditional contribution split
def _saver(salary, roth_c=10_000, td_c=10_000, **akw):
    a = dict(roth_conversion_strategy=ConversionStrategy.none,
             optimize_contribution_split=True)
    a.update(akw)
    return PlanInput(
        persons=[Person(name="Jo", current_age=40, retirement_age=65, death_age=90,
                        ss_monthly_at_fra=2500, ss_claim_age=67, salary=salary)],
        accounts=[
            Account(name="401k", type=AccountType.tax_deferred, owner=0,
                    vehicle=AccountVehicle.employer, balance=200_000,
                    annual_contribution=td_c, expected_return=0.06),
            Account(name="Roth 401k", type=AccountType.roth, owner=0,
                    vehicle=AccountVehicle.employer, balance=50_000,
                    annual_contribution=roth_c, expected_return=0.06),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=50_000, cost_basis=50_000, annual_contribution=0,
                    expected_return=0.06),
        ],
        annual_spending=70_000, assumptions=Assumptions(**a))


def test_split_low_bracket_favors_roth():
    # A low current bracket means paying tax now (Roth) beats deferring it.
    r = build_plan(_saver(salary=40_000))
    assert r.metrics.chosen_contribution_split == [1.0]


def test_split_high_bracket_favors_traditional():
    # A high current bracket makes the deduction worth more than tax-free growth.
    r = build_plan(_saver(salary=300_000))
    assert r.metrics.chosen_contribution_split == [0.0]


def test_split_reports_all_candidates_and_marks_current():
    r = build_plan(_saver(salary=90_000))
    assert len(r.contribution_split) >= len(SPLIT_LEVELS)
    pcts = {round(c.roth_pct[0], 2) for c in r.contribution_split}
    assert {0.0, 0.5, 1.0} <= pcts
    # current allocation is 10k/20k = 50% Roth and must be flagged exactly once
    current = [c for c in r.contribution_split if c.is_current]
    assert len(current) == 1 and current[0].roth_pct == [0.5]


def test_invest_the_tax_savings_reinvested():
    # The Traditional deduction's tax saving is reinvested in taxable; Roth has
    # no deduction, so nothing is reinvested during accumulation.
    plan = _saver(salary=200_000)
    trad = Simulator(apply_split(plan, [0.0]), strategy=ConversionStrategy.none).run()[0]
    roth = Simulator(apply_split(plan, [1.0]), strategy=ConversionStrategy.none).run()[0]
    acc_trad = sum(y.surplus_reinvested for y in trad if y.phase == "accumulation")
    acc_roth = sum(y.surplus_reinvested for y in roth if y.phase == "accumulation")
    assert acc_roth == 0
    assert acc_trad > 0


def test_salary_populates_accumulation_tax_fields():
    plan = _saver(salary=150_000, optimize_contribution_split=False)
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    acc = [y for y in rows if y.phase == "accumulation"]
    assert acc and all(y.agi > 0 and y.federal_tax > 0 and y.marginal_rate > 0
                       for y in acc)


def test_no_salary_keeps_legacy_flat_path():
    # Backward compatibility: with no salary the legacy flat-rate accumulation
    # path runs and the new income-tax fields stay unpopulated.
    plan = _saver(salary=0, optimize_contribution_split=False)
    rows = Simulator(plan, strategy=ConversionStrategy.none).run()[0]
    acc = [y for y in rows if y.phase == "accumulation"]
    assert acc and all(y.agi == 0 and y.federal_tax == 0 and y.taxable_income == 0
                       for y in acc)


def _one_account_plan(acct: Account, salary=120_000) -> PlanInput:
    return PlanInput(
        persons=[Person(name="Jo", current_age=40, retirement_age=65,
                        death_age=90, salary=salary)],
        accounts=[acct, Account(name="Tx", type=AccountType.taxable, owner=0,
                                balance=10_000, cost_basis=10_000)],
        annual_spending=60_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none))


def test_employer_vehicle_uses_elective_not_ira_limit():
    # $20k is fine in a 401k (under the elective-deferral limit) but exceeds the
    # IRA limit — the cap must follow the vehicle, not assume IRA.
    emp = build_plan(_one_account_plan(Account(
        name="401k", type=AccountType.tax_deferred, owner=0,
        vehicle=AccountVehicle.employer, balance=100_000,
        annual_contribution=20_000, expected_return=0.06)))
    ira = build_plan(_one_account_plan(Account(
        name="IRA", type=AccountType.tax_deferred, owner=0,
        vehicle=AccountVehicle.ira, balance=100_000,
        annual_contribution=20_000, expected_return=0.06)))
    assert not any("exceed" in w for w in emp.warnings)
    assert any("IRA contribution limit" in w for w in ira.warnings)


def test_backdoor_roth_flagged_for_high_earner():
    # High MAGI + a Roth IRA contribution -> allowed but flagged as a backdoor;
    # a Roth 401(k) at the same income has no income limit, so no flag.
    ira = build_plan(_one_account_plan(Account(
        name="Roth IRA", type=AccountType.roth, owner=0,
        vehicle=AccountVehicle.ira, balance=50_000,
        annual_contribution=7_000, expected_return=0.06), salary=400_000))
    emp = build_plan(_one_account_plan(Account(
        name="Roth 401k", type=AccountType.roth, owner=0,
        vehicle=AccountVehicle.employer, balance=50_000,
        annual_contribution=7_000, expected_return=0.06), salary=400_000))
    assert any("backdoor" in w.lower() for w in ira.warnings)
    assert not any("backdoor" in w.lower() for w in emp.warnings)


def test_split_optimizer_is_advisory_not_applied():
    # The suggestion must NOT change the modeled projection. With a high salary
    # the optimizer suggests all-Traditional, yet the plan must still reflect the
    # entered 50/50 split — i.e. the same ending wealth as running the input.
    plan = _saver(salary=300_000)  # 10k Roth + 10k Trad; suggestion will be 0% Roth
    r = build_plan(plan)
    assert r.metrics.chosen_contribution_split == [0.0]
    direct = Simulator(plan, strategy=ConversionStrategy.none).run()[1]
    assert math.isclose(r.metrics.ending_after_tax_real,
                        direct.ending_after_tax_real, rel_tol=1e-9)


def test_split_suggestion_is_single_household_value():
    # A couple gets ONE suggested household split, not a per-person breakdown.
    plan = PlanInput(
        persons=[Person(name="A", current_age=40, retirement_age=65,
                        death_age=90, salary=120_000),
                 Person(name="B", current_age=40, retirement_age=65,
                        death_age=90, salary=120_000)],
        accounts=[
            Account(name="A 401k", type=AccountType.tax_deferred, owner=0,
                    vehicle=AccountVehicle.employer, balance=100_000,
                    annual_contribution=15_000),
            Account(name="A Roth", type=AccountType.roth, owner=0,
                    vehicle=AccountVehicle.ira, balance=20_000,
                    annual_contribution=5_000),
            Account(name="B 401k", type=AccountType.tax_deferred, owner=1,
                    vehicle=AccountVehicle.employer, balance=80_000,
                    annual_contribution=10_000),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=20_000, cost_basis=20_000),
        ],
        annual_spending=70_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none,
                                optimize_contribution_split=True))
    r = build_plan(plan)
    assert len(r.metrics.chosen_contribution_split) == 1
    assert all(len(c.roth_pct) == 1 for c in r.contribution_split)
    assert any(c.is_current for c in r.contribution_split)


def test_split_cells_pair_each_split_with_best_conversions():
    # Each split is shown at its best, including the Roth-conversion lever. In a
    # large-tax-deferred household, the all-Traditional split should lean on
    # conversions (a non-'none' strategy) to defuse later RMDs — even though the
    # user's conversion toggle is OFF (the table always shows best-case).
    plan = PlanInput(
        persons=[Person(name="A", current_age=50, retirement_age=63, death_age=92,
                        ss_monthly_at_fra=2600, ss_claim_age=70, salary=110_000),
                 Person(name="B", current_age=50, retirement_age=63, death_age=92,
                        ss_monthly_at_fra=2000, ss_claim_age=70, salary=90_000)],
        accounts=[
            Account(name="A 401k", type=AccountType.tax_deferred, owner=0,
                    vehicle=AccountVehicle.employer, balance=1_500_000,
                    annual_contribution=15_000),
            Account(name="A Roth 401k", type=AccountType.roth, owner=0,
                    vehicle=AccountVehicle.employer, balance=60_000,
                    annual_contribution=8_000),
            Account(name="B 401k", type=AccountType.tax_deferred, owner=1,
                    vehicle=AccountVehicle.employer, balance=900_000,
                    annual_contribution=12_000),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=120_000, cost_basis=120_000),
        ],
        annual_spending=110_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none,
                                optimize_contribution_split=True))
    r = build_plan(plan)
    assert all(c.conversion_strategy for c in r.contribution_split)
    all_trad = next(c for c in r.contribution_split if round(c.roth_pct[0], 2) == 0.0)
    assert all_trad.conversion_strategy != "none"   # leans on conversions vs RMDs
    # headline is unaffected by the table's best-case conversions (toggle is none)
    direct = Simulator(plan, strategy=ConversionStrategy.none).run()[1]
    assert math.isclose(r.metrics.ending_after_tax_real,
                        direct.ending_after_tax_real, rel_tol=1e-9)


def test_apply_split_preserves_vehicle_totals():
    plan = _saver(salary=100_000)  # 10k Roth + 10k Trad in the employer bucket
    for pct in (0.0, 0.5, 1.0):
        p2 = apply_split(plan, [pct])
        emp = [a for a in p2.accounts if a.owner == 0
               and a.type in (AccountType.tax_deferred, AccountType.roth)
               and a.limit_vehicle() == AccountVehicle.employer]
        assert math.isclose(sum(a.annual_contribution for a in emp), 20_000, abs_tol=1)
        roth = sum(a.annual_contribution for a in emp if a.type == AccountType.roth)
        assert math.isclose(roth, 20_000 * pct, abs_tol=1)


def test_limit_warning_not_duplicated_per_year():
    # Regression: the message embedded {year}, so one over-limit input spammed a
    # separate warning for every accumulation year. It must appear exactly once.
    plan = _one_account_plan(Account(
        name="Overfunded 401k", type=AccountType.tax_deferred, owner=0,
        vehicle=AccountVehicle.employer, balance=100_000,
        annual_contribution=40_000, expected_return=0.06))
    r = build_plan(plan)
    elective = [w for w in r.warnings if "elective-deferral" in w]
    assert len(elective) == 1


def test_untagged_roth_defaults_to_ira_not_employer():
    # Regression: an untagged Roth account (vehicle=None) was treated as an
    # employer Roth 401(k) and lumped into the 401(k) elective-deferral bucket
    # with a real 401(k), producing a false over-limit warning. It must default
    # to a Roth IRA instead.
    plan = PlanInput(
        persons=[Person(name="Briar", current_age=40, retirement_age=65,
                        death_age=90, salary=120_000)],
        accounts=[
            Account(name="401k", type=AccountType.tax_deferred, owner=0,
                    vehicle=AccountVehicle.employer, balance=200_000,
                    annual_contribution=20_000),
            Account(name="Roth IRA", type=AccountType.roth, owner=0,  # vehicle=None
                    balance=50_000, annual_contribution=7_000),
            Account(name="Brokerage", type=AccountType.taxable, owner=0,
                    balance=10_000, cost_basis=10_000),
        ],
        annual_spending=60_000,
        assumptions=Assumptions(roth_conversion_strategy=ConversionStrategy.none))
    r = build_plan(plan)
    # 20k employer + 7k IRA, correctly bucketed, are each under their own cap.
    assert not any("elective-deferral" in w for w in r.warnings)
    assert Account(name="x", type=AccountType.roth, owner=0, balance=0)\
        .limit_vehicle() == AccountVehicle.ira
