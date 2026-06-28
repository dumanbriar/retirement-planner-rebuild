import { Plus, Trash2 } from "lucide-react";
import type { Liability } from "../../lib/types";
import { newLiability } from "../../lib/sample";
import { NumberField, OptionalNumberField, PercentField, TextField } from "../ui/fields";
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
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-3"}`}>
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
                help={
                  l.start_age != null
                    ? "Loan amount at purchase, in actual (future) dollars at the purchase date — enter the literal mortgage you expect to take, not today's dollars."
                    : undefined
                }
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
              <OptionalNumberField
                label="Start age"
                value={l.start_age ?? null}
                onChange={(start_age) => set(i, { start_age })}
                min={18}
                max={100}
                placeholder="now"
                error={e("start_age")}
                help="For a future purchase (e.g. a mortgage on a home bought later): the primary person's age when the debt begins. Leave blank for a debt you already have. The home itself is not tracked as an asset, so net worth dips at purchase."
              />
              {l.start_age != null && (
                <NumberField
                  label="Down payment"
                  value={l.down_payment ?? 0}
                  onChange={(down_payment) => set(i, { down_payment })}
                  min={0}
                  prefix="$"
                  error={e("down_payment")}
                  help="One-time cash at purchase (down payment + closing), in actual (future) dollars at the purchase date. Drawn from the portfolio in the purchase year — cash and taxable accounts first, then tax-advantaged accounts (with an early-withdrawal penalty before age 59½ and a warning) if those fall short. Your retirement contributions are not reduced to fund it; to save toward it instead, lower your contributions in the years before."
                />
              )}
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
