import type { ReactNode } from "react";
import type { Metrics } from "../../lib/types";
import { fmtCurrency, fmtCurrencyExact } from "../../lib/format";
import { StatusBadge } from "../ui/Badge";
import { InfoTip, Tooltip } from "../ui/Tooltip";

function MetricCard({
  label,
  help,
  primary,
  primaryExact,
  secondary,
  children,
}: {
  label: string;
  help: ReactNode;
  primary?: string;
  primaryExact?: string;
  secondary?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
      <p className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
        <InfoTip content={help} wide />
      </p>
      {primary && (
        <Tooltip content={<>Exact: {primaryExact ?? primary}</>}>
          <p className="mt-1.5 cursor-default text-2xl font-semibold tabular-nums tracking-tight text-slate-900">
            {primary}
          </p>
        </Tooltip>
      )}
      {children}
      {secondary && <p className="mt-0.5 text-xs text-slate-500">{secondary}</p>}
    </div>
  );
}

export function MetricCards({ metrics }: { metrics: Metrics }) {
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <MetricCard
        label="Nest egg at retirement"
        help={
          <>
            Total investable assets at the start of {metrics.retirement_year}, the first year both
            persons are retired. Shown in today's dollars (deflated at the plan inflation rate);
            the nominal figure is what the statements will actually say.
            <div className="mt-1 text-slate-300">
              Exact: {fmtCurrencyExact(metrics.nest_egg_at_retirement_real)} real /{" "}
              {fmtCurrencyExact(metrics.nest_egg_at_retirement)} nominal
            </div>
          </>
        }
        primary={fmtCurrency(metrics.nest_egg_at_retirement_real)}
        primaryExact={fmtCurrencyExact(metrics.nest_egg_at_retirement_real)}
        secondary={`${fmtCurrency(metrics.nest_egg_at_retirement)} nominal in ${metrics.retirement_year}`}
      />

      <MetricCard
        label="Plan outcome"
        help={
          <>
            FUNDED means every year's spending goal (plus healthcare, debt payments, and taxes) is
            met through both plan-end ages without running out of money. DEPLETED reports the
            primary person's age in the first year spending could not be met.
          </>
        }
        secondary={
          metrics.success
            ? "Spending fully met through both plan-end ages"
            : "Spending could not be met from this age on"
        }
      >
        <div className="mt-2.5">
          {metrics.success ? (
            <StatusBadge tone="success">Funded</StatusBadge>
          ) : (
            <StatusBadge tone="danger">
              Depleted at age {metrics.depletion_age ?? "—"}
            </StatusBadge>
          )}
        </div>
      </MetricCard>

      <MetricCard
        label="Ending after-tax wealth"
        help={
          <>
            Estate value at the end of the plan, in today's dollars, after discounting remaining
            tax-deferred and HSA balances at the heir tax rate (heirs owe income tax on inherited
            pre-tax dollars). Taxable assets assume a basis step-up. This is the number the Roth
            and Social Security optimizers maximize.
            <div className="mt-1 text-slate-300">
              Exact: {fmtCurrencyExact(metrics.ending_after_tax_real)}
            </div>
          </>
        }
        primary={fmtCurrency(metrics.ending_after_tax_real)}
        primaryExact={fmtCurrencyExact(metrics.ending_after_tax_real)}
        secondary={`Ending net worth ${fmtCurrency(metrics.ending_net_worth_real)} today's $ (${fmtCurrency(metrics.ending_net_worth)} nominal)`}
      />

      <MetricCard
        label="Lifetime taxes"
        help={
          <>
            Sum of all federal, state, capital-gains, and NIIT taxes (plus penalties) over the
            entire plan, expressed in today's dollars. Lower is not always better — paying some tax
            early (Roth conversions) can raise ending after-tax wealth.
            <div className="mt-1 text-slate-300">
              Exact: {fmtCurrencyExact(metrics.lifetime_taxes_real)} real /{" "}
              {fmtCurrencyExact(metrics.lifetime_taxes)} nominal
            </div>
          </>
        }
        primary={fmtCurrency(metrics.lifetime_taxes_real)}
        primaryExact={fmtCurrencyExact(metrics.lifetime_taxes_real)}
        secondary={`${fmtCurrency(metrics.lifetime_taxes)} nominal over the full plan`}
      />
    </div>
  );
}
