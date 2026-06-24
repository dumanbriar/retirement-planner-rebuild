import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { AssumptionNote } from "../../lib/types";
import { KindBadge } from "../ui/Badge";
import { Tooltip } from "../ui/Tooltip";

/**
 * Provenance methodology bar. Collapsed by default to a single header line —
 * title + a per-kind count summary ([modeled] = statutory/exact, [estimated] =
 * engine approximation, [assumed] = user/plan input) + a freshness nudge — so it
 * stays a visible trust signal without dominating the results screen. Expands to
 * reveal every modeling choice as a chip with its source on hover. Items with
 * freshness metadata show their last-verified date in the tooltip; stale items
 * (due for annual review) get an amber dot and a review panel, and the bar
 * auto-expands once per calendar month while any item needs review.
 */
export function AssumptionsStrip({ notes }: { notes: AssumptionNote[] }) {
  const [expanded, setExpanded] = useState(false);
  const [stalePanelDismissed, setStalePanelDismissed] = useState(false);

  const staleNotes = useMemo(() => notes.filter((n) => n.stale === "true"), [notes]);
  const staleCount = staleNotes.length;

  const counts = useMemo(() => {
    const c: Record<string, number> = { modeled: 0, estimated: 0, assumed: 0 };
    for (const n of notes) c[n.kind] = (c[n.kind] ?? 0) + 1;
    return c;
  }, [notes]);

  // Auto-expand once per calendar month when constants are due for review.
  useEffect(() => {
    if (!staleCount) return;
    const thisMonth = new Date().toISOString().slice(0, 7); // "YYYY-MM"
    try {
      if (localStorage.getItem("freshness-dismissed") !== thisMonth) {
        setExpanded(true);
        localStorage.setItem("freshness-dismissed", thisMonth);
      }
    } catch {
      // localStorage unavailable (private browsing) — expand once per session
      setExpanded(true);
    }
  }, [staleCount]);

  if (notes.length === 0) return null;

  const showStalePanel = expanded && staleCount > 0 && !stalePanelDismissed;

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-card">
      <header
        className={`flex items-center justify-between gap-3 px-5 py-3 ${
          expanded ? "border-b border-slate-100" : ""
        }`}
      >
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 flex-shrink-0 text-slate-400" />
          ) : (
            <ChevronRight className="h-4 w-4 flex-shrink-0 text-slate-400" />
          )}
          <span className="whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-slate-500">
            How this plan is modeled
          </span>
          <span className="hidden truncate text-[11px] text-slate-400 sm:inline">
            <span className="text-brand-700">{counts.modeled} modeled</span>
            {" · "}
            <span className="text-amber-700">{counts.estimated} estimated</span>
            {" · "}
            <span className="text-slate-500">{counts.assumed} assumed</span>
          </span>
        </button>

        <div className="flex flex-shrink-0 items-center gap-2">
          {staleCount > 0 && (
            <button
              type="button"
              onClick={() => {
                setExpanded(true);
                setStalePanelDismissed(false);
              }}
              className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700 hover:bg-amber-200"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              {staleCount} {staleCount === 1 ? "item" : "items"} may need review
            </button>
          )}
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="whitespace-nowrap text-[11px] font-medium text-brand-700 hover:text-brand-800"
          >
            {expanded ? "Hide" : "Show sources"}
          </button>
        </div>
      </header>

      {expanded && (
        <div className="p-5">
          {showStalePanel && (
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
                onClick={() => setStalePanelDismissed(true)}
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
      )}
    </section>
  );
}
