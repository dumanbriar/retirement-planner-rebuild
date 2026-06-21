# Horizon — Retirement Planner

**Live app**: https://horizon-retirement-kappa.vercel.app
**Engine API**: https://backend-production-cf36.up.railway.app (docs at `/docs`)

A professional retirement planning tool for financial advisors to use live
with clients. Deterministic, auditable, assumption-forward: every number on
screen is reproducible from the exported Excel workbook.

- **Frontend**: React + Vite + TypeScript + Tailwind + Recharts (deployed to Vercel)
- **Backend**: Python FastAPI projection engine (deployed to Railway)
- No accounts, no logins, no stored data — inputs live in the advisor's browser.

## What it models

**Accumulation** (until every household member reaches their retirement age):
per-account contributions, configurable expected returns, annual tax drag on
taxable dividends (15%) and cash interest (flat pre-retirement rate), forced
RMDs, and liabilities amortizing on schedule. When a salary is entered,
working-year federal/state income tax is computed from wages, and the
**Traditional-vs-Roth contribution split** can be optimized: each person's
contribution is held constant, the Traditional deduction is valued at the real
marginal bracket and its tax saving reinvested in taxable ("invest the tax
savings"), and splits are exhaustively compared on ending after-tax wealth.
Contribution limits are vehicle-aware per person (401(k)/403(b)
elective-deferral vs IRA); Roth-IRA contributions above the income limit are
flagged as requiring a backdoor Roth.

**Retirement** (year by year until the configured plan-end age):
- Withdrawal sequencing: cash → taxable → tax-deferred → Roth → HSA, with the
  HSA paying qualified medical costs first (tax-free).
- Roth conversions that fill a target ordinary-income bracket, with an
  `auto` mode that exhaustively compares fill levels and reports every
  candidate (objective: ending after-tax wealth in today's dollars).
- Social Security: exact monthly early-reduction / delayed-credit formulas,
  spousal top-up, survivor step-up, optional exhaustive claiming-age grid
  (62–70 per spouse).
- RMDs per SECURE 2.0 (age 73 born 1951–59, 75 born 1960+), IRS Uniform
  Lifetime Table.
- Taxes: 2026 federal brackets and standard deduction (indexed forward at the
  plan inflation assumption), LTCG/qualified-dividend 0/15/20% stacking,
  Social Security taxability worksheet (unindexed thresholds, as in law),
  NIIT (unindexed), OBBBA senior deduction (2025–2028 with phase-out),
  optional flat state rate. Taxes are solved to a fixed point with the
  withdrawals that fund them.
- Healthcare: ACA benchmark-premium subsidy model pre-65 (2026
  applicable-percentage schedule incl. the 400% FPL cliff), Medicare Part B +
  IRMAA with the statutory **two-year MAGI lookback** modeled explicitly.
- Cost-basis tracking on taxable accounts (pro-rata gain realization,
  dividend reinvestment), early-withdrawal penalties, spousal account
  rollover at death, survivor filing-status switch.

**Trust layer**
- `POST /api/plan/excel` exports an audit workbook: Summary, Assumptions
  (every input + every modeling rule with its source), Accumulation,
  Retirement (full cash-flow + tax detail per year), Account Detail (every
  account, every year: start + contributions − withdrawals ± conversions +
  growth = end), Strategies (all Roth/SS candidates considered), Sensitivity.
- Sensitivity scenarios: returns ±1/−2%, inflation +1%, spending ±10%,
  retirement age ±2, Social Security −23% (trust-fund depletion scenario),
  longevity to 100.
- Everything on screen is labeled **modeled** (statutory rule, exact),
  **estimated**, or **assumed**.

## Sources

| Item | Source |
|---|---|
| 2026 federal brackets, standard deduction, LTCG breakpoints | IRS Rev. Proc. 2025-32; OBBBA (P.L. 119-21) |
| Senior bonus deduction | OBBBA §70103 (IRC §151(d)(6)), 2025–2028 |
| SS benefit taxation | IRC §86; IRS Pub. 915 worksheet |
| SS claiming adjustments | 42 U.S.C. §402(q), §402(w); SSA |
| RMD ages & factors | SECURE 2.0 §107; IRS Pub. 590-B Uniform Lifetime Table |
| Medicare Part B 2026 ($202.90/mo) + IRMAA multiples | CMS 2026 announcement; 42 U.S.C. §1395r(i) |
| ACA applicable percentages 2026 | Rev. Proc. 2025-25; HHS 2025 poverty guidelines |
| NIIT | IRC §1411 |
| HSA rules | IRC §223; IRS Pub. 969 |
| Basis step-up at death | IRC §1014 |
| 2026 contribution limits & Roth-IRA MAGI phase-out | IRS Notice 2025-67; IRC §402(g), §219, §408A |

## Documented simplifications

These are deliberate, visible modeling choices (also listed in the workbook):
- Deterministic annual compounding; no return volatility (sensitivity
  scenarios bound the range instead of Monte Carlo).
- Wages are modeled only when a salary is entered (to value the
  Traditional-vs-Roth deduction and working-year income tax); otherwise they
  are not and pre-retirement investment income is taxed at flat rates. Either
  way, pre-retirement spending/debt service is assumed covered by employment
  income, and household drawdown begins when **both** spouses are retired.
  FICA is not modeled (it doesn't change the deferral decision), the
  backdoor-Roth pro-rata rule (IRC §408(d)(2)) is not modeled, and
  contributions above IRS limits are flagged rather than capped.
- Brackets/IRMAA/FPL index at the plan inflation assumption (IRS uses
  chained CPI with $25/$50 rounding).
- One inflation assumption serves as SS COLA proxy; PIA estimates are
  treated as today's-dollar amounts.
- Whole-year granularity (age 59.5 → 60, claiming ages in whole years).
- Survivor benefit = larger of the two benefits (approximation of the
  RIB-LIM rules); spousal top-up assumes deemed filing.
- ACA subsidy uses a user-supplied benchmark premium estimate; Medicaid
  territory below 100% FPL treated as fully subsidized.

## Run locally

```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000 (docs at /docs)
python -m pytest tests/ -q             # hand-verified statutory test cases

# frontend
cd frontend && npm install
npm run dev                            # http://localhost:5173
```

## Deployment

`.github/workflows/deploy.yml` tests, then deploys the backend to Railway
(`railway up`, health-checked, API smoke-tested) and the frontend to Vercel
with `VITE_API_URL` pointed at the deployed backend. Tokens live in repo
Actions secrets (`RAILWAY_TOKEN`, `VERCEL_TOKEN`).
