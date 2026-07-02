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
import { fmtCurrencyCompact, fmtCurrencyExact, makeDeflator } from "../../lib/format";
import { Card } from "../ui/Card";
import { Tooltip } from "../ui/Tooltip";
import { AXIS_TICK, ChartTooltipShell, TooltipRow, agesLabel } from "./chartShared";

const SERIES: { key: keyof Datum; label: string; color: string; help: string }[] = [
  { key: "ss", label: "Social Security", color: "#1e3a5f",
    help: "Gross Social Security benefits (before income tax). Includes COLA adjustments." },
  { key: "rmd", label: "RMDs", color: "#4f46e5",
    help: "Required Minimum Distributions — mandatory withdrawals from tax-deferred accounts starting at age 73 or 75 (SECURE 2.0). Taxed as ordinary income." },
  { key: "td_extra", label: "Tax-deferred withdrawals (beyond RMD)", color: "#818cf8",
    help: "Discretionary withdrawals from 401(k)/IRA beyond the mandatory RMD. Includes Roth conversion amounts." },
  { key: "taxable_wd", label: "Taxable withdrawals", color: "#38bdf8",
    help: "Withdrawals from brokerage accounts. Only the gain portion is taxed (at long-term capital-gains rates if held >1 year)." },
  { key: "roth_wd", label: "Roth withdrawals", color: "#0d9488",
    help: "Tax-free withdrawals from Roth IRA / Roth 401(k). Used last in the withdrawal waterfall to preserve tax-free growth." },
  { key: "hsa_wd", label: "HSA withdrawals", color: "#f59e0b",
    help: "Tax-free HSA withdrawals for qualified medical expenses (Medicare Part B, out-of-pocket costs). Non-medical use is taxed." },
  { key: "cash_wd", label: "Cash withdrawals", color: "#94a3b8",
    help: "Withdrawals from high-yield savings or money market. Used first in the waterfall to avoid unnecessary taxes." },
  { key: "other", label: "Other income", color: "#a78bfa",
    help: "Pensions, part-time income, rental income, and other user-defined income streams." },
  { key: "annuity", label: "Annuity / K-1 income", color: "#c084fc",
    help: "Payouts from deferred annuities once annuitized (basis tax-free, gain ordinary via the exclusion ratio) plus cash distributions from private holdings (K-1 / dividends)." },
];

interface Datum {
  year: number;
  ages: (number | null)[];
  ss: number;
  rmd: number;
  td_extra: number;
  taxable_wd: number;
  roth_wd: number;
  hsa_wd: number;
  cash_wd: number;
  other: number;
  annuity: number;
  need: number;
  shortfall: number;
}

export function IncomeSpendingChart({
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
    return result.years
      .filter((y) => y.phase !== "accumulation")
      .map((y) => {
        const d = mode === "real" ? deflate(y.year) : 1;
        const wd = y.withdrawals_by_type;
        const tdTotal = wd.tax_deferred ?? 0;
        // RMDs are reported inside tax-deferred withdrawals; split them out
        // so the stack never double-counts.
        const rmd = Math.min(y.rmd_total, tdTotal);
        return {
          year: y.year,
          ages: y.ages,
          ss: y.ss_total * d,
          rmd: rmd * d,
          td_extra: Math.max(0, tdTotal - rmd) * d,
          taxable_wd: (wd.taxable ?? 0) * d,
          roth_wd: (wd.roth ?? 0) * d,
          hsa_wd: (wd.hsa ?? 0) * d,
          cash_wd: (wd.cash ?? 0) * d,
          other: y.other_income * d,
          annuity: (y.legacy_distributions ?? 0) * d,
          need:
            (y.spend_goal + y.healthcare_cost + y.debt_payments + y.home_purchase + y.total_tax +
              (y.premiums_paid ?? 0) + (y.gifts_made ?? 0) + (y.legacy_purchases ?? 0)) *
            d,
          shortfall: y.shortfall * d,
        };
      });
  }, [result, mode, inflation]);

  const dollarNote = mode === "real" ? "today's $" : "nominal $";

  return (
    <Card
      title={`Retirement income vs. spending need (${dollarNote})`}
      help={
        <>
          Retirement years only. Bars stack each year's funding sources: gross Social Security,
          RMDs, additional withdrawals by account type, other income, and annuity payouts (Roth
          conversions are excluded — they move money between accounts rather than fund spending).
          The navy line is total spending need: lifestyle goal + healthcare + debt payments + any
          home-purchase down payment + insurance premiums + a planned annuity purchase + taxes.
          Bars can exceed the line when forced income (e.g. RMDs) outruns need — the surplus is
          reinvested in the taxable account.
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
              cursor={{ fill: "rgba(148,163,184,0.08)" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as Datum;
                const totalIncome = SERIES.reduce((s, sr) => s + (d[sr.key] as number), 0);
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
                    {SERIES.filter((s) => (d[s.key] as number) > 0.005).map((s) => (
                      <TooltipRow
                        key={s.key}
                        color={s.color}
                        label={s.label}
                        value={fmtCurrencyExact(d[s.key] as number)}
                      />
                    ))}
                    <div className="mt-1 border-t border-slate-100 pt-1">
                      <TooltipRow label="Total sources" value={fmtCurrencyExact(totalIncome)} strong />
                      <TooltipRow label="Spending need" value={fmtCurrencyExact(d.need)} strong />
                      {d.shortfall > 0.005 && (
                        <TooltipRow label="SHORTFALL" value={fmtCurrencyExact(d.shortfall)} strong />
                      )}
                    </div>
                  </ChartTooltipShell>
                );
              }}
            />
            {SERIES.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                stackId="income"
                fill={s.color}
                name={s.label}
                stroke="#fff"
                strokeWidth={1}
              />
            ))}
            <Line
              type="monotone"
              dataKey="need"
              stroke="#1e3a5f"
              strokeWidth={2}
              dot={false}
              name="Spending need"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        {SERIES.map((s) => (
          <Tooltip key={s.key} content={s.help} wide>
            <span className="flex cursor-help items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
              {s.label.replace(" (beyond RMD)", "")}
            </span>
          </Tooltip>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded bg-brand-900" /> Spending need
        </span>
      </div>
    </Card>
  );
}
