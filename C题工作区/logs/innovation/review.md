# Independent innovation code and mathematical review

Verdict: no blocking mathematical or causality defect found. The annual run may proceed. One low-priority reporting issue is listed below; it does not change decisions, bills, or candidate selection.

Reviewed against `reports/innovation/execution_plan.md`: `scripts/innovation_core.py`, `scripts/run_innovation.py`, their imported Q3 solver/fee/export functions and Q2 executor, `reports/innovation/core_report.md`, `logs/innovation/core_tests.log`, and `logs/innovation/smoke.log`. The existing log records 16 passing tests and all eleven smoke policies completing. Tests were not rerun. This is a static code/specification review, not an independent full-year file audit.

## Finding

**[P3] Gate solver-work totals omit the second branch solve.** `scripts/run_innovation.py:134–136` solves both the free-update and held-commitment models at every eligible intraday event. `scripts/run_innovation.py:159–170` retains only the selected branch in `statuses`, and line 185 passes that list to `run_q3.export_policy`; that exporter derives `solves` and `solver_seconds` from this list (`scripts/run_q3.py:109–110`). The two branch statuses are safely retained in `decisions.json`, so model verification remains possible, but generic summary fields understate gate computation (one recorded solve instead of two per intraday event). If runtime/solve counts are reported, derive them from both decision branches plus midnight solves, or label these fields explicitly as retained-plan counts/time. This correction can be made during postprocessing without changing the frozen computation.

## Specification and mathematics checked

- **PV correction:** `run_innovation.py:59–62,78–84` estimates raw residuals only on positive original forecasts, grouped by publication hour. Targets must end by the current day's midnight and start within the preceding 28 days. Current-day actual PV is not used for the correction. The application mask uses forecast positivity, not realized daylight. Original forecast selection delegates to Q3's exact issue/target coverage checks.
- **Risk training and units:** `run_innovation.py:64–69,87–100` forms the maximum positive cumulative prefix of actual-minus-forecast net load over slots 73–108, in interval kWh, then trains only completed days within 56 days. The same day's actual risk appears in diagnostic metadata but does not enter X, y, prediction, or reserve sizing. S/1000 training and prediction ×1000 are consistent. `innovation_core.py:195–198` uses X beta + positive residual − negative residual = y with weights alpha and 1−alpha, which is the specified pinball loss. Rank fallback and the 20-day activation rule are implemented in their respective layers.
- **Reserve:** `run_innovation.py:123–124` divides AC deficit energy by discharge efficiency to obtain internal battery kWh and caps usable reserve at 9600. `innovation_core.py:128–132` places the reference at E[72], the 12:00 boundary, above the 1200 lower SOC bound, with a soft shortfall. It does not impose an actual-dispatch reserve floor. The hard terminal remains in effect. The penalty unit is yuan/internal-kWh.
- **Gate feasibility and fair comparison:** `innovation_core.py:93–127` includes fixed q as the held feasible subset, common soft absolute terminal deviation, bounded emergency supply, charge/discharge exclusion, and emergency/charge exclusion. Normal q has no upper bound and is cheaper at the margin than emergency supply under the positive fixed prices. Settlement-A epigraph slopes and intercepts match the existing fee function. Both branches use the same current realized SOC, midnight target, q0 fee reference, and penalty (`run_innovation.py:134–150`).
- **Counterfactual causality:** `run_innovation.py:149–181` computes held and updated remaining-day replays from the same state with fixed branch q and the same greedy actual executor. Both include identical forms of terminal proxy. Replay residuals are appended to strategy-specific history only after that day; eligibility additionally checks availability/time/window/hour in `innovation_core.py:228–235`. Current-day replay outcomes cannot influence current acceptance. This is retrospective delayed-feedback replay as declared, not online observed counterfactuals.
- **Execution and attribution:** `run_innovation.py:172–182` uses the original Q2 greedy actual executor, whose hard-coded physical limits match this frozen configuration. The MILP schedules are forecasts, not substituted actual battery actions. Ledger billing includes contract and 5× emergency costs only; reserve/terminal proxies remain separate. `pv_raw` provides the hard-terminal paid-update comparator for the soft-terminal gate design. Gate benefit must be compared against `gate_paid`; comparing directly against `pv_raw` also includes the terminal-model change. Frozen-information controls retain the same q and executor.
- **Selection and baseline protection:** `run_innovation.py:195–220` writes only innovation output paths, hashes baseline inputs/code, computes selection from March actual bills before any April–December run, and preserves each strategy's own history. Common April initial states use the corresponding frozen Q2/Q3 baseline. All candidates remain available for evaluation. Exact-score tie ordering favors the predeclared simpler candidate.

## Completion boundary

The downstream saved-file auditor still needs to verify all produced time keys, conservation and physical limits, complete provenance, reconstructed bills/counterfactuals, frozen selection, and representative LP checks. This review does not establish full-year experimental effectiveness or sign off the final paper/figures. No implementation files were changed.

# Follow-up: independent validator and report generator

Reviewed `scripts/validate_innovation.py` and `scripts/report_innovation.py` before generated outputs were available. No tests or full-year validation runs were repeated. References below refer to the reviewed source snapshot; subsequent edits may move them.

## Findings requiring audit/report changes

