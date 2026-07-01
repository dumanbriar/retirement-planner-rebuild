/**
 * TypeScript mirror of the backend API contract (backend/app/models.py).
 *
 * All monetary INPUTS are in today's dollars unless the field name says
 * otherwise. The engine works in nominal dollars and reports both.
 */

// ----------------------------- inputs --------------------------------------

export type AccountType = "tax_deferred" | "roth" | "taxable" | "hsa" | "cash";

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  tax_deferred: "Tax-deferred (401k/IRA)",
  roth: "Roth",
  taxable: "Taxable brokerage",
  hsa: "HSA",
  cash: "Cash / HYSA",
};

export const ACCOUNT_TYPE_SHORT: Record<AccountType, string> = {
  tax_deferred: "Tax-deferred",
  roth: "Roth",
  taxable: "Taxable",
  hsa: "HSA",
  cash: "Cash",
};

/** Contribution-limit regime for a tax-advantaged retirement account. Drives
 * which IRS limit applies and the backdoor-Roth check — NOT withdrawal tax. */
export type AccountVehicle = "employer" | "ira";

export const ACCOUNT_VEHICLE_LABELS: Record<AccountVehicle, string> = {
  employer: "Employer plan (401k/403b)",
  ira: "IRA",
};

/** Default expected returns by account type (mirrors DEFAULT_RETURNS). */
export const DEFAULT_RETURNS: Record<AccountType, number> = {
  tax_deferred: 0.06,
  roth: 0.06,
  taxable: 0.06,
  hsa: 0.05,
  cash: 0.04,
};

export interface Person {
  name: string;
  current_age: number; // 18..99
  retirement_age: number; // 30..80
  death_age: number; // 60..105
  /** Monthly SS benefit at full retirement age (PIA from an SSA statement), today's $. */
  ss_monthly_at_fra: number;
  ss_claim_age: number; // 62..70
  /** Gross annual earned income (today's $), 0 if not working. Provides the
   * marginal-bracket context for the Roth-vs-Traditional contribution decision. */
  salary: number;
}

export interface Account {
  name: string;
  type: AccountType;
  owner: number; // index into persons (0 or 1)
  balance: number;
  /** tax_deferred / roth only: which contribution limit applies. null => employer. */
  vehicle?: AccountVehicle | null;
  /** Taxable accounts only: cost basis today (null => defaults to balance). */
  cost_basis: number | null;
  annual_contribution: number;
  /** null => engine default for the account type. */
  expected_return: number | null; // -0.10..0.20
}

export interface Liability {
  name: string;
  balance: number;
  interest_rate: number; // 0..0.30
  annual_payment: number;
  /** Primary person's age when a future mortgage/home purchase begins; null => already active. */
  start_age?: number | null;
  /** One-time cash at purchase (down payment + closing), today's dollars. */
  down_payment?: number;
}

/** Pension, annuity, rental, part-time work in retirement, etc. */
export interface IncomeStream {
  name: string;
  owner: number;
  annual_amount: number; // today's dollars
  start_age: number; // 30..100
  end_age: number | null; // 30..110
  cola: boolean; // grows with inflation
  taxable: boolean; // taxed as ordinary income
  /** Two-person households: fraction (0..1) that continues to a surviving spouse. Default 0. */
  survivor_pct?: number;
}

/**
 * Whole / permanent life insurance with cash value. Amounts are LEVEL NOMINAL
 * figures (the policy's actual contractual values), NOT today's dollars.
 */
export interface InsurancePolicy {
  name: string;
  owner: number;
  annual_premium: number; // level nominal $/yr
  paid_up_age: number | null; // premiums stop at this age (null => for life)
  cash_value: number; // current surrender value, nominal
  cash_value_return: number; // assumed growth rate
  death_benefit: number; // face amount, level nominal
  premiums_paid_to_date: number; // basis for surrender gain
  surrender_at_age: number | null; // optional lapse
}

/** Non-qualified deferred annuity: tax-deferred accumulation then a period-certain payout. */
export interface Annuity {
  name: string;
  owner: number;
  balance: number; // accumulation value, nominal
  basis: number; // after-tax premiums paid (exclusion-ratio basis)
  accumulation_return: number; // assumed growth rate
  annuitize_at_age: number; // 50..90
  payout_years: number; // 1..40
  /** Planned future purchase: age to buy (null => already owned today). */
  purchase_age: number | null;
  /** Lump sum drawn from the portfolio at purchase_age (nominal). */
  purchase_amount: number;
}

