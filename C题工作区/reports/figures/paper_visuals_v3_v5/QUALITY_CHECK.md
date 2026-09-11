# Figure Quality Check — v5

## Traceability

- Source files: `results/unified_direct_v5/comparison_all.csv`, `paired_monthly.csv`, and `paired_summary.csv`.
- Source SHA-256 values and selection rules: `source_hashes.json`.
- Q3 values reconcile to `q3_no_update`, `q3_soc`, `q3_raw`, and `q3_w28` in `comparison_all.csv`.
- Q4 panels are only matched pairs: `q42_ols` versus `q42_fixed`, and `q43_raw_ols` versus `q43_raw_fixed`.

## Rendering and inspection

- `framework_v5/outputs/chart.png`: 3129 × 1700 px, 300 dpi; English labels, no clipping observed.
- `q3_policy_costs/outputs/chart.png`: 2344 × 1243 px, 300 dpi; ModelViz technical and visual checks pass after one layout repair.
- `q4_price_effect/outputs/chart.png`: 3214 × 1420 px, 300 dpi; ModelViz technical and visual checks pass without repair.
- Each PNG has a corresponding SVG in the same output directory.
- Manual visual inspection confirmed readable axes, legends, labels, non-overlapping annotations, and positive-saving convention.

## Interpretation limits carried into the captions/text

- Q3’s selected raw-PV policy is highlighted as the frozen v5 choice, not as a significance claim.
- Q4 panels do not compare the absolute cost of Q4-2 with Q4-3. Each panel reports only its own matched fixed-versus-OLS planning-price comparison.
- The figures are descriptive historical outputs. Neither includes a claim of global optimization, a future-year guarantee, or statistical significance.
