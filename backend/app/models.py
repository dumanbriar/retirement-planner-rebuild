"""Pydantic models: the API contract between frontend and engine.

All monetary inputs are in TODAY'S dollars unless a field name says
otherwise. The engine works internally in nominal dollars and reports both.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AccountType(str, Enum):
    tax_deferred = "tax_deferred"  # 401(k), 403(b), traditional IRA
    roth = "roth"                  # Roth IRA / Roth 401(k)
    taxable = "taxable"            # brokerage
    hsa = "hsa"
    cash = "cash"                  # high-yield savings / cash


class AccountVehicle(str, Enum):
    """The contribution-limit regime for a tax-advantaged retirement account.
    Does NOT affect withdrawal taxation (that is driven by `type`); it only
    selects which IRS contribution limit applies and whether the Roth-IRA
    income phase-out (and the backdoor-Roth flag) is in play.
    """
    employer = "employer"  # 401(k)/403(b)/457(b): IRC 402(g) elective-deferral limit
    ira = "ira"            # traditional/Roth IRA: IRC 219 limit; Roth IRA MAGI phase-out


DEFAULT_RETURNS = {
    AccountType.tax_deferred: 0.06,
    AccountType.roth: 0.06,
    AccountType.taxable: 0.06,
    AccountType.hsa: 0.05,
    AccountType.cash: 0.04,
}


class TransferCharacter(str, Enum):
    """How an asset is taxed when it passes to its beneficiary at death."""
    tax_free = "tax_free"  # Roth; life-insurance death benefit (IRC §101)
    step_up = "step_up"    # basis reset at death, no income tax (IRC §1014)
    ird = "ird"            # income in respect of a decedent (IRC §691; §72)


class Beneficiary(str, Enum):
    heirs = "heirs"
    charity = "charity"


class Person(BaseModel):
    name: str = "You"
    current_age: int = Field(ge=18, le=99)
    retirement_age: int = Field(ge=30, le=80)
    death_age: int = Field(default=90, ge=60, le=105)
    # Estimated monthly Social Security benefit at full retirement age
    # (the PIA from an SSA statement), in today's dollars.
    ss_monthly_at_fra: float = Field(default=0, ge=0)
    ss_claim_age: int = Field(default=67, ge=62, le=70)
    # Current gross annual earned income (today's dollars), 0 if not working.
    # Provides the real marginal-bracket context for the Roth-vs-Traditional
    # contribution decision; grows with plan inflation while this person works.
    salary: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _check_death_vs_retirement(self) -> "Person":
        if self.death_age <= self.retirement_age:
            raise ValueError(
                f"death_age ({self.death_age}) must be greater than "
                f"retirement_age ({self.retirement_age})")
        return self


class Account(BaseModel):
    name: str
    type: AccountType
    owner: int = Field(default=0, ge=0, le=1)  # index into persons
    balance: float = Field(ge=0)
    # tax_deferred / roth only: which IRS contribution limit applies. None is
    # treated as an employer plan (the higher elective-deferral limit).
    vehicle: Optional[AccountVehicle] = None
    # Taxable accounts only: cost basis today (defaults to balance).
    cost_basis: Optional[float] = Field(default=None, ge=0)
    annual_contribution: float = Field(default=0, ge=0)
    expected_return: Optional[float] = Field(default=None, ge=-0.10, le=0.20)

    def rate(self) -> float:
        return self.expected_return if self.expected_return is not None else DEFAULT_RETURNS[self.type]

    def limit_vehicle(self) -> AccountVehicle:
        """Vehicle for contribution-limit purposes. When unspecified, default by
        type: a Roth account is most likely a Roth IRA, while a tax-deferred
        account is most likely an employer 401(k)/403(b). This avoids lumping an
        untagged Roth IRA into the (much larger) elective-deferral bucket."""
        if self.vehicle is not None:
            return self.vehicle
        return AccountVehicle.ira if self.type == AccountType.roth else AccountVehicle.employer


class Liability(BaseModel):
    name: str
    balance: float = Field(ge=0)
    interest_rate: float = Field(default=0.0, ge=0, le=0.30)
    annual_payment: float = Field(default=0, ge=0)
    # Future-dated debt (e.g. a home purchase). When set, the primary person's
    # age at which the mortgage begins; the balance and down_payment (today's
    # dollars) are grown to that year and the down payment is drawn from the
    # portfolio. None => already active today (current behavior).
    start_age: Optional[int] = Field(default=None, ge=18, le=100)
    down_payment: float = Field(default=0, ge=0)  # one-time cash at purchase, today's $


class IncomeStream(BaseModel):
    """Pension, annuity, rental, part-time work in retirement, etc."""
    name: str
    owner: int = Field(default=0, ge=0, le=1)
    annual_amount: float = Field(ge=0)  # today's dollars
    start_age: int = Field(ge=30, le=100)
    end_age: Optional[int] = Field(default=None, ge=30, le=110)
    cola: bool = True       # grows with inflation
    taxable: bool = True    # taxed as ordinary income
    # Joint-and-survivor: fraction of the benefit that continues to a surviving
    # spouse after the owner dies (e.g. 0.5 for a 50% survivor pension). Default
    # 0.0 preserves prior behavior — the stream stops at the owner's death.
    # Only meaningful in a two-person household, and only if the stream had
    # already started before the owner died.
    survivor_pct: float = Field(default=0.0, ge=0, le=1.0)


class InsurancePolicy(BaseModel):
    """Whole / permanent life insurance with cash value.

    Amounts here are LEVEL NOMINAL figures (the policy's actual contractual
    values), NOT today's dollars — whole-life premiums and the death benefit are
    fixed in nominal terms. The cash value grows at `cash_value_return`.
    """
    name: str = "Whole life policy"
    owner: int = Field(default=0, ge=0, le=1)
    annual_premium: float = Field(default=0, ge=0)       # level nominal $/yr
    paid_up_age: Optional[int] = Field(default=None, ge=30, le=110)  # premiums stop at this age
    cash_value: float = Field(default=0, ge=0)           # current surrender value, nominal
    cash_value_return: float = Field(default=0.04, ge=-0.10, le=0.20)  # assumed
    death_benefit: float = Field(ge=0)                   # face amount, level nominal
    premiums_paid_to_date: float = Field(default=0, ge=0)  # basis for surrender gain
    surrender_at_age: Optional[int] = Field(default=None, ge=30, le=110)  # optional lapse


class Annuity(BaseModel):
    """Non-qualified deferred annuity. Tax-deferred accumulation, then a fixed
    period-certain payout beginning at annuitize_at_age. Each payout is split by
    the exclusion ratio (basis returned tax-free, the gain ordinary, IRC §72(b)).
    Amounts are nominal. At death the remaining gain is IRD (no step-up, §691)."""
    name: str = "Deferred annuity"
    owner: int = Field(default=0, ge=0, le=1)
    balance: float = Field(default=0, ge=0)      # current accumulation value, nominal
    basis: float = Field(default=0, ge=0)        # after-tax premiums paid (exclusion basis)
    accumulation_return: float = Field(default=0.04, ge=-0.10, le=0.20)  # assumed
    annuitize_at_age: int = Field(ge=50, le=90)
    payout_years: int = Field(default=20, ge=1, le=40)  # period-certain payout length
    # Future (planned) purchase: when set, the annuity is dormant until the owner
    # reaches purchase_age, at which point a one-time purchase_amount is drawn from
    # the portfolio (nominal) and becomes the contract value and its (after-tax)
    # basis. None => the annuity is already owned today (uses balance/basis above).
    purchase_age: Optional[int] = Field(default=None, ge=40, le=90)
    purchase_amount: float = Field(default=0, ge=0)


class ConversionStrategy(str, Enum):
    none = "none"
    fill_10 = "fill_10"
    fill_12 = "fill_12"
    fill_22 = "fill_22"
    fill_24 = "fill_24"
    custom = "custom"
    auto = "auto"  # engine evaluates all bracket-fill options, picks best


class Assumptions(BaseModel):
    inflation: float = Field(default=0.025, ge=0, le=0.10)
    healthcare_inflation: float = Field(default=0.05, ge=0, le=0.12)
    state_tax_rate: float = Field(default=0.0, ge=0, le=0.15)
    # Flat marginal rate used ONLY before retirement, for the annual tax
    # drag on taxable-account dividends and any forced pre-retirement RMDs.
    pre_retirement_tax_rate: float = Field(default=0.22, ge=0, le=0.50)
    # Portion of taxable-account return paid out annually as (qualified)
    # dividends; the rest is unrealized appreciation.
    taxable_dividend_yield: float = Field(default=0.02, ge=0, le=0.08)
    # Used to value remaining tax-deferred dollars after death.
    heir_tax_rate: float = Field(default=0.24, ge=0, le=0.50)
    contributions_grow_with_inflation: bool = True
    roth_conversion_strategy: ConversionStrategy = ConversionStrategy.auto
    custom_conversion_amount: float = Field(default=0, ge=0)
    optimize_ss_claiming: bool = False
    # When True, exhaustively compares Traditional-vs-Roth contribution splits
    # (per person) and selects the one with the highest ending after-tax wealth.
    # Meaningful only when salaries are provided (the deduction needs a bracket).
    optimize_contribution_split: bool = False
    # Pre-65 ACA modeling (estimates, clearly labeled in UI/workbook).
    aca_benchmark_monthly_per_person: float = Field(default=850, ge=0)
    pre65_oop_annual_per_person: float = Field(default=2_500, ge=0)
    # 65+: Part D, Medigap/Advantage, dental, out-of-pocket (excl. Part B).
    medicare_other_annual_per_person: float = Field(default=3_500, ge=0)
    # Household MAGI in the last two working years (drives IRMAA for the
    # first two Medicare years via the 2-year lookback). None => engine
    # assumes 1.5x annual spending, labeled as an estimate.
    pre_retirement_magi: Optional[float] = Field(default=None, ge=0)


class PlanInput(BaseModel):
    persons: list[Person] = Field(min_length=1, max_length=2)
    accounts: list[Account] = Field(min_length=1, max_length=20)
    liabilities: list[Liability] = Field(default_factory=list, max_length=20)
    income_streams: list[IncomeStream] = Field(default_factory=list, max_length=20)
    insurance_policies: list[InsurancePolicy] = Field(default_factory=list, max_length=20)
    annuities: list[Annuity] = Field(default_factory=list, max_length=20)
    annual_spending: float = Field(gt=0)  # retirement spend goal, today's $
    assumptions: Assumptions = Field(default_factory=Assumptions)

    @model_validator(mode="after")
    def _check_owners(self) -> "PlanInput":
        n = len(self.persons)
        for a in self.accounts:
            if a.owner >= n:
                raise ValueError(f"Account '{a.name}' owner index out of range")
        for s in self.income_streams:
            if s.owner >= n:
                raise ValueError(f"Income stream '{s.name}' owner index out of range")
        for p in self.insurance_policies:
            if p.owner >= n:
                raise ValueError(f"Insurance policy '{p.name}' owner index out of range")
        for an in self.annuities:
            if an.owner >= n:
                raise ValueError(f"Annuity '{an.name}' owner index out of range")
        return self


# ----------------------------- outputs ------------------------------------

class AccountYear(BaseModel):
    """One account's audit trail for one year."""
    name: str
    type: Optional[AccountType] = None   # None for legacy assets (see asset_class)
    owner: int
    start_balance: float
    contribution: float
    withdrawal: float
    conversion_out: float = 0  # tax-deferred -> roth
    conversion_in: float = 0
    growth: float
    end_balance: float
    cost_basis: Optional[float] = None  # taxable accounts
    # Legacy-asset flows (default 0 / "account" so existing rows are unchanged).
    premium: float = 0                  # insurance premium outflow
    distribution: float = 0             # annuity payout / private distribution out
    death_benefit_paid: float = 0       # life-insurance death benefit paid to estate
    death_benefit: float = 0            # standing face amount (insurance terminal value)
    asset_class: str = "account"        # account | insurance | annuity | private | realestate
    transfer_character: Optional[str] = None  # TransferCharacter value
    beneficiary: str = "heirs"          # Beneficiary value


