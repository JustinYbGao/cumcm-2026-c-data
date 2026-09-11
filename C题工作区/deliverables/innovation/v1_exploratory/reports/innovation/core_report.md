# Innovation numerical core report

## Scope

Implemented the bounded numerical kernels in `scripts/innovation_core.py`; no annual experiment was run.

- `solve` preserves the Q3 hard-terminal result by delegating the unchanged/no-positive-reserve case to `run_q3.solve_horizon` with settlement A. A positive reserve adds only the soft SOC-reference shortfall and its proxy fee while retaining the hard terminal constraint.
- Gate solves share one model for free and frozen commitments. Frozen commitments are exact equalities. Soft-terminal solves include bounded emergency energy, binary emergency/charge exclusion, the existing charge/discharge binary, settlement-A epigraph fees, and an explicitly supplied absolute terminal-deviation fee.
- Plans retain the Q3 arrays and add the interval array `emergency_plan_kwh`. Solver status records scalar emergency energy, reserve shortfall, terminal deviation, contract/emergency/proxy/total objective components, bounds, gap, infeasibility, size, relaxation flag, and runtime.
- `quantile_fit_predict` solves pinball regression with free coefficients using SciPy HiGHS. Rank-deficient or sample-poor designs use a nonnegative empirical-quantile fallback and return JSON-serializable provenance.
- `risk_prefix` computes the maximum positive cumulative residual prefix. `gate_threshold` filters by availability, completed issue time, rolling issue-time window, and matching publication hour before computing a nonnegative empirical threshold.

## TDD and verification

The first intended red run failed because `innovation_core` did not exist. After implementation, the custom MILP tests exposed unsupported division of a HiGHS variable; replacing it with multiplication by reciprocal made the focused suite green.

Final command:

```sh
TMPDIR="$PWD/data/interim/innovation" TMP="$PWD/data/interim/innovation" TEMP="$PWD/data/interim/innovation" .venv/bin/python -B -m unittest tests.test_q3 tests.test_innovation_core -v
```

Result: 16 tests passed, including all seven pre-existing Q3 tests and nine innovation-core tests. Full output is in `logs/innovation/core_tests.log`.

## Limits

The quantile fallback is intentionally local to numerical rank/sample sufficiency; the experiment runner remains responsible for the frozen 20-day risk-model activation rule. Solver equivalence to Q3 is exact for the delegated hard-terminal/no-positive-reserve path; positive-reserve and gate paths use the new bounded formulation.
