import type { Beneficiary } from "../../lib/types";
import { CheckboxField } from "../ui/fields";

/**
 * "Leave to charity" designation, shared by every asset section. Charity
 * bequests settle income-tax-free out of the estate (a charity pays no income
 * tax, even on tax-deferred / IRD dollars) and are flagged estate-deductible.
 */
export function BequestToggle({
  value,
  onChange,
}: {
  value: Beneficiary | undefined;
  onChange: (b: Beneficiary) => void;
}) {
  return (
    <CheckboxField
      label="Leave to charity"
      checked={value === "charity"}
      onChange={(on) => onChange(on ? "charity" : "heirs")}
      help="Bequeath this asset to charity at the end of the plan. It passes income-tax-free out of the estate — a charity pays no income tax even on tax-deferred (IRD) dollars, which is why IRAs are the classic charitable bequest — and it's flagged estate-deductible (IRC §2055). Mid-plan, a surviving spouse still inherits and continues the asset; the designation is honored at the second death."
    />
  );
}
