import { useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import type { PlanInput } from "../../lib/types";
import { coercePlanInput } from "../../lib/storage";

/**
 * Export the current plan to a .json file and import one back. Lets a plan move
 * between browsers/origins (e.g. between the v1 and v2 apps, which keep separate
 * localStorage). Import reuses coercePlanInput, so older plans missing newer
 * optional fields still load.
 */
export function PlanIO({
  input,
  onImport,
  className = "",
}: {
  input: PlanInput;
  onImport: (next: PlanInput) => void;
  className?: string;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const exportPlan = () => {
    setError(null);
    const blob = new Blob([JSON.stringify(input, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "horizon-plan.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const importPlan = async (file: File) => {
    try {
      const parsed = coercePlanInput(JSON.parse(await file.text()) as Partial<PlanInput>);
      if (!parsed) {
        setError("Not a valid Horizon plan (needs persons, accounts, and spending).");
        return;
      }
      setError(null);
      onImport(parsed);
    } catch {
      setError("Could not read that file — expected a Horizon plan .json export.");
    }
  };

  const linkCls =
    "inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition-colors hover:text-brand-700";

  return (
    <div className={className}>
      <div className="flex items-center gap-4">
        <button type="button" onClick={exportPlan} className={linkCls}>
          <Download className="h-3 w-3" /> Export plan
        </button>
        <button type="button" onClick={() => fileRef.current?.click()} className={linkCls}>
          <Upload className="h-3 w-3" /> Import plan
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void importPlan(f);
            e.target.value = ""; // allow re-importing the same file
          }}
        />
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
