import type { ReactNode } from "react";
import { InfoTip } from "./Tooltip";

export function Card({
  title,
  help,
  action,
  children,
  className = "",
  bodyClassName = "",
}: {
  title?: ReactNode;
  help?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-card ${className}`}>
      {title != null && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold tracking-tight text-slate-800">
            {title}
            {help && <InfoTip content={help} wide />}
          </h2>
          {action}
        </header>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