/** How an asset is taxed when it passes to its beneficiary at death. */
export type TransferCharacter = "tax_free" | "step_up" | "ird";

export const TRANSFER_CHARACTER_LABELS: Record<TransferCharacter, string> = {
  tax_free: "Income-tax-free",
  step_up: "Stepped-up basis",
  ird: "Taxable to heirs (IRD)",
};

export type Beneficiary = "heirs" | "charity";

export type ConversionStrategy =
  | "none"
  | "fill_10"
  | "fill_12"
  | "fill_22"
  | "fill_24"
  | "custom"
  | "auto";

export const CONVERSION_STRATEGY_LABELS: Record<ConversionStrategy, string> = {
  auto: "Auto-optimize",
  none: "No conversions",
  fill_10: "Fill 10% bracket",
  fill_12: "Fill 12% bracket",
  fill_22: "Fill 22% bracket",
  fill_24: "Fill 24% bracket",
  custom: "Custom annual amount",
};

export interface Assumptions {
  inflation: number; // 0..0.10
  healthcare_inflation: number; // 0..0.12
  state_tax_rate: number; // 0..0.15
  /** Flat marginal rate used ONLY before retirement (dividend/interest drag). */
  pre_retirement_tax_rate: number; // 0..0.50
  /** Portion of taxable-account return paid out annually as qualified dividends. */
  taxable_dividend_yield: number; // 0..0.08
  /** Used to value remaining tax-deferred dollars after death. */
  heir_tax_rate: number; // 0..0.50
  contributions_grow_with_inflation: boolean;
  roth_conversion_strategy: ConversionStrategy;
  custom_conversion_amount: number;
  optimize_ss_claiming: boolean;
  /** Exhaustively compare per-person Traditional-vs-Roth contribution splits. */
  optimize_contribution_split: boolean;
  /** Pre-65 ACA modeling (estimates, clearly labeled). */
  aca_benchmark_monthly_per_person: number;
  pre65_oop_annual_per_person: number;
  /** 65+: Part D, Medigap/Advantage, dental, OOP (excl. Part B). */
  medicare_other_annual_per_person: number;
  /** Household MAGI in last two working years (IRMAA 2-yr lookback). null => engine estimate. */
  pre_retirement_magi: number | null;
}

export interface PlanInput {
  persons: Person[]; // 1..2
  accounts: Account[]; // >= 1
  liabilities: Liability[];
  income_streams: IncomeStream[];
  insurance_policies: InsurancePolicy[];
  annuities: Annuity[];
  annual_spending: number; // retirement spend goal, today's $
  assumptions: Assumptions;
}

// ----------------------------- outputs -------------------------------------

/** One account's audit trail for one year. */
export interface AccountYear {
  name: string;
  type: AccountType | null; // null for legacy assets (see asset_class)
  owner: number;
  start_balance: number;
  contribution: number;
  withdrawal: number;
  conversion_out: number; // tax-deferred -> roth
  conversion_in: number;
  growth: number;
  end_balance: number;
  cost_basis: number | null; // taxable accounts
  // legacy-asset flows (default 0 / "account" for ordinary accounts)
  premium?: number;
  distribution?: number;
  death_benefit_paid?: number;
  death_benefit?: number; // standing face amount (insurance terminal value)
  asset_class?: string; // account | insurance | annuity | private | realestate
  transfer_character?: TransferCharacter | null;
  beneficiary?: Beneficiary | string;
}

export interface YearRow {
  year: number;
  ages: (number | null)[]; // null once deceased
  phase: string; // accumulation | retirement
  filing_status: string; // single | mfj
  accounts: AccountYear[];

