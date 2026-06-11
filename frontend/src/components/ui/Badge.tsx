const KIND_STYLES: Record<string, string> = {
  modeled: "bg-brand-50 text-brand-700 ring-brand-200",
  estimated: "bg-amber-50 text-amber-700 ring-amber-200",
  assumed: "bg-slate-100 text-slate-600 ring-slate-200",
};

/**
 * Provenance badge: [modeled] = statutory rule, exact; [estimated] = engine
 * estimate; [assumed] = user/plan assumption.
 */
export function KindBadge({ kind }: { kind: string }) {
  const style = KIND_STYLES[kind] ?? KIND_STYLES.assumed;
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium uppercase tracking-wide ring-1 ring-inset ${style}`}
    >
      {kind}
    </span>
  );
}

export function StatusBadge({
  tone,
  children,
}: {
  tone: "success" | "danger" | "warning";
  children: React.ReactNode;
}) {
  const styles = {
    success: "bg-teal-50 text-teal-700 ring-teal-200",
    danger: "bg-red-50 text-red-700 ring-red-200",
    warning: "bg-amber-50 text-amber-700 ring-amber-200",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset ${styles[tone]}`}
    >
      {children}
    </span>
  );
}
