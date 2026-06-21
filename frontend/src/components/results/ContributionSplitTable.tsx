import { Check } from "lucide-react";
import type { ContributionSplitCell, Metrics } from "../../lib/types";
import { fmtCurrency, fmtCurrencyExact } from "../../lib/format";
import { Card } from "../ui/Card";
import { InfoTip } from "../ui/Tooltip";

function splitLabel(rothPct: number[], names: string[]): string {
  if (rothPct.length === 1) return `${Math.round(rothPct[0] * 100)}% Roth`;
  return rothPct
    .map((p, i) => `${names[i] ?? `P${i + 1}`} ${Math.round(p * 100)}%`)
    .join("  ·  ");
}

const sameSplit = (a: number[], b: number[]): boolean =>
  a.length === b.length &&
  a.every((x, i) => Math.round(x * 100) === Math.round((b[i] ?? -1) * 100));

const HEADERS: { label: string; help: string; align?: "right" }[] = [
  {
    label: "Household % to Roth",
    help: "Share of the household's total annual Traditional + Roth contributions routed to Roth; the remainder goes to Traditional (pre-tax). Each row is a full re-simulation. Because you file jointly, only the household ratio is modeled.",
  },
  {
    label: "Ending after-tax wealth",
    help: "Estate value at plan end in today's dollars, with remaining tax-deferred/HSA balances discounted at the heir tax rate. The comparison metric: higher is better.",
    align: "right",
  },
  {
    label: "Lifetime taxes",
    help: "All taxes paid over the plan, in today's dollars (including working-year income tax on wages once salary is modeled).",
    align: "right",
  },
  {
    label: "Depleted",
    help: "Age at which the portfolio would run out under this split, if it does.",
    align: "right",
  },
];

export function ContributionSplitTable({
  cells,
  metrics,
  personNames,
}: {
  cells: ContributionSplitCell[];
  metrics: Metrics;
  personNames: string[];
}) {
  if (cells.length === 0) return null;

  const chosen = metrics.chosen_contribution_split;
  const best = Math.max(...cells.map((c) => c.ending_after_tax_real));
  const rows = [...cells].sort((a, b) => b.ending_after_tax_real - a.ending_after_tax_real);
  const chosenCell = cells.find((c) => sameSplit(c.roth_pct, chosen));
  const currentCell = cells.find((c) => c.is_current);

  return (
    <Card
      title="Traditional vs Roth contribution split — suggestion"
      help={
        <>
          Advisory only: your plan above still models the contributions you entered. Each row is a
          full re-simulation at a different household Traditional/Roth split, holding the total
          constant. Traditional's tax deduction — valued at the real marginal bracket from salary —
          is reinvested in a taxable account ("invest the tax savings"), so the comparison is
          equal-cost. The highest ending after-tax wealth is at{" "}
          <span className="font-semibold">{splitLabel(chosen, personNames)}</span> to Roth.
        </>
      }
      bodyClassName="p-0 overflow-x-auto"
    >
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            {HEADERS.map((h) => (
              <th
                key={h.label}
                className={`px-4 py-2.5 font-medium ${h.align === "right" ? "text-right" : "text-left"}`}
              >
                <span className="inline-flex items-center gap-1">
                  {h.label}
                  <InfoTip content={h.help} wide />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const isChosen = sameSplit(c.roth_pct, chosen);
            return (
              <tr
                key={c.roth_pct.join("-")}
                className={`border-b border-slate-100 last:border-0 ${
                  isChosen ? "bg-brand-50/70" : "hover:bg-slate-50"
                }`}
              >
                <td className="px-4 py-2.5 font-medium text-slate-800">
                  <span className="inline-flex flex-wrap items-center gap-2">
                    {splitLabel(c.roth_pct, personNames)}
                    {isChosen && (
                      <span className="inline-flex items-center gap-1 rounded bg-brand-900 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-white">
                        <Check className="h-3 w-3" /> suggested
                      </span>
                    )}
                    {c.is_current && (
                      <span className="inline-flex items-center rounded bg-slate-200 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                        current
                      </span>
                    )}
                  </span>
                </td>
                <td
                  className={`px-4 py-2.5 text-right tabular-nums ${
                    c.ending_after_tax_real === best ? "font-semibold text-teal-700" : "text-slate-700"
                  }`}
                  title={fmtCurrencyExact(c.ending_after_tax_real)}
                >
                  {fmtCurrency(c.ending_after_tax_real)}
                </td>
                <td
                  className="px-4 py-2.5 text-right tabular-nums text-slate-700"
                  title={fmtCurrencyExact(c.lifetime_taxes_real)}
                >
                  {fmtCurrency(c.lifetime_taxes_real)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {c.depletion_age != null ? (
                    <span className="font-semibold text-red-600">age {c.depletion_age}</span>
                  ) : (
                    <span className="text-slate-400">never</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {(() => {
        if (!chosenCell || !currentCell || chosenCell === currentCell) return null;
        const delta = chosenCell.ending_after_tax_real - currentCell.ending_after_tax_real;
        if (delta <= 100) return null;
        return (
          <p className="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
            Shifting from your current split ({splitLabel(currentCell.roth_pct, personNames)}) to{" "}
            <span className="font-medium text-slate-700">
              {splitLabel(chosenCell.roth_pct, personNames)}
            </span>{" "}
            adds <span className="font-medium text-slate-700">{fmtCurrency(delta)}</span> of ending
            after-tax wealth in today's dollars.
          </p>
        );
      })()}
    </Card>
  );
}
