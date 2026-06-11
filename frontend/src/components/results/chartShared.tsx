import type { ReactNode } from "react";

/** Series colors by account type (per design spec). */
export const TYPE_COLORS: Record<string, string> = {
  tax_deferred: "#4f46e5", // indigo
  roth: "#0d9488", // teal
  taxable: "#38bdf8", // sky
  hsa: "#f59e0b", // amber
  cash: "#94a3b8", // slate
};

export const AXIS_TICK = { fontSize: 11, fill: "#64748b" } as const;

export function ChartTooltipShell({
  title,
  children,
}: {
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-semibold text-slate-800">{title}</p>
      {children}
    </div>
  );
}

export function TooltipRow({
  color,
  label,
  value,
  strong = false,
}: {
  color?: string;
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-px">
      <span className="flex items-center gap-1.5 text-slate-600">
        {color && <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: color }} />}
        {label}
      </span>
      <span className={`tabular-nums ${strong ? "font-semibold text-slate-900" : "text-slate-700"}`}>
        {value}
      </span>
    </div>
  );
}

/** Format the ages array for display: "Sam 65 · Alex 63". */
export function agesLabel(names: string[], ages: (number | null)[]): string {
  return ages
    .map((a, i) => (a == null ? null : `${names[i] ?? `P${i + 1}`} ${a}`))
    .filter(Boolean)
    .join(" · ");
}
