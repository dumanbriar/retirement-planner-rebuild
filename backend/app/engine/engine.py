"""Year-by-year deterministic projection engine.

One unified calendar-year loop covers both phases:

  Accumulation (until every person has reached their retirement age):
    contributions, growth, annual tax drag on taxable dividends and cash
    interest, forced RMDs. Lifestyle spending and debt payments are assumed
    covered by employment income (which is intentionally not modeled).

  Retirement (all persons retired):
    Social Security, other income streams, RMDs, the withdrawal waterfall,
    Roth conversions, healthcare (ACA pre-65; Medicare Part B + IRMAA with
    the statutory 2-year MAGI lookback), and a full federal/state tax
    computation solved to a fixed point (taxes are themselves funded from
    the withdrawal waterfall).

Timing conventions (also stated in the Excel workbook):
  - Ages are end-of-year ages (age = year - birth year).
  - Dividend/interest income is recognized on start-of-year balances.
  - Contributions and withdrawals occur at the start of the year; total
    return applies to the post-flow balance (dividends are treated as
    reinvested and are included in that total return).
  - RMDs are computed on the prior year-end balance (Treas. Reg.
    1.401(a)(9)-5) using the owner's end-of-year age.
"""
from __future__ import annotations

from typing import Optional

from ..models import (Account, AccountType, AccountVehicle, AccountYear,
                      Annuity, Beneficiary, ConversionStrategy,
                      DistributionKind, InsurancePolicy, LegacyAssetResult,
                      LegacyResult, Metrics, PlanInput, PrivateHolding,
                      RealEstate, TransferCharacter, YearRow)
from . import constants as C
from . import socialsecurity as ss
from .taxes import (TaxYearInput, aca_subsidy, compute_taxes, irmaa_tier,
                    medicare_part_b_annual)

WATERFALL = [AccountType.cash, AccountType.taxable, AccountType.tax_deferred,
             AccountType.roth, AccountType.hsa]

# How each account type passes to heirs at death (IRC §1014 step-up, §691 IRD,
# or tax-free for Roth). Legacy assets added in later phases set their own
# transfer_character on the AccountYear; accounts fall back to this map.
ACCOUNT_TRANSFER_CHARACTER = {
    AccountType.tax_deferred: TransferCharacter.ird,
    AccountType.hsa: TransferCharacter.ird,
    AccountType.taxable: TransferCharacter.step_up,
    AccountType.cash: TransferCharacter.step_up,
    AccountType.roth: TransferCharacter.tax_free,
}

BRACKET_TOP_INDEX = {
    ConversionStrategy.fill_10: 0,
    ConversionStrategy.fill_12: 1,
    ConversionStrategy.fill_22: 2,
    ConversionStrategy.fill_24: 3,
}

# Annual tax drag applied to qualified dividends during accumulation
# (15% LTCG-rate assumption, documented).
ACCUM_DIVIDEND_TAX_RATE = 0.15


class SimAccount:
    def __init__(self, spec: Account):
        self.spec = spec
        self.balance = spec.balance
        self.basis = spec.cost_basis if spec.cost_basis is not None else spec.balance
        self.owner = spec.owner
        self.reset_flows()

    def reset_flows(self):
        self.start_balance = self.balance
        self.contribution = 0.0
        self.withdrawal = 0.0
        self.conv_out = 0.0
        self.conv_in = 0.0
        self.growth = 0.0
        self.drag = 0.0  # accumulation-phase annual tax on divs/interest


class SimInsurance:
    """Internal state for a whole-life policy. Held parallel to self.accounts;
    never enters the withdrawal waterfall. Its cash value counts in net worth
    while in force; at the insured's death the (tax-free) death benefit is paid
    to the survivor's portfolio (mid-plan) or to the estate (terminal)."""
    def __init__(self, spec: InsurancePolicy):
        self.spec = spec
        self.owner = spec.owner
        self.cash_value = spec.cash_value
        self.basis = spec.premiums_paid_to_date  # total premiums paid (surrender basis)
        self.active = True
        self.growth = 0.0

    @property
    def rate(self) -> float:
        return self.spec.cash_value_return


class SimAnnuity:
    """Internal state for a non-qualified deferred annuity. Accumulates tax-
    deferred, then pays a level period-certain stream from annuitize_at_age.
    Never in the withdrawal waterfall; its balance counts in net worth."""
    def __init__(self, spec: Annuity):
        self.spec = spec
        self.owner = spec.owner
        future = spec.purchase_age is not None
        self.purchased = not future        # already owned vs planned future buy
        self.active = not future           # dormant until purchased
        self.balance = 0.0 if future else spec.balance
        self.basis = 0.0 if future else spec.basis  # remaining un-recovered basis
        self.annuitized = False
        self.payment = 0.0                 # level annual payout once annuitized
        self.excluded = 0.0                # basis returned tax-free per payout year
        self.payout_left = 0
        # per-year reporting scratch
        self.start_balance = self.balance
        self.growth = 0.0
        self.payout = 0.0
        self.contribution = 0.0            # lump sum in the purchase year

    @property
    def rate(self) -> float:
        return self.spec.accumulation_return


class SimPrivate:
    """Internal state for a private holding (company shares / partnership
    interest). Illiquid: never in the withdrawal waterfall; its value counts
    in net worth. Grows at the assumed rate, optionally pays a level annual
    K-1 cash distribution out of that growth, and can be sold in a one-time
    liquidity event (LTCG on the gain over basis)."""
    def __init__(self, spec: PrivateHolding):
        self.spec = spec
        self.owner = spec.owner
        self.value = spec.value
        self.basis = spec.basis
        self.original_value = spec.value  # base for phased-divestiture %s
        self.active = True
        # per-year reporting scratch
        self.start_balance = self.value
        self.growth = 0.0
        self.distribution = 0.0
        self.sale_proceeds = 0.0

    @property
    def rate(self) -> float:
        return self.spec.growth_rate


class SimRealEstate:
    """Internal state for a property. Illiquid: never in the withdrawal
    waterfall; its value counts in net worth (unless excluded by the toggle).
    Appreciates at the assumed rate; an optional sale pays off the linked
    mortgage's current balance and deposits the net proceeds, realizing the
    gain over basis as LTCG net of the §121 primary-residence exclusion."""
    def __init__(self, spec: RealEstate):
        self.spec = spec
        self.owner = spec.owner
        self.value = spec.value
        self.basis = spec.basis
        self.active = True
        # per-year reporting scratch
        self.start_balance = self.value
        self.growth = 0.0
        self.sale_proceeds = 0.0


class YearScratch:
    def __init__(self):
        self.withdrawals_by_type: dict[str, float] = {}
        self.realized_gains = 0.0
        self.penalties = 0.0
        self.hsa_nonmedical = 0.0
        self.hsa_medical = 0.0
        self.roth_conversion = 0.0
        self.shortfall = 0.0
        self.flags: list[str] = []


