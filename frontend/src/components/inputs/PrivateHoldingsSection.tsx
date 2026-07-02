import { Plus, Trash2 } from "lucide-react";
import type { DistributionKind, PrivateHolding } from "../../lib/types";
import { DISTRIBUTION_KIND_LABELS } from "../../lib/types";
import { newPrivateHolding } from "../../lib/sample";
import {
  NumberField,
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

type LiquidityMode = "none" | "sale" | "divest";

const MODE_OPTIONS: { value: LiquidityMode; label: string }[] = [
  { value: "none", label: "Hold to death (basis step-up)" },
  { value: "sale", label: "One-time sale" },
  { value: "divest", label: "Phased sale (% per year)" },
];

function modeOf(h: PrivateHolding): LiquidityMode {
  if (h.divest_start_age != null) return "divest";
  if (h.sale_age != null) return "sale";
  return "none";
}

export function PrivateHoldingsSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));
  const set = (i: number, patch: Partial<PrivateHolding>) =>
    onChange({ ...input, private_holdings: updateAt(input.private_holdings, i, patch) });

  const setMode = (i: number, h: PrivateHolding, mode: LiquidityMode) => {
    if (mode === "none") {
      set(i, { sale_age: null, divest_start_age: null, annual_divest_pct: 0 });
    } else if (mode === "sale") {
      set(i, { sale_age: h.sale_age ?? 65, divest_start_age: null, annual_divest_pct: 0 });
    } else {
      set(i, {
        sale_age: null,
        divest_start_age: h.divest_start_age ?? 65,
        annual_divest_pct: h.annual_divest_pct || 0.1,
      });
    }
  };

  return (
    <div className="space-y-3">
      {input.private_holdings.length === 0 && (
        <p className="text-xs text-slate-400">
          None — add private company shares or a partnership interest (illiquid).
        </p>
      )}
      {input.private_holdings.map((h, i) => {
        const e = (f: string) => errors[`private_holdings.${i}.${f}`];
        const mode = modeOf(h);
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
              <SelectField
                label="Liquidity plan"
                value={mode}
                onChange={(m) => setMode(i, h, m)}
                options={MODE_OPTIONS}
                help="How (if at all) the shares eventually convert to cash. Either a one-time sale or a phased sale — not both."
              />
              {mode === "sale" && (
                <NumberField
                  label="Sell at age"
                  value={h.sale_age ?? 65}
                  onChange={(sale_age) => set(i, { sale_age })}
                  min={18}
                  max={100}
                  error={e("sale_age")}
                  help="The entire holding is sold at this age; the gain over basis is taxed as a long-term capital gain and the proceeds join the portfolio."
                />
              )}
              {mode === "divest" && (
                <>
                  <NumberField
                    label="Start selling at age"
                    value={h.divest_start_age ?? 65}
                    onChange={(divest_start_age) => set(i, { divest_start_age })}
                    min={18}
                    max={100}
                    error={e("divest_start_age")}
                    help="Age at which the phased sale schedule begins."
                  />
                  <PercentField
                    label="% of stake sold / yr"
                    value={h.annual_divest_pct}
                    onChange={(annual_divest_pct) => set(i, { annual_divest_pct })}
                    min={0}
                    max={100}
                    error={e("annual_divest_pct")}
                    help="Fraction of the ORIGINAL holding value sold each year (e.g. 10%/yr), until fully divested. Each year's gain over the pro-rated basis is a long-term capital gain."
                  />
                </>
              )}
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
