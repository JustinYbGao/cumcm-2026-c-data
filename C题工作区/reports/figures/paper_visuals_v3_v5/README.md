# v5 Paper Figure Package

This package replaces only the figures made stale by the v5 direct-purchase migration:

- `framework_v5/outputs/chart.{png,svg}` — revised common model and verification flow.
- `q3_policy_costs/outputs/chart.{png,svg}` — within-family Q3 cost composition.
- `q4_price_effect/outputs/chart.{png,svg}` — monthly and cumulative within-branch Q4 price-planning differences.

The Q3 and Q4 charts were generated with the user-supplied ModelViz workflow. Their Stage 1/3 requirements and candidate recall, Stage 4 template selections, Stage 5 adaptation plans/code, and Stage 7 quality reports are retained in each task's `workspace/` directory. The chosen template IDs are `cmp_correlation_stacked_bar` for Q3 and `trd_dual_axis_bar_line` for Q4. Q3 required one localized repair: moving the legend and removing a redundant selected-policy annotation that overlapped the tick label. Both final reports pass technical and visual checks.

`source_hashes.json` records SHA-256 hashes of the v5 result files used to prepare the compact chart inputs. The plotting input tables contain no altered observations: `q3_policy_costs.csv` is a direct four-policy extract from `comparison_all.csv`, and `q4_price_effect.csv` is a direct paired-monthly extract with a chronological cumulative sum. Positive Q4 saving always means that the OLS planning-price candidate has the lower realized total cost within the named branch.

The framework diagram is a paper-native structural figure rather than a data chart; no suitable flow-diagram template exists in the supplied ModelViz catalog, so the ModelViz workflow was not forced onto that unsupported chart type. It was rendered from the declared v5 model structure by `scripts/paper_visuals_v3_v5/render_framework.py` and manually inspected.

All PNG files are 300 dpi and each has a matching SVG. The source-preparation and ModelViz driver scripts are stored in `scripts/paper_visuals_v3_v5/`. The copied local ModelViz runtime under `tools/modelviz-skill-main/` is a non-versioned execution aid; the final paper figures and their task-local provenance are independent of that runtime copy.
