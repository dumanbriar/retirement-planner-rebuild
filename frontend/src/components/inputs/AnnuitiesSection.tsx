import { Plus, Trash2 } from "lucide-react";
import type { Annuity } from "../../lib/types";
import { newAnnuity } from "../../lib/sample";
import {
  CheckboxField,
  NumberField,
  PercentField,
  SelectField,
  TextField,
} from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";
import { ModelingDisclosure } from "./ModelingDisclosure";
import { BequestToggle } from "./BequestToggle";

export function AnnuitiesSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));
  const set = (i: number, patch: Partial<Annuity>) =>
    onChange({ ...input, annuities: updateAt(input.annuities, i, patch) });

  return (
    <div className="space-y-3">
      {input.annuities.length === 0 && (
        <p className="text-xs text-slate-400">
          None — add a non-qualified deferred annuity (tax-deferred value, then a payout).
        </p>
      )}
      {input.annuities.map((a, i) => {
        const e = (f: string) => errors[`annuities.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
              <TextField
                label="Name"
                value={a.name}
                onChange={(name) => set(i, { name })}
                error={e("name")}
                className="col-span-2"
              />
              {input.persons.length > 1 && (
                <SelectField
                  label="Owner"
                  value={a.owner}
                  onChange={(owner) => set(i, { owner })}
                  options={ownerOptions}
                  error={e("owner")}
                />
              )}
              {a.purchase_age == null ? (
                <>
                  <NumberField
                    label="Value"
                    value={a.balance}
                    onChange={(balance) => set(i, { balance })}
                    min={0}
                    prefix="$"
                    error={e("balance")}
                    help="Current accumulation (contract) value. Grows tax-deferred until annuitized."
                  />
                  <NumberField
                    label="Cost basis"
                    value={a.basis}
                    onChange={(basis) => set(i, { basis })}
                    min={0}
                    prefix="$"
                    error={e("basis")}
                    help="After-tax premiums paid into the contract. Sets the exclusion ratio — the share of each payout returned tax-free."
                  />
                </>
              ) : (
                <>
                  <NumberField
                    label="Buy at age"
                    value={a.purchase_age}
                    onChange={(purchase_age) => set(i, { purchase_age })}
                    min={40}
                    max={90}
                    error={e("purchase_age")}
                    help="Age at which you plan to buy the annuity. The contract is dormant until then."
                  />
                  <NumberField
                    label="Purchase amount"
                    value={a.purchase_amount}
                    onChange={(purchase_amount) => set(i, { purchase_amount })}
                    min={0}
                    prefix="$"
                    error={e("purchase_amount")}
                    help="Lump sum drawn from the portfolio at that age to buy the annuity (becomes its value and full after-tax basis). A tax-deferred withdrawal to fund it is itself taxed that year."
                  />
                </>
              )}
              <PercentField
                label="Growth rate"
                value={a.accumulation_return}
                onChange={(accumulation_return) => set(i, { accumulation_return })}
                min={-10}
                max={20}
                error={e("accumulation_return")}
                help="Assumed tax-deferred growth of the contract value before annuitization."
              />
              <NumberField
                label="Annuitize at age"
                value={a.annuitize_at_age}
                onChange={(annuitize_at_age) => set(i, { annuitize_at_age })}
                min={50}
                max={90}
                error={e("annuitize_at_age")}
                help="Age at which the value converts into a level payout stream."
              />
              <NumberField
                label="Payout years"
                value={a.payout_years}
                onChange={(payout_years) => set(i, { payout_years })}
                min={1}
                max={40}
                error={e("payout_years")}
                help="Length of the period-certain payout (e.g. ~life expectancy at annuitization)."
              />
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-4">
                <CheckboxField
                  label="Buy in the future"
                  checked={a.purchase_age != null}
                  onChange={(on) =>
                    set(i, on
                      ? { purchase_age: Math.max(a.annuitize_at_age - 5, 60), purchase_amount: a.purchase_amount || a.balance }
                      : { purchase_age: null })
                  }
                  help="Model buying this annuity later with a lump sum from the portfolio, instead of already owning it."
                />
                <BequestToggle
                  value={a.beneficiary}
                  onChange={(beneficiary) => set(i, { beneficiary })}
                />
                <ModelingDisclosure assetKey="annuity" />
              </div>
              <button
                type="button"
                onClick={() => onChange({ ...input, annuities: removeAt(input.annuities, i) })}
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
        onClick={() => onChange({ ...input, annuities: [...input.annuities, newAnnuity()] })}
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add annuity
      </button>
    </div>
  );
}
