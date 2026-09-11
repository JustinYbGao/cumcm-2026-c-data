"""Small numerical kernels for the frozen innovation experiments."""
from __future__ import annotations

import os
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
for _key in ("TMPDIR", "TMP", "TEMP"):
    os.environ[_key] = str(WORK / "data/interim/innovation")

import highspy
import numpy as np
import pandas as pd
from scipy.optimize import linprog

from run_q3 import contract_fee, solve_horizon


def _arrays(load, pv, price, original, fixed_grid):
    load = np.asarray(load, dtype=float)
    pv = np.asarray(pv, dtype=float)
    price = np.asarray(price, dtype=float)
    if load.ndim != 1 or len(load) == 0 or len(pv) != len(load) or len(price) != len(load):
        raise ValueError("load, pv and price must be equal nonempty vectors")
    if not np.all(np.isfinite(np.r_[load, pv, price])) or np.any(load < 0) or np.any(price < 0):
        raise ValueError("inputs must be finite; load and price must be nonnegative")
    original = None if original is None else np.asarray(original, dtype=float)
    fixed_grid = None if fixed_grid is None else np.asarray(fixed_grid, dtype=float)
    if original is not None and (original.shape != load.shape or np.any(original < 0)):
        raise ValueError("original must be a nonnegative horizon vector")
    if fixed_grid is not None and (fixed_grid.shape != load.shape or np.any(fixed_grid < 0)):
        raise ValueError("fixed_grid must be a nonnegative horizon vector")
    return load, pv, price, original, fixed_grid


def _normalized_baseline(plan, status):
    n = len(plan["grid_kwh"])
    result = dict(plan)
    result["emergency_plan_kwh"] = np.zeros(n)
    normalized = dict(status)
    normalized.update(
        emergency_plan_kwh=0.0,
        reserve_shortfall_kwh=0.0,
        terminal_deviation_kwh=0.0,
        contract_cost_yuan=float(status["objective_yuan"]),
        emergency_cost_yuan=0.0,
        reserve_proxy_yuan=0.0,
        terminal_proxy_yuan=0.0,
        proxy_cost_yuan=0.0,
        total_objective_yuan=float(status["objective_yuan"]),
    )
    return result, normalized