class Simulator:
    def __init__(self, plan: PlanInput,
                 strategy: Optional[ConversionStrategy] = None,
                 claim_ages: Optional[list[int]] = None,
                 base_calendar_year: int = C.BASE_YEAR):
        self.plan = plan
        self.a = plan.assumptions
        self.strategy = strategy if strategy is not None else self.a.roth_conversion_strategy
        if self.strategy == ConversionStrategy.auto:
            raise ValueError("Simulator requires a concrete strategy; resolve 'auto' first")
        self.base_year = base_calendar_year
        self.persons = plan.persons
        # Wages drive the real accumulation-phase marginal bracket. With no
        # salary anywhere we keep the legacy flat-rate accumulation tax path.
        self.has_salary = any(p.salary > 0 for p in self.persons)
        self.claim_ages = claim_ages or [p.ss_claim_age for p in self.persons]
        self.birth_years = [self.base_year - p.current_age for p in self.persons]
        self.retirement_year = max(by + p.retirement_age
                                   for by, p in zip(self.birth_years, self.persons))
        self.end_year = max(by + p.death_age
                            for by, p in zip(self.birth_years, self.persons))
        self.warnings: list[str] = []

        self.policies = [SimInsurance(p) for p in plan.insurance_policies]
        self.annuities = [SimAnnuity(a) for a in plan.annuities]
        self.holdings = [SimPrivate(h) for h in plan.private_holdings]
        self.props = [SimRealEstate(r) for r in plan.real_estate]
        # per-year insurance/annuity scratch (set each year before the phase step)
        self._ins_premium = 0.0
        self._ins_surrender_gain = 0.0
        self._death_benefit_paid_year = 0.0
        self._annuity_payout = 0.0       # total annuity payments this year (cash)
        self._annuity_taxable = 0.0      # ordinary (gain) portion of those payments
        self._annuity_purchase = 0.0     # lump sum to fund a planned annuity buy
        self._priv_distribution = 0.0    # K-1 cash distributions this year
        self._priv_dist_ordinary = 0.0   # ...taxed as ordinary income
        self._priv_dist_qualified = 0.0  # ...taxed as qualified dividends
        self._priv_sale_gain = 0.0       # LTCG realized by a liquidity event
        self._re_sale_gain = 0.0         # taxable LTCG from property sales (post-§121)

        self.accounts = [SimAccount(s) for s in plan.accounts]
        if not any(x.spec.type in (AccountType.taxable, AccountType.cash)
                   for x in self.accounts):
            self.accounts.append(SimAccount(Account(
                name="Reinvested surplus (brokerage)", type=AccountType.taxable,
                owner=0, balance=0, cost_basis=0)))

        self.liabilities = [{"name": l.name, "balance": l.balance,
                             "rate": l.interest_rate, "payment": l.annual_payment,
                             "start_age": l.start_age, "down_payment": l.down_payment,
                             "activated": False}
                            for l in plan.liabilities]
        self.magi_history: dict[int, float] = {}
        self.ss_level: list[float] = [0.0] * len(self.persons)   # today's-$ annual
        self.ss_topped_up: list[bool] = [False] * len(self.persons)
        self.deceased_ss_level = 0.0

        for i, p in enumerate(self.persons):
            if p.ss_monthly_at_fra > 0 and \
                    self.birth_years[i] + self.claim_ages[i] < self.retirement_year:
                self.warnings.append(
                    f"{p.name}: Social Security starts before household retirement; those "
                    "benefits are reinvested net of the pre-retirement tax rate.")

    # ------------------------------------------------------------------ utils
    def infl(self, year: int) -> float:
        return (1 + self.a.inflation) ** (year - self.base_year)

    def hc_infl(self, year: int) -> float:
        return (1 + self.a.healthcare_inflation) ** (year - self.base_year)

    def age(self, i: int, year: int) -> int:
        return year - self.birth_years[i]

    def alive(self, i: int, year: int) -> bool:
        return self.age(i, year) <= self.persons[i].death_age

    def _liab_active(self, l: dict, year: int) -> bool:
        """A future-dated liability (a home purchase) is dormant until the
        primary person reaches its start age; None => active from year 1."""
        return l["start_age"] is None or self.age(0, year) >= l["start_age"]

    def _is_future_purchase(self, l: dict) -> bool:
        """True only for a genuinely future purchase (start age beyond the
        primary's age today), which carries a down payment. A start age
        at/below today's age is a pre-existing debt."""
        return l["start_age"] is not None and l["start_age"] > self.age(0, self.base_year)

    def activate_liabilities(self, year: int) -> float:
        """Activate any liabilities whose purchase year is `year`. Future-purchase
        amounts are entered as literal (nominal) purchase-date dollars, so no
        scaling is applied. Returns the down-payment outflow due now."""
        due = 0.0
        for l in self.liabilities:
            if l["activated"] or not self._liab_active(l, year):
                continue
            l["activated"] = True
            if self._is_future_purchase(l):
                due += l["down_payment"]
        return due

    def filing_status(self, year: int) -> str:
        n_alive = sum(self.alive(i, year) for i in range(len(self.persons)))
        return "mfj" if n_alive >= 2 else "single"

    def pre_retirement_magi(self) -> float:
        if self.a.pre_retirement_magi is not None:
            return self.a.pre_retirement_magi
        return self.plan.annual_spending * 1.5

    def lookback_magi(self, year: int) -> float:
        y = year - 2
        if y in self.magi_history:
            return self.magi_history[y]
        return self.pre_retirement_magi() * self.infl(y)

    def surplus_account(self) -> SimAccount:
        for t in (AccountType.taxable, AccountType.cash):
            for acct in self.accounts:
                if acct.spec.type == t:
                    return acct
        return self.accounts[0]

    def _reinvest(self, amount: float, row: YearRow) -> None:
        """Deposit surplus cash into the taxable/cash surplus account and
        record it on the row (used for net inflows and reinvested tax savings)."""
        if amount <= 0:
            return
        tgt = self.surplus_account()
        tgt.balance += amount
        tgt.contribution += amount
        if tgt.spec.type == AccountType.taxable:
            tgt.basis += amount
        row.surplus_reinvested += amount

    # ----------------------------------------------------------- income bits
    def update_ss_levels(self, year: int):
        for i, p in enumerate(self.persons):
            if not self.alive(i, year) or p.ss_monthly_at_fra <= 0:
                continue
            if self.age(i, year) >= self.claim_ages[i] and self.ss_level[i] == 0.0:
                self.ss_level[i] = p.ss_monthly_at_fra * 12 * \
                    ss.claiming_factor(self.birth_years[i], self.claim_ages[i])
        # spousal top-up once BOTH have claimed (deemed-filing simplification)
        if len(self.persons) == 2:
            both_claimed = all(
                self.ss_level[k] > 0 or self.persons[k].ss_monthly_at_fra == 0
                for k in range(2))
            if both_claimed:
                for i in range(2):
                    j = 1 - i
                    if self.ss_topped_up[i] or not self.alive(i, year):
                        continue
                    own_pia = self.persons[i].ss_monthly_at_fra
                    sp_pia = self.persons[j].ss_monthly_at_fra
                    spousal_base = max(0.0, 0.5 * sp_pia - own_pia)
                    if spousal_base > 0:
                        # spousal entitlement begins when both have filed
                        entitle_age = max(self.claim_ages[i],
                                          min(self.age(i, year), 70))
                        self.ss_level[i] += spousal_base * 12 * \
                            ss.spousal_factor(self.birth_years[i], entitle_age)
                    self.ss_topped_up[i] = True
            # survivor: higher of own and the deceased's actual benefit
            for i in range(2):
                j = 1 - i
                if self.alive(i, year) and not self.alive(j, year) \
                        and self.deceased_ss_level > self.ss_level[i] \
                        and self.age(i, year) >= self.claim_ages[i]:
                    self.ss_level[i] = self.deceased_ss_level

    def ss_benefits(self, year: int) -> list[float]:
        return [self.ss_level[i] * self.infl(year) if self.alive(i, year) else 0.0
                for i in range(len(self.persons))]

    def other_income(self, year: int) -> tuple[float, float]:
        taxable = nontaxable = 0.0
        for s in self.plan.income_streams:
            i = s.owner
            a = self.age(i, year)  # notional age; valid even after the owner dies
            if a < s.start_age or (s.end_age is not None and a > s.end_age):
                continue
            if self.alive(i, year):
                factor = 1.0
            else:
                # Joint-and-survivor: a fraction continues to a surviving spouse
                # (e.g. a 50% survivor pension). Requires the stream to have
                # already started (checked above) and a living spouse.
                survivor_pct = getattr(s, "survivor_pct", 0.0)
                survives = len(self.persons) == 2 and self.alive(1 - i, year)
                if not survives or survivor_pct <= 0:
                    continue
                factor = survivor_pct
            amt = s.annual_amount * (self.infl(year) if s.cola else 1.0) * factor
            if s.taxable:
                taxable += amt
            else:
                nontaxable += amt
        return taxable, nontaxable

    def compute_rmds(self, year: int) -> list[float]:
        """Prior year-end tax-deferred balance / uniform-table factor."""
        prior = {}
        for acct in self.accounts:
            if acct.spec.type == AccountType.tax_deferred:
                prior[acct.owner] = prior.get(acct.owner, 0.0) + acct.start_balance
        out = [0.0] * len(self.persons)
        for i in range(len(self.persons)):
            if not self.alive(i, year):
                continue
            a = self.age(i, year)
            if a >= C.rmd_start_age(self.birth_years[i]) and prior.get(i, 0) > 0:
                out[i] = prior[i] / C.rmd_factor(a)
        return out

    def start_of_year_income(self) -> tuple[float, float]:
        """(qualified dividends, cash interest) on start-of-year balances."""
        div = sum(x.start_balance * min(self.a.taxable_dividend_yield,
                                        max(x.spec.rate(), 0.0))
                  for x in self.accounts if x.spec.type == AccountType.taxable)
        intr = sum(x.start_balance * max(x.spec.rate(), 0.0)
                   for x in self.accounts if x.spec.type == AccountType.cash)
        return div, intr

    # ------------------------------------------------------------ withdrawals
    def withdraw_from(self, acct: SimAccount, amount: float,
                      scratch: YearScratch, year: int) -> float:
        take = min(amount, acct.balance)
        if take <= 0:
            return 0.0
        t = acct.spec.type
        if t == AccountType.taxable:
            frac = min(1.0, acct.basis / acct.balance) if acct.balance > 0 else 1.0
            scratch.realized_gains += take * (1 - frac)
            acct.basis -= take * frac
        elif t == AccountType.tax_deferred:
            if self.age(acct.owner, year) < C.EARLY_WITHDRAWAL_AGE:
                scratch.penalties += take * C.EARLY_WITHDRAWAL_PENALTY
                scratch.flags.append("10% early-withdrawal penalty (pre-59.5) applied")
        elif t == AccountType.hsa:
            scratch.hsa_nonmedical += take
            if self.age(acct.owner, year) < C.HSA_PENALTY_END_AGE:
                scratch.penalties += take * C.HSA_PENALTY_RATE
                scratch.flags.append("20% HSA non-medical withdrawal penalty applied")
        elif t == AccountType.roth:
            if self.age(acct.owner, year) < C.EARLY_WITHDRAWAL_AGE:
                scratch.flags.append(
                    "Roth withdrawal before 59.5: treated as contribution basis (no tax modeled)")
        acct.balance -= take
        acct.withdrawal += take
        scratch.withdrawals_by_type[t.value] = \
            scratch.withdrawals_by_type.get(t.value, 0.0) + take
        return take

    def waterfall_withdraw(self, amount: float, scratch: YearScratch, year: int) -> float:
        remaining = amount
        for t in WATERFALL:
            for acct in self.accounts:
                if acct.spec.type != t:
                    continue
                if remaining <= 0.005:
                    return amount
                remaining -= self.withdraw_from(acct, remaining, scratch, year)
        return amount - max(0.0, remaining)

    def conversion_target(self, year: int, ord_taxable_excl_conv: float,
                          td_available: float) -> float:
        if self.strategy == ConversionStrategy.none:
            return 0.0
        if self.strategy == ConversionStrategy.custom:
            return min(self.a.custom_conversion_amount * self.infl(year), td_available)
        status = self.filing_status(year)
        idx = BRACKET_TOP_INDEX[self.strategy]
        scale = self.infl(year)
        top = C.FEDERAL_BRACKETS[status][idx][0] * scale
        return max(0.0, min(top - ord_taxable_excl_conv, td_available))

    # -------------------------------------------------------------- main run
    def run(self) -> tuple[list[YearRow], Metrics]:
        rows: list[YearRow] = []
        prev_tax = 0.0
        lifetime_tax = lifetime_tax_real = 0.0
        depleted = False
        depletion_age: Optional[int] = None
        nest_egg = nest_egg_real = 0.0

        for year in range(self.base_year, self.end_year + 1):
            if not any(self.alive(i, year) for i in range(len(self.persons))):
                break

            self._death_benefit_paid_year = 0.0
            # spousal rollover: survivor inherits the deceased's accounts
            for i in range(len(self.persons)):
                if not self.alive(i, year):
                    if len(self.persons) == 2 and self.alive(1 - i, year):
                        for acct in self.accounts:
                            if acct.owner == i:
                                acct.owner = 1 - i
                        # non-qualified annuity: a surviving spouse continues it
                        # (spousal continuation); the schedule keys off their age.
                        for an in self.annuities:
                            if an.owner == i:
                                an.owner = 1 - i
                        # private shares / real estate: a surviving spouse
                        # inherits with a basis step-up to the date-of-death
                        # value (IRC §1014; full step-up assumed — see notes).
                        for h in self.holdings:
                            if h.active and h.owner == i:
                                h.owner = 1 - i
                                h.basis = h.value
                        for r in self.props:
                            if r.active and r.owner == i:
                                r.owner = 1 - i
                                r.basis = r.value
                        # life insurance: the death benefit is paid (income-tax-
                        # free, IRC §101) into the surviving spouse's portfolio.
                        for p in self.policies:
                            if p.active and p.owner == i:
                                db = p.spec.death_benefit
                                tgt = self.surplus_account()
                                tgt.balance += db
                                tgt.contribution += db
                                if tgt.spec.type == AccountType.taxable:
                                    tgt.basis += db
                                p.active = False
                                self._death_benefit_paid_year += db
                    if self.ss_level[i] > 0:
                        self.deceased_ss_level = max(self.deceased_ss_level,
                                                     self.ss_level[i])
                        self.ss_level[i] = 0.0

            for acct in self.accounts:
                acct.reset_flows()

            retired = year >= self.retirement_year
            status = self.filing_status(year)
            self.update_ss_levels(year)
            self.prepare_insurance(year)
            self.prepare_annuities(year)
            self.prepare_private(year)
            self.prepare_real_estate(year)
            dividends, interest = self.start_of_year_income()

            # a future home purchase activates here: the mortgage appears and a
            # one-time down payment must be funded from the portfolio this year
            home_purchase = self.activate_liabilities(year)

            if retired:
                row, prev_tax = self.retirement_year_step(
                    year, status, dividends, interest, prev_tax, home_purchase)
            else:
                row = self.accumulation_year_step(year, status, home_purchase)

            row.dividends = dividends
            row.interest = interest

            # growth on post-flow balances; dividends reinvest (add to basis)
            for acct in self.accounts:
                acct.growth = acct.balance * acct.spec.rate()
                acct.balance += acct.growth
                if acct.spec.type == AccountType.taxable:
                    acct.basis += acct.start_balance * min(
                        self.a.taxable_dividend_yield, max(acct.spec.rate(), 0.0))
                    acct.basis = min(acct.basis, acct.balance)

            # whole-life cash value compounds tax-deferred (no annual drag)
            for p in self.policies:
                p.growth = p.cash_value * p.rate if p.active else 0.0
                p.cash_value += p.growth

            # a surrender during accumulation is taxed at the flat pre-retirement
            # rate, drawn from the portfolio (retirement surrenders flow through
            # compute_taxes in retirement_year_step instead).
            if not retired and self._ins_surrender_gain > 0:
                t = self._ins_surrender_gain * self.a.pre_retirement_tax_rate
                row.total_tax += t
                tgt = self.surplus_account()
                tgt.balance -= t

            # an annuity that annuitizes before household retirement: the payout
            # is reinvested net of the flat pre-retirement tax on its gain portion.
            if not retired and self._annuity_payout > 0:
                t = self._annuity_taxable * self.a.pre_retirement_tax_rate
                net = self._annuity_payout - t
                row.total_tax += t
                row.legacy_distributions += self._annuity_payout
                tgt = self.surplus_account()
                tgt.balance += net
                tgt.contribution += net
                if tgt.spec.type == AccountType.taxable:
                    tgt.basis += net

            # K-1 distributions before retirement reinvest net of tax: ordinary
            # at the flat pre-retirement rate, qualified at the 15% dividend rate.
            if not retired and self._priv_distribution > 0:
                t = (self._priv_dist_ordinary * self.a.pre_retirement_tax_rate
                     + self._priv_dist_qualified * ACCUM_DIVIDEND_TAX_RATE)
                row.total_tax += t
                row.legacy_distributions += self._priv_distribution
                self._reinvest(self._priv_distribution - t, row)

            # a liquidity event / property sale during accumulation: the LTCG
            # is taxed at the flat 15% rate (the documented accumulation-phase
            # capital-gain assumption), paid from the portfolio. Retirement
            # sales instead flow through compute_taxes with full 0/15/20%
            # stacking + NIIT.
            if not retired and (self._priv_sale_gain + self._re_sale_gain) > 0:
                t = (self._priv_sale_gain + self._re_sale_gain) \
                    * ACCUM_DIVIDEND_TAX_RATE
                row.total_tax += t
                tgt = self.surplus_account()
                tgt.balance -= t

            if not retired:
                # annual drag, paid from the accounts (shown net in growth)
                for acct in self.accounts:
                    if acct.spec.type == AccountType.taxable:
                        d = acct.start_balance * min(self.a.taxable_dividend_yield,
                                                     max(acct.spec.rate(), 0.0))
                        acct.drag = d * ACCUM_DIVIDEND_TAX_RATE
                    elif acct.spec.type == AccountType.cash:
                        acct.drag = acct.start_balance * max(acct.spec.rate(), 0.0) \
                            * self.a.pre_retirement_tax_rate
                    acct.balance -= acct.drag
                    row.total_tax += acct.drag

            # active liabilities amortize every year (dormant future debts skip)
            debt_paid = 0.0
            for l in self.liabilities:
                if l["balance"] <= 0 or not self._liab_active(l, year):
                    continue
                accrued = l["balance"] * (1 + l["rate"])
                pay = min(l["payment"], accrued)
                l["balance"] = accrued - pay
                debt_paid += pay
            if retired:
                row.debt_payments = debt_paid

            row.accounts = [AccountYear(
                name=x.spec.name, type=x.spec.type, owner=x.owner,
                start_balance=x.start_balance,
                contribution=x.contribution, withdrawal=x.withdrawal,
                conversion_out=x.conv_out, conversion_in=x.conv_in,
                growth=x.growth - x.drag, end_balance=x.balance,
                cost_basis=x.basis if x.spec.type == AccountType.taxable else None,
                asset_class="account",
                transfer_character=ACCOUNT_TRANSFER_CHARACTER[x.spec.type].value,
                beneficiary=x.spec.beneficiary.value,
            ) for x in self.accounts]
            # whole-life policies report their cash value (their balance-sheet
            # value while in force); the death benefit is the terminal/legacy value.
            row.accounts += [AccountYear(
                name=p.spec.name, type=None, owner=p.owner,
                start_balance=p.cash_value - p.growth, contribution=0.0,
                withdrawal=0.0, growth=p.growth, end_balance=p.cash_value,
                premium=(p.spec.annual_premium if retired and (
                    p.spec.paid_up_age is None
                    or self.age(p.owner, year) < p.spec.paid_up_age) else 0.0),
                death_benefit=p.spec.death_benefit,
                asset_class="insurance",
                transfer_character=TransferCharacter.tax_free.value,
                beneficiary=p.spec.beneficiary.value,
            ) for p in self.policies if p.active]
            # deferred annuities (accumulation value, or remaining payout value)
            row.accounts += [AccountYear(
                name=a.spec.name, type=None, owner=a.owner,
                start_balance=a.start_balance, contribution=a.contribution,
                withdrawal=0.0, distribution=a.payout, growth=a.growth,
                end_balance=a.balance, cost_basis=a.basis,
                asset_class="annuity",
                transfer_character=TransferCharacter.ird.value,
                beneficiary=a.spec.beneficiary.value,
            ) for a in self.annuities if a.active or a.payout > 0]
            # private holdings (value, basis, this year's K-1 / sale flows)
            row.accounts += [AccountYear(
                name=h.spec.name, type=None, owner=h.owner,
                start_balance=h.start_balance, contribution=0.0,
                withdrawal=h.sale_proceeds, distribution=h.distribution,
                growth=h.growth, end_balance=h.value, cost_basis=h.basis,
                asset_class="private",
                transfer_character=TransferCharacter.step_up.value,
                beneficiary=h.spec.beneficiary.value,
            ) for h in self.holdings if h.active or h.sale_proceeds > 0]
            # real estate (value, basis, this year's appreciation / sale)
            row.accounts += [AccountYear(
                name=r.spec.name, type=None, owner=r.owner,
                start_balance=r.start_balance, contribution=0.0,
                withdrawal=r.sale_proceeds, growth=r.growth,
                end_balance=r.value, cost_basis=r.basis,
                asset_class="realestate",
                transfer_character=TransferCharacter.step_up.value,
                beneficiary=r.spec.beneficiary.value,
            ) for r in self.props if r.active or r.sale_proceeds > 0]
            row.premiums_paid = self._ins_premium if retired else 0.0
            row.legacy_purchases = self._annuity_purchase
            row.death_benefits_paid = self._death_benefit_paid_year
            if retired:
                row.legacy_distributions += self._annuity_payout \
                    + self._priv_distribution
                self.track_gifts(year, row.gifts_made)
            row.total_assets = (sum(x.balance for x in self.accounts)
                                + sum(p.cash_value for p in self.policies if p.active)
                                + sum(a.balance for a in self.annuities if a.active)
                                + sum(h.value for h in self.holdings if h.active)
                                + sum(r.value for r in self.props
                                      if r.active and r.spec.include_in_net_worth))
            row.total_liabilities = sum(l["balance"] for l in self.liabilities
                                        if self._liab_active(l, year))
            row.net_worth = row.total_assets - row.total_liabilities
            row.net_worth_real = row.net_worth / self.infl(year)
            self.magi_history[year] = row.magi if retired \
                else self.pre_retirement_magi() * self.infl(year)

            lifetime_tax += row.total_tax + row.penalties
            lifetime_tax_real += (row.total_tax + row.penalties) / self.infl(year)
            if row.shortfall > 1 and not depleted:
                depleted = True
                depletion_age = next(a for a in row.ages if a is not None)
                row.flags = list(row.flags) + ["PLAN DEPLETED: spending need unmet this year"]
            if year == self.retirement_year - 1 or \
                    (self.retirement_year <= self.base_year and year == self.base_year):
                nest_egg, nest_egg_real = row.total_assets, row.total_assets / self.infl(year)
            rows.append(row)

        last = rows[-1]
        after_tax, legacy = self.settle_estate(last)
        self.legacy = legacy

        metrics = Metrics(
            nest_egg_at_retirement=nest_egg,
            nest_egg_at_retirement_real=nest_egg_real,
            retirement_year=self.retirement_year,
            ending_net_worth=last.net_worth,
            ending_net_worth_real=last.net_worth_real,
            ending_after_tax_real=after_tax / self.infl(last.year),
            lifetime_taxes=lifetime_tax,
            lifetime_taxes_real=lifetime_tax_real,
            depleted=depleted,
            depletion_age=depletion_age,
            success=not depleted,
            chosen_conversion_strategy=self.strategy.value,
            ss_claim_ages=list(self.claim_ages),
            gross_estate_real=(legacy.to_heirs_gross + legacy.to_charity)
            / self.infl(last.year),
            net_to_heirs_real=legacy.to_heirs_net / self.infl(last.year),
            estate_ird_tax_real=legacy.ird_tax / self.infl(last.year),
            to_charity_real=legacy.to_charity / self.infl(last.year),
            gifts_made_total_real=legacy.gifts_lifetime / self.infl(last.year),
        )
        return rows, metrics

    def settle_estate(self, last: YearRow) -> tuple[float, LegacyResult]:
        """Value the estate at the end of the projection, dispatching on each
        asset's transfer character and destination.

        Returns (after_tax_to_heirs_nominal, LegacyResult). The first value
        feeds ``ending_after_tax_real`` after deflation, and exactly reproduces
        the previous terminal calc for ordinary accounts:
          - ird (tax-deferred, HSA; later: annuity gain): heirs owe ordinary
            income tax on the IRD portion -> balance * (1 - heir_rate)
            (IRC §691; §72).
          - step_up (taxable, cash; later: shares, real estate): basis reset at
            death, no income tax (IRC §1014).
          - tax_free (Roth; later: life-insurance death benefit): received
            income-tax-free (IRC §408A; §101).
        A charity destination passes tax-free OUT of the estate. Federal/state
        estate (transfer) tax — exemption, portability — is intentionally NOT
        modeled; see the assumption notes.
        """
        heir = self.a.heir_tax_rate
        assets: list[LegacyAssetResult] = []
        to_heirs_gross = to_heirs_net = to_charity = ird_tax = 0.0
        for x in last.accounts:
            char = x.transfer_character \
                or ACCOUNT_TRANSFER_CHARACTER[x.type].value
            dest = x.beneficiary or Beneficiary.heirs.value
            # a life policy still in force at the end pays its death benefit
            # (income-tax-free, IRC §101); its cash value is subsumed.
            gross = x.death_benefit if x.asset_class == "insurance" else x.end_balance
            # IRD is taxed on the full balance for tax-deferred/HSA, but only on
            # the GAIN above remaining basis for a non-qualified annuity (§72).
            ird_base = gross
            if x.asset_class == "annuity":
                ird_base = max(0.0, gross - (x.cost_basis or 0.0))
            if dest == Beneficiary.charity.value:
                tax = 0.0
                to_charity += gross
            elif char == TransferCharacter.ird.value:
                tax = ird_base * heir
                to_heirs_gross += gross
                to_heirs_net += gross - tax
                ird_tax += tax
            else:  # step_up or tax_free -> full value, no income tax to heirs
                tax = 0.0
                to_heirs_gross += gross
                to_heirs_net += gross
            assets.append(LegacyAssetResult(
                name=x.name, asset_class=x.asset_class,
                transfer_character=char, beneficiary=dest,
                gross=gross, tax=tax, net=gross - tax,
                # charitable bequests qualify for the estate-tax charitable
                # deduction (IRC §2055) — flagged for the estate-tax phase
                estate_deductible=(dest == Beneficiary.charity.value)))
        # debts reduce what heirs ultimately receive
        to_heirs_net -= last.total_liabilities
        # gifting totals are accumulated in today's dollars (track_gifts);
        # express them here in end-of-plan nominal terms, consistent with the
        # other LegacyResult figures (metrics deflate by the final year).
        legacy = LegacyResult(
            at_death_year=last.year, assets=assets,
            to_heirs_gross=to_heirs_gross, to_heirs_net=to_heirs_net,
            to_charity=to_charity, ird_tax=ird_tax,
            gifts_lifetime=getattr(self, "gifts_lifetime_real", 0.0)
            * self.infl(last.year),
            exemption_used=getattr(self, "exemption_used_real", 0.0)
            * self.infl(last.year))
        return to_heirs_net, legacy

    def annual_gifts(self, year: int) -> float:
        """Lifetime gifts out of the portfolio this year (today's $ * inflation),
        per the household gifting schedule. The hook feeds the retirement
        spending need, so gifts are modeled in retirement years; the schedule's
        ages key off the primary person (None => from household retirement,
        through the survivor's last year)."""
        a = self.a
        if a.annual_gifting <= 0:
            return 0.0
        age = self.age(0, year)  # notional primary age; valid past their death
        if a.gifting_start_age is not None and age < a.gifting_start_age:
            return 0.0
        if a.gifting_end_age is not None and age > a.gifting_end_age:
            return 0.0
        return a.annual_gifting * self.infl(year)

    def track_gifts(self, year: int, gifts: float) -> None:
        """Accumulate lifetime-gifting totals (in today's dollars): the gifts
        themselves, and the portion beyond the annual exclusions that consumes
        the unified lifetime exemption. The exclusion shelters (indexed)
        $19,000 per donee per LIVING donor (IRC §2503(b); a couple gift-splits
        under §2513); only the excess is a taxable gift charged against the
        §2010 exemption. No gift tax is modeled — the plan warns instead if
        the exemption is exhausted."""
        if gifts <= 0:
            return
        infl = self.infl(year)
        donors = sum(1 for i in range(len(self.persons)) if self.alive(i, year))
        shelter = C.GIFT_ANNUAL_EXCLUSION * infl * self.a.gift_recipients * donors
        self.gifts_lifetime_real = getattr(self, "gifts_lifetime_real", 0.0) \
            + gifts / infl
        self.exemption_used_real = getattr(self, "exemption_used_real", 0.0) \
            + max(0.0, gifts - shelter) / infl
        # the §2010 exemption is indexed, so in today's dollars it stays at the
        # 2026 base — compare real use against 15M per (original) person
        exemption_real = C.GIFT_LIFETIME_EXEMPTION * len(self.persons)
        if self.exemption_used_real > exemption_real:
            msg = ("Lifetime gifts beyond the annual exclusions exceed the "
                   "unified lifetime gift/estate exemption "
                   f"(${C.GIFT_LIFETIME_EXEMPTION:,.0f} per person, IRC §2010) — "
                   "gift tax would be owed on the excess, which this plan does "
                   "NOT model. Consider more recipients or smaller annual gifts.")
            if msg not in self.warnings:
                self.warnings.append(msg)

    def prepare_insurance(self, year: int) -> None:
        """Process whole-life policies for the year, BEFORE the phase step so
        the results are stable across the tax fixed point. Accrues premium basis
        and handles surrenders. Sets per-year scratch:
          self._ins_premium       -> level premium due (funded from the waterfall
                                      in retirement; assumed wage-covered pre-ret).
          self._ins_surrender_gain -> ordinary income from any surrender (§72(e)).
        Death benefits are handled in the run() death block (mid-plan) and in
        settle_estate (terminal)."""
        self._ins_premium = 0.0
        self._ins_surrender_gain = 0.0
        for p in self.policies:
            if not p.active or not self.alive(p.owner, year):
                continue
            age = self.age(p.owner, year)
            # surrender: pay cash value into the portfolio; gain over total
            # premiums paid is ordinary income (IRC §72(e)).
            if p.spec.surrender_at_age is not None and age >= p.spec.surrender_at_age:
                self._ins_surrender_gain += max(0.0, p.cash_value - p.basis)
                tgt = self.surplus_account()
                tgt.balance += p.cash_value
                tgt.contribution += p.cash_value
                if tgt.spec.type == AccountType.taxable:
                    tgt.basis += p.cash_value  # after-tax proceeds: no future gain
                p.active = False
                continue
            # level premium until the policy is paid up (basis accrues either way)
            if p.spec.paid_up_age is None or age < p.spec.paid_up_age:
                p.basis += p.spec.annual_premium
                self._ins_premium += p.spec.annual_premium

    def prepare_annuities(self, year: int) -> None:
        """Process deferred annuities for the year, BEFORE the phase step so the
        payout is available as income. Tax-deferred growth while accumulating;
        from annuitize_at_age a level period-certain payout, each payment split
        by the exclusion ratio (basis/balance at annuitization): excluded =
        basis/payout_years is tax-free, the rest is ordinary income (IRC §72(b)).
        Sets self._annuity_payout (cash) and self._annuity_taxable (ordinary)."""
        self._annuity_payout = 0.0
        self._annuity_taxable = 0.0
        self._annuity_purchase = 0.0
        for a in self.annuities:
            a.start_balance = a.balance
            a.growth = 0.0
            a.payout = 0.0
            a.contribution = 0.0
            if not self.alive(a.owner, year):
                continue
            age = self.age(a.owner, year)
            # planned future purchase: fund a lump sum from the portfolio (the
            # outflow is added to this year's need / waterfall draw) and start
            # the contract at that value with a full after-tax basis.
            if not a.purchased and age >= a.spec.purchase_age:
                a.balance = a.spec.purchase_amount
                a.basis = a.spec.purchase_amount
                a.contribution = a.spec.purchase_amount
                a.active = True
                a.purchased = True
                self._annuity_purchase += a.spec.purchase_amount
            if not a.active:
                continue
            if not a.annuitized:
                # accumulate tax-deferred
                a.growth = a.balance * a.rate
                a.balance += a.growth
                if age >= a.spec.annuitize_at_age:
                    n = a.spec.payout_years
                    a.payment = a.balance / n        # level period-certain payout
                    a.excluded = a.basis / n         # exclusion ratio = basis/balance
                    a.payout_left = n
                    a.annuitized = True
                else:
                    continue  # still accumulating
            # annuitized (possibly as of this year): pay the level amount
            if a.payout_left > 0:
                pay = min(a.payment, a.balance)
                a.balance -= pay
                taxable = max(0.0, pay - a.excluded)
                a.basis = max(0.0, a.basis - a.excluded)
                a.payout = pay
                self._annuity_payout += pay
                self._annuity_taxable += taxable
                a.payout_left -= 1
                if a.payout_left <= 0:
                    a.balance = 0.0
                    a.basis = 0.0
                    a.active = False

    def prepare_private(self, year: int) -> None:
        """Process private holdings for the year, BEFORE the phase step so the
        results are stable across the tax fixed point. The value grows at the
        assumed rate; a level K-1 cash distribution is paid out of that growth
        (taxed in full as ordinary income or qualified dividends per the
        holding's distribution_kind). Divestiture is EITHER a one-time
        liquidity event at sale_age (sells the entire holding) OR a phased
        sale from divest_start_age (a fixed % of the ORIGINAL value sold each
        year, pro-rating basis) — mutually exclusive by construction (model
        validator). Either way the realized gain over cost basis is a
        long-term capital gain (IRC §1(h)). Sets per-year scratch:
        _priv_distribution (cash, split into _priv_dist_ordinary /
        _priv_dist_qualified) and _priv_sale_gain (LTCG)."""
        self._priv_distribution = 0.0
        self._priv_dist_ordinary = 0.0
        self._priv_dist_qualified = 0.0
        self._priv_sale_gain = 0.0
        for h in self.holdings:
            h.start_balance = h.value
            h.growth = 0.0
            h.distribution = 0.0
            h.sale_proceeds = 0.0
            if not h.active or not self.alive(h.owner, year):
                continue
            age = self.age(h.owner, year)
            # one-time liquidity event: sell everything at the current value;
            # proceeds join the portfolio (after-tax — LTCG taxed separately).
            if h.spec.sale_age is not None and age >= h.spec.sale_age:
                self._priv_sale_gain += max(0.0, h.value - h.basis)
                h.sale_proceeds = h.value
                tgt = self.surplus_account()
                tgt.balance += h.value
                tgt.contribution += h.value
                if tgt.spec.type == AccountType.taxable:
                    tgt.basis += h.value
                h.value = 0.0
                h.active = False
                continue
            # phased divestiture: sell a fixed % of the ORIGINAL value each
            # year (basis reduced pro-rata to the fraction of the CURRENT
            # value sold), before this year's growth/distribution.
            if h.spec.divest_start_age is not None and age >= h.spec.divest_start_age \
                    and h.value > 0:
                target = h.original_value * h.spec.annual_divest_pct
                amount = min(target, h.value)
                frac = amount / h.value
                basis_sold = h.basis * frac
                self._priv_sale_gain += max(0.0, amount - basis_sold)
                h.value -= amount
                h.basis -= basis_sold
                h.sale_proceeds = amount
                tgt = self.surplus_account()
                tgt.balance += amount
                tgt.contribution += amount
                if tgt.spec.type == AccountType.taxable:
                    tgt.basis += amount
                if h.value <= 0.01:
                    h.value = 0.0
                    h.active = False
                    continue
            # grow, then pay the K-1 distribution out of the (grown) value
            h.growth = h.value * h.rate
            d = min(h.spec.annual_distribution, h.value + h.growth)
            h.value = h.value + h.growth - d
            h.distribution = d
            self._priv_distribution += d
            if h.spec.distribution_kind == DistributionKind.qualified:
                self._priv_dist_qualified += d
            else:
                self._priv_dist_ordinary += d

    def prepare_real_estate(self, year: int) -> None:
        """Process properties for the year, BEFORE the phase step so the
        results are stable across the tax fixed point. The value appreciates
        at the assumed rate. A sale at sale_age happens at the start-of-year
        value: the gain over basis — reduced by the IRC §121 exclusion for a
        primary residence ($250k/$500k by filing status, not indexed) — is a
        long-term capital gain; the linked mortgage's CURRENT balance is paid
        off from the proceeds and the net cash joins the portfolio. Sets
        self._re_sale_gain (taxable LTCG this year)."""
        self._re_sale_gain = 0.0
        for r in self.props:
            r.start_balance = r.value
            r.growth = 0.0
            r.sale_proceeds = 0.0
            if not r.active or not self.alive(r.owner, year):
                continue
            age = self.age(r.owner, year)
            if r.spec.sale_age is not None and age >= r.spec.sale_age:
                gain = max(0.0, r.value - r.basis)
                if r.spec.is_primary:
                    gain = max(0.0, gain
                               - C.SEC121_EXCLUSION[self.filing_status(year)])
                self._re_sale_gain += gain
                r.sale_proceeds = r.value
                # pay off the linked mortgage from the proceeds (its current
                # balance; the debt already lives in total_liabilities, so
                # zeroing it here is the only adjustment — no double count)
                payoff = 0.0
                li = r.spec.liability_index
                if li is not None and li < len(self.liabilities):
                    l = self.liabilities[li]
                    if self._liab_active(l, year) and l["balance"] > 0:
                        payoff = min(l["balance"], r.value)
                        l["balance"] -= payoff
                net = r.value - payoff
                tgt = self.surplus_account()
                tgt.balance += net
                tgt.contribution += net
                if tgt.spec.type == AccountType.taxable:
                    tgt.basis += net  # after-tax proceeds: no future gain
                r.value = 0.0
                r.active = False
                continue
            r.growth = r.value * r.spec.appreciation
            r.value += r.growth

    # -------------------------------------------------------- accumulation yr
    def accumulation_year_step(self, year: int, status: str,
                               home_purchase: float = 0.0) -> YearRow:
        row = YearRow(year=year, phase="accumulation", filing_status=status,
                      ages=[self.age(i, year) if self.alive(i, year) else None
                            for i in range(len(self.persons))], accounts=[])
        traditional_deferral = 0.0
        for acct in self.accounts:
            p = self.persons[acct.owner]
            if self.alive(acct.owner, year) and self.age(acct.owner, year) < p.retirement_age:
                c = acct.spec.annual_contribution
                if self.a.contributions_grow_with_inflation:
                    c *= self.infl(year)
                if c > 0:
                    acct.contribution = c
                    acct.balance += c
                    if acct.spec.type == AccountType.taxable:
                        acct.basis += c
                    if acct.spec.type == AccountType.tax_deferred:
                        traditional_deferral += c

        # forced RMDs before household retirement (taxed below)
        scratch = YearScratch()
        rmds = self.compute_rmds(year)
        for i, amt in enumerate(rmds):
            remaining = amt
            for acct in self.accounts:
                if acct.spec.type == AccountType.tax_deferred and acct.owner == i \
                        and remaining > 0:
                    remaining -= self.withdraw_from(acct, remaining, scratch, year)
        rmd_total = sum(rmds)
        if rmd_total > 0:
            row.flags = ["RMD required before household retirement"]
        benefits = self.ss_benefits(year)
        other_taxable, other_nontaxable = self.other_income(year)

        if self.has_salary:
            # Real income tax on wages + pre-retirement inflows, with the
            # Traditional deduction valued at the true marginal bracket and its
            # tax saving reinvested ("invest the tax savings").
            self._accumulation_taxes(year, status, row, rmd_total, benefits,
                                     other_taxable, other_nontaxable,
                                     traditional_deferral)
        else:
            # Legacy flat-rate path (wages not modeled): pre-retirement inflows
            # taxed at the flat rate and reinvested net.
            inflows = rmd_total + sum(benefits) + other_taxable
            net_inflow = inflows * (1 - self.a.pre_retirement_tax_rate) + other_nontaxable
            row.total_tax = inflows * self.a.pre_retirement_tax_rate
            self._reinvest(net_inflow, row)

        row.ss_benefit = benefits
        row.ss_total = sum(benefits)
        row.other_income = other_taxable + other_nontaxable
        row.rmd_total = rmd_total
        row.rmd_by_person = rmds

        # a home purchase this year: fund the down payment from the portfolio
        # (cash -> taxable -> ... via the waterfall). The down payment does NOT
        # reduce contributions — that year's full contributions are made above,
        # and the down payment is drawn from accumulated assets. Penalties for
        # raiding tax-advantaged accounts are folded into tax so they aren't free.
        if home_purchase > 0:
            adv = (AccountType.tax_deferred, AccountType.roth, AccountType.hsa)
            adv_before = sum(scratch.withdrawals_by_type.get(t.value, 0.0) for t in adv)
            pen_before = scratch.penalties
            got = self.waterfall_withdraw(home_purchase, scratch, year)
            row.home_purchase = home_purchase
            row.total_tax += scratch.penalties
            if scratch.flags:
                row.flags = list(row.flags) + scratch.flags
            if got + 1 < home_purchase:
                row.shortfall = home_purchase - got
                row.flags = list(row.flags) + [
                    "Portfolio could not fully fund the home down payment"]
            # If cash + taxable couldn't cover the down payment, the waterfall
            # raided tax-advantaged retirement accounts (a pre-59.5 draw also
            # incurs a 10% penalty). Surface that as an actionable plan-level
            # warning rather than only a quiet per-year row flag.
            raided = sum(scratch.withdrawals_by_type.get(t.value, 0.0)
                         for t in adv) - adv_before
            if raided > 1:
                penalized = scratch.penalties - pen_before > 1
                msg = (
                    f"The home down payment in {year} exceeds your projected cash "
                    "and taxable savings, so the model funds the rest from "
                    "tax-advantaged retirement accounts"
                    + (" (incurring a 10% early-withdrawal penalty before age 59.5)"
                       if penalized else "")
                    + ". Your retirement contributions are not reduced to pay for the "
                    "purchase — to model saving toward it instead, hold more in "
                    "taxable/cash by then, or lower your contributions in the years "
                    "before the purchase.")
                if msg not in self.warnings:
                    self.warnings.append(msg)

        # a planned annuity purchase before household retirement: fund the lump
        # sum from the portfolio (same waterfall as a home down payment).
        if self._annuity_purchase > 0:
            pen_before = scratch.penalties
            got = self.waterfall_withdraw(self._annuity_purchase, scratch, year)
            row.total_tax += scratch.penalties - pen_before
            if got + 1 < self._annuity_purchase:
                row.shortfall += self._annuity_purchase - got

        self._check_contribution_limits(year, row)
        row.withdrawals_by_type = scratch.withdrawals_by_type
        return row

    def _accumulation_taxes(self, year: int, status: str, row: YearRow,
                            rmd_total: float, benefits: list[float],
                            other_taxable: float, other_nontaxable: float,
                            traditional_deferral: float) -> None:
        """Working-year federal/state income tax using wages as the marginal
        context. Traditional (tax-deferred) deferrals are deductible and the
        resulting tax saving is reinvested. Dividends/cash interest stay on the
        separate annual drag (applied in run()), so they are not double-counted
        here. Wage tax is conceptually paid from wages and does not draw down
        the portfolio; only inflows are reinvested net of their marginal tax."""
        a = self.a
        salaries = sum(
            self.persons[i].salary * self.infl(year)
            for i in range(len(self.persons))
            if self.alive(i, year) and self.age(i, year) < self.persons[i].retirement_age)
        ages65 = sum(1 for i in range(len(self.persons))
                     if self.alive(i, year) and self.age(i, year) >= C.MEDICARE_AGE)
        ss_total = sum(benefits)

        def _tax(ordinary: float):
            return compute_taxes(TaxYearInput(
                year=year, filing_status=status, inflation=a.inflation,
                ordinary_income=max(0.0, ordinary), ss_benefits=ss_total,
                qualified_dividends=0.0, realized_ltcg=0.0, interest=0.0,
                ages_65_plus=ages65, state_rate=a.state_tax_rate))

        base_ordinary = salaries + rmd_total + other_taxable
        tax_with = _tax(base_ordinary - traditional_deferral)   # actual tax owed
        tax_without_deferral = _tax(base_ordinary)              # if not deducted
        tax_saving = max(0.0, tax_without_deferral.total - tax_with.total)
        # marginal tax caused by the inflows, so they reinvest net of their tax
        tax_salary_only = _tax(salaries - traditional_deferral)
        tax_on_inflows = max(0.0, tax_with.total - tax_salary_only.total)

        row.taxable_ss = tax_with.taxable_ss
        row.agi = tax_with.agi
        row.magi = tax_with.magi
        row.deductions = tax_with.deductions
        row.taxable_income = tax_with.taxable_income
        row.federal_tax = tax_with.federal_tax
        row.ltcg_tax = tax_with.ltcg_tax
        row.niit = tax_with.niit
        row.state_tax = tax_with.state_tax
        row.marginal_rate = tax_with.marginal_rate
        row.effective_rate = (tax_with.total / tax_with.agi) if tax_with.agi > 0 else 0.0
        row.total_tax = tax_with.total

        net_inflow = (rmd_total + ss_total + other_taxable) - tax_on_inflows \
            + other_nontaxable
        self._reinvest(net_inflow, row)
        self._reinvest(tax_saving, row)

    def _check_contribution_limits(self, year: int, row: YearRow) -> None:
        """Vehicle-aware, per-person contribution-limit and backdoor-Roth
        checks. Over-limit contributions are flagged (not silently capped, so
        results stay reproducible from inputs). Roth IRA contributions above the
        MAGI phase-out are allowed but flagged as requiring a backdoor Roth."""
        scale = self.infl(year)
        magi = row.magi if row.magi > 0 else self.pre_retirement_magi() * scale
        roth_phaseout_end = C.ROTH_IRA_PHASEOUT[row.filing_status][1] * scale
        new_flags: list[str] = []
        for i, p in enumerate(self.persons):
            if not self.alive(i, year) or self.age(i, year) >= p.retirement_age:
                continue
            age = self.age(i, year)
            emp = ira = roth_ira = 0.0
            for acct in self.accounts:
                if acct.owner != i or acct.contribution <= 0:
                    continue
                if acct.spec.type not in (AccountType.tax_deferred, AccountType.roth):
                    continue
                if acct.spec.limit_vehicle() == AccountVehicle.employer:
                    emp += acct.contribution
                else:
                    ira += acct.contribution
                    if acct.spec.type == AccountType.roth:
                        roth_ira += acct.contribution
            if emp > C.elective_deferral_limit(age) * scale + 1:
                new_flags.append(
                    f"{p.name}: employer-plan (401(k)/403(b)) contributions exceed "
                    "the IRS elective-deferral limit — check each account's Vehicle "
                    "setting (IRAs should be set to 'IRA').")
            if ira > C.ira_contribution_limit(age) * scale + 1:
                new_flags.append(
                    f"{p.name}: IRA contributions exceed the IRS IRA contribution limit.")
            if roth_ira > 0 and magi > roth_phaseout_end:
                new_flags.append(
                    f"{p.name}: Roth IRA contribution requires a backdoor Roth "
                    "(household MAGI exceeds the direct Roth IRA income limit).")
        if new_flags:
            row.flags = sorted(set(list(row.flags) + new_flags))
            for f in new_flags:
                if f not in self.warnings:
                    self.warnings.append(f)

    # ---------------------------------------------------------- retirement yr
    def retirement_year_step(self, year: int, status: str, dividends: float,
                             interest: float, prev_tax: float,
                             home_purchase: float = 0.0) -> tuple[YearRow, float]:
        a = self.a
        scale = self.infl(year)
        ages = [self.age(i, year) if self.alive(i, year) else None
                for i in range(len(self.persons))]
        n_alive = sum(1 for x in ages if x is not None)
        ages65 = sum(1 for x in ages if x is not None and x >= 65)

        spend_goal = self.plan.annual_spending * scale
        benefits = self.ss_benefits(year)
        ss_total = sum(benefits)
        other_taxable, other_nontaxable = self.other_income(year)
        rmds = self.compute_rmds(year)
        rmd_total = sum(rmds)

        # Medicare Part B + IRMAA (2-year lookback MAGI, known by now)
        tier = irmaa_tier(self.lookback_magi(year), status, year, a.inflation)
        medicare_premiums = irmaa_total = hsa_eligible_medicare = 0.0
        n_under65 = 0
        for i in range(len(self.persons)):
            if ages[i] is None:
                continue
            if ages[i] >= C.MEDICARE_AGE:
                std, surcharge = medicare_part_b_annual(tier, year, a.healthcare_inflation)
                medicare_premiums += std + surcharge \
                    + a.medicare_other_annual_per_person * self.hc_infl(year)
                # HSA-qualified: Part B only; Medigap/dental excluded (IRS Pub. 969)
                hsa_eligible_medicare += std + surcharge
                irmaa_total += surcharge
            else:
                n_under65 += 1
        aca_benchmark = a.aca_benchmark_monthly_per_person * 12 * n_under65 * self.hc_infl(year)
        pre65_oop = a.pre65_oop_annual_per_person * n_under65 * self.hc_infl(year)
        # HSA pays Part B + pre-65 OOP tax-free; ACA premiums and Medigap excluded (Pub. 969)
        hsa_eligible_costs = hsa_eligible_medicare + pre65_oop

        debt_payments = sum(min(l["payment"], l["balance"] * (1 + l["rate"]))
                            for l in self.liabilities
                            if l["balance"] > 0 and self._liab_active(l, year))

        snapshot = [(x.balance, x.basis) for x in self.accounts]
        tax_guess, subsidy_guess = prev_tax, 0.0
        last_conversion = 0.0
        last_ord_taxable = 0.0
        scratch = YearScratch()
        tax_res = None
        healthcare_net = 0.0
        healthcare_gross = 0.0
        converged = False

        for it in range(40):
            for (b, bs), acct in zip(snapshot, self.accounts):
                acct.balance, acct.basis = b, bs
                # preserve pre-step state across iterations: start_balance, and
                # any contribution deposited by the prepare_* steps before this
                # loop (a property/holding sale, an insurance surrender) — the
                # snapshot balance already contains those dollars, so wiping
                # the flow would break the start+flows=end audit identity.
                cur_start = acct.start_balance
                cur_contrib = acct.contribution
                acct.reset_flows()
                acct.start_balance = cur_start
                acct.contribution = cur_contrib
            scratch = YearScratch()

            # 0) qualified charitable distributions (IRC §408(d)(8)): direct
            # IRA-to-charity transfers by owners 70½+ (modeled as the age-71
            # year). Excluded from AGI — the draw reduces the balance and is
            # recorded on the account, but never enters ordinary income or the
            # withdrawal resources (the money goes to charity, not spending).
            # Capped per person at the indexed statutory limit.
            qcd_by_person = [0.0] * len(self.persons)
            qcd_target = a.annual_qcd * scale
            if qcd_target > 0:
                cap = C.QCD_ANNUAL_LIMIT * scale
                for i in range(len(self.persons)):
                    if ages[i] is None or ages[i] < C.QCD_START_AGE:
                        continue
                    want = min(qcd_target - sum(qcd_by_person), cap)
                    for acct in self.accounts:
                        if want <= 0.005:
                            break
                        if acct.spec.type == AccountType.tax_deferred \
                                and acct.owner == i:
                            take = min(acct.balance, want)
                            acct.balance -= take
                            acct.withdrawal += take
                            qcd_by_person[i] += take
                            want -= take
            qcd_total = sum(qcd_by_person)

            # 1) mandatory RMDs. A QCD counts toward the owner's RMD for the
            # year (§408(d)(8)), so only the excess is forced out as taxable.
            for i, amt in enumerate(rmds):
                remaining = max(0.0, amt - qcd_by_person[i])
                for acct in self.accounts:
                    if acct.spec.type == AccountType.tax_deferred and acct.owner == i \
                            and remaining > 0:
                        remaining -= self.withdraw_from(acct, remaining, scratch, year)

            # 2) HSA pays qualified medical first (tax-free)
            for acct in self.accounts:
                need_med = hsa_eligible_costs - scratch.hsa_medical
                if acct.spec.type == AccountType.hsa and need_med > 0.005:
                    take = min(acct.balance, need_med)
                    acct.balance -= take
                    acct.withdrawal += take
                    scratch.hsa_medical += take

            # healthcare_gross is the TRUE cost of care (reported to the user);
            # healthcare_net additionally nets out what the HSA already paid
            # tax-free, and is used ONLY internally to size the waterfall draw
            # so those dollars aren't funded twice.
            healthcare_gross = medicare_premiums + pre65_oop \
                + max(0.0, aca_benchmark - subsidy_guess)
            healthcare_net = healthcare_gross - scratch.hsa_medical

            # 3) Roth conversion to fill the target bracket (taxes paid
            #    from the waterfall, not from the converted amount)
            td_available = sum(x.balance for x in self.accounts
                               if x.spec.type == AccountType.tax_deferred)
            conv = self.conversion_target(
                year, max(0.0, last_ord_taxable - last_conversion), td_available)
            if conv > 0.5:
                remaining = conv
                for acct in self.accounts:
                    if acct.spec.type == AccountType.tax_deferred and remaining > 0:
                        take = min(acct.balance, remaining)
                        acct.balance -= take
                        acct.conv_out += take
                        remaining -= take
                converted = conv - remaining
                roth_tgt = next((x for x in self.accounts
                                 if x.spec.type == AccountType.roth), None)
                if roth_tgt is None:
                    roth_tgt = SimAccount(Account(
                        name="Roth IRA (from conversions)", type=AccountType.roth,
                        owner=0, balance=0))
                    self.accounts.append(roth_tgt)
                    snapshot.append((0.0, 0.0))
                roth_tgt.balance += converted
                roth_tgt.conv_in += converted
                scratch.roth_conversion = converted

            # 4) cover remaining need from the waterfall
            need = (spend_goal + debt_payments + home_purchase + healthcare_net
                    + tax_guess + self.annual_gifts(year) + self._ins_premium
                    + self._annuity_purchase)
            # only the RMD portion NOT satisfied by QCDs is spendable cash
            rmd_spendable = sum(max(0.0, rmds[i] - qcd_by_person[i])
                                for i in range(len(self.persons)))
            resources = (ss_total + other_taxable + other_nontaxable + rmd_spendable
                         + self._annuity_payout + self._priv_distribution)
            gap = need + scratch.penalties - resources
            if gap > 0:
                got = self.waterfall_withdraw(gap, scratch, year)
                scratch.shortfall = max(0.0, gap - got)

            # 5) taxes on the resulting income picture. A policy surrender adds
            # ordinary income (cash value over premiums, §72(e)); an annuity
            # payout's gain portion is ordinary via the exclusion ratio (§72(b)).
            td_withdrawn = scratch.withdrawals_by_type.get("tax_deferred", 0.0)
            ordinary = (td_withdrawn + scratch.roth_conversion
                        + scratch.hsa_nonmedical + other_taxable + interest
                        + self._ins_surrender_gain + self._annuity_taxable
                        + self._priv_dist_ordinary)
            sale_gain = self._priv_sale_gain + self._re_sale_gain
            tax_res = compute_taxes(TaxYearInput(
                year=year, filing_status=status, inflation=a.inflation,
                ordinary_income=ordinary, ss_benefits=ss_total,
                qualified_dividends=dividends + self._priv_dist_qualified,
                realized_ltcg=scratch.realized_gains + sale_gain,
                interest=interest, ages_65_plus=ages65, state_rate=a.state_tax_rate))
            pref = min(dividends + self._priv_dist_qualified
                       + max(0.0, scratch.realized_gains + sale_gain),
                       tax_res.taxable_income)
            last_ord_taxable = tax_res.taxable_income - pref
            last_conversion = scratch.roth_conversion

            new_subsidy = 0.0
            if aca_benchmark > 0:
                new_subsidy = aca_subsidy(tax_res.aca_magi, n_alive,
                                          aca_benchmark, year, a.inflation)
            if abs(tax_res.total - tax_guess) < 0.5 and \
                    abs(new_subsidy - subsidy_guess) < 0.5 and it > 0:
                tax_guess, subsidy_guess = tax_res.total, new_subsidy
                converged = True
                break
            tax_guess, subsidy_guess = tax_res.total, new_subsidy

        if not converged:
            scratch.flags.append("tax/ACA fixed point did not fully converge; last iterate used")

        # 6) any surplus income is reinvested. NOTE: RMDs are already inside
        # withdrawals_by_type (they flow through withdraw_from in step 1), so
        # rmd_total must NOT be added again here — doing so double-counts forced
        # distributions and mints phantom surplus in high-RMD years.
        need = (spend_goal + debt_payments + home_purchase + healthcare_net
                + tax_guess + scratch.penalties + self.annual_gifts(year)
                + self._ins_premium + self._annuity_purchase)
        resources = (ss_total + other_taxable + other_nontaxable
                     + self._annuity_payout + self._priv_distribution
                     + sum(scratch.withdrawals_by_type.values()))
        surplus = max(0.0, resources - need - scratch.shortfall)
        if surplus > 0.005 and scratch.shortfall <= 1:
            tgt = self.surplus_account()
            tgt.balance += surplus
            tgt.contribution += surplus
            if tgt.spec.type == AccountType.taxable:
                tgt.basis += surplus
        else:
            surplus = 0.0

        # Reporting-only view of withdrawals: the HSA's tax-free medical payment
        # (scratch.hsa_medical) funded part of healthcare_gross directly (step 2,
        # before the waterfall) and so is invisible in scratch.withdrawals_by_type
        # (which only tracks waterfall-routed draws). Surface it here as a copy —
        # NEVER by mutating scratch.withdrawals_by_type itself, since the surplus
        # calc above already consumed it for `resources`; mutating it there would
        # double-count those dollars into phantom surplus.
        report_wd = dict(scratch.withdrawals_by_type)
        report_wd["hsa"] = report_wd.get("hsa", 0.0) + scratch.hsa_medical

        row = YearRow(
            year=year, phase="retirement", filing_status=status, ages=ages, accounts=[],
            spend_goal=spend_goal, debt_payments=debt_payments,
            home_purchase=home_purchase,
            healthcare_cost=healthcare_gross, aca_subsidy=subsidy_guess,
            irmaa_surcharge=irmaa_total,
            ss_benefit=benefits, ss_total=ss_total,
            other_income=other_taxable + other_nontaxable,
            rmd_total=rmd_total, rmd_by_person=rmds,
            withdrawals_by_type=report_wd,
            roth_conversion=scratch.roth_conversion,
            surplus_reinvested=surplus, shortfall=scratch.shortfall,
            realized_gains=scratch.realized_gains + self._priv_sale_gain
            + self._re_sale_gain,
            taxable_ss=tax_res.taxable_ss, agi=tax_res.agi, magi=tax_res.magi,
            deductions=tax_res.deductions, taxable_income=tax_res.taxable_income,
            federal_tax=tax_res.federal_tax, ltcg_tax=tax_res.ltcg_tax,
            niit=tax_res.niit, state_tax=tax_res.state_tax,
            penalties=scratch.penalties,
            total_tax=tax_res.total + scratch.penalties,
            marginal_rate=tax_res.marginal_rate,
            effective_rate=(tax_res.total / tax_res.agi) if tax_res.agi > 0 else 0.0,
            flags=sorted(set(scratch.flags)),
            gifts_made=self.annual_gifts(year),
            qcd_amount=qcd_total,
        )
        return row, tax_guess