class YearRow(BaseModel):
    year: int
    ages: list[Optional[int]]          # None once deceased
    phase: str                          # accumulation | retirement
    filing_status: str                  # single | mfj
    accounts: list[AccountYear]

    # cash flows (nominal $)
    spend_goal: float = 0               # inflated lifestyle spending
    debt_payments: float = 0
    home_purchase: float = 0            # one-time down payment / purchase outflow
    healthcare_cost: float = 0          # net premiums + OOP, incl. IRMAA
    aca_subsidy: float = 0
    irmaa_surcharge: float = 0
    ss_benefit: list[float] = []        # per person, gross
    ss_total: float = 0
    other_income: float = 0
    rmd_total: float = 0
    rmd_by_person: list[float] = []
    withdrawals_by_type: dict[str, float] = {}
    roth_conversion: float = 0
    surplus_reinvested: float = 0
    shortfall: float = 0                # unmet spending (plan failure)
    premiums_paid: float = 0            # insurance premiums this year
    legacy_distributions: float = 0     # annuity/private distributions this year
    death_benefits_paid: float = 0      # life-insurance proceeds received this year
    qcd_amount: float = 0               # qualified charitable distribution (IRC §408(d)(8))
    gifts_made: float = 0               # lifetime gifts out of the portfolio this year

    # tax detail (nominal $)
    dividends: float = 0
    interest: float = 0
    realized_gains: float = 0
    taxable_ss: float = 0
    agi: float = 0
    magi: float = 0
    deductions: float = 0
    taxable_income: float = 0
    federal_tax: float = 0
    ltcg_tax: float = 0                 # portion of federal_tax from cap gains
    niit: float = 0
    state_tax: float = 0
    penalties: float = 0
    total_tax: float = 0
    marginal_rate: float = 0
    effective_rate: float = 0

    # balances
    total_assets: float = 0
    total_liabilities: float = 0
    net_worth: float = 0
    net_worth_real: float = 0           # deflated to today's dollars
    flags: list[str] = []