def solve(load, pv, price, initial, terminal, physical, original=None,
          fixed_grid=None, reserve=None, soft_terminal=False, relaxed=False,
          terminal_penalty=None):
    """Solve one bounded horizon using settlement A for changed commitments."""
    load, pv, price, original, fixed_grid = _arrays(load, pv, price, original, fixed_grid)
    if soft_terminal and terminal_penalty is None:
        raise ValueError("soft_terminal requires explicit terminal_penalty")
    if terminal_penalty is not None and (not soft_terminal or terminal_penalty < 0):
        raise ValueError("terminal_penalty is only valid for a soft terminal")

    reserve_amount = 0.0
    if reserve is not None:
        required = {"index", "amount_kwh", "penalty_yuan_per_kwh"}
        if set(reserve) != required:
            raise ValueError("reserve requires index, amount_kwh and penalty_yuan_per_kwh")
        reserve_index = int(reserve["index"])
        reserve_amount = float(reserve["amount_kwh"])
        reserve_penalty = float(reserve["penalty_yuan_per_kwh"])
        if not 0 <= reserve_index <= len(load) or reserve_amount < 0 or reserve_penalty < 0:
            raise ValueError("invalid reserve specification")

    if not soft_terminal and fixed_grid is None and reserve_amount == 0:
        plan, status = solve_horizon(
            load, pv, price, initial, terminal, physical,
            original=original, rule="A", relaxed=relaxed,
        )
        return _normalized_baseline(plan, status)

    n = len(load)
    battery = physical["battery"]
    dt = physical["interval_minutes"] / 60
    max_charge = float(battery["max_charge_kw"] * dt)
    max_discharge = float(battery["max_discharge_kw"] * dt)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    for key, value in physical["solver"].items():
        if key != "name" and h.setOptionValue(key, value) != highspy.HighsStatus.kOk:
            raise ValueError(key)
    q = [h.addVariable(lb=float(fixed_grid[t]) if fixed_grid is not None else 0,
                       ub=float(fixed_grid[t]) if fixed_grid is not None else highspy.kHighsInf,
                       obj=float(price[t]) if original is None else 0, name=f"q_{t}") for t in range(n)]
    c = [h.addVariable(ub=max_charge, name=f"c_{t}") for t in range(n)]
    d = [h.addVariable(ub=max_discharge, name=f"d_{t}") for t in range(n)]
    w = [h.addVariable(name=f"w_{t}") for t in range(n)]
    e = [h.addVariable(lb=battery["min_energy_kwh"], ub=battery["max_energy_kwh"], name=f"E_{t}")
         for t in range(n + 1)]
    vartype = highspy.HighsVarType.kContinuous if relaxed else highspy.HighsVarType.kInteger
    z = [h.addVariable(ub=1, type=vartype, name=f"z_{t}") for t in range(n)]
    u = [h.addVariable(ub=float(load[t]), obj=5 * float(price[t]), name=f"u_{t}") for t in range(n)] if soft_terminal else []
    y = [h.addVariable(ub=1, type=vartype, name=f"y_{t}") for t in range(n)] if soft_terminal else []
    h.addConstr(e[0] == float(initial))
    terminal_pos = terminal_neg = None
    if soft_terminal:
        terminal_pos = h.addVariable(obj=float(terminal_penalty), name="terminal_above")
        terminal_neg = h.addVariable(obj=float(terminal_penalty), name="terminal_below")
        h.addConstr(e[-1] - float(terminal) == terminal_pos - terminal_neg)
    else:
        h.addConstr(e[-1] == float(terminal))
    for t in range(n):
        emergency = u[t] if soft_terminal else 0
        h.addConstr(q[t] + emergency + d[t] - c[t] - w[t] == float(load[t] - pv[t]))
        h.addConstr(e[t + 1] == e[t] + battery["eta_charge"] * c[t]
                    - (1 / battery["eta_discharge"]) * d[t])
        h.addConstr(c[t] <= max_charge * z[t])
        h.addConstr(d[t] <= max_discharge * (1 - z[t]))
        if soft_terminal:
            h.addConstr(u[t] <= float(load[t]) * y[t])
            h.addConstr(c[t] <= max_charge * (1 - y[t]))
        if original is not None:
            fee = h.addVariable(obj=1, name=f"fee_{t}")
            p, base = float(price[t]), float(original[t])
            h.addConstr(fee >= 1.5 * p * q[t] - 0.5 * p * base)
            h.addConstr(fee >= 0.5 * p * q[t] + 0.5 * p * base)
    shortfall = None
    if reserve_amount > 0:
        shortfall = h.addVariable(obj=reserve_penalty, name="reserve_shortfall")
        reference = float(battery["min_energy_kwh"]) + reserve_amount
        h.addConstr(e[reserve_index] + shortfall >= reference)
    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(h.modelStatusToString(h.getModelStatus()))
    solution, info = h.getSolution(), h.getInfo()
    values = lambda variables: np.array([solution.col_value[int(v)] for v in variables])
    state = values(e)
    emergency_values = values(u) if soft_terminal else np.zeros(n)
    plan = {
        "grid_kwh": values(q), "charge_kwh": values(c), "discharge_kwh": values(d),
        "surplus_kwh": values(w), "energy_start_kwh": state[:-1],
        "energy_end_kwh": state[1:], "charge_mode": values(z),
        "emergency_plan_kwh": emergency_values,
    }
    contract = float(np.dot(price, plan["grid_kwh"]) if original is None else
                     contract_fee(original, plan["grid_kwh"], price, "A").sum())
    emergency_cost = float(np.dot(5 * price, emergency_values))
    reserve_shortfall = 0.0 if shortfall is None else float(solution.col_value[int(shortfall)])
    terminal_deviation = 0.0 if not soft_terminal else float(
        solution.col_value[int(terminal_pos)] + solution.col_value[int(terminal_neg)])
    reserve_proxy = reserve_penalty * reserve_shortfall if reserve_amount > 0 else 0.0
    terminal_proxy = float(terminal_penalty or 0) * terminal_deviation
    objective = float(h.getObjectiveValue())
    status = {
        "status": "Optimal", "objective_yuan": objective, "total_objective_yuan": objective,
        "solver_objective_yuan": objective,
        "contract_cost_yuan": contract, "emergency_cost_yuan": emergency_cost,
        "reserve_proxy_yuan": float(reserve_proxy), "terminal_proxy_yuan": terminal_proxy,
        "proxy_cost_yuan": float(reserve_proxy + terminal_proxy),
        "emergency_plan_kwh": float(emergency_values.sum()),
        "reserve_shortfall_kwh": reserve_shortfall,
        "terminal_deviation_kwh": terminal_deviation,
        "lower_bound_yuan": objective if relaxed else float(info.mip_dual_bound),
        "mip_gap": None if relaxed else float(info.mip_gap), "runtime_seconds": h.getRunTime(),
        "max_primal_infeasibility": float(info.max_primal_infeasibility),
        "relaxed": bool(relaxed), "variables": h.getNumCol(), "constraints": h.getNumRow(),
    }
    return plan, status