**[P2] Tie gate replay inputs to the verified event instead of only checking self-consistency.** `validate_innovation.py:110–116` passes stored decision initial SOC/terminal target and candidate forecast/q0 fields into both the plan checker and independent replay. These fields are not linked to the current actual ledger state, midnight target, or already verified version/source. Thus a pair of internally consistent candidate plans/replays based on another SOC or forecast can pass while the retained q still matches the selected version. Compare the decision initial SOC and target to the verified ledger/day start, and both candidates' slot keys, load, PV and q0 to the verified current version. Existing held-q and selected-q checks at lines 127–132 are useful and should remain.

**[P2] Complete risk-model source provenance checks, including the truth used by the report.** `validate_innovation.py:143–151` selects training rows using saved `risk_targets.available_time` and verifies a prediction using saved `model.features`. It does not require availability to equal the target date plus one day, features to equal the current frozen source features, or `model.realized_s_kwh` to equal the independently reconstructed target. The latter is consumed directly by `report_innovation.py:56–59` for loss and coverage. Verify all three equalities. The empirical-quantile branch should additionally verify rank/fallback eligibility and the declared higher-method quantile; the current optimality check executes only when a record says its source is `pinball_lp`. These are source-audit gaps; the reviewed runner itself constructs these values correctly.

**[P2] Validate the comparison table used for effect claims.** `report_innovation.py:20–24,62–65` derives savings and conclusion rows from `comparison.csv`, whereas `validate_innovation.py:103–105` checks only per-policy `summary.json` and `daily.csv`. A stale or erroneous comparison table can therefore generate incorrect effect claims even when both audit prerequisites pass. Reconcile the comparison's policy identities, group mapping, costs/emergency volume and initial/final SOC against the verified evaluation ledgers/summaries, or derive the report's cost table directly from those verified files. Apply the same check to any update counts or inventory adjustments presented as verified totals.

**[P3] Correct the calibration-period sentence.** `report_innovation.py:73` says “3月31日实际回放费用用于选型”, which reads as the March 31 bill. The implementation and plan use all 31 March days. Use “3月全部31天的实际回放费用用于选型”.

## Confirmed reporting behavior

- `report_innovation.py:30–33` correctly fixes the earlier computational accounting issue: retained state records plus one omitted counterpart per gate decision counts both actual solves and their runtime, for either acceptance outcome.
- Savings baselines are correctly separated: corrected PV versus raw PV, reserve candidates versus no reserve, and gate candidates versus the common soft-terminal paid-update policy. Frozen-contract rows use the paid-update comparator and the text explicitly disclaims interpreting those differences as pure gate effects.
- The text distinguishes retrospective sequential evaluation from untouched holdout testing, local frozen-q counterfactual values from annual rolling bills, and soft-terminal model changes from gate contributions. It preserves candidate failures and avoids claiming chance-constraint guarantees or cross-year validity.
- Plan and ledger audits independently reconstruct energy conservation, greedy dispatch, fees, reserve penalties, terminal costs, delayed gate thresholds, original raw forecasts, PV-bias training, and risk targets. The above findings concern missing links between individually checked objects and report inputs, not a need to replace the overall audit approach.

Follow-up verdict: no newly found numerical-run blocker. Resolve these audit/report issues before final validation and effect claims; source edits were not made by this reviewer.

# Final review gate: fixes and generated chapter

**Final verdict: approved for packaging as the declared internal exploratory experiment. No material unresolved review findings.** This verdict closes implementation/audit/report-methodology review; it does not turn the experiment into a formal submission or guarantee generalization.

Read the revised validator/report source, generated `papers/innovation_draft.md`, `logs/innovation/audit_fix_report.md`, final validation log, and saved independent LP audit result. Existing successful full validation/tests were not rerun. Numerical core and runner remain frozen according to the checked input-hash validation.

Prior findings are resolved:

- Gate candidates now link their slot keys, forecasts and midnight commitment to verified versions, and link both branch initial SOC and terminal target to the actual event/day (`validate_innovation.py:112–127`). The independent replay uses those linked values.
- Risk target availability, model features, realized target, rank/sample eligibility, fallback coefficients and objective are now checked (`validate_innovation.py:148–179`). This also validates the target metadata consumed by the report's loss/coverage calculation.
- Both phase comparison tables and innovation summaries now reconcile policy/group/scope, all exported energy/cost aggregates, SOC/inventory and gate totals to the checked ledgers/decisions (`validate_innovation.py:196–225`). The effect table therefore uses reconciled evaluation costs.
- The chapter clearly identifies all 31 March days as calibration. Computational counts include both gate branches and are explicitly limited to April–December evaluation.

Evidence and interpretation are consistent:

- The final log records **308,491 passing read-back checks**, with no failed checks. The fix report records maximum numerical residual **5.85168891120702e-09**.
- Saved LP audit records **36 passing representative horizons**, maximum true MILP-minus-LP relaxation difference **226.84556174751924 yuan**, and maximum LP constraint violation **1.8189894035458565e-12**. The chapter reports the nonzero relaxation gap and does not claim MILP/LP equivalence or whole-year optimality.
- The chapter retains the selected PV correction's **46,146.49 yuan** saving and the risk reserve's economically negligible **5.03 yuan** difference, as well as the gate candidates' losses. Group-specific baselines, soft/hard terminal differences and the exploratory retrospective scope are disclosed.
- All/daylight PV error tables preserve the early-hour degradation as well as later-hour improvement. Gate reporting separates candidate acceptance from nonzero commitment changes and does not equate local replay profitability with annual savings.

No source or generated report edits were made by this reviewer. Chart appearance/ModelViz quality approval is outside this final code-and-methodology check and was performed by the parent task.
