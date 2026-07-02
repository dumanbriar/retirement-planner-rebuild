import type { PlanInput } from "./types";

export type FieldErrors = Record<string, string>;

function inRange(v: number, lo: number, hi: number): boolean {
  return Number.isFinite(v) && v >= lo && v <= hi;
}

/**
 * Client-side mirror of the backend's Pydantic constraints. Keys are paths
 * like "persons.0.current_age" so sections can render errors inline.
 */
export function validatePlanInput(input: PlanInput): FieldErrors {
  const errors: FieldErrors = {};

  input.persons.forEach((p, i) => {
    const k = (f: string) => `persons.${i}.${f}`;
    if (!p.name.trim()) errors[k("name")] = "Name is required.";
    if (!inRange(p.current_age, 18, 99)) errors[k("current_age")] = "Age must be 18–99.";
    if (!inRange(p.retirement_age, 30, 80))
      errors[k("retirement_age")] = "Retirement age must be 30–80.";
    if (!inRange(p.death_age, 60, 105)) errors[k("death_age")] = "Plan-end age must be 60–105.";
    else if (p.death_age <= p.current_age)
      errors[k("death_age")] = "Plan-end age must be after current age.";
    if (!(p.ss_monthly_at_fra >= 0)) errors[k("ss_monthly_at_fra")] = "Must be ≥ 0.";
    if (!inRange(p.ss_claim_age, 62, 70)) errors[k("ss_claim_age")] = "Claiming age must be 62–70.";
    if (!(p.salary >= 0)) errors[k("salary")] = "Salary must be ≥ 0.";
  });

  if (input.accounts.length === 0) errors["accounts"] = "Add at least one account.";
  input.accounts.forEach((a, i) => {
    const k = (f: string) => `accounts.${i}.${f}`;
    if (!a.name.trim()) errors[k("name")] = "Name is required.";
    if (!(a.balance >= 0)) errors[k("balance")] = "Balance must be ≥ 0.";
    if (a.cost_basis != null && !(a.cost_basis >= 0)) errors[k("cost_basis")] = "Must be ≥ 0.";
    if (!(a.annual_contribution >= 0)) errors[k("annual_contribution")] = "Must be ≥ 0.";
    if (a.expected_return != null && !inRange(a.expected_return, -0.1, 0.2))
      errors[k("expected_return")] = "Return must be between −10% and 20%.";
    if (a.owner >= input.persons.length) errors[k("owner")] = "Owner is out of range.";
  });

  input.liabilities.forEach((l, i) => {
    const k = (f: string) => `liabilities.${i}.${f}`;
    if (!l.name.trim()) errors[k("name")] = "Name is required.";
    if (!(l.balance >= 0)) errors[k("balance")] = "Balance must be ≥ 0.";
    if (!inRange(l.interest_rate, 0, 0.3)) errors[k("interest_rate")] = "Rate must be 0–30%.";
    if (!(l.annual_payment >= 0)) errors[k("annual_payment")] = "Must be ≥ 0.";
    if (l.start_age != null && !inRange(l.start_age, 18, 100))
      errors[k("start_age")] = "Start age must be 18–100.";
    if (l.down_payment != null && !(l.down_payment >= 0))
      errors[k("down_payment")] = "Must be ≥ 0.";
  });

  input.income_streams.forEach((s, i) => {
    const k = (f: string) => `income_streams.${i}.${f}`;
    if (!s.name.trim()) errors[k("name")] = "Name is required.";
    if (!(s.annual_amount >= 0)) errors[k("annual_amount")] = "Must be ≥ 0.";
    if (!inRange(s.start_age, 30, 100)) errors[k("start_age")] = "Start age must be 30–100.";
    if (s.end_age != null) {
      if (!inRange(s.end_age, 30, 110)) errors[k("end_age")] = "End age must be 30–110.";
      else if (s.end_age < s.start_age) errors[k("end_age")] = "End age must be ≥ start age.";
    }
    if (s.owner >= input.persons.length) errors[k("owner")] = "Owner is out of range.";
    if (s.survivor_pct != null && !inRange(s.survivor_pct, 0, 1))
      errors[k("survivor_pct")] = "Survivor benefit must be 0–100%.";
  });

  (input.insurance_policies ?? []).forEach((p, i) => {
    const k = (f: string) => `insurance_policies.${i}.${f}`;
    if (!p.name.trim()) errors[k("name")] = "Name is required.";
    if (!(p.death_benefit >= 0)) errors[k("death_benefit")] = "Must be ≥ 0.";
    if (!(p.annual_premium >= 0)) errors[k("annual_premium")] = "Must be ≥ 0.";
    if (!(p.cash_value >= 0)) errors[k("cash_value")] = "Must be ≥ 0.";
    if (!(p.premiums_paid_to_date >= 0)) errors[k("premiums_paid_to_date")] = "Must be ≥ 0.";
    if (!inRange(p.cash_value_return, -0.1, 0.2))
      errors[k("cash_value_return")] = "Return must be −10% to 20%.";
    if (p.paid_up_age != null && !inRange(p.paid_up_age, 30, 110))
      errors[k("paid_up_age")] = "Paid-up age must be 30–110.";
    if (p.surrender_at_age != null && !inRange(p.surrender_at_age, 30, 110))
      errors[k("surrender_at_age")] = "Surrender age must be 30–110.";
    if (p.owner >= input.persons.length) errors[k("owner")] = "Owner is out of range.";
  });

  (input.annuities ?? []).forEach((a, i) => {
    const k = (f: string) => `annuities.${i}.${f}`;
    if (!a.name.trim()) errors[k("name")] = "Name is required.";
    if (!(a.balance >= 0)) errors[k("balance")] = "Must be ≥ 0.";
    if (!(a.basis >= 0)) errors[k("basis")] = "Must be ≥ 0.";
    if (!inRange(a.accumulation_return, -0.1, 0.2))
      errors[k("accumulation_return")] = "Return must be −10% to 20%.";
    if (!inRange(a.annuitize_at_age, 50, 90))
      errors[k("annuitize_at_age")] = "Annuitize age must be 50–90.";
    if (!inRange(a.payout_years, 1, 40))
      errors[k("payout_years")] = "Payout years must be 1–40.";
    if (a.purchase_age != null) {
      if (!inRange(a.purchase_age, 40, 90))
        errors[k("purchase_age")] = "Purchase age must be 40–90.";
      if (!(a.purchase_amount > 0))
        errors[k("purchase_amount")] = "Enter the amount to buy with.";
      if (a.annuitize_at_age < a.purchase_age)
        errors[k("annuitize_at_age")] = "Annuitize age must be ≥ purchase age.";
    }
    if (a.owner >= input.persons.length) errors[k("owner")] = "Owner is out of range.";
  });

  (input.private_holdings ?? []).forEach((h, i) => {
    const k = (f: string) => `private_holdings.${i}.${f}`;
    if (!h.name.trim()) errors[k("name")] = "Name is required.";
    if (!(h.value >= 0)) errors[k("value")] = "Must be ≥ 0.";
    if (!(h.basis >= 0)) errors[k("basis")] = "Must be ≥ 0.";
    if (!inRange(h.growth_rate, -0.1, 0.2))
      errors[k("growth_rate")] = "Growth must be −10% to 20%.";
    if (!(h.annual_distribution >= 0)) errors[k("annual_distribution")] = "Must be ≥ 0.";
    if (h.sale_age != null && !inRange(h.sale_age, 18, 100))
      errors[k("sale_age")] = "Sale age must be 18–100.";
    if (h.owner >= input.persons.length) errors[k("owner")] = "Owner is out of range.";
  });

  if (!(input.annual_spending > 0))
    errors["annual_spending"] = "Annual retirement spending must be greater than 0.";

  const a = input.assumptions;
  if (!inRange(a.inflation, 0, 0.1)) errors["assumptions.inflation"] = "Must be 0–10%.";
  if (!inRange(a.healthcare_inflation, 0, 0.12))
    errors["assumptions.healthcare_inflation"] = "Must be 0–12%.";
  if (!inRange(a.state_tax_rate, 0, 0.15)) errors["assumptions.state_tax_rate"] = "Must be 0–15%.";
  if (!inRange(a.pre_retirement_tax_rate, 0, 0.5))
    errors["assumptions.pre_retirement_tax_rate"] = "Must be 0–50%.";
  if (!inRange(a.taxable_dividend_yield, 0, 0.08))
    errors["assumptions.taxable_dividend_yield"] = "Must be 0–8%.";
  if (!inRange(a.heir_tax_rate, 0, 0.5)) errors["assumptions.heir_tax_rate"] = "Must be 0–50%.";
  if (!(a.custom_conversion_amount >= 0))
    errors["assumptions.custom_conversion_amount"] = "Must be ≥ 0.";
  if (!(a.aca_benchmark_monthly_per_person >= 0))
    errors["assumptions.aca_benchmark_monthly_per_person"] = "Must be ≥ 0.";
  if (!(a.pre65_oop_annual_per_person >= 0))
    errors["assumptions.pre65_oop_annual_per_person"] = "Must be ≥ 0.";
  if (!(a.medicare_other_annual_per_person >= 0))
    errors["assumptions.medicare_other_annual_per_person"] = "Must be ≥ 0.";
  if (a.pre_retirement_magi != null && !(a.pre_retirement_magi >= 0))
    errors["assumptions.pre_retirement_magi"] = "Must be ≥ 0.";

  return errors;
}
