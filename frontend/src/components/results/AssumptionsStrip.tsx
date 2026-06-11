import type { AssumptionNote } from "../../lib/types";
import { KindBadge } from "../ui/Badge";
import { Tooltip } from "../ui/Tooltip";

/**
 * Always-visible provenance strip: every modeling choice with its kind
 * ([modeled] = statutory/exact, [estimated], [assumed]) and source on hover.
 */
export function AssumptionsStrip({ notes }: { notes: AssumptionNote[] }) {
  if (notes.length === 0) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-card">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        How this plan is modeled{" "}
        <span className="normal-case text-slate-400">— hover any item for its source</span>
      </p>
      <div className="flex flex-wrap gap-1.5">
        {notes.map((n, i) => (
          <Tooltip
            key={i}
            wide
            content={
              <>
                <span className="font-semibold">{n.label}.</span> {n.source}
              </>
            }
          >
            <span className="inline-flex cursor-help items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
              <span className="font-medium">{n.label}:</span>
              <span className="text-slate-500">{n.value}</span>
              <KindBadge kind={n.kind} />
            </span>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
