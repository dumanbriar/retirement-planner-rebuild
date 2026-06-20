import { useEffect, useState } from "react";
import type { AssumptionNote } from "../../lib/types";
import { KindBadge } from "../ui/Badge";
import { Tooltip } from "../ui/Tooltip";

/**
 * Always-visible provenance strip: every modeling choice with its kind
 * ([modeled] = statutory/exact, [estimated], [assumed]) and source on hover.
 * Items with freshness metadata show their last-verified date in the tooltip.
 * Stale items (due for annual review) get an amber dot and are listed in a
 * collapsible panel that auto-opens once per calendar month.
 */
export function AssumptionsStrip({ notes }: { notes: AssumptionNote[] }) {
  const [showStale, setShowStale] = useState(false);

  const staleNotes = notes.filter((n) => n.stale === "true");
  const staleCount = staleNotes.length;

  // Auto-open the stale panel once per calendar month when items need review.
  useEffect(() => {
    if (!staleCount) return;
    const thisMonth = new Date().toISOString().slice(0, 7); // "YYYY-MM"
    try {
      if (localStorage.getItem("freshness-dismissed") !== thisMonth) {
        setShowStale(true);
        localStorage.setItem("freshness-dismissed", thisMonth);
      }
    } catch {
      // localStorage unavailable (private browsing) — open once per session
      setShowStale(true);
    }
  }, [staleCount]);

  if (notes.length === 0) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-card">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          How this plan is modeled{" "}
          <span className="normal-case text-slate-400">— hover any item for its source</span>
        </p>
        {staleCount > 0 && (
          <button
            onClick={() => setShowStale((s) => !s)}
            className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700 hover:bg-amber-200"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            {staleCount} {staleCount === 1 ? "item" : "items"} may need review
          </button>
        )}
      </div>

      {showStale && staleCount > 0 && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="mb-1.5 font-semibold">
            These constants are likely due for their annual update — verify against the primary
            source and update{" "}
            <code className="rounded bg-amber-100 px-1 font-mono">
              backend/app/engine/constants.py
            </code>{" "}
            if new values have been published:
          </p>
          <ul className="space-y-1">
            {staleNotes.map((n) => (
              <li key={n.label} className="flex flex-wrap items-baseline gap-x-1.5">
                <span className="font-medium">{n.label}</span>
                {n.last_updated && (
                  <span className="text-amber-700">— last verified {n.last_updated}</span>
                )}
                {n.review_url && (
                  <>
                    {" · "}
                    <a
                      href={n.review_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-amber-900"
                    >
                      check source
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
          <button
            onClick={() => setShowStale(false)}
            className="mt-2 text-[10px] text-amber-600 underline hover:text-amber-900"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400">
        <span className="flex items-center gap-1">
          <KindBadge kind="modeled" /> statutory law, exact
        </span>
        <span className="flex items-center gap-1">
          <KindBadge kind="estimated" /> engine approximation
        </span>
        <span className="flex items-center gap-1">
          <KindBadge kind="assumed" /> user / plan input
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {notes.map((n, i) => (
          <Tooltip
            key={i}
            wide
            content={
              <>
                <span className="font-semibold">{n.label}.</span> {n.source}
                {n.last_updated && (
                  <span className="mt-1 block text-slate-400">
                    Last verified: {n.last_updated}
                    {n.review_url && (
                      <>
                        {" · "}
                        <a
                          href={n.review_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline"
                        >
                          check source
                        </a>
                      </>
                    )}
                  </span>
                )}
              </>
            }
          >
            <span className="inline-flex cursor-help items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700">
              {n.stale === "true" && (
                <span
                  className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-400"
                  title="May need annual review"
                />
              )}
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
