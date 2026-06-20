import type { Account, Assumptions, IncomeStream, Liability, Person, PlanInput } from "./types";
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
  aca_benchmark_monthly_per_person: 850,
  pre65_oop_annual_per_person: 2500,
  medicare_other_annual_per_person: 3500,
  pre_retirement_magi: null,
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
    },
    {
      name: "Alex",
      current_age: 53,
      retirement_age: 63,
      death_age: 94,
      ss_monthly_at_fra: 1900,
      ss_claim_age: 67,
    },
  ],
  accounts: [
    {
      name: "Sam 401(k)",
      type: "tax_deferred",
      owner: 0,
      balance: 850_000,
      cost_basis: null,
      annual_contribution: 30_000,
      expected_return: 0.06,
    },
    {
      name: "Alex 403(b)",
      type: "tax_deferred",
      owner: 1,
      balance: 310_000,
      cost_basis: null,
      annual_contribution: 15_000,
      expected_return: 0.06,
    },
    {
      name: "Roth IRA",
      type: "roth",
      owner: 0,
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
  annual_spending: 96_000,
  assumptions: { ...DEFAULT_ASSUMPTIONS, roth_conversion_strategy: "auto", optimize_ss_claiming: true },
};

export function newPerson(index: number): Person {
  return {
    name: index === 0 ? "You" : "Spouse",
    current_age: 50,
    retirement_age: 65,
    death_age: 90,
    ss_monthly_at_fra: 0,
    ss_claim_age: 67,
  };
}

export function newAccount(): Account {
  return {
    name: "New account",
    type: "tax_deferred",
    owner: 0,
    balance: 0,
    cost_basis: null,
    annual_contribution: 0,
    expected_return: DEFAULT_RETURNS.tax_deferred,
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
  };
}
