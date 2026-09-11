# v5 Explanatory Figure Package

This independent package adds three English-only explanatory figures to the active v5 manuscript. It does not replace the already reviewed Q1/Q2 or v5 Q3/Q4 result-comparison figures.

| Paper figure | Asset directory | Purpose and source boundary |
|---|---|---|
| Figure 8 | `q3_monthly_saving/outputs/chart.{png,svg}` | Monthly and chronological cumulative historical saving of `q3_raw` versus `q3_no_update`. The total is derived by adding two compatible paired monthly comparisons, as documented in `source_hashes.json`. |
| Figure 9 | `q3_peak_day_execution/outputs/chart.{png,svg}` | Physical execution trace for the `q3_raw` date with the largest realized daily emergency purchase. The date is selected by that deterministic rule, not for typicality. |
| Figure 11 | `q43_causal_trace/outputs/chart.{png,svg}` | Actual price, causally available price forecasts, purchase-plan versions, and strict execution on the predeclared causal-audit date 2025-07-14. |

The input copies, source hashes, ModelViz requirement and candidate records, final selections, dependency records, adapted plotting scripts, execution records, and final technical/visual quality reports remain under each task's `data/` and `workspace/` directories. All three charts use a ModelViz-recalled time-series template from the local catalog (`trd_dual_axis_bar_line`) and were adapted only to the listed real columns. The original result ledgers and their time keys are never modified.

Each PNG is 300 dpi and each has an SVG counterpart. Manual visual inspection and the retained ModelViz quality reports found no clipping, overlap, or missing output artifact. The first trial for the two multi-panel charts selected a catalog template that required `scipy`; it was rejected before plot execution because that unused dependency is unavailable in the execution environment. The final selected template requires only the available plotting stack, and the failed dependency record is retained in the corresponding workspace for an auditable run history.

The source-preparation and ModelViz driver scripts are in `scripts/paper_visuals_v4_explanation/`. Re-run the input preparation before regenerating figures if, and only if, the verified v5 result bundle changes.
