import type { DisplayMode, PlanResult, TransferCharacter } from "../../lib/types";
import { TRANSFER_CHARACTER_LABELS } from "../../lib/types";
import { fmtCurrency, fmtCurrencyExact } from "../../lib/format";
import { Card } from "../ui/Card";
import { InfoTip } from "../ui/Tooltip";

const CHARACTER_STYLE: Record<TransferCharacter, string> = {
  tax_free: "bg-teal-50 text-teal-700 ring-teal-600/20",
  step_up: "bg-sky-50 text-sky-700 ring-sky-600/20",
  ird: "bg-amber-50 text-amber-800 ring-amber-600/20",
};

const CHARACTER_HELP: Record<TransferCharacter, string> = {
  tax_free:
    "Passes income-tax-free to heirs — Roth accounts and life-insurance death benefits (IRC §101).",
  step_up:
    "Cost basis is reset to date-of-death value, so heirs owe no income tax on a later sale (IRC §1014). Applies to taxable, cash, private shares, and real estate.",
  ird:
    "Income in respect of a decedent: heirs owe ordinary income tax (at the heir tax rate) on inherited tax-deferred / HSA dollars and non-qualified annuity gains (IRC §691, §72).",
};

function CharacterBadge({ character }: { character: string }) {
  const c = character as TransferCharacter;
  const style = CHARACTER_STYLE[c] ?? "bg-slate-100 text-slate-600 ring-slate-500/20";
  const label = TRANSFER_CHARACTER_LABELS[c] ?? character;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-px text-[10px] font-medium ring-1 ring-inset ${style}`}
    >
      {label}
      {CHARACTER_HELP[c] && <InfoTip content={CHARACTER_HELP[c]} wide />}
    </span>
  );
}

export function LegacyPanel({
  result,
  mode,
  inflation,
}: {
  result: PlanResult;
  mode: DisplayMode;
  inflation: number;
}) {
  const legacy = result.legacy;
  if (!legacy || legacy.assets.length === 0) return null;

  const baseYear = result.years[0]?.year ?? legacy.at_death_year;
  const deflator =
    mode === "real" ? Math.pow(1 + inflation, legacy.at_death_year - baseYear) : 1;
  const v = (nominal: number) => nominal / deflator;
  const unit = mode === "real" ? "today's dollars" : "nominal dollars";

  // charity vs heirs split for the per-asset table ordering: heirs first
  const assets = [...legacy.assets].sort((a, b) =>
    a.beneficiary === b.beneficiary ? b.gross - a.gross : a.beneficiary === "charity" ? 1 : -1,
  );

  return (
    <Card
      title="Legacy & estate"
      help={
        <>
          What each asset passes at the end of the plan (
          {legacy.at_death_year}), and what heirs receive net of tax. Assets are valued by
          their <span className="font-semibold">transfer character</span>: income-tax-free,
          stepped-up basis, or taxable to heirs (IRD). Figures shown in {unit}.{" "}
          <span className="font-semibold">
            Estate (transfer) tax — the lifetime exemption, portability, and state estate tax —
            is not modeled.
          </span>
        </>
      }
      bodyClassName="p-0 overflow-x-auto"
    >
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            <th className="px-4 py-2.5 text-left font-medium">Asset</th>
            <th className="px-4 py-2.5 text-left font-medium">
              <span className="inline-flex items-center gap-1">
                Transfer character
                <InfoTip
                  wide
                  content="How the asset is taxed when it passes to its beneficiary at death."
                />
              </span>
            </th>
            <th className="px-4 py-2.5 text-left font-medium">To</th>
            <th className="px-4 py-2.5 text-right font-medium">Gross</th>
            <th className="px-4 py-2.5 text-right font-medium">
              <span className="inline-flex items-center gap-1">
                Heir tax
                <InfoTip
                  wide
                  content="Ordinary income tax heirs owe on IRD assets, at the heir tax rate. Zero for stepped-up and income-tax-free assets."
                />
              </span>
            </th>
            <th className="px-4 py-2.5 text-right font-medium">Net</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((a, i) => (
            <tr key={`${a.name}-${i}`} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td className="px-4 py-2.5 font-medium text-slate-800">{a.name}</td>
              <td className="px-4 py-2.5">
                <CharacterBadge character={a.transfer_character} />
              </td>
              <td className="px-4 py-2.5">
                {a.beneficiary === "charity" ? (
                  <span className="text-violet-700">Charity</span>
                ) : (
                  <span className="text-slate-500">Heirs</span>
                )}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-slate-700" title={fmtCurrencyExact(v(a.gross))}>
                {fmtCurrency(v(a.gross))}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums" title={fmtCurrencyExact(v(a.tax))}>
                {a.tax > 0 ? (
                  <span className="text-amber-700">−{fmtCurrency(v(a.tax))}</span>
                ) : (
                  <span className="text-slate-300">—</span>
                )}
              </td>
              <td
                className="px-4 py-2.5 text-right tabular-nums font-medium text-slate-800"
                title={fmtCurrencyExact(v(a.net))}
              >
                {fmtCurrency(v(a.net))}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-slate-200 bg-slate-50 font-semibold text-slate-800">
            <td className="px-4 py-2.5" colSpan={3}>
              To heirs — net of income tax{legacy.to_charity > 0 ? "" : " & debts"}
            </td>
            <td className="px-4 py-2.5 text-right tabular-nums" title={fmtCurrencyExact(v(legacy.to_heirs_gross))}>
              {fmtCurrency(v(legacy.to_heirs_gross))}
            </td>
            <td className="px-4 py-2.5 text-right tabular-nums text-amber-700" title={fmtCurrencyExact(v(legacy.ird_tax))}>
              {legacy.ird_tax > 0 ? `−${fmtCurrency(v(legacy.ird_tax))}` : "—"}
            </td>
            <td className="px-4 py-2.5 text-right tabular-nums text-teal-700" title={fmtCurrencyExact(v(legacy.to_heirs_net))}>
              {fmtCurrency(v(legacy.to_heirs_net))}
            </td>
          </tr>
          {legacy.to_charity > 0 && (
            <tr className="bg-slate-50 font-semibold text-violet-700">
              <td className="px-4 py-2.5" colSpan={5}>
                To charity (bequests, income-tax-free)
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums" title={fmtCurrencyExact(v(legacy.to_charity))}>
                {fmtCurrency(v(legacy.to_charity))}
              </td>
            </tr>
          )}
        </tfoot>
      </table>
    </Card>
  );
}
