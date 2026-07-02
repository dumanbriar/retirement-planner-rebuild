import type { ConversionStrategy } from "../../lib/types";
import { CONVERSION_STRATEGY_LABELS } from "../../lib/types";
import { CheckboxField, NumberField, OptionalNumberField, SelectField } from "../ui/fields";
import type { SectionProps } from "./sectionProps";

const STRATEGY_OPTIONS = (
  ["auto", "none", "fill_10", "fill_12", "fill_22", "fill_24", "custom"] as ConversionStrategy[]
).map((s) => ({ value: s, label: CONVERSION_STRATEGY_LABELS[s] }));

export function SpendingSection({ input, onChange, errors, dense }: SectionProps) {
  const a = input.assumptions;
  const setA = (patch: Partial<typeof a>) =>
    onChange({ ...input, assumptions: { ...a, ...patch } });

  return (
    <div className="space-y-4">
      <NumberField
        big
        label="Annual retirement spending (today's $)"
        value={input.annual_spending}
        onChange={(annual_spending) => onChange({ ...input, annual_spending })}
        min={0}
        prefix="$"
        error={errors["annual_spending"]}
        help="Lifestyle spending goal per year in retirement, in today's dollars — excluding healthcare, debt payments, and taxes, which the engine adds on top. Inflated each year at the inflation assumption."
      />
      <div className={`grid gap-3 ${dense ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2"}`}>
        <SelectField
          label="Roth conversion strategy"
          value={a.roth_conversion_strategy}
          onChange={(roth_conversion_strategy) => setA({ roth_conversion_strategy })}
          options={STRATEGY_OPTIONS}
          help="Converts tax-deferred dollars to Roth in low-income years, paying tax now to avoid larger RMDs and heir taxes later. 'Fill X%' converts up to the top of that federal bracket each year. 'Auto-optimize' tries every bracket-fill option and keeps the one with the highest ending after-tax wealth."
        />
        {a.roth_conversion_strategy === "custom" && (
          <NumberField
            label="Custom conversion / yr"
            value={a.custom_conversion_amount}
            onChange={(custom_conversion_amount) => setA({ custom_conversion_amount })}
            min={0}
            prefix="$"
            error={errors["assumptions.custom_conversion_amount"]}
            help="Fixed amount converted from tax-deferred to Roth each retirement year (until tax-deferred balances run out)."
          />
        )}
      </div>
      <NumberField
        label="Annual charitable giving from IRAs (QCD, today's $)"
        value={a.annual_qcd}
        onChange={(annual_qcd) => setA({ annual_qcd })}
        min={0}
        prefix="$"
        error={errors["assumptions.annual_qcd"]}
        help="Qualified charitable distributions: direct IRA-to-charity gifts once the owner is 70½ (modeled from the age-71 year). Excluded from AGI — also lowering IRMAA and ACA exposure — and counts toward the RMD (IRC §408(d)(8)). Capped per person at the statutory limit ($111,000 in 2026, indexed). Grows with inflation; drawn only from tax-deferred accounts."
      />
      <NumberField
        label="Annual gifting to family (today's $)"
        value={a.annual_gifting}
        onChange={(annual_gifting) => setA({ annual_gifting })}
        min={0}
        prefix="$"
        error={errors["assumptions.annual_gifting"]}
        help="Lifetime gifts out of the portfolio each retirement year (inflated). The annual exclusion (IRC §2503(b), $19,000 per recipient per living donor in 2026, indexed; a couple gift-splits) shelters gifts each year; the excess consumes the $15M-per-person lifetime exemption (IRC §2010), tracked in the Legacy view with a warning if it would run out. Gift tax itself is not modeled."
      />
      {a.annual_gifting > 0 && (
        <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-3"}`}>
          <OptionalNumberField
            label="Gifting start age"
            value={a.gifting_start_age}
            onChange={(gifting_start_age) => setA({ gifting_start_age })}
            min={18}
            max={100}
            placeholder="retirement"
            error={errors["assumptions.gifting_start_age"]}
            help="Primary person's age when gifting starts. Blank = at household retirement (gifts before retirement aren't modeled)."
          />
          <OptionalNumberField
            label="Gifting end age"
            value={a.gifting_end_age}
            onChange={(gifting_end_age) => setA({ gifting_end_age })}
            min={18}
            max={110}
            placeholder="death"
            error={errors["assumptions.gifting_end_age"]}
            help="Primary person's age of the last gift. Blank = gifting continues through the survivor's final year."
          />
          <NumberField
            label="Recipients"
            value={a.gift_recipients}
            onChange={(gift_recipients) => setA({ gift_recipients })}
            min={1}
            max={20}
            error={errors["assumptions.gift_recipients"]}
            help="How many people receive the gifts (children, grandchildren…). Each recipient shelters one annual exclusion per living donor from the lifetime exemption."
          />
        </div>
      )}
      <CheckboxField
        label="Optimize Social Security claiming ages"
        checked={a.optimize_ss_claiming}
        onChange={(optimize_ss_claiming) => setA({ optimize_ss_claiming })}
        help="Evaluates every claiming-age combination (62–70 per person) and picks the one with the highest ending after-tax wealth, overriding the per-person claiming ages above. The full grid is shown in the results."
      />
      <CheckboxField
        label="Suggest the best Traditional vs Roth contribution split"
        checked={a.optimize_contribution_split}
        onChange={(optimize_contribution_split) => setA({ optimize_contribution_split })}
        help="Advisory only — your plan still models the contributions you entered. Re-simulates across household Traditional/Roth split levels and shows which maximizes ending after-tax wealth. Needs each working person's salary (Household tab) to value the Traditional deduction; it reinvests the tax saving and respects per-vehicle IRS limits. The comparison appears in the results."
      />
    </div>
  );
}
