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
                      Beneficiary, ConversionStrategy, LegacyAssetResult,
                      LegacyResult, Metrics, PlanInput, TransferCharacter,
                      YearRow)
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

            # spousal rollover: survivor inherits the deceased's accounts
            for i in range(len(self.persons)):
                if not self.alive(i, year):
                    if len(self.persons) == 2 and self.alive(1 - i, year):
                        for acct in self.accounts:
                            if acct.owner == i:
                                acct.owner = 1 - i
                    if self.ss_level[i] > 0:
                        self.deceased_ss_level = max(self.deceased_ss_level,
                                                     self.ss_level[i])
                        self.ss_level[i] = 0.0

            for acct in self.accounts:
                acct.reset_flows()

            retired = year >= self.retirement_year
            status = self.filing_status(year)
            self.update_ss_levels(year)
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
                beneficiary=Beneficiary.heirs.value,
            ) for x in self.accounts]
            row.total_assets = sum(x.balance for x in self.accounts)
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
            gross = x.end_balance
            if dest == Beneficiary.charity.value:
                tax = 0.0
                to_charity += gross
            elif char == TransferCharacter.ird.value:
                tax = gross * heir
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
                gross=gross, tax=tax, net=gross - tax))
        # debts reduce what heirs ultimately receive
        to_heirs_net -= last.total_liabilities
        legacy = LegacyResult(
            at_death_year=last.year, assets=assets,
            to_heirs_gross=to_heirs_gross, to_heirs_net=to_heirs_net,
            to_charity=to_charity, ird_tax=ird_tax,
            gifts_lifetime=getattr(self, "gifts_lifetime", 0.0),
            exemption_used=getattr(self, "exemption_used", 0.0))
        return to_heirs_net, legacy

    def annual_gifts(self, year: int) -> float:
        """Lifetime gifts out of the portfolio this year (today's $ * inflation).
        Phase-1 hook: returns 0 until Phase 8 (lifetime gifting) populates it."""
        return 0.0

    def qcd_total(self, year: int) -> float:
        """Qualified charitable distributions from tax-deferred accounts this
        year (IRC §408(d)(8)). Phase-1 hook: returns 0 until Phase 7."""
        return 0.0

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
        converged = False

        for it in range(40):
            for (b, bs), acct in zip(snapshot, self.accounts):
                acct.balance, acct.basis = b, bs
                cur_start = acct.start_balance
                acct.reset_flows()
                acct.start_balance = cur_start
            scratch = YearScratch()

            # 1) mandatory RMDs
            for i, amt in enumerate(rmds):
                remaining = amt
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

            healthcare_net = medicare_premiums + pre65_oop \
                + max(0.0, aca_benchmark - subsidy_guess) - scratch.hsa_medical

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
                    + tax_guess + self.annual_gifts(year))
            resources = ss_total + other_taxable + other_nontaxable + rmd_total
            gap = need + scratch.penalties - resources
            if gap > 0:
                got = self.waterfall_withdraw(gap, scratch, year)
                scratch.shortfall = max(0.0, gap - got)

            # 5) taxes on the resulting income picture
            td_withdrawn = scratch.withdrawals_by_type.get("tax_deferred", 0.0)
            ordinary = (td_withdrawn + scratch.roth_conversion
                        + scratch.hsa_nonmedical + other_taxable + interest)
            tax_res = compute_taxes(TaxYearInput(
                year=year, filing_status=status, inflation=a.inflation,
                ordinary_income=ordinary, ss_benefits=ss_total,
                qualified_dividends=dividends, realized_ltcg=scratch.realized_gains,
                interest=interest, ages_65_plus=ages65, state_rate=a.state_tax_rate))
            pref = min(dividends + max(0.0, scratch.realized_gains),
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
                + tax_guess + scratch.penalties + self.annual_gifts(year))
        resources = (ss_total + other_taxable + other_nontaxable
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

        row = YearRow(
            year=year, phase="retirement", filing_status=status, ages=ages, accounts=[],
            spend_goal=spend_goal, debt_payments=debt_payments,
            home_purchase=home_purchase,
            healthcare_cost=healthcare_net, aca_subsidy=subsidy_guess,
            irmaa_surcharge=irmaa_total,
            ss_benefit=benefits, ss_total=ss_total,
            other_income=other_taxable + other_nontaxable,
            rmd_total=rmd_total, rmd_by_person=rmds,
            withdrawals_by_type=scratch.withdrawals_by_type,
            roth_conversion=scratch.roth_conversion,
            surplus_reinvested=surplus, shortfall=scratch.shortfall,
            realized_gains=scratch.realized_gains,
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
            qcd_amount=self.qcd_total(year),
        )
        return row, tax_guess