  // cash flows (nominal $)
  spend_goal: number;
  debt_payments: number;
  home_purchase: number; // one-time down payment / purchase outflow
  healthcare_cost: number; // gross premiums + OOP, incl. IRMAA; HSA-funded portion is in withdrawals_by_type.hsa
  aca_subsidy: number;
  irmaa_surcharge: number;
  ss_benefit: number[]; // per person, gross
  ss_total: number;
  other_income: number;
  rmd_total: number;
  rmd_by_person: number[];
  withdrawals_by_type: Partial<Record<AccountType, number>>;
  roth_conversion: number;
  surplus_reinvested: number;
  shortfall: number; // unmet spending (plan failure)
  premiums_paid?: number;
  legacy_distributions?: number;
  legacy_purchases?: number;
  death_benefits_paid?: number;
  qcd_amount?: number;
  gifts_made?: number;

  // tax detail (nominal $)
  dividends: number;
  interest: number;
  realized_gains: number;
  taxable_ss: number;
  agi: number;
  magi: number;
  deductions: number;
  taxable_income: number;
  federal_tax: number;
  ltcg_tax: number;
  niit: number;
  state_tax: number;
  penalties: number;
  total_tax: number;
  marginal_rate: number;
  effective_rate: number;

  // balances
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  net_worth_real: number; // deflated to today's dollars
  flags: string[];
}

export interface Metrics {
  nest_egg_at_retirement: number;
  nest_egg_at_retirement_real: number;
  retirement_year: number;
  ending_net_worth: number;
  ending_net_worth_real: number;
  ending_after_tax_real: number; // tax-deferred discounted at heir rate
  lifetime_taxes: number;
  lifetime_taxes_real: number;
  depleted: boolean;
  depletion_age: number | null; // primary person's age when funds ran out
  success: boolean;
  chosen_conversion_strategy: string;
  ss_claim_ages: number[];
  // legacy / estate (today's dollars); estate transfer tax is NOT modeled
  gross_estate_real?: number;
  net_to_heirs_real?: number;
  estate_ird_tax_real?: number;
  to_charity_real?: number;
  gifts_made_total_real?: number;
  /** Per-person Roth fraction under the chosen split ([] if not optimized). */
  chosen_contribution_split: number[];
}

export interface SensitivityRow {
  label: string;
  parameter: string;
  delta: string;
  ending_net_worth_real: number;
  nest_egg_real: number;
  depletion_age: number | null;
  success: boolean;
}

export interface StrategyComparison {
  strategy: string;
  ending_after_tax_real: number;
  lifetime_taxes_real: number;
  total_converted: number;
  depletion_age: number | null;
}

export interface SSGridCell {
  claim_ages: number[];
  ending_after_tax_real: number;
  depletion_age: number | null;
}

export interface ContributionSplitCell {
  /** Single-element list: the household Roth fraction (couple files jointly). */
  roth_pct: number[];
  ending_after_tax_real: number;
  lifetime_taxes_real: number;
  depletion_age: number | null;
  /** Optimal Roth-conversion strategy paired with this split (best-case). */
  conversion_strategy: string;
  is_current: boolean;
}

export type AssumptionKind = "modeled" | "estimated" | "assumed";

export interface AssumptionNote {
  label: string;
  value: string;
  kind: AssumptionKind | string;
  source: string;
  /** ISO date the developer last verified this value against a primary source. */
  last_updated?: string;
  /** "true" when the value is likely due for annual review based on calendar logic. */
  stale?: "true" | "false";
  /** URL of the primary source document to check for an updated value. */
  review_url?: string;
}

export interface ConstantsFreshness {
  key: string;
  last_updated: string;
  update_cycle: string;
  review_url: string;
  stale: boolean;
}

export interface LegacyAssetResult {
  name: string;
  asset_class: string;
  transfer_character: TransferCharacter | string;
  beneficiary: Beneficiary | string;
  gross: number;
  tax: number;
  net: number;
}

export interface LegacyResult {
  at_death_year: number;
  assets: LegacyAssetResult[];
  to_heirs_gross: number;
  to_heirs_net: number;
  to_charity: number;
  ird_tax: number;
  gifts_lifetime: number;
  exemption_used: number;
}

export interface PlanResult {
  metrics: Metrics;
  years: YearRow[];
  sensitivity: SensitivityRow[];
  conversion_comparison: StrategyComparison[];
  ss_grid: SSGridCell[];
  contribution_split: ContributionSplitCell[];
  warnings: string[];
  assumption_notes: AssumptionNote[];
  legacy?: LegacyResult | null;
}

export type DisplayMode = "real" | "nominal";
