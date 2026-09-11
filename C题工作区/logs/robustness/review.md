# Supplemental experiment independent implementation review

Status: runner implementation reviewed; independent saved-file audit and representative LP audit prepared, awaiting completion of all ten continuous output paths. Internal retrospective work only.

## Ownership and scope

This reviewer owns `scripts/validate_robustness.py`, `scripts/audit_robustness_lp.py`, `tests/test_robustness_audit.py`, the new validation/LP artifacts, and this report. Existing experiment scripts and artifacts were not changed. The new validator imports no planner, PV-correction implementation or actual executor. The LP driver reuses only the previously independently assembled `audit_innovation_lp.independent_lp`, resets temporary paths after that import, and audits four prescribed dates and four issue hours for each of ten settings (160 horizons).

## Read-only runner findings

No blocking numerical or causality defect found in `scripts/run_robustness.py` against `reports/robustness/execution_plan.md` and `configs/robustness.json`.

- Correction activates on April 1; pre-switch forecasts remain raw. `day_initial` records the continuously carried actual SOC, and nothing resets March 31 to April 1 (`run_robustness.py:188–213,297–303`).
- Both directional efficiencies are changed in the copied planning physical configuration and in the inherited actual greedy executor for the efficiency pair (`run_robustness.py:169–184,300–302`). Fixed February initial state isolates the requested assumption rather than recomputing a different warmup.
- Bias fitting uses positive raw forecasts, the same publication hour, the trailing target window and completed targets by midnight. It applies only on positive current raw PV and clips negative corrected values (`run_robustness.py:43–78`).
- Planning prices remain separate from settlement prices. The variable-price pair reads issue-keyed frozen Q4 OLS forecasts for planning and actual variable prices for final A settlement; other settings settle at fixed prices (`run_robustness.py:193–219,320–324`). No actual future variable prices enter the optimization.
- Soft terminal penalty and monetary inventory reference use the same explicitly fixed value, 0.9 times mean fixed price. Real bills exclude terminal proxies; inventory-adjusted comparisons are separately labeled (`run_robustness.py:339–355`).
- Completed policy outputs and completed runs are protected, and before/after source hashes include numerical kernels/configuration/data. Only new robustness output paths are written.

## Independent audit implementation

The saved-file validator checks continuous time/date/slot keys, source truth and Q2 load forecasts, initial SOC and all interval/day transitions, greedy dispatch, physical power/energy bounds, disposal bookkeeping, each fee component and total bill. Every saved planning horizon is checked against its raw/corrected PV source, issue-specific planning prices and causal metadata, current actual SOC, midnight commitment/terminal target, efficiency setting, physical constraints, exclusivity, terminal behavior, forecast contract fee and total objective. It reconstructs bias training/metadata, all daily/summary/paired comparison totals and inventory adjustments, all three prescribed representative tables and emergency events, the pre-April common pair trajectories, fixed_raw baseline reproduction, and source/status hashes.

The LP audit checks lower bounds and primal feasibility, not exact MILP/LP equality or optimality of realized annual bills. Planned gate/emergency binaries may yield a genuine positive LP relaxation gap.

## New targeted test evidence

A first test-first run recorded the missing validator module. After implementation, three tests passed. A fourth table-boundary test then exposed boolean subtraction and declared missing-window handling; `Audit.frame` was corrected to compare booleans directly and require exact matching missing-value positions before numerical comparison. The full new audit suite now passes four tests (recorded in `logs/robustness/audit_tests.log`): nonfinite residual rejection, shape-mismatch rejection, an analytical settlement-A example, and explicit table missing-value/boolean handling. Prior completed model suites were not rerun.

## Stability-analysis review so far

`analyze_robustness.py` correctly pairs daily raw-minus-corrected costs and applies inventory adjustments using endpoint SOC differences. Within-month moving blocks of 3/7/14 days remain the main frozen resampling design; sampled months are truncated to their original lengths. The separately added circular 7-day control was raised in review because it was absent from the initial plan. The parent confirmed it was added before analysis for a documented boundary-sampling diagnostic and records it separately in `design_addendum.md`, preserving the original plan. It must remain labeled an additional control in the final report.

Final numerical audit and generated-paper review pending; no effectiveness claim is approved by this interim note.

## Completed numerical verification

Both independent commands completed with exit code 0 on the completed ten-policy artifacts; neither required a rerun or changes to runner/numerical kernels:

