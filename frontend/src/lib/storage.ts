import type { PlanInput } from "./types";
import { DEFAULT_ASSUMPTIONS, SAMPLE_INPUT } from "./sample";

const KEY = "horizon.plan-input.v1";

export function loadStoredInput(): PlanInput | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PlanInput>;
    if (
      !parsed ||
      !Array.isArray(parsed.persons) ||
      parsed.persons.length < 1 ||
      !Array.isArray(parsed.accounts) ||
      typeof parsed.annual_spending !== "number"
    ) {
      return null;
    }
    // Merge assumptions over defaults so newly-added fields get sane values.
    return {
      persons: parsed.persons,
      accounts: parsed.accounts,
      liabilities: parsed.liabilities ?? [],
      income_streams: parsed.income_streams ?? [],
      annual_spending: parsed.annual_spending,
      assumptions: { ...DEFAULT_ASSUMPTIONS, ...(parsed.assumptions ?? {}) },
    };
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
