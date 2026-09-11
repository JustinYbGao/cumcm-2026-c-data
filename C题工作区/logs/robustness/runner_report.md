# Robustness runner report

Date: 2026-09-10  
Scope: frozen Task 1 replay and assumption runs; internal and retrospective.

## Outcome

The runner completed all ten continuous February 1–December 31 policies from the common
7268.4231640740745 kWh state. Every policy contains 334 days, 48,096 executed intervals,
1,336 saved 0/6/12/18 plans, and the standard ledger, daily, solver, representative-table,
summary, and emergency-event exports.

The `fixed_raw` cash total is 13,772,880.061223056 yuan, exactly equal to the frozen Q3
`all_A` result. Its maximum absolute difference from the Q3 ledger is zero over the shared
physical, state, and cash columns. `variable_raw` likewise has zero maximum difference from
the frozen Q4 `q43_all_A_ols` ledger over those columns.

No January warmup was recomputed. All policies start from the frozen February state, actual
SOC is carried interval to interval across day and month boundaries, and corrected policies
use raw PV through March 31. Each corrected policy has 1,100 active correction issues from
April 1 onward. Bias fits use only positive raw-PV targets from the same issue hour whose
target intervals completed by the issue-day midnight cutoff. Correction is applied only to
positive current raw PV and is clipped at zero.

The variable policies use `results/q4/price_forecasts.csv` for planning and
`actual_price_yuan_per_kwh` from `data/processed/actual_10min.csv` for settlement. The fixed
policies use Appendix 1 fixed prices for both. The soft policies use an explicit terminal
penalty of 0.6895775 yuan/kWh. The terminal-inventory diagnostic uses that same common
reference and is kept separate from cash cost.

## Cash results

| Policy | Full 334-day cost (yuan) | Apr–Dec cost (yuan) | Final SOC (kWh) | Full inventory-adjusted diagnostic (yuan) |
|---|---:|---:|---:|---:|
| fixed_raw | 13,772,880.061223056 | 11,438,135.242117018 | 7,173.092755226 | 13,772,945.798928063 |
| fixed_w28 | 13,726,733.574967869 | 11,391,988.755861834 | 7,114.890175392 | 13,726,839.447862372 |
| fixed_w14 | 13,736,212.994924420 | 11,401,468.175818384 | 7,095.720289964 | 13,736,332.086940590 |
| fixed_w56 | 13,724,087.090618731 | 11,389,342.271512697 | 7,114.387035476 | 13,724,193.310467200 |
| efficiency_raw | 13,306,927.336907811 | 11,055,054.933124851 | 7,532.254162639 | 13,306,745.404987400 |
| efficiency_w28 | 13,255,998.709691064 | 11,004,126.305908104 | 7,429.686773909 | 13,255,887.505934151 |
| soft_raw | 13,772,796.986768603 | 11,438,052.167662568 | 7,086.667934802 | 13,772,922.321085218 |
| soft_w28 | 13,726,608.563173931 | 11,391,863.744067896 | 7,091.963624233 | 13,726,730.245702269 |
| variable_raw | 14,534,062.642403048 | 12,142,444.109469593 | 7,804.593371647 | 14,533,692.911491737 |
| variable_w28 | 14,492,279.546435216 | 12,100,661.013501760 | 7,804.649180961 | 14,491,909.777039057 |

## Paired correction comparisons

Positive savings mean the corrected policy cost less than its setting-matched raw policy.
The Apr–Dec comparison is the predeclared configuration comparison; the full-period value is
also retained, including the final deployed fixed w28 versus raw comparison.

| Setting | Window | Apr–Dec cash saving (yuan) | Apr–Dec inventory-adjusted saving (yuan) | Full 334-day cash saving (yuan) |
|---|---:|---:|---:|---:|
| fixed | 14 | 36,667.066298634 | 36,613.711987469 | 36,667.066298638 |
| fixed | 28 | 46,146.486255184 | 46,106.351065690 | 46,146.486255188 |
| fixed | 56 | 48,792.970604323 | 48,752.488460863 | 48,792.970604325 |
| efficiency | 28 | 50,928.627216747 | 50,857.899053246 | 50,928.627216749 |
| soft terminal | 28 | 46,188.423594672 | 46,192.075382952 | 46,188.423594672 |
| variable price | 28 | 41,783.095967833 | 41,783.134452680 | 41,783.095967831 |

