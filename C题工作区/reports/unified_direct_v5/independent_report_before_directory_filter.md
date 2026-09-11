# Independent validation

Executed scope: sources_regressions_and_available_policy_evidence
Executed checks: PASS; 0 failed check groups.

Original Appendix 1–4 workbooks were independently reconstructed and compared with processed inputs. B0 forecasts were refit from each completed prefix. Appendix 3 interpolation uses the preceding published forecast as first-hour anchor, and historical PV corrections use their own midnight cutoffs, same-day horizons, same issue hour and April 1 activation. Prices are independently refit using causal 28-day OLS.

Working assumptions remain interval-end labels, average interval power, point-power trapezoidal forecasts, end-of-interval actual availability and settlement rule A. These are not newly confirmed interpretations of the original problem.

Frozen Q2 D112 and Q1 regressions are independently recomputed from source prices and physical equations.

## Coverage
- q3_no_update: 48096 ledger intervals, 334 decisions, 2004 candidate vectors, 204030 candidate-scenario physical paths.
- q3_raw: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.
- q3_soc: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.
- q3_w28: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.
- q42_fixed: 48096 ledger intervals, 334 decisions, 2004 candidate vectors, 204030 candidate-scenario physical paths.
- q42_ols: 48096 ledger intervals, 334 decisions, 2004 candidate vectors, 204030 candidate-scenario physical paths.
- q43_raw_fixed: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.
- q43_raw_ols: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.
- q43_w28_fixed: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.
- q43_w28_ols: 48096 ledger intervals, 1336 decisions, 9018 candidate vectors, 918135 candidate-scenario physical paths.

## Failures
- None in the executed checks.

## Pending / outside scope
- Independent XLSX readback is owned by the workbook reviewer and not asserted here.
- .DS_Store: incomplete run
