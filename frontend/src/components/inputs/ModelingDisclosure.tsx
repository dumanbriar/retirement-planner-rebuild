import { useLayoutEffect, useRef, useState } from "react";
import { Check, Info, Minus } from "lucide-react";
import { modelingSpec } from "../../lib/modelingDisclosures";

interface Box {
  left: number;
  top: number;
  maxHeight: number;
  ready: boolean;
}

/**
 * On-demand "How this is modeled" disclosure for the asset type being entered.
 * A compact text trigger opens a click-pinned popover with the modeled /
 * not-modeled bullets from the MODELING_DISCLOSURES registry. The popover uses
 * fixed coordinates (like ui/Tooltip) so it's never clipped by the scrollable
 * sidebar; it measures its own height and flips above / caps its height so it
 * always fits the viewport. Closes on outside-click, Escape, scroll, or resize.
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
  const popRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<Box | null>(null);
  const open = box !== null;

  const clampX = (r: DOMRect) => {
    const HALF = 150; // half of the w-72 popover
    return Math.min(Math.max(r.left + r.width / 2, HALF + 8), window.innerWidth - HALF - 8);
  };

  // Place below as a first guess; the layout effect measures and corrects it
  // (before paint) so a tall popover near the bottom flips up / scrolls instead
  // of overflowing the viewport.
  useLayoutEffect(() => {
    if (!box || box.ready || !btnRef.current || !popRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    const h = popRef.current.scrollHeight;
    const margin = 8;
    const below = window.innerHeight - r.bottom - margin;
    const above = r.top - margin;
    let top: number;
    let maxHeight: number;
    if (h <= below || below >= above) {
      top = r.bottom + 6; // open downward
      maxHeight = below;
    } else {
      maxHeight = above; // open upward
      top = Math.max(margin, r.top - 6 - Math.min(h, above));
    }
    setBox({ left: clampX(r), top, maxHeight, ready: true });
  }, [box]);

  useLayoutEffect(() => {
    if (!open) return;
    const close = () => setBox(null);
    const onDoc = (e: MouseEvent) => {
      if (btnRef.current?.contains(e.target as Node)) return;
      if (popRef.current?.contains(e.target as Node)) return;
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

  const toggle = () => {
    if (open) {
      setBox(null);
      return;
    }
    const r = btnRef.current?.getBoundingClientRect();
    if (!r) return;
    setBox({ left: clampX(r), top: r.bottom + 6, maxHeight: 9999, ready: false });
  };

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className={`inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 outline-none transition-colors hover:text-brand-600 focus-visible:text-brand-600 ${className}`}
      >
        <Info className="h-3 w-3" aria-hidden /> How this is modeled
      </button>
      {box && (
        <div
          ref={popRef}
          role="dialog"
          className="fixed z-[100] w-72 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 text-left text-[11px] leading-relaxed shadow-xl"
          style={{
            left: box.left,
            top: box.top,
            maxHeight: box.maxHeight,
            transform: "translateX(-50%)",
            visibility: box.ready ? "visible" : "hidden",
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