These are retrospective assumption comparisons and do not select a new winning configuration.

## Files and interface

- Runner: `scripts/run_robustness.py`
- Frozen configuration: `configs/robustness.json`
- Boundary tests: `tests/test_robustness.py`
- Top-level outputs: `results/robustness/config_snapshot.json`,
  `input_code_hashes_before.json`, `input_code_hashes_after.json`, `comparison.csv`,
  `paired_comparison.csv`, `pv_bias_models.json`, and `run_status.json`
- Policy outputs: `results/robustness/<policy>/ledger.csv`, `plan_versions.csv`,
  `solvers.json`, `daily.csv`, `summary.json`, `table1_representative.csv`,
  `table2_representative.csv`, `table3_representative.csv`, and
  `emergency_events.csv`
- Logs: `logs/robustness/run.log`, `tests.log`, and `output_checks.log`
- All temporary paths were redirected to `data/interim/robustness`.

Ledgers retain raw, corrected, and used PV forecasts; Q4 planning, actual, and settlement
prices; active issue times; and actual executor state/physics. Saved plans retain both PV
versions, planning prices, efficiencies, terminal form and penalty, and planned physical
variables. Solver records retain the full correction cutoff/window/bias metadata, price
provenance, physical assumption, objective decomposition, status, bound, gap, and runtime.

## Commands and observed results

Initial test-first run:

```bash
.venv/bin/python -m unittest tests/test_robustness.py
```

Observed before implementation: 4 tests ran; 3 failures and 1 error, caused by the missing
runner/config and therefore the intended red state.

Boundary test after implementation:

```bash
.venv/bin/python -m unittest tests/test_robustness.py
```

Observed: 4 tests passed.

Full execution:

```bash
mkdir -p logs/robustness
set -o pipefail; .venv/bin/python scripts/run_robustness.py 2>&1 | tee logs/robustness/run.log
```

Observed: exit 0; ten policies completed; baseline difference 0.0 yuan; before/after source
hash manifests identical.

Fresh combined tests:

```bash
set -o pipefail; .venv/bin/python -m unittest tests/test_robustness.py tests/test_innovation_core.py tests/test_q4.py 2>&1 | tee logs/robustness/tests.log
```

Observed: 18 tests passed in 0.042 s.

The integration assertions were run with an inline
`.venv/bin/python - <<'PY' ... PY` block and logged with
`tee logs/robustness/output_checks.log`. Observed: all ten policy artifact sets present;
48,096 ledger rows, 120,240 plan rows, 1,336 solver records and 334 daily rows per policy;
SOC continuity residual 0; 6,600 active bias records; no correction before April 1; all
nonpositive raw-PV outputs stayed zero; Q3 and Q4 raw anchor residuals both 0; manifests
identical.

Independent Task 2 verification reported 429,222 checks with no failures and maximum
residual 2.5756889954209328e-09. Its 160 independent LP cases all passed; maximum LP primal
violation was 1.8189894035458565e-12 and the reported objective differences were numerical
roundoff.

## Hashes

| Artifact | SHA-256 |
|---|---|
| `configs/robustness.json` | `1ebe2e37d86b75d956022c54258179662f913fd2071420bbdf2157e5cdb9241e` |
| `scripts/run_robustness.py` | `7b259693b5929442c467c3583cc80d2d433d11ac5bff7d3c762b39cb97c5ed63` |
| `tests/test_robustness.py` | `9a0280997709870e91595dcdd9ee16ccb250ef887e724317f326a2321aa11efe` |
| before hash manifest | `134dbeaff96585a7cd91483a9774b9b281675f7f7b930b42b805dc98576148cd` |
| after hash manifest | `134dbeaff96585a7cd91483a9774b9b281675f7f7b930b42b805dc98576148cd` |
| `results/robustness/run_status.json` | `e587deafa88fca9ac734ad6fb1e3d0e8199e826c1c4c5fd3d477e78983a1019b` |
| `logs/robustness/run.log` | `5b13e4b41b52211e9fd44de9f63172cdab81f605282ac26a71d4e596f3deacd8` |
| `logs/robustness/tests.log` | `f56cc8547d186f57eda612a82d984afd07531897c7e15343cd070f21ed30e2ea` |
| `logs/robustness/output_checks.log` | `a8b847583e91fc8fe84691f4683b6b0a63333a245533bd73892b2c00aa27fb7e` |
