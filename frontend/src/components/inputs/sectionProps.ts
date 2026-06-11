import type { PlanInput } from "../../lib/types";
import type { FieldErrors } from "../../lib/validate";

export interface SectionProps {
  input: PlanInput;
  onChange: (next: PlanInput) => void;
  errors: FieldErrors;
  /** Compact layout for the 320px results sidebar. */
  dense?: boolean;
}

export function updateAt<T>(list: T[], index: number, patch: Partial<T>): T[] {
  return list.map((item, i) => (i === index ? { ...item, ...patch } : item));
}

export function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, i) => i !== index);
}
