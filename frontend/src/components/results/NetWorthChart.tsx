import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AccountType, DisplayMode, PlanResult } from "../../lib/types";
import { ACCOUNT_TYPE_SHORT } from "../../lib/types";
import { fmtCurrencyCompact, fmtCurrencyExact, makeDeflator } from "../../lib/format";
import { Card } from "../ui/Card";
import { AXIS_TICK, ChartTooltipShell, TooltipRow, TYPE_COLORS, agesLabel } from "./chartShared";

const TYPES: AccountType[] = ["tax_deferred", "roth", "taxable", "hsa", "cash"];

interface Datum {
  year: number;
  ages: (number | null)[];
  tax_deferred: number;
  roth: number;
  taxable: number;
  hsa: number;
  cash: number;
  liabilities: number;
  net_worth: number;
}

export function NetWorthChart({
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
      const byType: Record<AccountType, number> = {
        tax_deferred: 0,
        roth: 0,
        taxable: 0,
        hsa: 0,
        cash: 0,
      };
      for (const a of y.accounts) byType[a.type] += a.end_balance;
      return {
        year: y.year,
        ages: y.ages,
        tax_deferred: byType.tax_deferred * d,
        roth: byType.roth * d,
        taxable: byType.taxable * d,
        hsa: byType.hsa * d,
        cash: byType.cash * d,
        liabilities: -y.total_liabilities * d,
        net_worth: mode === "real" ? y.net_worth_real : y.net_worth,
      };
    });
  }, [result, mode, inflation]);

  const dollarNote = mode === "real" ? "today's $" : "nominal $";

  return (
    <Card
      title={`Net worth by account type (${dollarNote})`}
      help={
        <>
          End-of-year balances from the year-by-year audit, stacked by account type, with total
          liabilities as the red line below zero. Net worth = total assets − liabilities.{" "}
          {mode === "real"
            ? `Deflated to today's purchasing power at ${(inflation * 100).toFixed(1)}% inflation.`
            : "Raw nominal dollars — what statements will actually show."}{" "}
          The dashed marker is the first full retirement year.
        </>
      }
      bodyClassName="pt-2"
    >
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="year" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "#cbd5e1" }} />
            <YAxis
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              tickFormatter={fmtCurrencyCompact}
              width={58}
            />
            <RTooltip
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
                    {TYPES.map((t) => (
                      <TooltipRow
                        key={t}
                        color={TYPE_COLORS[t]}
                        label={ACCOUNT_TYPE_SHORT[t]}
                        value={fmtCurrencyExact(d[t])}
                      />
                    ))}
                    <TooltipRow color="#f87171" label="Liabilities" value={fmtCurrencyExact(d.liabilities)} />
                    <div className="mt-1 border-t border-slate-100 pt-1">
                      <TooltipRow label="Net worth" value={fmtCurrencyExact(d.net_worth)} strong />
                    </div>
                  </ChartTooltipShell>
                );
              }}
            />
            {TYPES.map((t) => (
              <Area
                key={t}
                type="monotone"
                dataKey={t}
                stackId="assets"
                stroke={TYPE_COLORS[t]}
                fill={TYPE_COLORS[t]}
                fillOpacity={0.55}
                strokeWidth={1}
                name={ACCOUNT_TYPE_SHORT[t]}
              />
            ))}
            <Line
              type="monotone"
              dataKey="liabilities"
              stroke="#f87171"
              strokeWidth={1.5}
              dot={false}
              name="Liabilities"
            />
            <ReferenceLine
              x={result.metrics.retirement_year}
              stroke="#1e3a5f"
              strokeDasharray="4 3"
              label={{
                value: "Retirement",
                position: "insideTopLeft",
                fontSize: 11,
                fill: "#1e3a5f",
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        {TYPES.map((t) => (
          <span key={t} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: TYPE_COLORS[t] }} />
            {ACCOUNT_TYPE_SHORT[t]}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded bg-red-400" /> Liabilities
        </span>
      </div>
    </Card>
  );
}
