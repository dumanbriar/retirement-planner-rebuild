import { useState } from "react";
import { FileSpreadsheet, Loader2 } from "lucide-react";
import type { DisplayMode, PlanInput, PlanResult } from "../../lib/types";
import { downloadAuditWorkbook } from "../../lib/api";
import { Tooltip } from "../ui/Tooltip";
import { MetricCards } from "./MetricCards";
import { AssumptionsStrip } from "./AssumptionsStrip";
import { WarningsList } from "./WarningsList";
import { NetWorthChart } from "./NetWorthChart";
import { IncomeSpendingChart } from "./IncomeSpendingChart";
import { TaxChart } from "./TaxChart";
import { ConversionTable } from "./ConversionTable";
import { SSGridTable } from "./SSGridTable";
import { ContributionSplitTable } from "./ContributionSplitTable";
import { SensitivityTable } from "./SensitivityTable";
import { YearTable } from "./YearTable";

export function Dashboard({
  result,
  calcInput,
  mode,
  stale,
}: {
  result: PlanResult;
  /** The exact input snapshot the result was computed from. */
  calcInput: PlanInput;
  mode: DisplayMode;
  stale: boolean;
}) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const inflation = calcInput.assumptions.inflation;
  const personNames = calcInput.persons.map((p) => p.name);

  const download = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadAuditWorkbook(calcInput);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  const chartProps = { result, mode, inflation, personNames };

  return (
    <div className="min-w-0 flex-1 space-y-5 px-6 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-900">
            {personNames.join(" & ")} — retirement plan
          </h1>
          <p className="text-xs text-slate-500">
            Deterministic projection, {result.years[0]?.year}–
            {result.years[result.years.length - 1]?.year}. Charts and the year table shown{" "}
            {mode === "real" ? "in today's dollars" : "in nominal dollars"}; metric cards and
            strategy tables are always in today's dollars (as labeled).
          </p>
        </div>
        <Tooltip
          wide
          content="Generates an Excel workbook with the complete year-by-year engine trace — every account, cash flow, and tax line. Every number on this screen is reproducible from that workbook."
        >
          <button
            type="button"
            onClick={download}
            disabled={downloading}
            className="inline-flex items-center gap-2 rounded-lg border border-brand-300 bg-white px-4 py-2 text-sm font-semibold text-brand-800 shadow-sm transition-colors hover:bg-brand-50 disabled:opacity-60"
          >
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="h-4 w-4" />
            )}
            Download audit workbook (.xlsx)
          </button>
        </Tooltip>
      </div>

      {downloadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {downloadError}
        </div>
      )}

      {stale && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          Inputs have changed since this plan was calculated — results below reflect the previous
          inputs. Use <span className="font-semibold">Recalculate</span> in the sidebar to refresh.
        </div>
      )}

      <WarningsList warnings={result.warnings} />

      <MetricCards metrics={result.metrics} />

      <AssumptionsStrip notes={result.assumption_notes} />

      <NetWorthChart {...chartProps} />

      <div className="grid gap-5 2xl:grid-cols-2">
        <IncomeSpendingChart {...chartProps} />
        <TaxChart {...chartProps} />
      </div>

      <ConversionTable comparison={result.conversion_comparison} metrics={result.metrics} />

      <ContributionSplitTable
        cells={result.contribution_split}
        metrics={result.metrics}
        personNames={personNames}
      />

      <SSGridTable grid={result.ss_grid} metrics={result.metrics} personNames={personNames} />

      <SensitivityTable rows={result.sensitivity} metrics={result.metrics} />

      <YearTable {...chartProps} />

      <p className="pb-4 text-center text-[11px] text-slate-400">
        Deterministic planning model — not investment, tax, or legal advice. Statutory parameters
        are 2026 values indexed at the assumed inflation rate; see the assumptions strip for
        provenance of every modeling choice. Your inputs stay in your browser and are sent to the
        stateless engine only to compute — nothing is stored on a server or shared.
      </p>
    </div>
  );
}
