import { Plus, Trash2 } from "lucide-react";
import type { InsurancePolicy } from "../../lib/types";
import { newInsurancePolicy } from "../../lib/sample";
import {
  NumberField,
  OptionalNumberField,
  PercentField,
  SelectField,
  TextField,
} from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";
import { BequestToggle } from "./BequestToggle";
import { ModelingDisclosure } from "./ModelingDisclosure";

export function InsuranceSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));
  const set = (i: number, patch: Partial<InsurancePolicy>) =>
    onChange({ ...input, insurance_policies: updateAt(input.insurance_policies, i, patch) });

  return (
    <div className="space-y-3">
      {input.insurance_policies.length === 0 && (
        <p className="text-xs text-slate-400">
          None — add a whole/permanent life policy with cash value and a death benefit.
        </p>
      )}
      <p className="text-[11px] text-slate-400">
        Amounts are the policy's actual (level nominal) figures, not today's dollars.
      </p>
      {input.insurance_policies.map((p, i) => {
        const e = (f: string) => errors[`insurance_policies.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
              <TextField
                label="Name"
                value={p.name}
                onChange={(name) => set(i, { name })}
                error={e("name")}
                className={dense ? "col-span-2" : "col-span-2"}
              />
              {input.persons.length > 1 && (
                <SelectField
                  label="Insured"
                  value={p.owner}
                  onChange={(owner) => set(i, { owner })}
                  options={ownerOptions}
                  error={e("owner")}
                />
              )}
              <NumberField
                label="Death benefit"
                value={p.death_benefit}
                onChange={(death_benefit) => set(i, { death_benefit })}
                min={0}
                prefix="$"
                error={e("death_benefit")}
                help="Face amount paid income-tax-free at death. Level nominal."
              />
              <NumberField
                label="Annual premium"
                value={p.annual_premium}
                onChange={(annual_premium) => set(i, { annual_premium })}
                min={0}
                prefix="$"
                error={e("annual_premium")}
                help="Level nominal premium, funded from the portfolio in retirement (assumed wage-covered before retirement)."
              />
              <NumberField
                label="Cash value"
                value={p.cash_value}
                onChange={(cash_value) => set(i, { cash_value })}
                min={0}
                prefix="$"
                error={e("cash_value")}
                help="Current cash surrender value. Grows tax-deferred at the rate below."
              />
              <PercentField
                label="Cash value growth"
                value={p.cash_value_return}
                onChange={(cash_value_return) => set(i, { cash_value_return })}
                min={-10}
                max={20}
                error={e("cash_value_return")}
                help="Assumed annual growth of the cash value."
              />
              <NumberField
                label="Premiums paid"
                value={p.premiums_paid_to_date}
                onChange={(premiums_paid_to_date) => set(i, { premiums_paid_to_date })}
                min={0}
                prefix="$"
                error={e("premiums_paid_to_date")}
                help="Total premiums paid so far — the basis used to compute the taxable gain if the policy is surrendered."
              />
              <OptionalNumberField
                label="Paid-up age"
                value={p.paid_up_age}
                onChange={(paid_up_age) => set(i, { paid_up_age })}
                min={30}
                max={110}
                placeholder="for life"
                error={e("paid_up_age")}
                help="Age at which premiums stop. Leave blank if premiums continue for life."
              />
              <OptionalNumberField
                label="Surrender age"
                value={p.surrender_at_age}
                onChange={(surrender_at_age) => set(i, { surrender_at_age })}
                min={30}
                max={110}
                placeholder="never"
                error={e("surrender_at_age")}
                help="Optional: age to surrender the policy for its cash value (gain over premiums paid is taxed as ordinary income). Leave blank to hold for life."
              />
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-4">
                <BequestToggle
                  value={p.beneficiary}
                  onChange={(beneficiary) => set(i, { beneficiary })}
                />
                <ModelingDisclosure assetKey="insurance" />
              </div>
              <button
                type="button"
                onClick={() =>
                  onChange({ ...input, insurance_policies: removeAt(input.insurance_policies, i) })
                }
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
              >
                <Trash2 className="h-3.5 w-3.5" /> Remove
              </button>
            </div>
          </div>
        );
      })}
      <button
        type="button"
        onClick={() =>
          onChange({ ...input, insurance_policies: [...input.insurance_policies, newInsurancePolicy()] })
        }
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add policy
      </button>
    </div>
  );
}
