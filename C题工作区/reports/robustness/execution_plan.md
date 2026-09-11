# Supplemental experiments — frozen before execution

Status at creation: not run. Date: 2026-09-10. All results remain internal and retrospective.

## Global constraints
Preserve all existing scripts, data, frozen packages and other members' work. New artifacts stay below C题工作区; no tmp. Interval-end mapping remains unchanged. Charts have English labels only and use modelviz-skill. No official Excel export. Never select a new winning configuration using these comparisons. A settlement applies throughout.

## Task 1 — replay and assumptions
Implement scripts/run_robustness.py, configs/robustness.json, tests/test_robustness.py and runner report logs/robustness/runner_report.md. Reuse innovation_core.solve, existing Q2 causal load forecasts, Appendix3 PV and Q4 price forecasts. Do not change old modules.
Nine continuous February 1–December 31 runs, same initial 7268.4231640740745 kWh:
1 fixed_raw: fixed price, eta_c=eta_d=.9, hard daily terminal, raw PV all year.
2 fixed_w28: same, raw PV before April 1 then 28-day correction.
3 fixed_w14: same, correction window14 from April1.
4 fixed_w56: same, correction window56 from April1.
5 efficiency_raw: same as1, eta_c=eta_d=sqrt(.9).
6 efficiency_w28: same as5, 28-day correction from April1.
7 soft_raw: same as1, soft terminal with explicit penalty mean(fixedprice)*.9.
8 soft_w28: same as7, 28-day correction from April1.
9 variable_raw and 10 variable_w28: use causal Q4 OLS prices for planning, actual variable prices for A settlement, eta each .9, hard terminal; correction from April1 only for w28.
All run 0/6/12/18 updates and unchanged actual greedy executor, carry actual SOC across every interval/day/month including March31→April1. Keep all 10 policies: numbering above deliberately includes two variable policies. Export ledger, plan versions, solver logs, daily, summary, table1/2/3, emergency events; saved plans carry planning price and raw/corrected PV. Record per-issue correction bias, training cutoff and window; only positive raw PV fitted/applied, completed targets before midnight. No future data. Do not recompute Q2 forecasts or January warmup for efficiency case: common fixed February initial isolates efficiency assumption.
Configuration comparison uses paired April–December costs (each pair shares its own setting's continuous February–March state), while final deployed w28 vs raw also reports entire334days bill. Add terminal-inventory adjusted comparison at explicit common reference .9*mean(fixedprice); this diagnostic is not cash cost.
Persist run status and input/code/config hashes before/after. Guard against overwriting completed output. Redirect temp paths after imports into new interim directory. Meaningful tests must cover switch date, window cutoff and daylight behavior. Run everything, report exact commands/results.

## Task 2 — independent verification
New validate_robustness.py: independently check actual physics, SOC continuity, bills, saved planning constraints and objectives with correct hard/soft/efficiency/price variants, forecast provenance/causality, correction replay, tables. Independent sparse LP lower bounds for representative 0/6/12/18 saved plans across each setting via audit_innovation_lp.independent_lp. Verify solver status/gap and source hashes. Do not call optimizer to validate actual physics or costs. Save concise counts/max residuals and detailed exceptions.

## Task 3 — stability and uncertainty
New analyze_robustness.py. Pair daily raw minus corrected cost; report monthly gain, positive/negative/tie days, worst day, end SOC, cumulative gain and monetary inventory adjustment. Predeclare monthly-stratified moving block resampling of daily pairs: block lengths3,7,14 days, 5000 replicates, seed20260910, contiguous blocks wholly within each month with replacement, truncate resampled month to original length. Percentile95% intervals describe conditional historical resampling variability, not future guarantees or a fresh unseen test. Include method limitations, sensitivity across block length, daily and monthly CSVs. No resampling of individual10-minute intervals. No formal distribution-free robustness claim.

## Task 4 — paper assembly and charts
Use modelviz skill for English plots of window/assumption comparisons and monthly stability. Preserve originals. Create ordered papers/assembly_v1/ parts plus index mapping EVERY prior q1/q2/q3/q4/innovation draft and new sensitivity draft to exact main text or appendix parts, including what to remove/reuse and figure/table source paths. Shared physical model once. Each question needs relevant correctness verification; sensitivity and uncertainty target assumptions/conclusions rather than repeat every test in every question. Include official source basis, no fabricated contest mandate. Keep negative innovations as ablations. Produce BZD solution check and reproducible result manifest, update progress.
