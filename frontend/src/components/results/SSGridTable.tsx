import type { Metrics, SSGridCell } from "../../lib/types";
import { fmtCurrencyCompact, fmtCurrencyExact } from "../../lib/format";
import { Card } from "../ui/Card";
import { Tooltip } from "../ui/Tooltip";

/** teal heat scale: stronger = higher ending after-tax wealth. */
function heat(norm: number): string {
  return `rgba(13, 148, 136, ${0.06 + norm * 0.5})`;
}

export function SSGridTable({
  grid,
  metrics,
  personNames,
}: {
  grid: SSGridCell[];
  metrics: Metrics;
  personNames: string[];
}) {
  if (grid.length === 0) return null;

  const twoPersons = grid[0].claim_ages.length > 1;
  const p1Ages = [...new Set(grid.map((c) => c.claim_ages[0]))].sort((a, b) => a - b);
  const p2Ages = twoPersons
    ? [...new Set(grid.map((c) => c.claim_ages[1]))].sort((a, b) => a - b)
    : [0];

  const byKey = new Map<string, SSGridCell>();
  for (const c of grid) byKey.set(c.claim_ages.join("-"), c);

  const values = grid.map((c) => c.ending_after_tax_real);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const norm = (v: number) => (max > min ? (v - min) / (max - min) : 0.5);

  const chosenKey = metrics.ss_claim_ages.join("-");
  const p1 = personNames[0] ?? "Person 1";
  const p2 = personNames[1] ?? "Person 2";

  const cell = (key: string) => {
    const c = byKey.get(key);
    if (!c) return <td key={key} className="p-1 text-center text-slate-300">—</td>;
    const chosen = key === chosenKey;
    return (
      <td key={key} className="p-0.5">
        <Tooltip
          className="w-full"
          content={
            <>
              {twoPersons
                ? `${p1} claims at ${c.claim_ages[0]}, ${p2} at ${c.claim_ages[1]}`
                : `${p1} claims at ${c.claim_ages[0]}`}
              <div>Ending after-tax wealth: {fmtCurrencyExact(c.ending_after_tax_real)}</div>
              {c.depletion_age != null && <div>Depletes at age {c.depletion_age}</div>}
              {chosen && <div className="font-semibold">Selected by the optimizer</div>}
            </>
          }
        >
          <span
            className={`block w-full cursor-help rounded px-1.5 py-1.5 text-center text-[11px] tabular-nums ${
              chosen ? "font-bold text-brand-950 ring-2 ring-inset ring-brand-900" : "text-slate-700"
            } ${c.depletion_age != null ? "!bg-red-100 text-red-700" : ""}`}
            style={c.depletion_age == null ? { backgroundColor: heat(norm(c.ending_after_tax_real)) } : undefined}
          >
            {fmtCurrencyCompact(c.ending_after_tax_real)}
          </span>
        </Tooltip>
      </td>
    );
  };

  return (
    <Card
      title="Social Security claiming-age grid"
      help={
        <>
          Each cell is a full plan re-simulation with those claiming ages, colored by ending
          after-tax wealth in today's dollars (deeper teal = better; red = portfolio depletes). The
          outlined cell is the combination the optimizer selected:{" "}
          {metrics.ss_claim_ages.map((a, i) => `${personNames[i] ?? `P${i + 1}`} at ${a}`).join(", ")}.
          Benefit adjustments use the exact statutory monthly reduction/credit formulas.
        </>
      }
      bodyClassName="overflow-x-auto"
    >
      <table className="mx-auto border-separate" style={{ borderSpacing: 0 }}>
        <thead>
          {twoPersons && (
            <tr>
              <th />
              <th
                colSpan={p2Ages.length}
                className="pb-1 text-center text-xs font-medium text-slate-500"
              >
                {p2} claiming age →
              </th>
            </tr>
          )}
          <tr>
            <th className="pr-2 text-right text-xs font-medium text-slate-500">
              {twoPersons ? `${p1} ↓` : `${p1} claiming age`}
            </th>
            {twoPersons &&
              p2Ages.map((a) => (
                <th key={a} className="px-1 pb-1 text-center text-xs font-semibold text-slate-600">
                  {a}
                </th>
              ))}
          </tr>
        </thead>
        <tbody>
          {twoPersons ? (
            p1Ages.map((a1) => (
              <tr key={a1}>
                <th className="pr-2 text-right text-xs font-semibold text-slate-600">{a1}</th>
                {p2Ages.map((a2) => cell(`${a1}-${a2}`))}
              </tr>
            ))
          ) : (
            <>
              <tr>
                <th />
                {p1Ages.map((a) => (
                  <th key={a} className="px-1 pb-1 text-center text-xs font-semibold text-slate-600">
                    {a}
                  </th>
                ))}
              </tr>
              <tr>
                <th />
                {p1Ages.map((a) => cell(String(a)))}
              </tr>
            </>
          )}
        </tbody>
      </table>
    </Card>
  );
}
