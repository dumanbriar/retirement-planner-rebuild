import type { Person } from "../../lib/types";
import { newPerson } from "../../lib/sample";
import { CheckboxField, NumberField, SelectField, TextField } from "../ui/fields";
import { type SectionProps, updateAt } from "./sectionProps";

const CLAIM_AGES = [62, 63, 64, 65, 66, 67, 68, 69, 70].map((a) => ({
  value: a,
  label: a === 67 ? "67 (FRA)" : String(a),
}));

function PersonFields({
  person,
  index,
  onChange,
  errors,
  dense,
}: {
  person: Person;
  index: number;
  onChange: (p: Person) => void;
  errors: SectionProps["errors"];
  dense?: boolean;
}) {
  const e = (f: string) => errors[`persons.${index}.${f}`];
  const set = (patch: Partial<Person>) => onChange({ ...person, ...patch });
  return (
    <div className="space-y-3">
      <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
        <TextField
          label="Name"
          value={person.name}
          onChange={(name) => set({ name })}
          error={e("name")}
          className={dense ? "col-span-2" : "col-span-2 sm:col-span-1"}
        />
        <NumberField
          label="Current age"
          value={person.current_age}
          onChange={(current_age) => set({ current_age })}
          min={18}
          max={99}
          error={e("current_age")}
        />
        <NumberField
          label="Retirement age"
          value={person.retirement_age}
          onChange={(retirement_age) => set({ retirement_age })}
          min={30}
          max={80}
          error={e("retirement_age")}
          help="The age this person stops working. Contributions stop and the plan switches to drawing down savings."
        />
        <NumberField
          label="Plan-end age"
          value={person.death_age}
          onChange={(death_age) => set({ death_age })}
          min={60}
          max={105}
          error={e("death_age")}
          help="Plan horizon for this person (life expectancy). The plan must fund spending through this age. Stress-tested to 100 in the sensitivity analysis."
        />
      </div>
      <div className={`grid gap-3 ${dense ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-4"}`}>
        <NumberField
          label="SS monthly at FRA"
          value={person.ss_monthly_at_fra}
          onChange={(ss_monthly_at_fra) => set({ ss_monthly_at_fra })}
          min={0}
          prefix="$"
          error={e("ss_monthly_at_fra")}
          className="col-span-2"
          help="Monthly Social Security benefit at full retirement age, from this person's SSA statement (the PIA), in today's dollars. Claiming earlier or later adjusts it using the exact statutory monthly formula."
        />
        <SelectField
          label="SS claiming age"
          value={person.ss_claim_age}
          onChange={(ss_claim_age) => set({ ss_claim_age })}
          options={CLAIM_AGES}
          error={e("ss_claim_age")}
          className={dense ? "col-span-2" : "col-span-2"}
          help="Age benefits start (62–70). Early claiming reduces the benefit 5/9% per month (first 36 months) then 5/12%; delaying past FRA earns 2/3% per month to 70. Check 'Optimize Social Security claiming ages' to let the engine search all combinations."
        />
        <NumberField
          label="Annual salary (today's $)"
          value={person.salary}
          onChange={(salary) => set({ salary })}
          min={0}
          prefix="$"
          error={e("salary")}
          className="col-span-2"
          help="Gross earned income while working, in today's dollars. Enables real working-year income tax and the marginal bracket used to weigh Traditional vs Roth contributions. Leave 0 if not working or not optimizing the contribution split."
        />
      </div>
    </div>
  );
}

export function HouseholdSection({ input, onChange, errors, dense }: SectionProps) {
  const hasSpouse = input.persons.length > 1;

  const toggleSpouse = (on: boolean) => {
    if (on) {
      onChange({ ...input, persons: [input.persons[0], newPerson(1)] });
    } else {
      // Reassign anything owned by person 2 back to person 1.
      onChange({
        ...input,
        persons: [input.persons[0]],
        accounts: input.accounts.map((a) => ({ ...a, owner: 0 })),
        income_streams: input.income_streams.map((s) => ({ ...s, owner: 0 })),
      });
    }
  };

  return (
    <div className="space-y-4">
      {input.persons.map((p, i) => (
        <div key={i} className={i > 0 ? "border-t border-slate-100 pt-4" : ""}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Person {i + 1}
          </p>
          <PersonFields
            person={p}
            index={i}
            errors={errors}
            dense={dense}
            onChange={(np) => onChange({ ...input, persons: updateAt(input.persons, i, np) })}
          />
        </div>
      ))}
      <CheckboxField
        label="Include spouse / partner"
        checked={hasSpouse}
        onChange={toggleSpouse}
        help="Adds a second person. The plan files as married-filing-jointly while both are alive and models spousal Social Security benefits."
      />
    </div>
  );
}
