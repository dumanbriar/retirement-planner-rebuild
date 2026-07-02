import { Plus, Trash2 } from "lucide-react";
import type { RealEstate } from "../../lib/types";
import { newRealEstate } from "../../lib/sample";
import {
  CheckboxField,
  NumberField,
  OptionalNumberField,
  PercentField,
  SelectField,
  TextField,
} from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";
import { ModelingDisclosure } from "./ModelingDisclosure";

export function RealEstateSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));
  const mortgageOptions = [
    { value: -1, label: "None" },
    ...input.liabilities.map((l, i) => ({ value: i, label: l.name || `Liability ${i + 1}` })),
  ];
  const set = (i: number, patch: Partial<RealEstate>) =>
    onChange({ ...input, real_estate: updateAt(input.real_estate, i, patch) });

  return (
    <div className="space-y-3">
      {input.real_estate.length === 0 && (
        <p className="text-xs text-slate-400">
          None — add a home or investment property (illiquid; appreciates until sold or inherited).
        </p>
      )}
      {input.real_estate.map((r, i) => {
        const e = (f: string) => errors[`real_estate.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
              <TextField
                label="Name"
                value={r.name}
                onChange={(name) => set(i, { name })}
                error={e("name")}
                className="col-span-2"
              />
              {input.persons.length > 1 && (
                <SelectField
                  label="Owner"
                  value={r.owner}
                  onChange={(owner) => set(i, { owner })}
                  options={ownerOptions}
                  error={e("owner")}
                />
              )}
              <NumberField
                label="Market value"
                value={r.value}
                onChange={(value) => set(i, { value })}
                min={0}
                prefix="$"
                error={e("value")}
                help="Today's market value. Illiquid: the model never sells it to cover spending — only the optional sale below turns it into cash."
              />
              <NumberField
                label="Cost basis"
                value={r.basis}
                onChange={(basis) => set(i, { basis })}
                min={0}
                prefix="$"
                error={e("basis")}
                help="Purchase price plus improvements. A sale realizes value over basis as a long-term capital gain (primary residences exclude $250k/$500k under IRC §121); held to death the basis steps up (IRC §1014)."
              />
              <PercentField
                label="Appreciation"
                value={r.appreciation}
                onChange={(appreciation) => set(i, { appreciation })}
                min={-10}
                max={20}
                error={e("appreciation")}
                help="Assumed annual appreciation of the property's value."
              />
              <OptionalNumberField
                label="Sell at age"
                value={r.sale_age ?? null}
                onChange={(sale_age) => set(i, { sale_age })}
                min={18}
                max={100}
                placeholder="never"
                error={e("sale_age")}
                help="Optional: sell the property at this age. Any linked mortgage is paid off from the proceeds, the taxable gain (after the §121 exclusion for a primary home) is realized as LTCG, and the net cash joins the portfolio. Leave blank to hold to death."
              />
              {input.liabilities.length > 0 && (
                <SelectField
                  label="Linked mortgage"
                  value={r.liability_index ?? -1}
                  onChange={(v) => set(i, { liability_index: v === -1 ? null : v })}
                  options={mortgageOptions}
                  error={e("liability_index")}
                  help="The loan on this property (from Liabilities). Its remaining balance is paid off from the sale proceeds. The debt itself is only counted once, in Liabilities — linking never double-counts it."
                />
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-4">
                <CheckboxField
                  label="Primary residence"
                  checked={r.is_primary}
                  onChange={(is_primary) => set(i, { is_primary })}
                  help="A primary residence excludes up to $250k (single) / $500k (married filing jointly) of gain at sale (IRC §121). Uncheck for a rental / investment property — the full gain is then taxable."
                />
                <CheckboxField
                  label="Count in net worth"
                  checked={r.include_in_net_worth}
                  onChange={(include_in_net_worth) => set(i, { include_in_net_worth })}
                  help="Uncheck to leave the home out of net worth and total assets (a common conservative choice for the roof over your head). Sale proceeds and the at-death legacy are still modeled."
                />
                <ModelingDisclosure assetKey="realestate" />
              </div>
              <button
                type="button"
                onClick={() => onChange({ ...input, real_estate: removeAt(input.real_estate, i) })}
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
        onClick={() => onChange({ ...input, real_estate: [...input.real_estate, newRealEstate()] })}
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add property
      </button>
    </div>
  );
}
