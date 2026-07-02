import { Plus, Trash2 } from "lucide-react";
import type { DistributionKind, PrivateHolding } from "../../lib/types";
import { DISTRIBUTION_KIND_LABELS } from "../../lib/types";
import { newPrivateHolding } from "../../lib/sample";
import {
  NumberField,
  OptionalNumberField,
  PercentField,
  SelectField,
  TextField,
} from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";
import { ModelingDisclosure } from "./ModelingDisclosure";
import { BequestToggle } from "./BequestToggle";

const KIND_OPTIONS = (Object.keys(DISTRIBUTION_KIND_LABELS) as DistributionKind[]).map(
  (k) => ({ value: k, label: DISTRIBUTION_KIND_LABELS[k] }),
);

export function PrivateHoldingsSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));
  const set = (i: number, patch: Partial<PrivateHolding>) =>
    onChange({ ...input, private_holdings: updateAt(input.private_holdings, i, patch) });

  return (
    <div className="space-y-3">
      {input.private_holdings.length === 0 && (
        <p className="text-xs text-slate-400">
          None — add private company shares or a partnership interest (illiquid).
        </p>
      )}
      {input.private_holdings.map((h, i) => {
        const e = (f: string) => errors[`private_holdings.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
              <TextField
                label="Name"
                value={h.name}
                onChange={(name) => set(i, { name })}
                error={e("name")}
                className="col-span-2"
              />
              {input.persons.length > 1 && (
                <SelectField
                  label="Owner"
                  value={h.owner}
                  onChange={(owner) => set(i, { owner })}
                  options={ownerOptions}
                  error={e("owner")}
                />
              )}
              <NumberField
                label="Value"
                value={h.value}
                onChange={(value) => set(i, { value })}
                min={0}
                prefix="$"
                error={e("value")}
                help="Current fair market value of the shares. Illiquid: the model never sells them to cover spending — only the optional liquidity event turns them into cash."
              />
              <NumberField
                label="Cost basis"
                value={h.basis}
                onChange={(basis) => set(i, { basis })}
                min={0}
                prefix="$"
                error={e("basis")}
                help="What the shares cost you. A sale realizes the value over basis as a long-term capital gain; held to death the basis steps up and heirs owe no income tax (IRC §1014)."
              />
              <PercentField
                label="Growth rate"
                value={h.growth_rate}
                onChange={(growth_rate) => set(i, { growth_rate })}
                min={-10}
                max={20}
                error={e("growth_rate")}
                help="Assumed annual growth of the company's value. Distributions are paid out of this growth."
              />
              <NumberField
                label="Distribution / yr"
                value={h.annual_distribution}
                onChange={(annual_distribution) => set(i, { annual_distribution })}
                min={0}
                prefix="$"
                error={e("annual_distribution")}
                help="Optional level annual cash distribution (K-1 / dividend) the business pays you, taxed in full each year. 0 if the business retains its earnings."
              />
              <SelectField
                label="Distribution tax"
                value={h.distribution_kind}
                onChange={(distribution_kind) => set(i, { distribution_kind })}
                options={KIND_OPTIONS}
                error={e("distribution_kind")}
                help="Pass-through (S-corp/partnership K-1) income is ordinary; C-corp dividends are typically qualified (0/15/20% rates)."
              />
              <OptionalNumberField
                label="Sell at age"
                value={h.sale_age ?? null}
                onChange={(sale_age) => set(i, { sale_age })}
                min={18}
                max={100}
                placeholder="never"
                error={e("sale_age")}
                help="Optional liquidity event: the entire holding is sold at this age; the gain over basis is taxed as a long-term capital gain and the proceeds join the portfolio. Leave blank to hold to death (basis step-up)."
              />
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-4">
                <BequestToggle
                  value={h.beneficiary}
                  onChange={(beneficiary) => set(i, { beneficiary })}
                />
                <ModelingDisclosure assetKey="private" />
              </div>
              <button
                type="button"
                onClick={() =>
                  onChange({ ...input, private_holdings: removeAt(input.private_holdings, i) })
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
          onChange({ ...input, private_holdings: [...input.private_holdings, newPrivateHolding()] })
        }
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add private holding
      </button>
    </div>
  );
}