class Metrics(BaseModel):
    nest_egg_at_retirement: float
    nest_egg_at_retirement_real: float
    retirement_year: int
    ending_net_worth: float
    ending_net_worth_real: float
    ending_after_tax_real: float        # tax-deferred discounted at heir rate
    lifetime_taxes: float
    lifetime_taxes_real: float
    depleted: bool
    depletion_age: Optional[int] = None  # primary person's age when funds ran out
    success: bool
    chosen_conversion_strategy: str
    ss_claim_ages: list[int]
    # Legacy / estate (today's dollars). Estate transfer tax is NOT modeled.
    gross_estate_real: float = 0         # to heirs + to charity, before heir income tax
    net_to_heirs_real: float = 0         # after IRD income tax, net of liabilities
    estate_ird_tax_real: float = 0       # ordinary income tax heirs owe on IRD assets
    to_charity_real: float = 0           # charitable bequests
    gifts_made_total_real: float = 0     # cumulative lifetime gifts
    # Suggested household Roth fraction (single-element list) from the advisory
    # split optimizer; empty when it was not run. Not applied to this projection.
    chosen_contribution_split: list[float] = []


class SensitivityRow(BaseModel):
    label: str
    parameter: str
    delta: str
    ending_net_worth_real: float
    nest_egg_real: float
    depletion_age: Optional[int]
    success: bool


