import { useMemo } from "react";
import type { DisplayMode, PlanResult, YearRow } from "../../lib/types";
import { fmtCurrency, fmtCurrencyExact, fmtPct, makeDeflator } from "../../lib/format";
import { Card } from "../ui/Card";
import { InfoTip } from "../ui/Tooltip";

interface Col {
  label: string;
  help: string;
  align?: "right";
  value: (y: YearRow, d: number) => string;
  exact?: (y: YearRow, d: number) => string;
}

function money(get: (y: YearRow) => number): Pick<Col, "value" | "exact" | "align"> {
  return {
    align: "right",
    value: (y, d) => {
      const v = get(y) * d;
      return Math.abs(v) < 0.005 ? "·" : fmtCurrency(v);
    },
    exact: (y, d) => fmtCurrencyExact(get(y) * d),
  };
}

export function YearTable({
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
  const baseYear = result.years[0]?.year ?? new Date().getFullYear();
  const deflate = useMemo(() => makeDeflator(baseYear, inflation), [baseYear, inflation]);
  const dollarNote = mode === "real" ? "today's $" : "nominal $";

  const cols: Col[] = useMemo(
    () => [
      {
        label: "Year",
        help: "Calendar year. The first row is the current year.",
        value: (y) => String(y.year),
      },
      {
        label: "Ages",
        help: `Ages at year end (${personNames.join(" / ")}). Blank once deceased.`,
        value: (y) => y.ages.map((a) => (a == null ? "—" : String(a))).join(" / "),
      },
      {
        label: "Phase",
        help: "Accumulation while anyone is still working and contributing; retirement once drawdown begins.",
        value: (y) => (y.phase === "accumulation" ? "accum" : "retire"),
      },
      { label: "Contrib.", help: "New money contributed to accounts this year (excludes reinvested surplus / Social Security, shown under their own columns).", ...money((y) => y.accounts.reduce((s, a) => s + a.contribution, 0) - y.surplus_reinvested) },
      { label: "Growth", help: "Investment growth across all accounts, net of any pre-retirement dividend/interest tax drag.", ...money((y) => y.accounts.reduce((s, a) => s + a.growth, 0)) },
      { label: "Spending", help: "Lifestyle spending goal for the year (the inflated annual spending input). Excludes healthcare, debt, and taxes, shown separately.", ...money((y) => y.spend_goal) },
      { label: "Healthcare", help: "Net healthcare cost: ACA premiums minus subsidies before 65; Medicare Part B (incl. IRMAA) plus other premiums/OOP after 65.", ...money((y) => y.healthcare_cost) },
      { label: "Debt pay", help: "Liability payments made this year.", ...money((y) => y.debt_payments) },
      { label: "Home buy", help: "One-time down payment / purchase cash drawn from the portfolio when a future mortgage starts. The home itself is not tracked as an asset.", ...money((y) => y.home_purchase) },
      { label: "Soc. Sec.", help: "Gross household Social Security benefits received.", ...money((y) => y.ss_total) },
      { label: "Other inc.", help: "Pensions, annuities, rentals, part-time work.", ...money((y) => y.other_income) },
      { label: "RMD", help: "Required minimum distributions (start at 73 or 75 by birth year; IRS Uniform Lifetime Table). Included in the tax-deferred withdrawal column.", ...money((y) => y.rmd_total) },
      { label: "Wd cash", help: "Withdrawals from cash/HYSA accounts (first in the withdrawal order).", ...money((y) => y.withdrawals_by_type.cash ?? 0) },
      { label: "Wd taxable", help: "Withdrawals from taxable brokerage (realizes capital gains pro-rata to the unrealized gain).", ...money((y) => y.withdrawals_by_type.taxable ?? 0) },
      { label: "Wd tax-def", help: "Withdrawals from 401(k)/IRA, taxed as ordinary income. Includes RMDs.", ...money((y) => y.withdrawals_by_type.tax_deferred ?? 0) },
      { label: "Wd Roth", help: "Tax-free Roth withdrawals (drawn late in the order to preserve tax-free growth).", ...money((y) => y.withdrawals_by_type.roth ?? 0) },
      { label: "Wd HSA", help: "HSA withdrawals, applied to qualified medical costs first (tax-free).", ...money((y) => y.withdrawals_by_type.hsa ?? 0) },
      { label: "Roth conv.", help: "Dollars converted from tax-deferred to Roth this year (taxable as ordinary income now, tax-free growth afterward).", ...money((y) => y.roth_conversion) },
      { label: "AGI", help: "Adjusted gross income: ordinary income + taxable Social Security + dividends/interest + realized gains + conversions.", ...money((y) => y.agi) },
      { label: "Total tax", help: "Federal + LTCG layer + NIIT + state + penalties for the year.", ...money((y) => y.total_tax) },
      {
        label: "Eff. rate",
        help: "Effective tax rate = total tax ÷ AGI.",
        align: "right",
        value: (y) => (y.effective_rate === 0 ? "·" : fmtPct(y.effective_rate)),
        exact: (y) => fmtPct(y.effective_rate, 3),
      },
      {
        label: "Net worth",
        help: "Total assets minus liabilities at year end. Follows the today's-$/nominal toggle.",
        align: "right",
        value: (y) => fmtCurrency(mode === "real" ? y.net_worth_real : y.net_worth),
        exact: (y) => fmtCurrencyExact(mode === "real" ? y.net_worth_real : y.net_worth),
      },
    ],
    [mode, personNames],
  );

  return (
    <Card
      title={`Year-by-year audit (${dollarNote})`}
      help={
        <>
          Every year of the plan, row by row — the on-screen version of the audit workbook. Cash
          flows follow the toggle ({dollarNote}); hover any cell for the unrounded value. Rows
          tinted red have a spending shortfall (the plan failed to fund that year). A dot (·) means
          exactly zero.
        </>
      }
      bodyClassName="p-0"
    >
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full min-w-[1600px] text-xs">
          <thead className="sticky top-0 z-10 bg-slate-50 shadow-[0_1px_0_#e2e8f0]">
            <tr className="text-[11px] uppercase tracking-wide text-slate-500">
              {cols.map((c) => (
                <th
                  key={c.label}
                  className={`whitespace-nowrap px-2.5 py-2 font-medium ${
                    c.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  <span className="inline-flex items-center gap-0.5">
                    {c.label}
                    <InfoTip content={c.help} wide />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.years.map((y) => {
              const d = mode === "real" ? deflate(y.year) : 1;
              const shortfall = y.shortfall > 0.005;
              return (
                <tr
                  key={y.year}
                  className={`border-b border-slate-100 last:border-0 ${
                    shortfall
                      ? "bg-red-50 text-red-800"
                      : y.phase === "accumulation"
                        ? "text-slate-500"
                        : "text-slate-700"
                  } hover:bg-brand-50/40`}
                  title={shortfall ? `Shortfall: ${fmtCurrencyExact(y.shortfall * d)} unmet spending` : undefined}
                >
                  {cols.map((c) => (
                    <td
                      key={c.label}
                      className={`whitespace-nowrap px-2.5 py-1.5 tabular-nums ${
                        c.align === "right" ? "text-right" : "text-left"
                      }`}
                      title={c.exact ? c.exact(y, d) : undefined}
                    >
                      {c.value(y, d)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
