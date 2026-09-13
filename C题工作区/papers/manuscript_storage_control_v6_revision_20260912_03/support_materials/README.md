# Scientific programs and saved-result support

This directory contains the complete scientific source used for Q1 and the current v6 procurement and reserve-controller experiment, configurations, losslessly stored issued decisions, comparison evidence and the five unchanged English result workbooks. It contains no manuscript PDF and no copies of the original contest attachments.

## Environment and a lightweight first run

Use Python 3.12 and a C99 compiler available as `cc`. The exact tested Python packages are pinned in `requirements.txt`. Run commands from this directory, ideally in a fresh extracted copy:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python scripts/check_saved.py
python scripts/smoke_test.py
```

`check_saved.py` does not import production optimizer modules. It checks the exact workbook identities, reads every workbook cell, checks the saved Q1 solution, all four selected annual issued q/R paths, 16 complete specified-day executions, all 22 daily cost summaries and the January boundary continuity. `smoke_test.py` compiles the actual C kernel, repeats the small Q1 MILP, and exercises the unchanged joint search on one synthetic six-interval diagnostic. Neither command runs an annual optimization. They write only new check reports and a local compiled runtime.

## Prepare original inputs

Place the four original attachments in `raw/` as specified in `raw/README.md`; their contents and headers must remain unchanged. Then run:

```sh
python scripts/prepare_inputs.py
python scripts/check_saved.py --full-inputs --output full_replay_checks.json
```

Preparation executes `prepare_data.py` for raw parsing and trapezoidal integration and the frozen `compat.forecast_day` body for each historical release using only its own completed history. It saves `results/q2_direct_v4/forecasts/linear_harmonic.csv`. The v6 price module constructs the OLS cache using only observations completed by each issue. Use `--without-price-cache` only if prices should instead be recalculated on demand by the unchanged input module.

The optional `--full-inputs` check replays the four selected annual physical trajectories from the original actual inputs and the saved q/R arrays, comparing daily costs and states. It performs no optimization. Full input reconstruction and a lightweight clean-extraction run were checked for this package; the separate manuscript audit provides an independent reconstruction of all 22 original annual trajectories.

## Complete scientific programs

| Program | Role |
| --- | --- |
| scripts/prepare_data.py | Original raw schema, interval mapping and PV integration |
| scripts/prepare_inputs.py | Portable preparation order and historical forecast archive |
| scripts/solve_q1.py | Complete Q1 MILP, LP relaxation and named Q1 diagnostics |
| scripts/run_q2.py | Preserved historical baseline, January warmup and forecast-selection source |
| scripts/storage_control_v6/compat.py | Frozen forecast, initializer and settlement function bodies |
| scripts/storage_control_v6/inputs.py | Causal scenario, PV correction and price inputs |
| scripts/storage_control_v6/control.py | Actual reserve-threshold storage execution |
| scripts/storage_control_v6/kernel.py and kernel.c | Compiled scenario objective and derivatives |
| scripts/storage_control_v6/policy.py | Candidate generation, four searches, retention and selection |
| scripts/storage_control_v6/run.py | All 22 current policies, issue timing, continuous storage and cash settlement |
| scripts/storage_control_v6/analyze.py | Current selection and 29 matched/historical comparisons |
| scripts/check_saved.py and scripts/smoke_test.py | Independent saved-result checks and bounded execution checks |

All original scientific modules retain their mathematical function bodies and parameters. Only input-root/file naming and non-scientific logging metadata were adapted where necessary; `SOURCE_PROVENANCE.json` gives original and package hashes and exact roles. `source_changes.diff` records these few changes. Original input-schema strings retain their runtime meaning.

These preserved configuration status strings and legacy policy entries document their original development stage; the current 22-policy run is selected by `configs/storage_control_v6/experiments.json`. They are not current submission-status or permission claims.

## Optional expensive reproduction

The following commands are provided for later reproduction and were **not** run as annual optimization during this packaging revision:

```sh
python scripts/solve_q1.py
python scripts/storage_control_v6/run.py --policies q2_reserve q3_w28_reserve q42_ols_reserve q43_raw_ols_reserve
```

The Q1 entry runs its declared one-day diagnostics. The annual entry above reruns four selected strategies over 334 days; omitting `--policies` reruns all 22. Each run refuses to overwrite an existing run directory. Full annual analysis requires all 22 regenerated current ledgers:

```sh
python scripts/storage_control_v6/run.py
python scripts/storage_control_v6/analyze.py
```

Choose either the selected-only run or the all-policy run in a clean extracted copy; do not run both into the same default results directories. These optional commands regenerate scientific ledgers and analysis; they do not update the five preserved XLSX deliverables. The spreadsheet-formatting exporter is not included in this scientific program package. The packaged four thin historical-reference ledgers provide precisely the date, cash and final-state columns needed by `analyze.py`; they are identified historical two-search references, not regenerated current outputs. Running `scripts/run_q2.py` is a separate historical baseline/selection experiment and is not required for v6 because its frozen February initial state and chosen forecast family are already recorded.

## Saved evidence, roles and limits

- `saved/q1/` contains the baseline and explicitly named relaxation, efficiency, no-storage and alternative-optimum diagnostics. The baseline schedule is the source of result1.xlsx.
- `saved/warmup/` preserves the January seasonal path, ending at 7,268.4231640740745 kWh. Annual policies start there and carry their own continuous states; they do not reuse Q1's solved daily purchase vector.
- `saved/selected/` contains full annual q0/final-q/R arrays and all selected-policy issued q/R versions as compressed NPZ columns. Numeric values and row ordering are exactly retained from the original CSVs. It also contains complete ledger and version rows for 20 March, 21 June, 23 September and 21 December.
- `saved/all_policies/` retains all 22 daily summaries, configurations and totals, including adverse greedy/reserve and correction results. `saved/comparisons/` retains the 29 matched/historical comparisons and restricted reserve-family selection.
- `results/q2_direct_v4/runs/D112/` and the three `results/unified_direct_v5/runs/` reference directories are historical cost/state projections for comparison, with source hashes. They are not current v6 physical ledgers.
- `workbooks/` contains the five byte-identical English attachments and their policy mapping. The mapping's project-relative source paths identify original provenance; the runnable package's current files are under `workbooks/` and `saved/`.

Reserve R limits deficit discharge; it is not a hard lower bound on actual inventory and emergency electricity is not used to charge toward R. Emergency cost is the complete fivefold price and is added once to final contract cost. Terminal inventory value in planning is not cash revenue. The diagnostic value 0.6895775 CNY/kWh is the mean fixed tariff times 0.9; it differs from the planning weight 0.38232. The frozen policy matrix preserves the paper's Q4-2 information interpretation and reserve-family selection; packaging does not resolve those scientific scope choices or add sensitivity evidence.

`MANIFEST.csv` is the exact file inventory with hashes, excluding the manifest itself to avoid a self-hash cycle. Complete source listings appear in the paper's program appendix. Compressed saved arrays preserve decisions and support replay; they do not include every discarded candidate or replace a new optimization run. Solver/platform changes can affect nonsmooth ties and alternative optimum choices; the bounded tests do not establish universal portability or global optimality of the annual searches.

`Details of AI Tool Usage.pdf` is prepared under the official English filename, accompanied by an English declaration. The actual submission route remains to be confirmed by the team; this package does not certify that the English filename is the applicable portal choice. The manuscript PDF is delivered separately.