def quantile_fit_predict(X, y, x, alpha=0.75):
    """Fit linear pinball loss and predict one nonnegative value."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if X.ndim != 2 or y.shape != (len(X),) or x.shape != (X.shape[1],) or len(y) == 0:
        raise ValueError("incompatible quantile regression inputs")
    if not 0 < alpha < 1 or not np.all(np.isfinite(np.r_[X.ravel(), y, x])):
        raise ValueError("alpha and data must be finite and valid")
    n, p = X.shape
    rank = int(np.linalg.matrix_rank(X))
    if rank < p or n <= p:
        quantile = float(np.quantile(y, alpha, method="higher"))
        residual = y - quantile
        objective = float(np.sum(alpha * np.maximum(residual, 0)
                                 + (1 - alpha) * np.maximum(-residual, 0)))
        beta = np.zeros(p)
        if p:
            beta[0] = quantile
        return max(0.0, quantile), {
            "beta": beta.tolist(), "rank": rank, "objective": objective,
            "source": "empirical_quantile", "n": int(n),
        }
    objective = np.r_[np.zeros(p), np.full(n, alpha), np.full(n, 1 - alpha)]
    equality = np.column_stack([X, np.eye(n), -np.eye(n)])
    result = linprog(objective, A_eq=equality, b_eq=y,
                     bounds=[(None, None)] * p + [(0, None)] * (2 * n), method="highs")
    if not result.success:
        raise RuntimeError(f"quantile LP failed: {result.message}")
    beta = result.x[:p]
    return max(0.0, float(x @ beta)), {
        "beta": beta.tolist(), "rank": rank, "objective": float(result.fun),
        "source": "pinball_lp", "n": int(n),
    }


def risk_prefix(residual):
    values = np.asarray(residual, dtype=float)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("residual must be a finite vector")
    return float(max(0.0, np.max(np.cumsum(values), initial=0.0)))


def gate_threshold(records, issue, hour, alpha, window_days=56, min_samples=20):
    """Build a causal empirical update threshold for one publication hour."""
    if not 0 < alpha < 1 or window_days <= 0 or min_samples <= 0:
        raise ValueError("invalid gate settings")
    issue = pd.Timestamp(issue)
    frame = pd.DataFrame(records).copy()
    if frame.empty:
        return 0.0, {"n": 0, "latest_available_time": None, "record_ids": [], "active": False}
    required = {"available_time", "issue_time", "issue_hour", "zeta_yuan"}
    if not required.issubset(frame.columns):
        raise ValueError("gate records missing required fields")
    frame["available_time"] = pd.to_datetime(frame["available_time"])
    frame["issue_time"] = pd.to_datetime(frame["issue_time"])
    start = issue - pd.Timedelta(days=window_days)
    frame = frame.loc[(frame.available_time <= issue) & (frame.issue_time < issue)
                      & (frame.issue_time >= start) & (frame.issue_hour == hour)].copy()
    frame = frame.sort_values(["issue_time", "available_time"], kind="stable")
    ids = frame["id"].tolist() if "id" in frame else frame.index.tolist()
    latest = None if frame.empty else str(pd.Timestamp(frame.available_time.max()))
    active = len(frame) >= min_samples
    tau = max(0.0, float(np.quantile(frame.zeta_yuan.to_numpy(float), alpha, method="higher"))) if active else 0.0
    return tau, {"n": int(len(frame)), "latest_available_time": latest,
                 "record_ids": [str(value) for value in ids], "active": bool(active)}
