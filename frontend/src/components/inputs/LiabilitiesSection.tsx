import { Home, Plus, Trash2 } from "lucide-react";
import type { Liability } from "../../lib/types";
import { newLiability, newRealEstate } from "../../lib/sample";
import { CheckboxField, NumberField, OptionalNumberField, PercentField, TextField } from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";

export function LiabilitiesSection({ input, onChange, errors, dense }: SectionProps) {
  const set = (i: number, patch: Partial<Liability>) =>
    onChange({ ...input, liabilities: updateAt(input.liabilities, i, patch) });

  // Removing a liability shifts the indices that real-estate entries link to.
  const removeLiability = (i: number) =>
    onChange({
      ...input,
      liabilities: removeAt(input.liabilities, i),
      real_estate: input.real_estate.map((r) =>
        r.liability_index == null || r.liability_index < i
          ? r
          : { ...r, liability_index: r.liability_index === i ? null : r.liability_index - 1 },
      ),
    });

  // Second entry path for a property: track the home behind a mortgage.
  // Reversible — turning it back off removes the linked Real estate entry
  // (rather than leaving a one-way, unremovable link).
  const setTrackProperty = (i: number, on: boolean) => {
    if (on) {
      onChange({
        ...input,
        real_estate: [
          ...input.real_estate,
          newRealEstate(i, `Home (${input.liabilities[i].name})`),
        ],
      });
    } else {
      const linkedIndex = input.real_estate.findIndex((r) => r.liability_index === i);
      if (linkedIndex === -1) return;
      onChange({ ...input, real_estate: removeAt(input.real_estate, linkedIndex) });
    }
  };

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
                help="For a future purchase (e.g. a mortgage on a home bought later): the primary person's age when the debt begins. Leave blank for a debt you already have. The home itself isn't tracked automatically — use 'Track the property as an asset' below (or add it under Real estate) to model its value too."
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
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              {(() => {
                const linked = input.real_estate.find((r) => r.liability_index === i);
                return (
                  <CheckboxField
                    label={
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500">
                        <Home className="h-3 w-3" />
                        {linked ? `Tracked as an asset: ${linked.name}` : "Track the property as an asset"}
                      </span>
                    }
                    checked={!!linked}
                    onChange={(on) => setTrackProperty(i, on)}
                    help="Also track the property behind this loan under Real estate — appreciation, sale with mortgage payoff, basis step-up at death. Turning this off removes that Real estate entry (any values entered there are lost); the loan itself is unaffected."
                  />
                );
              })()}
              <button
                type="button"
                onClick={() => removeLiability(i)}
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
