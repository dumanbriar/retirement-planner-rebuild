import { ArrowRight, Loader2, RotateCcw } from "lucide-react";
import type { PlanInput } from "../../lib/types";
import type { FieldErrors } from "../../lib/validate";
import { Card } from "../ui/Card";
import { HouseholdSection } from "./HouseholdSection";
import { AccountsSection } from "./AccountsSection";
import { LiabilitiesSection } from "./LiabilitiesSection";
import { IncomeStreamsSection } from "./IncomeStreamsSection";
import { InsuranceSection } from "./InsuranceSection";
import { AnnuitiesSection } from "./AnnuitiesSection";
import { PrivateHoldingsSection } from "./PrivateHoldingsSection";
import { RealEstateSection } from "./RealEstateSection";
import { SpendingSection } from "./SpendingSection";
import { AssumptionsSection } from "./AssumptionsSection";
import { PlanIO } from "./PlanIO";

export function PlanForm({
  input,
  onChange,
  errors,
  serverError,
  loading,
  onCalculate,
  onReset,
}: {
  input: PlanInput;
  onChange: (next: PlanInput) => void;
  errors: FieldErrors;
  serverError: string | null;
  loading: boolean;
  onCalculate: () => void;
  onReset: () => void;
}) {
  const errorCount = Object.keys(errors).length;
  const sectionProps = { input, onChange, errors };

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">
          Build the retirement plan
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Enter the household's full picture below. Every number in the resulting plan is traceable
          — statutory rules are modeled exactly, estimates are labeled, and the audit workbook
          reproduces the entire projection.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Household"
          help="The people in the plan. Ages drive the timeline: contributions until each retirement age, spending and Social Security through each plan-end age."
        >
          <HouseholdSection {...sectionProps} />
        </Card>

        <div className="space-y-6">
          <Card
            title="Spending & strategy"
            help="The core question the plan answers: can this spending level be funded for life — and which tax strategy funds it best?"
          >
            <SpendingSection {...sectionProps} />
          </Card>
          <Card
            title="Liabilities"
            help="Outstanding debts. Annual payments continue (with interest accruing) until each balance is paid off, and count toward spending need. Set a start age to model a future mortgage / home purchase (the down payment is drawn from the portfolio then; the home isn't tracked as an asset)."
          >
            <LiabilitiesSection {...sectionProps} />
          </Card>
        </div>

        <Card
          className="lg:col-span-2"
          title="Accounts"
          help="All investable accounts. Type drives tax treatment; the withdrawal order in retirement is cash → taxable → tax-deferred → Roth, with HSA reserved for medical costs."
        >
          <AccountsSection {...sectionProps} />
        </Card>

        <Card
          title="Other income in retirement"
          help="Pensions, annuities, rentals, or part-time work. Amounts are in today's dollars and can be COLA-adjusted and taxable or tax-free."
        >
          <IncomeStreamsSection {...sectionProps} />
        </Card>

        <Card
          title="Life insurance"
          help="Whole/permanent policies with cash value and a death benefit. The death benefit passes income-tax-free to heirs (IRC §101); cash value grows tax-deferred. Amounts are level nominal figures, not today's dollars."
        >
          <InsuranceSection {...sectionProps} />
        </Card>

        <Card
          title="Annuities"
          help="Non-qualified deferred annuities: tax-deferred growth, then a level payout split by the exclusion ratio (basis tax-free, gain ordinary). At death the remaining gain is taxable to heirs (IRD)."
        >
          <AnnuitiesSection {...sectionProps} />
        </Card>

        <Card
          title="Private holdings"
          help="Private company shares or partnership interests. Illiquid — never sold to cover spending. Optional K-1 cash distributions are taxed each year; an optional liquidity event realizes the gain as LTCG; held to death the basis steps up (IRC §1014)."
        >
          <PrivateHoldingsSection {...sectionProps} />
        </Card>

        <Card
          title="Real estate"
          help="Homes and investment properties. Illiquid — never sold to cover spending. An optional sale pays off the linked mortgage and realizes the gain (primary residences exclude $250k/$500k under IRC §121); held to death the basis steps up (IRC §1014)."
        >
          <RealEstateSection {...sectionProps} />
        </Card>

        <Card
          title="Assumptions"
          help="Economic and tax assumptions. Statutory parameters (brackets, RMD tables, Medicare/IRMAA, ACA schedules) are modeled exactly from 2026 law and indexed forward at your inflation assumption."
        >
          <AssumptionsSection {...sectionProps} />
        </Card>
      </div>

      <div className="mt-8 flex flex-col items-center gap-3">
        {serverError && (
          <div className="w-full max-w-2xl whitespace-pre-line rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {serverError}
          </div>
        )}
        {errorCount > 0 && (
          <p className="text-sm font-medium text-red-600">
            Fix {errorCount === 1 ? "1 highlighted field" : `${errorCount} highlighted fields`} to
            continue.
          </p>
        )}
        <button
          type="button"
          onClick={onCalculate}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-900 px-8 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-brand-800 disabled:opacity-60"
        >
          {loading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" /> Calculating…
            </>
          ) : (
            <>
              Calculate plan <ArrowRight className="h-5 w-5" />
            </>
          )}
        </button>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition-colors hover:text-brand-700"
          >
            <RotateCcw className="h-3 w-3" /> Reset to sample data (Sam & Alex)
          </button>
          <PlanIO input={input} onImport={onChange} />
        </div>
      </div>
    </div>
  );
}
