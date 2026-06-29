import { Check, Minus } from "lucide-react";
import { modelingSpec } from "../../lib/modelingDisclosures";

/**
 * Inline "what is and isn't modeled" panel for the asset type currently being
 * entered. Reusable across every input section; the text comes from the
 * MODELING_DISCLOSURES registry so each asset type owns its own caveats.
 */
export function ModelingDisclosure({
  assetKey,
  className = "",
}: {
  assetKey: string;
  className?: string;
}) {
  const spec = modelingSpec(assetKey);
  if (!spec) return null;
  return (
    <div
      className={`rounded-md border border-slate-200 bg-white/70 px-3 py-2 text-[11px] leading-relaxed ${className}`}
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
  );
}
