import { Plus, Trash2 } from "lucide-react";
import type { Account, AccountType, AccountVehicle } from "../../lib/types";
import { ACCOUNT_TYPE_LABELS, ACCOUNT_VEHICLE_LABELS, DEFAULT_RETURNS } from "../../lib/types";
import { newAccount } from "../../lib/sample";
import {
  NumberField,
  OptionalNumberField,
  OptionalPercentField,
  SelectField,
  TextField,
} from "../ui/fields";
import { removeAt, type SectionProps, updateAt } from "./sectionProps";
import { ModelingDisclosure } from "./ModelingDisclosure";

const TYPE_OPTIONS = (Object.keys(ACCOUNT_TYPE_LABELS) as AccountType[]).map((t) => ({
  value: t,
  label: ACCOUNT_TYPE_LABELS[t],
}));

const VEHICLE_OPTIONS = (Object.keys(ACCOUNT_VEHICLE_LABELS) as AccountVehicle[]).map((v) => ({
  value: v,
  label: ACCOUNT_VEHICLE_LABELS[v],
}));

export function AccountsSection({ input, onChange, errors, dense }: SectionProps) {
  const ownerOptions = input.persons.map((p, i) => ({ value: i, label: p.name || `Person ${i + 1}` }));

  const setAccount = (i: number, patch: Partial<Account>) =>
    onChange({ ...input, accounts: updateAt(input.accounts, i, patch) });

  const setType = (i: number, type: AccountType) => {
    // Prefill the expected return with the type default (6/6/6/5/4) and a
    // sensible contribution-limit vehicle: Roth -> IRA (a Roth IRA is far more
    // common than a Roth 401k), tax-deferred -> employer plan.
    setAccount(i, {
      type,
      expected_return: DEFAULT_RETURNS[type],
      cost_basis: type === "taxable" ? input.accounts[i].cost_basis : null,
      vehicle:
        type === "roth" ? "ira" : type === "tax_deferred" ? "employer" : input.accounts[i].vehicle,
    });
  };

  return (
    <div className="space-y-3">
      {errors["accounts"] && (
        <p className="text-xs font-medium text-red-600">{errors["accounts"]}</p>
      )}
      {input.accounts.map((a, i) => {
        const e = (f: string) => errors[`accounts.${i}.${f}`];
        return (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
            <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 lg:grid-cols-12"}`}>
              <TextField
                label="Account name"
                value={a.name}
                onChange={(name) => setAccount(i, { name })}
                error={e("name")}
                className={dense ? "col-span-2" : "col-span-2 lg:col-span-3"}
              />
              <SelectField
                label="Type"
                value={a.type}
                onChange={(t) => setType(i, t)}
                options={TYPE_OPTIONS}
                error={e("type")}
                className={dense ? "" : "lg:col-span-3"}
                help="Drives tax treatment: tax-deferred is taxed as ordinary income on withdrawal (with RMDs); Roth withdrawals are tax-free; taxable pays dividend/capital-gains tax; HSA is tax-free for medical; cash interest is taxed annually."
              />
              {(a.type === "tax_deferred" || a.type === "roth") && (
                <SelectField
                  label="Vehicle"
                  value={a.vehicle ?? (a.type === "roth" ? "ira" : "employer")}
                  onChange={(vehicle) => setAccount(i, { vehicle })}
                  options={VEHICLE_OPTIONS}
                  className={dense ? "" : "lg:col-span-2"}
                  help="Which IRS contribution limit applies: employer plans (401k/403b) allow far larger contributions than IRAs. Also decides whether the Roth IRA income limit applies (a backdoor Roth is flagged above it). Does not change how withdrawals are taxed."
                />
              )}
              <SelectField
                label="Owner"
                value={a.owner}
                onChange={(owner) => setAccount(i, { owner })}
                options={ownerOptions}
                error={e("owner")}
                className={dense ? "" : "lg:col-span-2"}
                help="Determines whose age drives RMDs, early-withdrawal penalties, and survivor treatment."
              />
              <NumberField
                label="Balance"
                value={a.balance}
                onChange={(balance) => setAccount(i, { balance })}
                min={0}
                prefix="$"
                error={e("balance")}
                className={dense ? "" : "lg:col-span-2"}
              />
              <OptionalPercentField
                label="Return"
                value={a.expected_return}
                onChange={(expected_return) => setAccount(i, { expected_return })}
                min={-10}
                max={20}
                placeholder={`${DEFAULT_RETURNS[a.type] * 100}`}
                error={e("expected_return")}
                className={dense ? "" : "lg:col-span-2"}
                help="Expected nominal annual return. Defaults by type: 6% tax-deferred/Roth/taxable, 5% HSA, 4% cash. Deterministic compounding — see the sensitivity table for ±1–2% return stress tests."
              />
              <NumberField
                label="Annual contribution"
                value={a.annual_contribution}
                onChange={(annual_contribution) => setAccount(i, { annual_contribution })}
                min={0}
                prefix="$"
                error={e("annual_contribution")}
                className={dense ? "" : "lg:col-span-3"}
                help="Contributed each year until the owner retires. Grows with inflation if that assumption is enabled."
              />
              {a.type === "taxable" && (
                <OptionalNumberField
                  label="Cost basis"
                  value={a.cost_basis}
                  onChange={(cost_basis) => setAccount(i, { cost_basis })}
                  min={0}
                  prefix="$"
                  placeholder="= balance"
                  error={e("cost_basis")}
                  className={dense ? "" : "lg:col-span-3"}
                  help="Taxable accounts only: total cost basis today. Withdrawals realize capital gains in proportion to the unrealized gain. Leave blank to assume basis equals the balance (no embedded gain)."
                />
              )}
              <div
                className={`flex items-end justify-end ${dense ? "col-span-2" : "lg:col-span-6"}`}
              >
                <button
                  type="button"
                  onClick={() => onChange({ ...input, accounts: removeAt(input.accounts, i) })}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Remove
                </button>
              </div>
            </div>
            <ModelingDisclosure assetKey={a.type} className="mt-3" />
          </div>
        );
      })}
      <button
        type="button"
        onClick={() => onChange({ ...input, accounts: [...input.accounts, newAccount()] })}
        className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-700"
      >
        <Plus className="h-3.5 w-3.5" /> Add account
      </button>
    </div>
  );
}
