import { Plus, Trash2 } from "lucide-react";
import type { IncomeStream } from "../../lib/types";
import { newIncomeStream } from "../../lib/sample";
import {
  CheckboxField,
  NumberField,
  OptionalNumberField,
  SelectField,
  TextField,
} from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";

export function IncomeStreamsSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));
  const set = (i: number, patch: Partial<IncomeStream>) =>
    onChange({ ...input, income_streams: updateAt(input.income_streams, i, patch) });

  return (
    <div className="space-y-3">
      {input.income_streams.length === 0 && (
        <p className="text-xs text-slate-400">
          None — add pensions, annuities, rentals, or part-time work in retirement.
        </p>
      )}
      {input.income_streams.map((s, i) => {
        const e = (f: string) => errors[`income_streams.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-5"}`}>
              <TextField
                label="Name"
                value={s.name}
                onChange={(name) => set(i, { name })}
                error={e("name")}
                className={dense ? "col-span-2" : ""}
              />
              <SelectField
                label="Owner"
                value={s.owner}
                onChange={(owner) => set(i, { owner })}
                options={ownerOptions}
                error={e("owner")}
              />
              <NumberField
                label="Annual amount"
                value={s.annual_amount}
                onChange={(annual_amount) => set(i, { annual_amount })}
                min={0}
                prefix="$"
                error={e("annual_amount")}
                help="In today's dollars. If COLA is checked, it grows with inflation from today; otherwise it stays fixed in nominal dollars."
              />
              <NumberField
                label="Start age"
                value={s.start_age}
                onChange={(start_age) => set(i, { start_age })}
                min={30}
                max={100}
                error={e("start_age")}
              />
              <OptionalNumberField
                label="End age"
                value={s.end_age}
                onChange={(end_age) => set(i, { end_age })}
                min={30}
                max={110}
                placeholder="lifetime"
                error={e("end_age")}
                help="Last age the income is received. Leave blank for lifetime income (e.g. a pension or annuity)."
              />
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-4">
                <CheckboxField
                  label="COLA"
                  checked={s.cola}
                  onChange={(cola) => set(i, { cola })}
                  help="Cost-of-living adjustment: the amount grows with the plan's inflation assumption."
                />
                <CheckboxField
                  label="Taxable"
                  checked={s.taxable}
                  onChange={(taxable) => set(i, { taxable })}
                  help="Taxed as ordinary income (typical for pensions and annuity payouts). Uncheck for tax-free income."
                />
              </div>
              <button
                type="button"
                onClick={() =>
                  onChange({ ...input, income_streams: removeAt(input.income_streams, i) })
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
          onChange({ ...input, income_streams: [...input.income_streams, newIncomeStream()] })
        }
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add income stream
      </button>
    </div>
  );
}
