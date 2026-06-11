import { useEffect, useRef, useState, type ReactNode } from "react";
import { InfoTip } from "./Tooltip";

const INPUT_CLASS =
  "w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:bg-slate-50";

export function FieldShell({
  label,
  help,
  error,
  children,
  className = "",
}: {
  label: ReactNode;
  help?: ReactNode;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-600">
        {label}
        {help && <InfoTip content={help} wide />}
      </span>
      {children}
      {error && <span className="mt-1 block text-xs font-medium text-red-600">{error}</span>}
    </label>
  );
}

export function TextField({
  label,
  value,
  onChange,
  help,
  error,
  placeholder,
  className,
}: {
  label: ReactNode;
  value: string;
  onChange: (v: string) => void;
  help?: ReactNode;
  error?: string;
  placeholder?: string;
  className?: string;
}) {
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      <input
        type="text"
        className={`${INPUT_CLASS} ${error ? "border-red-400" : ""}`}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </FieldShell>
  );
}

/**
 * Numeric input that tolerates intermediate typing states ("", "-", "1.").
 * `value` is the committed number; empty commits `emptyValue` (default 0,
 * pass null for optional fields).
 */
function RawNumberInput({
  value,
  onChange,
  emptyValue,
  min,
  max,
  step,
  prefix,
  suffix,
  placeholder,
  error,
  big = false,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  emptyValue: number | null;
  min?: number;
  max?: number;
  step?: number;
  prefix?: string;
  suffix?: string;
  placeholder?: string;
  error?: string;
  big?: boolean;
}) {
  const [text, setText] = useState(value == null ? "" : String(value));
  const focused = useRef(false);
  useEffect(() => {
    if (!focused.current) setText(value == null ? "" : String(value));
  }, [value]);

  const handle = (t: string) => {
    setText(t);
    if (t.trim() === "") {
      onChange(emptyValue);
      return;
    }
    const p = Number(t);
    if (Number.isFinite(p)) onChange(p);
  };

  return (
    <span className="relative block">
      {prefix && (
        <span
          className={`pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-400 ${big ? "text-base" : "text-sm"}`}
        >
          {prefix}
        </span>
      )}
      <input
        type="number"
        inputMode="decimal"
        className={`${INPUT_CLASS} ${big ? "py-2.5 text-lg font-semibold" : ""} ${prefix ? (big ? "pl-7" : "pl-6") : ""} ${suffix ? "pr-7" : ""} ${error ? "border-red-400" : ""}`}
        value={text}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        onFocus={() => {
          focused.current = true;
        }}
        onBlur={() => {
          focused.current = false;
          setText(value == null ? "" : String(value));
        }}
        onChange={(e) => handle(e.target.value)}
      />
      {suffix && (
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-sm text-slate-400">
          {suffix}
        </span>
      )}
    </span>
  );
}

export function NumberField({
  label,
  value,
  onChange,
  help,
  error,
  min,
  max,
  step,
  prefix,
  suffix,
  className,
  big,
}: {
  label: ReactNode;
  value: number;
  onChange: (v: number) => void;
  help?: ReactNode;
  error?: string;
  min?: number;
  max?: number;
  step?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  big?: boolean;
}) {
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      <RawNumberInput
        value={value}
        onChange={(v) => onChange(v ?? 0)}
        emptyValue={0}
        min={min}
        max={max}
        step={step}
        prefix={prefix}
        suffix={suffix}
        error={error}
        big={big}
      />
    </FieldShell>
  );
}

export function OptionalNumberField({
  label,
  value,
  onChange,
  help,
  error,
  min,
  max,
  step,
  prefix,
  suffix,
  placeholder,
  className,
}: {
  label: ReactNode;
  value: number | null;
  onChange: (v: number | null) => void;
  help?: ReactNode;
  error?: string;
  min?: number;
  max?: number;
  step?: number;
  prefix?: string;
  suffix?: string;
  placeholder?: string;
  className?: string;
}) {
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      <RawNumberInput
        value={value}
        onChange={onChange}
        emptyValue={null}
        min={min}
        max={max}
        step={step}
        prefix={prefix}
        suffix={suffix}
        placeholder={placeholder}
        error={error}
      />
    </FieldShell>
  );
}

/** Stores a fraction (0.025) but displays a percentage (2.5). */
export function PercentField({
  label,
  value,
  onChange,
  help,
  error,
  min,
  max,
  step = 0.1,
  className,
}: {
  label: ReactNode;
  value: number;
  onChange: (v: number) => void;
  help?: ReactNode;
  error?: string;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
}) {
  const display = Math.round(value * 100 * 1e6) / 1e6;
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      <RawNumberInput
        value={display}
        onChange={(v) => onChange((v ?? 0) / 100)}
        emptyValue={0}
        min={min}
        max={max}
        step={step}
        suffix="%"
        error={error}
      />
    </FieldShell>
  );
}

/** Optional percent: null means "use default". */
export function OptionalPercentField({
  label,
  value,
  onChange,
  help,
  error,
  min,
  max,
  step = 0.1,
  placeholder,
  className,
}: {
  label: ReactNode;
  value: number | null;
  onChange: (v: number | null) => void;
  help?: ReactNode;
  error?: string;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  className?: string;
}) {
  const display = value == null ? null : Math.round(value * 100 * 1e6) / 1e6;
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      <RawNumberInput
        value={display}
        onChange={(v) => onChange(v == null ? null : v / 100)}
        emptyValue={null}
        min={min}
        max={max}
        step={step}
        suffix="%"
        placeholder={placeholder}
        error={error}
      />
    </FieldShell>
  );
}

export function SelectField<T extends string | number>({
  label,
  value,
  onChange,
  options,
  help,
  error,
  className,
}: {
  label: ReactNode;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  help?: ReactNode;
  error?: string;
  className?: string;
}) {
  const numeric = typeof value === "number";
  return (
    <FieldShell label={label} help={help} error={error} className={className}>
      <select
        className={`${INPUT_CLASS} ${error ? "border-red-400" : ""}`}
        value={String(value)}
        onChange={(e) => onChange((numeric ? Number(e.target.value) : e.target.value) as T)}
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

export function CheckboxField({
  label,
  checked,
  onChange,
  help,
  className = "",
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
  help?: ReactNode;
  className?: string;
}) {
  return (
    <label className={`flex cursor-pointer items-center gap-2 text-sm text-slate-700 ${className}`}>
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-slate-300 accent-brand-700"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="flex items-center gap-1">
        {label}
        {help && <InfoTip content={help} wide />}
      </span>
    </label>
  );
}
