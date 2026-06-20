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
        """Vehicle for limit purposes; defaults to employer when unspecified."""
        return self.vehicle if self.vehicle is not None else AccountVehicle.employer


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
        return self


# ----------------------------- outputs ------------------------------------

class AccountYear(BaseModel):
    """One account's audit trail for one year."""
    name: str
    type: AccountType
    owner: int
    start_balance: float
    contribution: float
    withdrawal: float
    conversion_out: float = 0  # tax-deferred -> roth
    conversion_in: float = 0
    growth: float
    end_balance: float
    cost_basis: Optional[float] = None  # taxable accounts


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
    # Per-person fraction of the retirement-contribution budget routed to Roth
    # under the chosen split (empty when the split optimizer was not run).
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


class ContributionSplitCell(BaseModel):
    """One evaluated Traditional-vs-Roth contribution split (a full re-sim).

    `roth_pct` is per person: the fraction of that person's combined
    Traditional+Roth annual contribution routed to Roth.
    """
    roth_pct: list[float]
    ending_after_tax_real: float
    lifetime_taxes_real: float
    depletion_age: Optional[int]
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
