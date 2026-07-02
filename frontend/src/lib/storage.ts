import type { PlanInput } from "./types";
import { DEFAULT_ASSUMPTIONS, SAMPLE_INPUT } from "./sample";

const KEY = "horizon.plan-input.v1";

/**
 * Validate and normalize an arbitrary parsed object into a PlanInput, or null
 * if it isn't a plan. Merges assumptions over defaults so newly-added fields
 * (and older exports missing them) get sane values. Shared by localStorage
 * loading and by file import, so both tolerate v1 plans loaded in v2.
 */
export function coercePlanInput(
  parsed: Partial<PlanInput> | null | undefined,
): PlanInput | null {
  if (
    !parsed ||
    !Array.isArray(parsed.persons) ||
    parsed.persons.length < 1 ||
    !Array.isArray(parsed.accounts) ||
    typeof parsed.annual_spending !== "number"
  ) {
    return null;
  }
  return {
    persons: parsed.persons,
    accounts: parsed.accounts,
    liabilities: parsed.liabilities ?? [],
    income_streams: parsed.income_streams ?? [],
    insurance_policies: parsed.insurance_policies ?? [],
    annuities: parsed.annuities ?? [],
    private_holdings: parsed.private_holdings ?? [],
    real_estate: parsed.real_estate ?? [],
    annual_spending: parsed.annual_spending,
    assumptions: { ...DEFAULT_ASSUMPTIONS, ...(parsed.assumptions ?? {}) },
  };
}

export function loadStoredInput(): PlanInput | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    return coercePlanInput(JSON.parse(raw) as Partial<PlanInput>);
  } catch {
    return null;
  }
}

export function saveStoredInput(input: PlanInput): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(input));
  } catch {
    /* storage may be unavailable; non-fatal */
  }
}

export function resetToSample(): PlanInput {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  return structuredClone(SAMPLE_INPUT);
}
