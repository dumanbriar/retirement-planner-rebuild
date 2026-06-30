import { useState, type ComponentType, type ReactNode } from "react";
import {
  Banknote,
  ChevronDown,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CreditCard,
  Landmark,
  Loader2,
  RefreshCw,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Users,
  Wallet,
} from "lucide-react";
import type { PlanInput } from "../../lib/types";
import { ACCOUNT_TYPE_SHORT, CONVERSION_STRATEGY_LABELS } from "../../lib/types";
import { fmtCurrency, fmtPct } from "../../lib/format";
import { InfoTip } from "../ui/Tooltip";
import type { FieldErrors } from "../../lib/validate";
import { HouseholdSection } from "./HouseholdSection";
import { AccountsSection } from "./AccountsSection";
import { LiabilitiesSection } from "./LiabilitiesSection";
import { IncomeStreamsSection } from "./IncomeStreamsSection";
import { InsuranceSection } from "./InsuranceSection";
import { SpendingSection } from "./SpendingSection";
import { AssumptionsSection } from "./AssumptionsSection";
import { PlanIO } from "./PlanIO";

interface SidebarProps {
  input: PlanInput;
  onChange: (next: PlanInput) => void;
  errors: FieldErrors;
  dirty: boolean;
  loading: boolean;
  onRecalculate: () => void;
  onReset: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

function SectionAccordion({
  icon: Icon,
  title,
  summary,
  hasError,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  summary: ReactNode;
  hasError?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-slate-100">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-2.5 px-4 py-3 text-left transition-colors hover:bg-slate-50"
      >
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-700">
            {title}
            {hasError && <span className="h-1.5 w-1.5 rounded-full bg-red-500" />}
          </span>
          <span className="mt-0.5 block truncate text-xs text-slate-500">{summary}</span>
        </span>
        {open ? (
          <ChevronDown className="mt-1 h-3.5 w-3.5 shrink-0 text-slate-400" />
        ) : (
          <ChevronRight className="mt-1 h-3.5 w-3.5 shrink-0 text-slate-400" />
        )}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

export function Sidebar({
  input,
  onChange,
  errors,
  dirty,
  loading,
  onRecalculate,
  onReset,
  collapsed,
  onToggleCollapsed,
}: SidebarProps) {
  if (collapsed) {
    return (
      <div className="sticky top-12 flex h-[calc(100vh-3rem)] w-10 shrink-0 flex-col items-center border-r border-slate-200 bg-white py-3">
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label="Expand inputs panel"
          className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-brand-700"
        >
          <ChevronsRight className="h-4 w-4" />
        </button>
        <span
          className="mt-4 text-[10px] font-semibold uppercase tracking-widest text-slate-400"
          style={{ writingMode: "vertical-rl" }}
        >
          Plan inputs
        </span>
        {dirty && <span className="mt-3 h-2 w-2 rounded-full bg-amber-500" title="Unsaved changes" />}
      </div>
    );
  }

  const totalAssets = input.accounts.reduce((s, a) => s + a.balance, 0);
  const totalDebt = input.liabilities.reduce((s, l) => s + l.balance, 0);
  const sectionProps = { input, onChange, errors, dense: true };
  const hasErr = (prefix: string) => Object.keys(errors).some((k) => k.startsWith(prefix));

  const typeCounts = input.accounts.reduce<Record<string, number>>((m, a) => {
    m[a.type] = (m[a.type] ?? 0) + 1;
    return m;
  }, {});

  return (
    <aside className="sticky top-12 flex h-[calc(100vh-3rem)] w-80 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Plan inputs
        </span>
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label="Collapse inputs panel"
          className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-brand-700"
        >
          <ChevronsLeft className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <SectionAccordion
          icon={Users}
          title="Household"
          hasError={hasErr("persons.")}
          summary={input.persons
            .map((p) => `${p.name} ${p.current_age} → ${p.retirement_age}`)
            .join(" · ")}
        >
          <HouseholdSection {...sectionProps} />
        </SectionAccordion>

        <SectionAccordion
          icon={Wallet}
          title="Accounts"
          hasError={hasErr("accounts")}
          summary={`${input.accounts.length} accounts · ${fmtCurrency(totalAssets)} · ${Object.entries(
            typeCounts,
          )
            .map(([t, n]) => `${n} ${ACCOUNT_TYPE_SHORT[t as keyof typeof ACCOUNT_TYPE_SHORT]}`)
            .join(", ")}`}
        >
          <AccountsSection {...sectionProps} />
        </SectionAccordion>

        <SectionAccordion
          icon={CreditCard}
          title="Liabilities"
          hasError={hasErr("liabilities.")}
          summary={
            input.liabilities.length === 0
              ? "None"
              : `${input.liabilities.length} · ${fmtCurrency(totalDebt)} owed`
          }
        >
          <LiabilitiesSection {...sectionProps} />
        </SectionAccordion>

        <SectionAccordion
          icon={Landmark}
          title="Other income"
          hasError={hasErr("income_streams.")}
          summary={
            input.income_streams.length === 0
              ? "None"
              : input.income_streams.map((s) => `${s.name} ${fmtCurrency(s.annual_amount)}/yr`).join(" · ")
          }
        >
          <IncomeStreamsSection {...sectionProps} />
        </SectionAccordion>

        <SectionAccordion
          icon={ShieldCheck}
          title="Life insurance"
          hasError={hasErr("insurance_policies.")}
          summary={
            input.insurance_policies.length === 0
              ? "None"
              : input.insurance_policies
                  .map((p) => `${p.name} ${fmtCurrency(p.death_benefit)}`)
                  .join(" · ")
          }
        >
          <InsuranceSection {...sectionProps} />
        </SectionAccordion>

        <SectionAccordion
          icon={Banknote}
          title="Spending & strategy"
          hasError={!!errors["annual_spending"] || hasErr("assumptions.custom_conversion")}
          summary={`${fmtCurrency(input.annual_spending)}/yr · Roth: ${
            CONVERSION_STRATEGY_LABELS[input.assumptions.roth_conversion_strategy]
          }${input.assumptions.optimize_ss_claiming ? " · SS optimized" : ""}${
            input.assumptions.optimize_contribution_split ? " · split suggestion" : ""
          }`}
        >
          <SpendingSection {...sectionProps} />
        </SectionAccordion>

        <SectionAccordion
          icon={Settings2}
          title="Assumptions"
          hasError={hasErr("assumptions.")}
          summary={`Inflation ${fmtPct(input.assumptions.inflation)} · Healthcare ${fmtPct(
            input.assumptions.healthcare_inflation,
          )} · State tax ${fmtPct(input.assumptions.state_tax_rate)}`}
        >
          <AssumptionsSection {...sectionProps} />
        </SectionAccordion>

        <div className="space-y-2 px-4 py-3">
          <PlanIO input={input} onImport={onChange} />
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition-colors hover:text-brand-700"
          >
            <RotateCcw className="h-3 w-3" /> Reset to sample data
          </button>
        </div>
      </div>

      <div className="border-t border-slate-200 p-3">
        {dirty ? (
          <button
            type="button"
            onClick={onRecalculate}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-800 disabled:opacity-60"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Recalculating…
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" /> Recalculate
              </>
            )}
          </button>
        ) : (
          <p className="text-center text-xs text-slate-400">Results reflect current inputs.</p>
        )}
        <p className="mt-2.5 flex items-center justify-center gap-1 text-center text-[11px] text-slate-400">
          <ShieldCheck className="h-3 w-3 shrink-0" />
          Your inputs stay in this browser
          <InfoTip
            content="Inputs are saved only in this browser (localStorage) and sent to the calculation engine over HTTPS solely to compute your plan — nothing is stored on a server, logged, or shared with any third party (no accounts, no analytics). 'Reset to sample data' clears the local copy."
            wide
          />
        </p>
      </div>
    </aside>
  );
}