class StrategyComparison(BaseModel):
    strategy: str
    ending_after_tax_real: float
    lifetime_taxes_real: float
    total_converted: float
    depletion_age: Optional[int]


class SSGridCell(BaseModel):
    claim_ages: list[int]
    ending_after_tax_real: float
    depletion_age: Optional[int]


class LegacyAssetResult(BaseModel):
    """One asset's at-death disposition for the Legacy / Estate view."""
    name: str
    asset_class: str           # account | insurance | annuity | private | realestate
    transfer_character: str    # TransferCharacter value
    beneficiary: str           # Beneficiary value
    gross: float               # value passing (today's dollars)
    tax: float                 # heir income tax (IRD); 0 for step-up/tax-free
    net: float                 # gross - tax


class LegacyResult(BaseModel):
    at_death_year: int                       # primary person's death year
    assets: list[LegacyAssetResult] = []
    to_heirs_gross: float = 0
    to_heirs_net: float = 0                   # net of IRD tax and liabilities
    to_charity: float = 0
    ird_tax: float = 0
    gifts_lifetime: float = 0
    exemption_used: float = 0                 # cumulative gift/estate exemption consumed
    # All figures in today's dollars. Federal/state estate tax is NOT modeled.


class ContributionSplitCell(BaseModel):
    """One evaluated Traditional-vs-Roth contribution split (a full re-sim).

    `roth_pct` is a single-element list holding the HOUSEHOLD Roth fraction:
    the share of total Traditional+Roth contributions routed to Roth (the
    couple files jointly, so only the household ratio is meaningful).
    """
    roth_pct: list[float]
    ending_after_tax_real: float
    lifetime_taxes_real: float
    depletion_age: Optional[int]
    # Optimal Roth-conversion strategy paired with this split (best-case): the
    # comparison shows each split at its best, including the conversion lever.
    conversion_strategy: str = ""
    is_current: bool = False  # matches the household's current allocation


class PlanResult(BaseModel):
    metrics: Metrics
    years: list[YearRow]
    sensitivity: list[SensitivityRow]
    conversion_comparison: list[StrategyComparison]
    ss_grid: list[SSGridCell] = []
    contribution_split: list[ContributionSplitCell] = []
    warnings: list[str] = []
    assumption_notes: list[dict[str, str]] = []  # label/value/source triples
    legacy: Optional[LegacyResult] = None
