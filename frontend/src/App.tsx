import { useEffect, useMemo, useRef, useState } from "react";
import { Compass } from "lucide-react";
import type { DisplayMode, PlanInput, PlanResult } from "./lib/types";
import { calculatePlan, ApiError } from "./lib/api";
import { SAMPLE_INPUT } from "./lib/sample";
import { loadStoredInput, resetToSample, saveStoredInput } from "./lib/storage";
import { validatePlanInput, type FieldErrors } from "./lib/validate";
import { PlanForm } from "./components/inputs/PlanForm";
import { Sidebar } from "./components/inputs/Sidebar";
import { Dashboard } from "./components/results/Dashboard";
import { Tooltip } from "./components/ui/Tooltip";

export default function App() {
  const [input, setInput] = useState<PlanInput>(
    () => loadStoredInput() ?? structuredClone(SAMPLE_INPUT),
  );
  const [result, setResult] = useState<PlanResult | null>(null);
  const [calcInput, setCalcInput] = useState<PlanInput | null>(null);
  const [loading, setLoading] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [mode, setMode] = useState<DisplayMode>("real");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const inputRef = useRef(input);
  inputRef.current = input;

  // Persist inputs on every change.
  useEffect(() => {
    saveStoredInput(input);
  }, [input]);

  // Re-validate live once errors have been surfaced, so fixes clear inline.
  const handleChange = (next: PlanInput) => {
    setInput(next);
    if (Object.keys(errors).length > 0) setErrors(validatePlanInput(next));
  };

  const dirty = useMemo(
    () => calcInput != null && JSON.stringify(input) !== JSON.stringify(calcInput),
    [input, calcInput],
  );

  const calculate = async () => {
    const snapshot = inputRef.current;
    const v = validatePlanInput(snapshot);
    setErrors(v);
    if (Object.keys(v).length > 0) {
      setServerError(null);
      return;
    }
    setLoading(true);
    setServerError(null);
    try {
      const r = await calculatePlan(snapshot);
      setResult(r);
      setCalcInput(structuredClone(snapshot));
    } catch (e) {
      if (e instanceof ApiError) {
        setServerError(
          e.status === 422 ? `The engine rejected the inputs:\n${e.message}` : e.message,
        );
      } else {
        setServerError("Unexpected error while calculating the plan.");
      }
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setInput(resetToSample());
    setErrors({});
    setServerError(null);
  };

  const hasResults = result != null && calcInput != null;

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800 antialiased">
      {/* Top bar */}
      <header className="sticky top-0 z-40 flex h-12 items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-900 text-white">
            <Compass className="h-4 w-4" />
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-brand-950">Horizon</span>
          <span className="text-sm text-slate-400">— Retirement Planner</span>
        </div>
        {hasResults && (
          <Tooltip
            wide
            content="Global display toggle. Today's $ deflates every nominal figure back to current purchasing power using the plan's inflation assumption — the honest way to compare amounts decades apart. Nominal shows the raw future dollars."
          >
            <div
              className="flex items-center rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs font-medium"
              role="group"
              aria-label="Dollar display mode"
            >
              {(["real", "nominal"] as DisplayMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`rounded-md px-3 py-1 transition-colors ${
                    mode === m
                      ? "bg-white text-brand-900 shadow-sm"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {m === "real" ? "Today's $" : "Nominal $"}
                </button>
              ))}
            </div>
          </Tooltip>
        )}
      </header>

      {hasResults ? (
        <div className="flex items-start">
          <Sidebar
            input={input}
            onChange={handleChange}
            errors={errors}
            dirty={dirty}
            loading={loading}
            onRecalculate={calculate}
            onReset={reset}
            collapsed={sidebarCollapsed}
            onToggleCollapsed={() => setSidebarCollapsed((v) => !v)}
          />
          <div className="min-w-0 flex-1">
            {serverError && (
              <div className="mx-6 mt-5 whitespace-pre-line rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {serverError}
              </div>
            )}
            <Dashboard result={result} calcInput={calcInput} mode={mode} stale={dirty} />
          </div>
        </div>
      ) : (
        <PlanForm
          input={input}
          onChange={handleChange}
          errors={errors}
          serverError={serverError}
          loading={loading}
          onCalculate={calculate}
          onReset={reset}
        />
      )}
    </div>
  );
}
