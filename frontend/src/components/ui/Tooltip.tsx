import { useRef, useState, type ReactNode } from "react";
import { Info } from "lucide-react";

interface Pos {
  x: number;
  y: number;
  below: boolean;
}

/**
 * Lightweight hover + focus tooltip. Uses fixed positioning so it is never
 * clipped by scroll containers (e.g. the year-by-year table).
 */
export function Tooltip({
  content,
  children,
  className = "",
  wide = false,
}: {
  content: ReactNode;
  children: ReactNode;
  className?: string;
  wide?: boolean;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<Pos | null>(null);

  const show = () => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const below = r.top < 170;
    const half = wide ? 190 : 150;
    const x = Math.min(Math.max(r.left + r.width / 2, half + 8), window.innerWidth - half - 8);
    setPos({ x, y: below ? r.bottom + 7 : r.top - 7, below });
  };
  const hide = () => setPos(null);

  return (
    <span
      ref={ref}
      className={`inline-flex ${className}`}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {pos && (
        <span
          role="tooltip"
          className={`pointer-events-none fixed z-[100] block whitespace-normal break-words ${wide ? "max-w-sm" : "max-w-xs"} rounded-lg bg-slate-800 px-3 py-2 text-left text-xs font-normal leading-relaxed normal-case text-slate-100 shadow-lg`}
          style={{
            left: pos.x,
            top: pos.y,
            transform: `translate(-50%, ${pos.below ? "0" : "-100%"})`,
            width: "max-content",
          }}
        >
          {content}
        </span>
      )}
    </span>
  );
}

/** Small focusable info glyph with an explanatory tooltip. */
export function InfoTip({ content, wide = false }: { content: ReactNode; wide?: boolean }) {
  return (
    <Tooltip content={content} wide={wide} className="align-middle">
      <button
        type="button"
        aria-label="More information"
        className="inline-flex cursor-help items-center rounded-full text-slate-400 outline-none transition-colors hover:text-brand-600 focus-visible:ring-2 focus-visible:ring-brand-400"
        onClick={(e) => e.preventDefault()}
      >
        <Info className="h-3.5 w-3.5" aria-hidden />
      </button>
    </Tooltip>
  );
}
