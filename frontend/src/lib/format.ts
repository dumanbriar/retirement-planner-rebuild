/** Number formatting helpers. Never round misleadingly: full precision is
 * always available via fmtCurrencyExact (used in tooltips / title attrs). */

const currency0 = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const currency2 = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** "$1,234,568" (rounded to whole dollars for display density). */
export function fmtCurrency(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return currency0.format(v);
}

/** Full-precision currency, e.g. "$1,234,567.89" — for tooltips. */
export function fmtCurrencyExact(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return currency2.format(v);
}

/** Compact axis labels: "$1.2M", "$450k". */
export function fmtCurrencyCompact(v: number): string {
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 1_000_000_000) return `${sign}$${trim(a / 1_000_000_000)}B`;
  if (a >= 1_000_000) return `${sign}$${trim(a / 1_000_000)}M`;
  if (a >= 1_000) return `${sign}$${trim(a / 1_000)}k`;
  return `${sign}$${Math.round(a)}`;
}

function trim(n: number): string {
  return n >= 100 ? n.toFixed(0) : n >= 10 ? n.toFixed(1) : n.toFixed(2).replace(/\.?0+$/, "");
}

/** Fraction -> percent string: fmtPct(0.0625) === "6.25%". */
export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  const s = (v * 100).toFixed(digits);
  return `${s.replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1")}%`;
}

export function fmtNum(v: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(v);
}

/** Deflator to convert nominal dollars in `year` into base-year (today's) dollars. */
export function makeDeflator(baseYear: number, inflation: number): (year: number) => number {
  return (year: number) => 1 / Math.pow(1 + inflation, year - baseYear);
}
