import { Plus, Trash2 } from "lucide-react";
import type { Liability } from "../../lib/types";
import { newLiability } from "../../lib/sample";
import { NumberField, PercentField, TextField } from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";

export function LiabilitiesSection({ input, onChange, errors, dense }: SectionProps) {
  const set = (i: number, patch: Partial<Liability>) =>
    onChange({ ...input, liabilities: updateAt(input.liabilities, i, patch) });

  return (
    <div className="space-y-3">
      {input.liabilities.length === 0 && (
        <p className="text-xs text-slate-400">No liabilities — debt-free household.</p>
      )}
      {input.liabilities.map((l, i) => {
        const e = (f: string) => errors[`liabilities.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
              <TextField
                label="Name"
                value={l.name}
                onChange={(name) => set(i, { name })}
                error={e("name")}
                className={dense ? "col-span-2" : ""}
              />
              <NumberField
                label="Balance"
                value={l.balance}
                onChange={(balance) => set(i, { balance })}
                min={0}
                prefix="$"
                error={e("balance")}
              />
              <PercentField
                label="Interest rate"
                value={l.interest_rate}
                onChange={(interest_rate) => set(i, { interest_rate })}
                min={0}
                max={30}
                error={e("interest_rate")}
              />
              <NumberField
                label="Annual payment"
                value={l.annual_payment}
                onChange={(annual_payment) => set(i, { annual_payment })}
                min={0}
                prefix="$"
                error={e("annual_payment")}
                help="Fixed annual payment until the balance reaches zero. Payments are part of spending need in retirement, on top of the lifestyle spending goal."
              />
            </div>
            <div className="mt-2 flex justify-end">
              <button
                type="button"
                onClick={() => onChange({ ...input, liabilities: removeAt(input.liabilities, i) })}
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
        onClick={() => onChange({ ...input, liabilities: [...input.liabilities, newLiability()] })}
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add liability
      </button>
    </div>
  );
}
