# Independent innovation LP audit implementation

`scripts/audit_innovation_lp.py` independently reconstructs the prescribed continuous LP relaxations with SciPy sparse matrices. It imports no planner, Q3, or innovation runner module.

The audit is fixed at 36 evaluation cases: midnight horizons for `risk_fixed`, `risk_g10`, and `pv_raw` on April 1, June 21, September 23, and December 21; plus both saved `gate_paid` hold/update candidates at 06:00, 12:00, and 18:00 on those dates. The gate hold branch fixes grid purchases exactly to its saved candidate path.

The matrix contains grid purchase, charge, discharge, surplus, energy state, relaxed charge mode, and—where applicable—emergency purchase, relaxed emergency mode, terminal deviation, settlement-A fee epigraph, and reserve shortfall. It independently enforces balance, battery dynamics and bounds, charge/discharge exclusion, emergency/load bounds, emergency/charge exclusion, terminal conditions, and the 12:00 reserve reference from saved solver metadata.

Each row retains the saved MILP objective, independent lower bound, relaxation gap, equality residual, inequality violation, bound violation, matrix dimensions, solver status/message, runtime, and pass flag. The JSON summary reports the observed relaxation gaps rather than requiring them to vanish. Acceptance requires the LP bound to be no more than `1e-5` above the saved MILP objective and maximum primal violation no more than `1e-6`.

The script first runs a two-interval analytical check whose unique cost is 9 yuan. A full run waits for a completed evaluation `run_status.json` and all required saved artifacts, then writes `results/innovation/independent_lp_audit.csv` and `.json`.

Implementation verification used the analytical check plus existing calibration artifacts. One reserve solve and the paired gate hold/update solves each produced a valid lower bound; their largest absolute saved-MILP gap and primal residual were both below `4e-12`. No annual evaluation was started by this audit work.
