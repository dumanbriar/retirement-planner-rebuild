import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CheckboxField, NumberField, OptionalNumberField, PercentField } from "../ui/fields";
import type { SectionProps } from "./sectionProps";

export function AssumptionsSection({ input, onChange, errors, dense }: SectionProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const a = input.assumptions;
  const setA = (patch: Partial<typeof a>) =>
    onChange({ ...input, assumptions: { ...a, ...patch } });
  const e = (f: string) => errors[`assumptions.${f}`];

  const gridClass = dense ? "grid grid-cols-2 gap-3" : "grid grid-cols-2 gap-3 sm:grid-cols-3";

  return (
    <div className="space-y-4">
      <div className={gridClass}>
        <PercentField
          label="Inflation"
          value={a.inflation}
          onChange={(inflation) => setA({ inflation })}
          min={0}
          max={10}
          error={e("inflation")}
          help="General CPI assumption. Used to inflate spending and COLAs and to index tax brackets, deductions, and IRMAA thresholds. Also the deflator behind every 'today's $' figure."
        />
        <PercentField
          label="Healthcare inflation"
          value={a.healthcare_inflation}
          onChange={(healthcare_inflation) => setA({ healthcare_inflation })}
          min={0}
          max={12}
          error={e("healthcare_inflation")}
          help="Applied to premiums and out-of-pocket healthcare costs. Historically runs above general CPI."
        />
        <PercentField
          label="State tax rate"
          value={a.state_tax_rate}
          onChange={(state_tax_rate) => setA({ state_tax_rate })}
          min={0}
          max={15}
          error={e("state_tax_rate")}
          help="Flat state income-tax rate applied to taxable income. Set to 0 for no-income-tax states."
        />
      </div>

      <button
        type="button"
        onClick={() => setAdvancedOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 transition-colors hover:text-brand-900"
        aria-expanded={advancedOpen}
      >
        {advancedOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        Advanced assumptions
      </button>

      {advancedOpen && (
        <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
          <div className={gridClass}>
            <PercentField
              label="Pre-retirement tax rate"
              value={a.pre_retirement_tax_rate}
              onChange={(pre_retirement_tax_rate) => setA({ pre_retirement_tax_rate })}
              min={0}
              max={50}
              error={e("pre_retirement_tax_rate")}
              help="Flat marginal rate used ONLY before retirement, for the annual tax drag on cash interest and any forced pre-retirement inflows. Wages themselves are not modeled."
            />
            <PercentField
              label="Taxable dividend yield"
              value={a.taxable_dividend_yield}
              onChange={(taxable_dividend_yield) => setA({ taxable_dividend_yield })}
              min={0}
              max={8}
              error={e("taxable_dividend_yield")}
              help="Portion of the taxable account's return paid out each year as qualified dividends (taxed annually); the rest stays as unrealized appreciation."
            />
            <PercentField
              label="Heir tax rate"
              value={a.heir_tax_rate}
              onChange={(heir_tax_rate) => setA({ heir_tax_rate })}
              min={0}
              max={50}
              error={e("heir_tax_rate")}
              help="Discount applied to remaining tax-deferred/HSA dollars when valuing the estate ('ending after-tax wealth'). Taxable assets assume a basis step-up at death."
            />
            <NumberField
              label="ACA benchmark $/mo/person"
              value={a.aca_benchmark_monthly_per_person}
              onChange={(aca_benchmark_monthly_per_person) =>
                setA({ aca_benchmark_monthly_per_person })
              }
              min={0}
              prefix="$"
              error={e("aca_benchmark_monthly_per_person")}
              help="Estimated monthly benchmark (second-lowest-cost silver) marketplace premium per person before subsidies, for pre-65 retirement years. Premium tax credits are then computed from MAGI using the statutory schedule."
            />
            <NumberField
              label="Pre-65 OOP $/yr/person"
              value={a.pre65_oop_annual_per_person}
              onChange={(pre65_oop_annual_per_person) => setA({ pre65_oop_annual_per_person })}
              min={0}
              prefix="$"
              error={e("pre65_oop_annual_per_person")}
              help="Estimated annual out-of-pocket healthcare costs (deductibles, copays) per person before Medicare at 65."
            />
            <NumberField
              label="Medicare other $/yr/person"
              value={a.medicare_other_annual_per_person}
              onChange={(medicare_other_annual_per_person) =>
                setA({ medicare_other_annual_per_person })
              }
              min={0}
              prefix="$"
              error={e("medicare_other_annual_per_person")}
              help="Age 65+: Part D, Medigap/Advantage, dental and out-of-pocket — everything except the Part B premium, which is modeled exactly (including IRMAA)."
            />
            <OptionalNumberField
              label="Pre-retirement MAGI"
              value={a.pre_retirement_magi}
              onChange={(pre_retirement_magi) => setA({ pre_retirement_magi })}
              min={0}
              prefix="$"
              placeholder="auto-estimate"
              error={e("pre_retirement_magi")}
              className="col-span-2"
              help="Household MAGI in the last two working years. Drives Medicare IRMAA surcharges for the first two Medicare years (2-year lookback). Leave blank and the engine assumes 1.5x annual spending, labeled as an estimate."
            />
          </div>
          <CheckboxField
            label="Contributions grow with inflation"
            checked={a.contributions_grow_with_inflation}
            onChange={(contributions_grow_with_inflation) =>
              setA({ contributions_grow_with_inflation })
            }
            help="If checked, annual contributions increase with inflation each year until retirement; otherwise they stay flat in nominal dollars."
          />
        </div>
      )}
    </div>
  );
}
