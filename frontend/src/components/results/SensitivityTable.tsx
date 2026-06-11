import type { Metrics, SensitivityRow } from "../../lib/types";
import { fmtCurrency, fmtCurrencyExact } from "../../lib/format";
import { Card } from "../ui/Card";
import { StatusBadge } from "../ui/Badge";
import { InfoTip } from "../ui/Tooltip";

const HEADERS: { label: string; help: string; align?: "right" }[] = [
  { label: "Scenario", help: "Each scenario re-runs the entire plan with one parameter changed and everything else held constant." },
  { label: "Change", help: "The single parameter shock applied in this scenario." },
  { label: "Nest egg (today's $)", help: "Investable assets at retirement under this scenario, in today's dollars.", align: "right" },
  { label: "Ending net worth (today's $)", help: "Net worth at the end of the plan under this scenario, in today's dollars.", align: "right" },
  { label: "Outcome", help: "Funded = spending met through both plan-end ages. Otherwise the age the money runs out." },
];

export function SensitivityTable({
  rows,
  metrics,
}: {
  rows: SensitivityRow[];
  metrics: Metrics;
}) {
  const allRows: SensitivityRow[] = [
    {
      label: "Base plan",
      parameter: "base",
      delta: "—",
      ending_net_worth_real: metrics.ending_net_worth_real,
      nest_egg_real: metrics.nest_egg_at_retirement_real,
      depletion_age: metrics.depletion_age,
      success: metrics.success,
    },
    ...rows,
  ];

  return (
    <Card
      title="Sensitivity analysis"
      help={
        <>
          Stress tests: the full plan is re-simulated with one assumption shocked at a time.
          Because returns are deterministic, this table is the honest substitute for a Monte Carlo
          band — pay most attention to the downside rows (returns −1/−2%, spending +10%, the 2034
          Social Security trust-fund cut, and living to 100).
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
          {allRows.map((r, i) => (
            <tr
              key={`${r.label}-${i}`}
              className={`border-b border-slate-100 last:border-0 ${
                !r.success ? "bg-red-50" : i === 0 ? "bg-slate-50/80 font-medium" : "hover:bg-slate-50"
              }`}
            >
              <td className="px-4 py-2 text-slate-800">{r.label}</td>
              <td className="px-4 py-2 text-slate-500">{r.delta}</td>
              <td
                className="px-4 py-2 text-right tabular-nums text-slate-700"
                title={fmtCurrencyExact(r.nest_egg_real)}
              >
                {fmtCurrency(r.nest_egg_real)}
              </td>
              <td
                className="px-4 py-2 text-right tabular-nums text-slate-700"
                title={fmtCurrencyExact(r.ending_net_worth_real)}
              >
                {fmtCurrency(r.ending_net_worth_real)}
              </td>
              <td className="px-4 py-2">
                {r.success ? (
                  <StatusBadge tone="success">Funded</StatusBadge>
                ) : (
                  <StatusBadge tone="danger">
                    Depleted{r.depletion_age != null ? ` at ${r.depletion_age}` : ""}
                  </StatusBadge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
