import { useEffect, useRef, useState } from "react";
import { Check, Info, Minus } from "lucide-react";
import { modelingSpec } from "../../lib/modelingDisclosures";

interface Pos {
  x: number;
  y: number;
  above: boolean;
}

/**
 * On-demand "How this is modeled" disclosure for the asset type currently being
 * entered. A compact text trigger that opens a click-pinned popover with the
 * modeled / not-modeled bullets from the MODELING_DISCLOSURES registry. The
 * popover is positioned with fixed coordinates (like ui/Tooltip) so it is never
 * clipped by the scrollable inputs sidebar; it closes on outside-click, Escape,
 * scroll, or resize. Reused by every asset Section so each type owns its caveats.
 */
export function ModelingDisclosure({
  assetKey,
  className = "",
}: {
  assetKey: string;
  className?: string;
}) {
  const spec = modelingSpec(assetKey);
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<Pos | null>(null);
  const open = pos !== null;

  const place = () => {
    const el = btnRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const HALF = 150; // half of the w-72 popover
    const above = window.innerHeight - r.bottom < 220; // flip up if little room below
    const x = Math.min(Math.max(r.left + r.width / 2, HALF + 8), window.innerWidth - HALF - 8);
    setPos({ x, y: above ? r.top - 6 : r.bottom + 6, above });
  };

  useEffect(() => {
    if (!open) return;
    const close = () => setPos(null);
    const onDoc = (e: MouseEvent) => {
      if (btnRef.current?.contains(e.target as Node)) return;
      close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  if (!spec) return null;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => (open ? setPos(null) : place())}
        aria-expanded={open}
        className={`inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 outline-none transition-colors hover:text-brand-600 focus-visible:text-brand-600 ${className}`}
      >
        <Info className="h-3 w-3" aria-hidden /> How this is modeled
      </button>
      {pos && (
        <div
          role="dialog"
          className="fixed z-[100] w-72 rounded-lg border border-slate-200 bg-white p-3 text-left text-[11px] leading-relaxed shadow-xl"
          style={{
            left: pos.x,
            top: pos.y,
            transform: `translate(-50%, ${pos.above ? "-100%" : "0"})`,
          }}
        >
          <p className="mb-1 font-semibold uppercase tracking-wide text-slate-400">
            How this is modeled
          </p>
          <ul className="space-y-0.5">
            {spec.modeled.map((m) => (
              <li key={m} className="flex items-start gap-1.5 text-slate-600">
                <Check className="mt-px h-3 w-3 shrink-0 text-teal-600" />
                <span>{m}</span>
              </li>
            ))}
            {spec.notModeled.map((m) => (
              <li key={m} className="flex items-start gap-1.5 text-slate-400">
                <Minus className="mt-px h-3 w-3 shrink-0 text-slate-300" />
                <span>Not modeled: {m}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
