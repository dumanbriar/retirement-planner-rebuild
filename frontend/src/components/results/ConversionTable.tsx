import { Check } from "lucide-react";
import type { Metrics, StrategyComparison } from "../../lib/types";
import { CONVERSION_STRATEGY_LABELS, type ConversionStrategy } from "../../lib/types";
import { fmtCurrency, fmtCurrencyExact } from "../../lib/format";
import { Card } from "../ui/Card";
import { InfoTip } from "../ui/Tooltip";

function strategyLabel(s: string): string {
  return CONVERSION_STRATEGY_LABELS[s as ConversionStrategy] ?? s;
}

const HEADERS: { label: string; help: string; align?: "right" }[] = [
  { label: "Strategy", help: "Roth conversion approach simulated over the full plan. 'Fill X%' converts tax-deferred dollars to Roth each retirement year until taxable income reaches the top of that federal bracket." },
  { label: "Ending after-tax wealth", help: "Estate value at plan end in today's dollars, with remaining tax-deferred/HSA balances discounted at the heir tax rate. The comparison metric: higher is better.", align: "right" },
  { label: "Lifetime taxes", help: "All taxes paid over the plan, in today's dollars. Conversions raise taxes now to lower them (and heirs' taxes) later — so the lowest-tax row is not automatically the best row.", align: "right" },
  { label: "Total converted", help: "Cumulative nominal dollars moved from tax-deferred to Roth over the plan.", align: "right" },
  { label: "Depleted", help: "Age at which the portfolio would run out under this strategy, if it does.", align: "right" },
];

export function ConversionTable({
  comparison,
  metrics,
}: {
  comparison: StrategyComparison[];
  metrics: Metrics;
}) {
  if (comparison.length === 0) return null;
  const best = Math.max(...comparison.map((c) => c.ending_after_tax_real));

  return (
    <Card
      title="Roth conversion strategies compared"
      help={
        <>
          Every strategy is a full re-simulation of the plan. With "Auto-optimize" the engine picks
          the strategy with the highest ending after-tax wealth — here that is{" "}
          <span className="font-semibold">{strategyLabel(metrics.chosen_conversion_strategy)}</span>
          . Lifetime taxes alone can mislead: a strategy can cut taxes yet end with less after-tax
          wealth because the tax was paid too early.
        </>
      }
      bodyClassName="p-0 overflow-x-auto"
    >
      <table className="w-full min-w-[640px] text-sm">
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
          {comparison.map((c) => {
            const chosen = c.strategy === metrics.chosen_conversion_strategy;
            return (
              <tr
                key={c.strategy}
                className={`border-b border-slate-100 last:border-0 ${
                  chosen ? "bg-brand-50/70" : "hover:bg-slate-50"
                }`}
              >
                <td className="px-4 py-2.5 font-medium text-slate-800">
                  <span className="inline-flex items-center gap-2">
                    {strategyLabel(c.strategy)}
                    {chosen && (
                      <span className="inline-flex items-center gap-1 rounded bg-brand-900 px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-white">
                        <Check className="h-3 w-3" /> chosen
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
                <td
                  className="px-4 py-2.5 text-right tabular-nums text-slate-700"
                  title={fmtCurrencyExact(c.total_converted)}
                >
                  {fmtCurrency(c.total_converted)}
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
        const chosen = comparison.find((c) => c.strategy === metrics.chosen_conversion_strategy);
        const noneRow = comparison.find((c) => c.strategy === "none");
        if (!chosen || !noneRow || chosen.strategy === "none") return null;
        const delta = chosen.ending_after_tax_real - noneRow.ending_after_tax_real;
        if (delta <= 100) return null;
        return (
          <p className="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
            {strategyLabel(chosen.strategy)} produced{" "}
            <span className="font-medium text-slate-700">{fmtCurrency(delta)}</span> more
            after-tax wealth than doing nothing by converting{" "}
            <span className="font-medium text-slate-700">{fmtCurrency(chosen.total_converted)}</span>{" "}
            total — pre-paying tax on deferred dollars at today's lower rates instead of
            heirs' or future RMD-forced rates.
          </p>
        );
      })()}
    </Card>
  );
}