```bash
.venv/bin/python -B scripts/validate_robustness.py > logs/robustness/validate.log 2>&1
.venv/bin/python -B scripts/audit_robustness_lp.py > logs/robustness/lp_audit.log 2>&1
```

- **429,222 read-back checks passed**, with no failures and maximum recorded residual **2.5756889954209328e-09**. Complete check identities/residuals are saved in `results/robustness/validation.json`.
- **160/160 independent LP horizons passed**, sixteen for each policy. Maximum MILP-minus-LP difference was **5.820766091346741e-11 yuan**, minimum **−1.4551915228366852e-11 yuan**, and maximum LP primal violation **1.8189894035458565e-12**. These representative free-update horizons agree to numerical tolerance; this does not prove general MILP/LP equivalence. The previously observed positive innovation held-commitment relaxation gap belongs to a different audit and is not copied into this one.
- The LP sample dates are April 1, June 21, September 23 and December 21, each at 0/6/12/18. Independently reconstructed contest tables use March 20, June 21, September 23 and December 21. The April switch-boundary LP case must not be confused with the March prescribed reporting date.
- The new targeted audit unit suite passed **four tests** with `.venv/bin/python -B -m unittest tests.test_robustness_audit -v`; log is `logs/robustness/audit_tests.log`. Existing completed model suites were not rerun.

No numerical issues were found requiring changes to the runner or recomputation.

## Assembly/report source review

The generated-supplement logic preserves paired within-setting comparisons and the fixed 28-day selected configuration, separates cash gains from endpoint inventory valuation, reports monthly/daily losses, and correctly limits the bootstrap intervals to conditional historical resampling of already-realized daily fees. It does not claim independently rerun battery paths under resampling or future guarantees. The circular-control addition is separately documented before analysis.

Two factual wording corrections were requested before final generation: (1) the new folders contain full 334-day ledgers/daily fees but only four prescribed dates in table1/2, so the assembly should not call the representative tables full-year tables; (2) the LP's four sample dates should be listed explicitly rather than conflated with the contest's four prescribed table dates. Final generated-file review follows below.

## Final generated-file and packaging-source review

**Final implementation/audit/methodology verdict: approved for packaging as an internal retrospective result and ordered paper-assembly draft. No material unresolved review findings.** Actual final chart visual quality and archive generation remain the parent task's final gates.

Reviewed the generated `papers/robustness_draft.md`, relevant ordered `papers/assembly_v1` main parts/appendices, `source_map.json` and `assembly_validation.json`, plus `scripts/report_robustness.py`, `scripts/assemble_paper.py` and `scripts/package_robustness.py`.

- Both wording fixes are present: Appendix A distinguishes full 334-day ledgers/daily fees from four-date tables, and the new LP paragraph explicitly lists April 1/June 21/September 23/December 21.
- The generated primary result states full-period original/corrected costs **13,772,880.06 / 13,726,733.57 yuan**, saving **46,146.49 yuan (0.3351%)**; it separately identifies April–December's **0.4034%** gain and **46,106.35 yuan** inventory-adjusted gain. Periods and denominators are consistent.
- All six tested scenario gains are retained, including the better 56-day numerical result without replacing the frozen 28-day main policy. The chapter shows the main policy's **153 cheaper / 122 more expensive days**, two losing months, and worst-day loss. The positive cumulative result is not described as an every-day guarantee.
- The principal seven-day monthly moving-block interval **[23,728.63, 78,185.26] yuan** is explicitly conditional historical resampling. All 3/7/14-day intervals and the separately documented circular seven-day control appear. Resampling realized fees is not claimed to rerun battery physics or to guarantee future profit.
- Assembly status is accurate: the original innovation chapter is a clearly labeled historical appendix, Q4 correction migration is described as newly completed, shared assumptions/physics are centralized, and six source drafts map to twelve ordered main/appendix parts. Existing source chapters remain preserved. The generated assembly validation reports no broken absolute links. Outstanding notation/format/official-export work is not claimed complete.
- The package source includes the independent validator's required baseline ledger and source metadata, the independent LP module, numerical input hashes and new code/tests/results. It refuses to overwrite an existing frozen version, requires passed numerical and chart gates, binds visual assessment to current PNG/script hashes, and verifies archive CRC plus all manifest/member hashes. Archive execution itself was not performed by this reviewer.

No further numerical run or prior-suite rerun was requested or performed after successful verification. The only changes by this reviewer are the assigned new validator/LP scripts, dedicated audit tests, their generated new artifacts/logs, and this review report.
