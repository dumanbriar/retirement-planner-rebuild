import type {
  Account,
  Annuity,
  Assumptions,
  IncomeStream,
  InsurancePolicy,
  Liability,
  Person,
  PlanInput,
  PrivateHolding,
  RealEstate,
} from "./types";
import { DEFAULT_RETURNS } from "./types";

export const DEFAULT_ASSUMPTIONS: Assumptions = {
  inflation: 0.025,
  healthcare_inflation: 0.05,
  state_tax_rate: 0.0,
  pre_retirement_tax_rate: 0.22,
  taxable_dividend_yield: 0.02,
  heir_tax_rate: 0.24,
  contributions_grow_with_inflation: true,
  roth_conversion_strategy: "auto",
  custom_conversion_amount: 0,
  optimize_ss_claiming: false,
  optimize_contribution_split: false,
  aca_benchmark_monthly_per_person: 850,
  pre65_oop_annual_per_person: 2500,
  medicare_other_annual_per_person: 3500,
  pre_retirement_magi: null,
  annual_qcd: 0,
  annual_gifting: 0,
  gifting_start_age: null,
  gifting_end_age: null,
  gift_recipients: 1,
};

/** The Sam & Alex sample scenario (mirrors the backend's sample request). */
export const SAMPLE_INPUT: PlanInput = {
  persons: [
    {
      name: "Sam",
      current_age: 55,
      retirement_age: 65,
      death_age: 92,
      ss_monthly_at_fra: 2800,
      ss_claim_age: 67,
      salary: 180_000,
    },
    {
      name: "Alex",
      current_age: 53,
      retirement_age: 63,
      death_age: 94,
      ss_monthly_at_fra: 1900,
      ss_claim_age: 67,
      salary: 110_000,
    },
  ],
  accounts: [
    {
      name: "Sam 401(k)",
      type: "tax_deferred",
      owner: 0,
      vehicle: "employer",
      balance: 850_000,
      cost_basis: null,
      annual_contribution: 23_000,
      expected_return: 0.06,
    },
    {
      name: "Alex 403(b)",
      type: "tax_deferred",
      owner: 1,
      vehicle: "employer",
      balance: 310_000,
      cost_basis: null,
      annual_contribution: 15_000,
      expected_return: 0.06,
    },
    {
      name: "Roth IRA",
      type: "roth",
      owner: 0,
      vehicle: "ira",
      balance: 120_000,
      cost_basis: null,
      annual_contribution: 7_000,
      expected_return: 0.065,
    },
    {
      name: "Brokerage",
      type: "taxable",
      owner: 0,
      balance: 400_000,
      cost_basis: 250_000,
      annual_contribution: 12_000,
      expected_return: 0.06,
    },
    {
      name: "HSA",
      type: "hsa",
      owner: 0,
      balance: 45_000,
      cost_basis: null,
      annual_contribution: 8_300,
      expected_return: 0.05,
    },
    {
      name: "HY Savings",
      type: "cash",
      owner: 0,
      balance: 60_000,
      cost_basis: null,
      annual_contribution: 0,
      expected_return: 0.04,
    },
  ],
  liabilities: [
    { name: "Mortgage", balance: 220_000, interest_rate: 0.0325, annual_payment: 24_000 },
  ],
  income_streams: [],
  insurance_policies: [],
  annuities: [],
  private_holdings: [],
  real_estate: [],
  annual_spending: 96_000,
  assumptions: {
    ...DEFAULT_ASSUMPTIONS,
    roth_conversion_strategy: "auto",
    optimize_ss_claiming: true,
    optimize_contribution_split: true,
  },
};

export function newPerson(index: number): Person {
  return {
    name: index === 0 ? "You" : "Spouse",
    current_age: 50,
    retirement_age: 65,
    death_age: 90,
    ss_monthly_at_fra: 0,
    ss_claim_age: 67,
    salary: 0,
  };
}

export function newAccount(): Account {
  return {
    name: "New account",
    type: "tax_deferred",
    owner: 0,
    vehicle: "employer",
    balance: 0,
    cost_basis: null,
    annual_contribution: 0,
    expected_return: DEFAULT_RETURNS.tax_deferred,
    beneficiary: "heirs",
  };
}

export function newLiability(): Liability {
  return {
    name: "New liability",
    balance: 0,
    interest_rate: 0.05,
    annual_payment: 0,
    start_age: null,
    down_payment: 0,
  };
}

export function newIncomeStream(): IncomeStream {
  return {
    name: "Pension",
    owner: 0,
    annual_amount: 0,
    start_age: 65,
    end_age: null,
    cola: true,
    taxable: true,
    survivor_pct: 0,
  };
}

export function newInsurancePolicy(): InsurancePolicy {
  return {
    name: "Whole life policy",
    owner: 0,
    annual_premium: 0,
    paid_up_age: null,
    cash_value: 0,
    cash_value_return: 0.04,
    death_benefit: 0,
    premiums_paid_to_date: 0,
    surrender_at_age: null,
    beneficiary: "heirs",
  };
}

export function newPrivateHolding(): PrivateHolding {
  return {
    name: "Private company shares",
    owner: 0,
    value: 0,
    basis: 0,
    growth_rate: 0.04,
    annual_distribution: 0,
    distribution_kind: "ordinary",
    sale_age: null,
    beneficiary: "heirs",
  };
}

export function newRealEstate(liabilityIndex: number | null = null, name = "Home"): RealEstate {
  return {
    name,
    owner: 0,
    value: 0,
    basis: 0,
    appreciation: 0.03,
    is_primary: true,
    sale_age: null,
    liability_index: liabilityIndex,
    include_in_net_worth: true,
    beneficiary: "heirs",
  };
}

export function newAnnuity(): Annuity {
  return {
    name: "Deferred annuity",
    owner: 0,
    balance: 0,
    basis: 0,
    accumulation_return: 0.04,
    annuitize_at_age: 70,
    payout_years: 20,
    purchase_age: null,
    purchase_amount: 0,
    beneficiary: "heirs",
  };
}
