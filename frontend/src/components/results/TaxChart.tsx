import { useMemo } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DisplayMode, PlanResult } from "../../lib/types";
import { fmtCurrencyCompact, fmtCurrencyExact, fmtPct, makeDeflator } from "../../lib/format";
import { Card } from "../ui/Card";
import { AXIS_TICK, ChartTooltipShell, TooltipRow, agesLabel } from "./chartShared";

interface Datum {
  year: number;
  ages: (number | null)[];
  tax: number;
  rate: number; // percent (0-100 scale for the right axis)
  federal: number;
  state: number;
  ltcg: number;
  niit: number;
  irmaa: number;
}

export function TaxChart({
  result,
  mode,
  inflation,
  personNames,
}: {
  result: PlanResult;
  mode: DisplayMode;
  inflation: number;
  personNames: string[];
}) {
  const data: Datum[] = useMemo(() => {
    const baseYear = result.years[0]?.year ?? new Date().getFullYear();
    const deflate = makeDeflator(baseYear, inflation);
    return result.years.map((y) => {
      const d = mode === "real" ? deflate(y.year) : 1;
      return {
        year: y.year,
        ages: y.ages,
        tax: y.total_tax * d,
        rate: y.effective_rate * 100,
        federal: y.federal_tax * d,
        state: y.state_tax * d,
        ltcg: y.ltcg_tax * d,
        niit: y.niit * d,
        irmaa: y.irmaa_surcharge * d,
      };
    });
  }, [result, mode, inflation]);

  const dollarNote = mode === "real" ? "today's $" : "nominal $";

  return (
    <Card
      title={`Taxes by year (${dollarNote})`}
      help={
        <>
          Bars: total tax each year — federal income tax (including the capital-gains layer), NIIT,
          state tax, and penalties. Line (right axis): effective rate = total tax ÷ AGI. Watch for
          the RMD ramp late in the plan and the conversion-era bump if Roth conversions are active.
          IRMAA surcharges appear in healthcare costs, not here.
        </>
      }
      bodyClassName="pt-2"
    >
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="year" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "#cbd5e1" }} />
            <YAxis
              yAxisId="tax"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              tickFormatter={fmtCurrencyCompact}
              width={58}
            />
            <YAxis
              yAxisId="rate"
              orientation="right"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
              width={40}
            />
            <RTooltip
              cursor={{ fill: "rgba(148,163,184,0.08)" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as Datum;
                return (
                  <ChartTooltipShell
                    title={
                      <>
                        {label}{" "}
                        <span className="font-normal text-slate-400">
                          {agesLabel(personNames, d.ages)}
                        </span>
                      </>
                    }
                  >
                    <TooltipRow color="#335e89" label="Total tax" value={fmtCurrencyExact(d.tax)} strong />
                    {d.federal > 0.005 && (
                      <TooltipRow label="· Federal (incl. LTCG)" value={fmtCurrencyExact(d.federal)} />
                    )}
                    {d.ltcg > 0.005 && (
                      <TooltipRow label="· of which LTCG layer" value={fmtCurrencyExact(d.ltcg)} />
                    )}
                    {d.niit > 0.005 && <TooltipRow label="· NIIT" value={fmtCurrencyExact(d.niit)} />}
                    {d.state > 0.005 && <TooltipRow label="· State" value={fmtCurrencyExact(d.state)} />}
                    <TooltipRow color="#0d9488" label="Effective rate" value={fmtPct(d.rate / 100, 2)} />
                  </ChartTooltipShell>
                );
              }}
            />
            <Bar yAxisId="tax" dataKey="tax" fill="#335e89" fillOpacity={0.8} name="Total tax" />
            <Line
              yAxisId="rate"
              type="monotone"
              dataKey="rate"
              stroke="#0d9488"
              strokeWidth={2}
              dot={false}
              name="Effective rate"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-brand-600/80" /> Total tax (left)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded bg-teal-600" /> Effective rate (right)
        </span>
      </div>
    </Card>
  );
}
