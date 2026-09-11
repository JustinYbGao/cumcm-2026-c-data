"""Independent sparse-matrix LP bounds for prescribed innovation horizons.

This module deliberately does not import any planning or innovation implementation.
It reconstructs the continuous relaxation directly for SciPy's HiGHS interface.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

WORK = Path(__file__).resolve().parents[1]
for _key in ("TMPDIR", "TMP", "TEMP"):
    os.environ[_key] = str(WORK / "data/interim/innovation")

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

DATES = ["2025-04-01", "2025-06-21", "2025-09-23", "2025-12-21"]


def independent_lp(frame, initial, target, battery, minutes, *, original=None,
                   fixed_grid=None, soft_terminal=False, terminal_penalty=None,
                   reserve=None):
    """Return an independently assembled continuous LP solution and diagnostics."""
    frame = frame.reset_index(drop=True)
    n = len(frame)
    if n == 0:
        raise ValueError("empty audit horizon")
    load = frame.load_forecast_kwh.to_numpy(float)
    pv = frame.pv_forecast_kwh.to_numpy(float)
    price = frame.price_yuan_per_kwh.to_numpy(float)
    original = None if original is None else np.asarray(original, dtype=float)
    fixed_grid = None if fixed_grid is None else np.asarray(fixed_grid, dtype=float)
    if original is not None and original.shape != (n,):
        raise ValueError("original length mismatch")
    if fixed_grid is not None and fixed_grid.shape != (n,):
        raise ValueError("fixed grid length mismatch")
    if soft_terminal != (terminal_penalty is not None):
        raise ValueError("soft terminal requires, and alone accepts, a penalty")

    names = ["q", "c", "d", "w", "E"]
    sizes = [n, n, n, n, n + 1]
    if soft_terminal:
        names += ["u", "z", "y", "terminaldev"]
        sizes += [n, n, n, 1]
    else:
        names += ["z"]
        sizes += [n]
    if original is not None:
        names += ["fee"]
        sizes += [n]
    if reserve is not None and float(reserve["amount_kwh"]) > 0:
        names += ["reserve_shortfall"]
        sizes += [1]
    offsets = {}
    cursor = 0
    for name, size in zip(names, sizes):
        offsets[name] = slice(cursor, cursor + size)
        cursor += size
    m = cursor
    objective = np.zeros(m)
    bounds = [(0.0, None)] * m
    q, c, d, w, energy = (offsets[k] for k in ("q", "c", "d", "w", "E"))
    ec = float(battery["eta_charge"])
    ed = float(battery["eta_discharge"])
    mc = float(battery["max_charge_kw"] * minutes / 60)
    md = float(battery["max_discharge_kw"] * minutes / 60)
    for t in range(n):
        bounds[c.start + t] = (0.0, mc)
        bounds[d.start + t] = (0.0, md)
        if fixed_grid is not None:
            bounds[q.start + t] = (float(fixed_grid[t]), float(fixed_grid[t]))
        if original is None:
            objective[q.start + t] = price[t]
    for t in range(n + 1):
        bounds[energy.start + t] = (float(battery["min_energy_kwh"]),
                                    float(battery["max_energy_kwh"]))
    z = offsets["z"]
    for t in range(n):
        bounds[z.start + t] = (0.0, 1.0)
    if soft_terminal:
        u, y, terminaldev = offsets["u"], offsets["y"], offsets["terminaldev"]
        objective[u] = 5 * price
        objective[terminaldev] = float(terminal_penalty)
        for t in range(n):
            bounds[u.start + t] = (0.0, float(load[t]))
            bounds[y.start + t] = (0.0, 1.0)
    if original is not None:
        fee = offsets["fee"]
        objective[fee] = 1.0
    if "reserve_shortfall" in offsets:
        reserve_shortfall = offsets["reserve_shortfall"]
        objective[reserve_shortfall] = float(reserve["penalty_yuan_per_kwh"])

    eq_rows = 2 * n + 1 + (0 if soft_terminal else 1)
    eq = lil_matrix((eq_rows, m))
    eq_rhs = np.zeros(eq_rows)
    for t in range(n):
        eq[t, q.start + t] = 1
        eq[t, c.start + t] = -1
        eq[t, d.start + t] = 1
        eq[t, w.start + t] = -1
        if soft_terminal:
            eq[t, u.start + t] = 1
        eq_rhs[t] = load[t] - pv[t]
        row = n + t
        eq[row, energy.start + t + 1] = 1
        eq[row, energy.start + t] = -1
        eq[row, c.start + t] = -ec
        eq[row, d.start + t] = 1 / ed
    eq[2 * n, energy.start] = 1
    eq_rhs[2 * n] = float(initial)
    if not soft_terminal:
        eq[2 * n + 1, energy.stop - 1] = 1
        eq_rhs[2 * n + 1] = float(target)

    inequalities = []
    limits = []
    def add_ub(coefficients, rhs):
        inequalities.append(coefficients)
        limits.append(float(rhs))
    for t in range(n):
        add_ub({c.start + t: 1, z.start + t: -mc}, 0)
        add_ub({d.start + t: 1, z.start + t: md}, md)
        if soft_terminal:
            add_ub({u.start + t: 1, y.start + t: -load[t]}, 0)
            add_ub({c.start + t: 1, y.start + t: mc}, mc)
        if original is not None:
            base, p = float(original[t]), float(price[t])
            add_ub({q.start + t: 1.5 * p, fee.start + t: -1}, 0.5 * p * base)
            add_ub({q.start + t: 0.5 * p, fee.start + t: -1}, -0.5 * p * base)
    if soft_terminal:
        add_ub({energy.stop - 1: 1, terminaldev.start: -1}, float(target))
        add_ub({energy.stop - 1: -1, terminaldev.start: -1}, -float(target))
    if "reserve_shortfall" in offsets:
        index = int(reserve["index"])
        reference = float(battery["min_energy_kwh"]) + float(reserve["amount_kwh"])
        add_ub({energy.start + index: -1, reserve_shortfall.start: -1}, -reference)
    ub = lil_matrix((len(inequalities), m))
    for row, coefficients in enumerate(inequalities):
        for col, value in coefficients.items():
            ub[row, col] = value
    ub_rhs = np.asarray(limits)
    eq, ub = eq.tocsr(), ub.tocsr()
    result = linprog(objective, A_ub=ub, b_ub=ub_rhs, A_eq=eq, b_eq=eq_rhs,
                     bounds=bounds, method="highs",
                     options={"primal_feasibility_tolerance": 1e-8,
                              "dual_feasibility_tolerance": 1e-8})
    if not result.success:
        raise RuntimeError(result.message)
    x = result.x
    equality = float(np.max(np.abs(eq @ x - eq_rhs)))
    inequality = float(max(0.0, np.max(ub @ x - ub_rhs, initial=0.0)))
    bound_violation = 0.0
    for value, (low, high) in zip(x, bounds):
        bound_violation = max(bound_violation, low - value,
                              0.0 if high is None else value - high)
    return {
        "objective_yuan": float(result.fun),
        "equality_residual": equality,
        "inequality_violation": inequality,
        "bound_violation": float(bound_violation),
        "variables": int(m), "equalities": int(eq.shape[0]),
        "inequalities": int(ub.shape[0]), "solver_status": int(result.status),
        "solver_message": str(result.message),
    }


def _with_price(frame, prices, hour):
    frame = frame.copy()
    if "price_yuan_per_kwh" not in frame:
        frame["price_yuan_per_kwh"] = prices[hour * 6:hour * 6 + len(frame)]
    return frame


def _append(rows, policy, date, hour, alternative, frame, saved, result, elapsed):
    gap = float(saved - result["objective_yuan"])
    primal = max(result["equality_residual"], result["inequality_violation"],
                 result["bound_violation"])
    rows.append({
        "policy": policy, "date": date, "issue_hour": int(hour),
        "alternative": alternative, "horizon_intervals": int(len(frame)),
        "milp_objective_yuan": float(saved),
        "independent_lp_bound_yuan": result["objective_yuan"],
        "milp_minus_lp_yuan": gap,
        "lp_equality_residual": result["equality_residual"],
        "lp_inequality_violation": result["inequality_violation"],
        "lp_bound_violation": result["bound_violation"],
        "lp_variables": result["variables"], "lp_equalities": result["equalities"],
        "lp_inequalities": result["inequalities"],
        "solver_status": result["solver_status"], "solver_message": result["solver_message"],
        "runtime_seconds": float(elapsed),
        "passed": bool(gap >= -1e-5 and primal <= 1e-6),
    })


def audit(out, physical, prices):
    rows = []
    battery, minutes = physical["battery"], physical["interval_minutes"]
    for policy in ("risk_fixed", "risk_g10", "pv_raw"):
        folder = out / "evaluation" / policy
        versions = pd.read_csv(folder / "plan_versions.csv", float_precision="round_trip")
        grouped = versions.groupby(["date", "issue_hour"], sort=False)
        statuses = json.loads((folder / "solvers.json").read_text())
        for status in statuses:
            date, hour = status["date"], int(status["issue_hour"])
            if date not in DATES or hour != 0:
                continue
            frame = _with_price(grouped.get_group((date, hour)), prices, hour)
            reserve = status["metadata"].get("reserve") if policy.startswith("risk_") else None
            started = time.perf_counter()
            result = independent_lp(frame, status["initial_energy_kwh"],
                                    status["terminal_target_kwh"], battery, minutes,
                                    reserve=reserve)
            _append(rows, policy, date, hour, "selected", frame,
                    status["solver"]["objective_yuan"], result,
                    time.perf_counter() - started)

    folder = out / "evaluation" / "gate_paid"
    candidates = pd.read_csv(folder / "candidate_versions.csv", float_precision="round_trip")
    grouped = candidates.groupby(["date", "issue_hour", "alternative"], sort=False)
    decisions = json.loads((folder / "decisions.json").read_text())
    penalty = float(json.loads((out / "config_snapshot.json").read_text())[
        "proxy_penalty_yuan_per_kwh"])
    for decision in decisions:
        date, hour = decision["date"], int(decision["issue_hour"])
        if date not in DATES or hour not in (6, 12, 18):
            continue
        for alternative in ("hold", "update"):
            frame = grouped.get_group((date, hour, alternative)).reset_index(drop=True)
            original = frame.grid_original_kwh.to_numpy(float)
            fixed = frame.grid_kwh.to_numpy(float) if alternative == "hold" else None
            started = time.perf_counter()
            result = independent_lp(
                frame, decision["initial_energy_kwh"], decision["terminal_target_kwh"],
                battery, minutes, original=original, fixed_grid=fixed,
                soft_terminal=True, terminal_penalty=penalty,
            )
            saved = decision[f"{alternative}_solver"]["objective_yuan"]
            _append(rows, "gate_paid", date, hour, alternative, frame, saved, result,
                    time.perf_counter() - started)
    return pd.DataFrame(rows)


def self_check():
    frame = pd.DataFrame({"load_forecast_kwh": [1.0, 2.0],
                          "pv_forecast_kwh": [0.0, 0.0],
                          "price_yuan_per_kwh": [3.0, 3.0]})
    battery = {"min_energy_kwh": 0.0, "max_energy_kwh": 10.0,
               "max_charge_kw": 0.0, "max_discharge_kw": 0.0,
               "eta_charge": 0.9, "eta_discharge": 0.9}
    result = independent_lp(frame, 5.0, 5.0, battery, 10)
    if abs(result["objective_yuan"] - 9.0) > 1e-9 or result["equality_residual"] > 1e-9:
        raise AssertionError("two-interval analytical LP check failed")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    check = self_check()
    if args.self_check:
        print(json.dumps({"passed": True, "analytical_objective_yuan": check["objective_yuan"]}, indent=2))
        return
    out = WORK / "results/innovation"
    required = [out / "run_status.json", out / "config_snapshot.json"]
    required += [out / "evaluation" / p / "plan_versions.csv"
                 for p in ("risk_fixed", "risk_g10", "pv_raw")]
    required += [out / "evaluation/gate_paid/candidate_versions.csv",
                 out / "evaluation/gate_paid/decisions.json"]
    missing = [str(path.relative_to(WORK)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Innovation evaluation is not ready; missing: " + ", ".join(missing))
    status = json.loads((out / "run_status.json").read_text())
    if not status.get("completed"):
        raise SystemExit("Innovation evaluation run_status is not completed")
    physical = json.loads((WORK / "configs/model_baseline.json").read_text())
    prices = pd.read_csv(WORK / "data/processed/fixed_price.csv",
                         float_precision="round_trip").price_yuan_per_kwh.to_numpy(float)
    frame = audit(out, physical, prices)
    expected = 36
    if len(frame) != expected:
        raise RuntimeError(f"expected {expected} prescribed cases, found {len(frame)}")
    frame.to_csv(out / "independent_lp_audit.csv", index=False)
    primal_columns = ["lp_equality_residual", "lp_inequality_violation", "lp_bound_violation"]
    report = {
        "passed": bool(frame.passed.all()), "sample_count": int(len(frame)),
        "case_counts": {f"{p}:{a}": int(len(g)) for (p, a), g in frame.groupby(["policy", "alternative"])},
        "minimum_milp_minus_lp_yuan": float(frame.milp_minus_lp_yuan.min()),
        "maximum_relaxation_gap_yuan": float(frame.milp_minus_lp_yuan.max()),
        "mean_relaxation_gap_yuan": float(frame.milp_minus_lp_yuan.mean()),
        "maximum_lp_primal_violation": float(frame[primal_columns].to_numpy().max()),
        "analytical_self_check_objective_yuan": check["objective_yuan"],
        "method": "Independent SciPy sparse-matrix LP relaxation using the HiGHS algorithm family; no planner modules imported.",
        "scope": "Four evaluation dates; risk_fixed/risk_g10/PV raw at 00:00 and gate_paid hold/update at 06:00, 12:00, 18:00.",
    }
    (out / "independent_lp_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
