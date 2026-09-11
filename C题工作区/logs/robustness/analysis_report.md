# Robustness stability-analysis implementation

## Frozen comparisons and outputs

The analysis pairs six raw-versus-corrected policies using each policy's saved daily ledger: fixed-price correction windows of 14, 28, and 56 days versus `fixed_raw`; `efficiency_w28` versus `efficiency_raw`; `soft_w28` versus `soft_raw`; and `variable_w28` versus `variable_raw`. Human-readable English comparison labels are exported for charting.

`paired_daily.csv` contains all 334 continuous days from February 1 through December 31 and flags the April–December main evaluation interval. `paired_monthly.csv` and `paired_summary.csv` report both the 275-day April–December main comparison and the additional 334-day February–December comparison. They preserve cash, contract-cost, emergency-cost, and emergency-energy differences; winning, losing, and tied days; best and worst days; cumulative/monthly gains; and each policy's own period-start and period-end SOC.

Inventory-adjusted costs use the explicit common diagnostic value `0.9 × mean(fixed daily price)`. Each raw and corrected cost is adjusted using its own initial and final energy. This diagnostic is kept separate from cash cost.

## Resampling design and limitations

The predeclared main analysis resamples paired April–December daily cost differences, never individual 10-minute intervals. Within every calendar month, fixed-length contiguous blocks are sampled with replacement until the original month length is reached, then truncated. Moving-block lengths are 3, 7, and 14 days, with 5,000 replicates and seed 20260910.

ARCH's [time-series bootstrap documentation](https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html) explains that moving blocks do not wrap and systematically under-sample observations near series endpoints. Monthly stratification creates endpoints in every month, so this issue can recur at each month boundary. The supplement therefore includes an equally reported 7-day circular-within-month control with the same 5,000 replicates and seed. That control removes endpoint underweighting but creates artificial adjacency from each month end to the same month start. Its `method` column identifies it as a sensitivity control; it does not replace the frozen moving-block analysis.

The 95% percentile intervals and `positive_fraction` describe conditional variability under retrospective resampling of the observed daily pairs. `positive_fraction` is descriptive and is not a p-value. Neither method reruns the physical closed-loop controller, represents a fresh unseen test, provides a future guarantee, or supports a formal distribution-free robustness claim. Cross-month dependence is broken by design because blocks remain wholly within calendar months.

## Verification status

Test-first verification command:

```sh
TMPDIR="$PWD/data/interim/robustness" TMP="$PWD/data/interim/robustness" TEMP="$PWD/data/interim/robustness" .venv/bin/python -B -m unittest tests.test_robustness_analysis -v
```

Result: three tests passed. They verify deterministic month-contained moving blocks, month-contained circular wrapping, daily gain signs, cost decomposition, and inventory adjustment from each path's own endpoints.

After all ten runner outputs completed, the final analysis command was:

```sh
TMPDIR="$PWD/data/interim/robustness" TMP="$PWD/data/interim/robustness" TEMP="$PWD/data/interim/robustness" .venv/bin/python -B scripts/analyze_robustness.py
```

Result: exit code 0. All eight internal checks passed. The exports contain 2,004 paired daily rows, 120 monthly rows, 12 scoped summary rows, and 24 bootstrap interval rows. Across the six April–December comparisons, cash gains range from 36,667.07 to 50,928.63 yuan. All moving-block and circular-control 95% intervals are positive in this observed historical resampling; this remains conditional retrospective evidence under the limitations above.
