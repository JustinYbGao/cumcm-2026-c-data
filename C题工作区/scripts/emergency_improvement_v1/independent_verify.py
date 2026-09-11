"""Independent source/ledger audit; never import producer or optimizer code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[2]
ROOT = WORK / "results/emergency_improvement_v1"
REPORT = WORK / "reports/emergency_improvement_v1"
for key in ("TMPDIR", "TMP", "TEMP", "MPLCONFIGDIR", "XDG_CACHE_HOME"):
    os.environ[key] = str(REPORT / "independent_cache")
import numpy as np
import pandas as pd

ETOL, CTOL = 1e-6, 1e-5
KEYS = ["date", "slot_id"]
PLAN = ["grid_plan_kwh", "charge_plan_kwh", "discharge_plan_kwh",
        "energy_start_plan_kwh", "energy_end_plan_kwh", "pv_curtailment_plan_kwh", "charge_mode_plan"]
SUMS = ["grid_plan_kwh", "emergency_kwh", "planned_cost_yuan", "emergency_cost_yuan",
        "total_cost_yuan", "charge_actual_kwh", "discharge_actual_kwh", "surplus_kwh",
        "unused_grid_kwh", "pv_curtailment_kwh"]


def csv(path):
    return pd.read_csv(path, float_precision="round_trip")


def js(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


class Audit:
    def __init__(self):
        self.checks = []

    def check(self, name, condition, detail=None):
        a = np.asarray(condition, dtype=bool)
        item = dict(check=name, passed=bool(a.all()), comparisons=int(a.size), failures=int((~a).sum()))
        if detail is not None:
            item["detail"] = detail
        if not item["passed"] and a.ndim:
            item["first_failed_indices"] = np.flatnonzero(~a)[:5].tolist()
        self.checks.append(item)
        return item["passed"]

    def equal(self, name, left, right=0., tol=ETOL):
        a, b = np.broadcast_arrays(np.asarray(left, dtype=float), np.asarray(right, dtype=float))
        error = abs(a - b)
        finite = np.isfinite(a) & np.isfinite(b)
        self.check(name, finite & (error <= tol), dict(tolerance=tol,
                   max_abs_error=float(error[finite].max()) if finite.any() else None))

    def result(self):
        return dict(passed=all(x["passed"] for x in self.checks), checks=self.checks,
                    comparisons=sum(x["comparisons"] for x in self.checks),
                    failed_groups=sum(not x["passed"] for x in self.checks))


def keys(a, f, start, end, tag):
    expected = [(str(day.date()), slot) for day in pd.date_range(start, end) for slot in range(1, 145)]
    a.check(tag + ".complete_unique_ordered", list(f[KEYS].itertuples(index=False, name=None)) == expected,
            dict(expected_rows=len(expected), actual_rows=len(f), duplicates=int(f.duplicated(KEYS).sum())))


def time_equal(a, f, field, expected, tag):
    parsed = pd.to_datetime(f[field], errors="coerce")
    a.check(tag + "." + field, parsed.notna() & (parsed.to_numpy() == np.asarray(expected)))


def harmonic_predictions(actual):
    """Equation-level reconstruction using only the day prefixes of actual input."""
    loads = actual.load_actual_kwh.to_numpy().reshape(365, 144)
    pvs = actual.pv_actual_kwh.to_numpy().reshape(365, 144)
    dates = pd.date_range("2025-01-01", "2025-12-31")
    phase = np.arange(144) / 144
    lf = np.column_stack([np.ones(144)] + [fn(2*np.pi*k*phase) for k in (1, 2) for fn in (np.sin, np.cos)])
    pf = np.column_stack([np.ones(144)] + [fn(2*np.pi*k*phase) for k in (1, 2, 3) for fn in (np.sin, np.cos)])
    load_predictions, pv_predictions = [], []
    for n in range(1, 365):
        load = loads[n-7 if n >= 7 else n-1].copy()
        pv = pvs[n-1].copy()
        if n >= 14:
            first = max(7, n-28)

            def design(i):
                weekday = np.repeat([[float(dates[i].weekday() == k) for k in range(1, 7)]], 144, axis=0)
                return np.column_stack((lf, loads[i-1]/1000, loads[i-7]/1000, weekday))

            x = np.concatenate([design(i) for i in range(first, n)])
            beta = np.linalg.lstsq(x, loads[first:n].ravel(), rcond=None)[0]
            load = np.maximum(design(n) @ beta, 0)
        if n >= 2:
            x = np.tile(pf, (min(n, 7), 1))
            y = pvs[max(0, n-7):n].ravel()
            beta = np.linalg.lstsq(x, y, rcond=None)[0]
            residual = y-x@beta
            denominator = residual[:-1]@residual[:-1]
            phi = np.clip((residual[:-1]@residual[1:])/denominator if denominator > 1e-12 else 0, -.99, .99)
            pv = np.maximum(pf@beta + phi**np.arange(1, 145)*residual[-1], 0)
        load_predictions.append(load)
        pv_predictions.append(pv)
    return np.concatenate(load_predictions), np.concatenate(pv_predictions)


def sources():
    a = Audit()
    source_map = {"actual_10min.csv": "data/processed/actual_10min.csv",
        "fixed_price.csv": "data/processed/fixed_price.csv", "model_baseline.json": "configs/model_baseline.json",
        "q2_baseline.json": "configs/q2_baseline.json", "original_run_q2.py": "scripts/run_q2.py",
        "original_solve_q1.py": "scripts/solve_q1.py", "problem_text.txt": "data/interim/problem_text.txt",
        "selection.json": "results/q2/selection.json",
        "bzd_quantile_record.json": "reports/emergency_research_v1/bzd_quantile_record.json"}
    for name, original in source_map.items():
        a.check("unchanged_snapshot." + name, sha(ROOT / "inputs" / name) == sha(WORK / original))
    for policy, old in [("B0", "selected"), ("B1", "seasonal"), ("no_storage", "no_storage")]:
        snapshot = ROOT / "inputs" / ("baseline_" + policy + ".csv")
        if snapshot.is_file():
            a.check("unchanged_baseline_snapshot." + policy, sha(snapshot) == sha(WORK / "results/q2" / old / "ledger.csv"))
    protocol = js(WORK / "configs/emergency_improvement_v1/experiments.json")
    a.check("protocol_frozen_hash", protocol["protocol_sha256"] == sha(REPORT / "protocol.md"))
    before = js(REPORT / "protected_hashes_before.json")
    changed = [name for name, digest in before.items()
               if not (WORK / name).is_file() or sha(WORK / name) != digest]
    a.check("all_protected_files_unchanged", not changed, dict(count=len(before), changed=changed))
    actual, price = csv(ROOT / "inputs/actual_10min.csv"), csv(ROOT / "inputs/fixed_price.csv")
    keys(a, actual, "2025-01-01", "2025-12-31", "actual")
    a.check("price.slots", price.slot_id.tolist() == list(range(1, 145)))
    a.equal("price.start_minutes", price.start_minute, np.arange(144) * 10)
    a.equal("price.end_minutes", price.end_minute, np.arange(1, 145) * 10)
    for source in ("load", "pv"):
        a.equal("source." + source + "_kwh", actual[source + "_actual_kwh"], actual[source + "_actual_kw"] / 6)
    a.check("source.finite_nonnegative", np.isfinite(actual[["load_actual_kwh", "pv_actual_kwh"]]) &
            (actual[["load_actual_kwh", "pv_actual_kwh"]] >= 0))
    a.check("source.positive_price", np.isfinite(price.price_yuan_per_kwh) & (price.price_yuan_per_kwh > 0))
    t = pd.to_datetime(actual.date) + pd.to_timedelta((actual.slot_id - 1) * 10, unit="min")
    for field, expected in [("interval_start", t), ("interval_end", t + pd.Timedelta(minutes=10)),
                            ("available_time", t + pd.Timedelta(minutes=10))]:
        time_equal(a, actual, field, expected, "actual")
    forecasts, checks = {}, {}
    for kind in ("linear_harmonic", "seasonal"):
        audit = Audit()
        f = csv(ROOT / "forecasts" / (kind + ".csv"))
        keys(audit, f, "2025-01-02", "2025-12-31", kind)
        dates = pd.to_datetime(f.date)
        for field, expected in [("issue_time", dates), ("history_end", dates),
                                ("residual_available_time", dates + pd.Timedelta(days=1))]:
            time_equal(audit, f, field, expected, "forecast")
        truth = actual.set_index(KEYS).reindex(pd.MultiIndex.from_frame(f[KEYS]))
        audit.equal("residual_from_actual_source", f.net_residual_kwh,
            truth.load_actual_kwh.to_numpy() - truth.pv_actual_kwh.to_numpy() -
            f.load_forecast_kwh.to_numpy() + f.pv_forecast_kwh.to_numpy())
        audit.check("finite_nonnegative_forecasts", np.isfinite(f[["load_forecast_kwh", "pv_forecast_kwh"]]) &
                    (f[["load_forecast_kwh", "pv_forecast_kwh"]] >= 0))
        if kind == "seasonal":
            loads = actual.load_actual_kwh.to_numpy().reshape(365, 144)
            pvs = actual.pv_actual_kwh.to_numpy().reshape(365, 144)
            audit.equal("seasonal_load_from_history", f.load_forecast_kwh,
                        np.concatenate([loads[n-7 if n >= 7 else n-1] for n in range(1, 365)]))
            audit.equal("seasonal_pv_from_history", f.pv_forecast_kwh, pvs[:-1].ravel())
        else:
            load_hat, pv_hat = harmonic_predictions(actual)
            audit.equal("linear_load_from_history", f.load_forecast_kwh, load_hat)
            audit.equal("harmonic_ar1_pv_from_history", f.pv_forecast_kwh, pv_hat)
        forecasts[kind], checks[kind] = f, audit.result()
    return actual, price, forecasts, dict(inputs=a.result(), forecasts=checks)


def run(folder, actual, price, forecasts):
    a = Audit()
    files = ["ledger.csv", "plans.csv", "daily.csv", "summary.json", "models_and_solvers.json", "config.json"]
    missing = [name for name in files if not (folder / name).is_file()]
    if not a.check("artifact_set_complete", not missing, missing):
        return a.result()
    f, plan, daily = [csv(folder / name) for name in files[:3]]
    summary, models, cfg = [js(folder / name) for name in files[3:]]
    frozen_cfg = next(c for c in js(WORK / "configs/emergency_improvement_v1/experiments.json")["runs"]
                      if c["policy"] == cfg["policy"]).copy()
    if folder.parent.name == "january":
        frozen_cfg.update(start="2025-01-15", end="2025-01-31", initial_energy_kwh=6000.)
    a.check("config_matches_frozen_protocol", cfg == frozen_cfg)
    required = KEYS + PLAN + SUMS + ["interval_start", "interval_end", "available_time", "issue_time",
        "load_actual_kwh", "pv_actual_kwh", "load_forecast_kwh", "pv_forecast_kwh", "price_yuan_per_kwh",
        "energy_start_actual_kwh", "energy_end_actual_kwh", "plan_load_kwh", "plan_pv_kwh",
        "risk_delta_kwh", "reserve_internal_kwh", "dispatch_time", "decision_input_cutoff",
        "forecast_history_end", "risk_history_start", "risk_history_end", "risk_sample_count"]
    if not a.check("ledger.required_fields", set(required) <= set(f), sorted(set(required) - set(f))):
        return a.result()
    for frame, name in [(f, "ledger"), (plan, "plan")]:
        keys(a, frame, cfg["start"], cfg["end"], name)
    if len(f) != len(plan):
        return a.result()
    days = pd.to_datetime(f.date)
    t = days + pd.to_timedelta((f.slot_id - 1) * 10, unit="min")
    for field, expected in [("interval_start", t), ("interval_end", t + pd.Timedelta(minutes=10)),
        ("available_time", t + pd.Timedelta(minutes=10)), ("issue_time", days),
        ("forecast_history_end", days), ("dispatch_time", t + pd.Timedelta(minutes=10)),
        ("decision_input_cutoff", t + pd.Timedelta(minutes=10))]:
        time_equal(a, f, field, expected, "ledger")
    time_equal(a, plan, "issue_time", days, "plan")
    truth = actual.set_index(KEYS).reindex(pd.MultiIndex.from_frame(f[KEYS]))
    for field in ["load_actual_kwh", "pv_actual_kwh"]:
        a.equal("source." + field, f[field], truth[field].to_numpy())
    p = price.set_index("slot_id").loc[f.slot_id, "price_yuan_per_kwh"].to_numpy()
    a.equal("source.fixed_prices", f.price_yuan_per_kwh, p)
    for field in PLAN + ["load_forecast_kwh", "pv_forecast_kwh", "plan_load_kwh", "plan_pv_kwh", "risk_delta_kwh"]:
        a.equal("frozen_plan." + field, f[field], plan[field])
    ec, ed = cfg["eta_charge"], cfg["eta_discharge"]
    a.check("valid_efficiency", any(abs(ec-v) < 1e-14 and abs(ed-v) < 1e-14 for v in (.9, np.sqrt(.9))))
    a.check("valid_power_basis", cfg["power_basis"] in ("AC_bus", "battery_internal"))
    a.check("valid_executor", cfg["executor"] in ("greedy", "reserve"))
    mc = 5000 / 6 / ec if cfg["power_basis"] == "battery_internal" else 5000 / 6
    md = 5000 / 6 * ed if cfg["power_basis"] == "battery_internal" else 5000 / 6
    nonnegative = sorted(set(k for k in required if k.endswith("_kwh") and k != "risk_delta_kwh"))
    a.check("finite_nonnegative_energy", np.isfinite(f[nonnegative]) & (f[nonnegative] >= -ETOL))
    for suffix in ("actual", "plan"):
        c, d = f["charge_" + suffix + "_kwh"], f["discharge_" + suffix + "_kwh"]
        e0, e1 = f["energy_start_" + suffix + "_kwh"], f["energy_end_" + suffix + "_kwh"]
        a.equal(suffix + ".soc_recurrence", e1, e0 + ec*c - d/ed)
        a.check(suffix + ".soc_bounds", (e0 >= 1200-ETOL) & (e1 >= 1200-ETOL) & (e0 <= 10800+ETOL) & (e1 <= 10800+ETOL))
        a.check(suffix + ".power", (c <= mc+ETOL) & (d <= md+ETOL))
        a.check(suffix + ".mutual_exclusion", (c <= ETOL) | (d <= ETOL))
        select = np.ones(len(f)-1, dtype=bool) if suffix == "actual" else f.date.to_numpy()[1:] == f.date.to_numpy()[:-1]
        a.equal(suffix + ".continuity", e0.to_numpy()[1:][select], e1.to_numpy()[:-1][select])
    a.equal("initial_actual", f.energy_start_actual_kwh.iloc[0], cfg["initial_energy_kwh"])
    january = folder.parent.name == "january"
    a.equal("common_initial", cfg["initial_energy_kwh"], 6000 if january else 7268.4231640740745)
    a.check("evaluation_period", (cfg["start"], cfg["end"]) ==
            (("2025-01-15", "2025-01-31") if january else ("2025-02-01", "2025-12-31")))
    g, c, d, emergency, surplus, load, pv = [f[k].to_numpy() for k in
        ["grid_plan_kwh", "charge_actual_kwh", "discharge_actual_kwh", "emergency_kwh",
         "surplus_kwh", "load_actual_kwh", "pv_actual_kwh"]]
    a.equal("actual.balance", g+pv+d+emergency, load+c+surplus)
    a.equal("actual.surplus_allocation", surplus, f.unused_grid_kwh+f.pv_curtailment_kwh)
    a.equal("actual.paid_unused_contract", f.unused_grid_kwh, np.minimum(g, surplus))
    a.check("actual.pv_curtailment_bound", f.pv_curtailment_kwh <= pv+ETOL)
    a.equal("actual.emergency_use", emergency, np.maximum(load-pv-g-d, 0))
    a.check("actual.no_emergency_charge_or_dump", (emergency <= ETOL) | ((c <= ETOL) & (surplus <= ETOL)))
    a.equal("plan.balance", g+f.plan_pv_kwh+f.discharge_plan_kwh,
            f.plan_load_kwh+f.charge_plan_kwh+f.pv_curtailment_plan_kwh)
    a.check("plan.curtailment_bound", f.pv_curtailment_plan_kwh <= f.plan_pv_kwh+ETOL)
    z = f.charge_mode_plan
    a.check("plan.mode_binary", (abs(z) <= 1e-7) | (abs(z-1) <= 1e-7))
    a.check("plan.mode_power", (f.charge_plan_kwh <= mc*z+ETOL) & (f.discharge_plan_kwh <= md*(1-z)+ETOL))
    for field, expected in dict(planned_cost_yuan=p*g, emergency_cost_yuan=5*p*emergency,
                               total_cost_yuan=p*g+5*p*emergency).items():
        a.equal("cost." + field, f[field], expected, CTOL)
    forecast = forecasts[cfg["forecast_model"]]
    published = forecast.set_index(KEYS).reindex(pd.MultiIndex.from_frame(f[KEYS]))
    for field in ["load_forecast_kwh", "pv_forecast_kwh"]:
        a.equal("published." + field, f[field], published[field].to_numpy())
    delta, counts, reserves = np.zeros(len(f)), np.zeros(len(f), dtype=int), np.zeros(len(f))
    for date, rows in f.groupby("date", sort=False):
        indices, day = rows.index.to_numpy(), pd.Timestamp(date)
        history = forecast.loc[(forecast.date >= str((day-pd.Timedelta(days=cfg["residual_days"])).date())) &
                               (forecast.date < date) & (pd.to_datetime(forecast.residual_available_time) <= day)]
        if cfg["risk"]:
            for hour in range(24):
                sample = history.loc[(history.slot_id-1)//6 == hour, "net_residual_kwh"].to_numpy()
                counts[indices[hour*6:hour*6+6]] = len(sample)
                if history.date.nunique() >= 7:
                    delta[indices[hour*6:hour*6+6]] = np.quantile(sample, cfg["tau"], method="linear")
        for field, expected in [("risk_history_start", history.date.min()), ("risk_history_end", history.date.max())]:
            if not cfg["risk"] or history.empty:
                a.check(date + "." + field, rows[field].isna() | rows[field].eq(""))
            else:
                a.check(date + "." + field, rows[field].astype(str).eq(expected))
        if "risk_history_days" in rows:
            a.equal(date + ".history_days", rows.risk_history_days, history.date.nunique() if cfg["risk"] else 0, 0)
        if "risk_cold_start" in rows:
            a.check(date + ".cold_start", rows.risk_cold_start.eq(bool(cfg["risk"] and history.date.nunique() < 7)))
        a.equal(date + ".plan_actual_initial", rows.energy_start_plan_kwh.iloc[0], rows.energy_start_actual_kwh.iloc[0])
        target = rows.energy_start_actual_kwh.iloc[0] if cfg["terminal_target"] == "equal_initial" else float(cfg["terminal_target"])
        a.equal(date + ".plan_terminal", rows.energy_end_plan_kwh.iloc[-1], target)
        if cfg["executor"] == "reserve":
            future_deficit = np.maximum(rows.load_forecast_kwh.to_numpy()-rows.pv_forecast_kwh.to_numpy()-rows.grid_plan_kwh.to_numpy(), 0)
            price_day = rows.price_yuan_per_kwh.to_numpy()
            for i in range(144):
                reserves[indices[i]] = min(9600, future_deficit[(np.arange(144) > i) & (price_day > price_day[i])].sum()/ed)
    a.equal("risk.empirical_quantile", f.risk_delta_kwh, delta)
    a.equal("risk.sample_count", f.risk_sample_count, counts, 0)
    a.equal("risk.plan_load", f.plan_load_kwh, np.maximum(f.load_forecast_kwh+delta, 0))
    a.equal("risk.plan_pv", f.plan_pv_kwh, f.pv_forecast_kwh+np.maximum(-f.load_forecast_kwh-delta, 0))
    a.equal("executor.reserve", f.reserve_internal_kwh, reserves)
    net, state = g+pv-load, f.energy_start_actual_kwh.to_numpy()
    a.equal("executor.charge", c, np.where(net >= 0, np.minimum(np.minimum(net, mc), np.maximum((10800-state)/ec, 0)), 0))
    a.equal("executor.discharge", d, np.where(net < 0, np.minimum(np.minimum(-net, md), np.maximum((state-1200-reserves)*ed, 0)), 0))
    grouped = f.groupby("date", sort=True)
    a.check("daily.unique_ordered_dates", daily.date.tolist() == sorted(f.date.unique()))
    for field in SUMS:
        a.equal("daily." + field, daily[field], grouped[field].sum().to_numpy(), CTOL)
        a.equal("summary." + field, summary[field], f[field].sum(), CTOL)
    for field, op in [("energy_start_actual_kwh", "first"), ("energy_end_actual_kwh", "last")]:
        a.equal("daily." + field, daily[field], getattr(grouped[field], op)().to_numpy())
    inventory_unit = price.price_yuan_per_kwh.mean()*ed
    totals = dict(days=f.date.nunique(), intervals=len(f), initial_energy_kwh=f.energy_start_actual_kwh.iloc[0],
        final_energy_kwh=f.energy_end_actual_kwh.iloc[-1], inventory_value_yuan_per_kwh=inventory_unit,
        inventory_adjusted_cost_yuan=f.total_cost_yuan.sum()-inventory_unit*(f.energy_end_actual_kwh.iloc[-1]-f.energy_start_actual_kwh.iloc[0]),
        emergency_share_of_load=emergency.sum()/load.sum(), emergency_intervals=int((emergency > ETOL).sum()),
        emergency_days=f.loc[f.emergency_kwh > ETOL, "date"].nunique())
    for field, value in totals.items():
        a.equal("summary." + field, summary[field], value, CTOL)
    a.check("models.unique_ordered_dates", [m["date"] for m in models] == sorted(f.date.unique()))
    runtimes, gaps, failed, fallbacks = [], [], 0, 0
    for model in models:
        date, solver = model["date"], model["solver"]
        rows = f.loc[f.date == date]
        a.check(date + ".optimal_solver", solver["status"] == "Optimal")
        failed += solver["status"] != "Optimal"
        fallbacks += bool(solver.get("fallback", False))
        a.equal(date + ".model_initial", model["initial_energy_kwh"], rows.energy_start_actual_kwh.iloc[0])
        a.check(date + ".model_history", pd.Timestamp(model["forecast"]["history_end"]) == pd.Timestamp(date))
        objective = (rows.grid_plan_kwh*rows.price_yuan_per_kwh).sum()
        a.equal(date + ".solver_objective", solver["objective_yuan"], objective, CTOL)
        a.equal(date + ".solver_internal_objective", solver["solver_objective"], objective, CTOL)
        bound, gap, runtime = solver["lower_bound_yuan"], solver["mip_gap"], solver["runtime_seconds"]
        a.check(date + ".bound_and_gap", np.isfinite([bound, gap]).all() and gap >= 0 and gap <= 1.001e-9 and
                bound <= objective+CTOL and objective-bound <= max(CTOL, abs(objective)*(gap+1e-12)))
        a.check(date + ".bound_unit", solver["lower_bound_unit"] == "yuan")
        a.check(date + ".solver_feasibility", solver["max_primal_infeasibility"] <= ETOL and solver["max_integrality_violation"] <= 1e-7)
        a.check(date + ".runtime", np.isfinite(runtime) and runtime >= 0)
        runtimes.append(runtime)
        gaps.append(gap)
    statistics = dict(solver_runtime_seconds=sum(runtimes), solver_max_runtime_seconds=max(runtimes),
                      solver_max_mip_gap=max(gaps), solver_failures=failed, solver_fallbacks=fallbacks)
    for field, value in statistics.items():
        a.equal("summary." + field, summary[field], value, CTOL)
    boundary = dict(normal_surplus=int((net >= 0).sum()), deficit=int((net < -ETOL).sum()),
        soc_lower_bound=int((f.energy_end_actual_kwh <= 1200+ETOL).sum()),
        charge_power_limit=int((c >= mc-ETOL).sum()), discharge_power_limit=int((d >= md-ETOL).sum()),
        conditional_emergency_before_exhaustion=int(((emergency > ETOL) & (d < md-ETOL) &
                                                     (f.energy_end_actual_kwh > 1200+ETOL)).sum()))
    baseline = None
    if not january and cfg["policy"] in ("B0", "B1"):
        old = csv(WORK / "results/q2" / ("selected" if cfg["policy"] == "B0" else "seasonal") / "ledger.csv")
        keys(a, old, cfg["start"], cfg["end"], "old_baseline")
        fields = PLAN + SUMS + ["load_forecast_kwh", "pv_forecast_kwh", "energy_start_actual_kwh", "energy_end_actual_kwh"]
        baseline = {field: float(abs(f[field]-old[field]).max()) for field in fields}
        a.check("old_baseline_exact_reproduction", all(value == 0 for value in baseline.values()), baseline)
    return dict(**a.result(), config=cfg, boundary_coverage=boundary, solver_statistics=statistics,
        totals={**{field: float(f[field].sum()) for field in SUMS}, **{k: float(v) for k, v in totals.items()}},
        baseline_reproduction=baseline, artifact_sha256={name: sha(folder/name) for name in files})


def causality():
    """Check saved metamorphic-test evidence independently, without running producer code."""
    a = Audit()
    path = REPORT / "causality_validation.json"
    if not a.check("causality_evidence_present", path.is_file()):
        return a.result()
    report = js(path)
    a.check("causality_script_hash", report["script_sha256"] == sha(WORK / "scripts/emergency_improvement_v1/causality_checks.py"))
    cutoff = pd.Timestamp(report["mutation_cutoff"])
    for policy in ("B0", "B1", "P", "E", "PE"):
        original = csv(ROOT / "causality" / (policy + "_original.csv"))
        changed = csv(ROOT / "causality" / (policy + "_future_mutated.csv"))
        a.check(policy + ".identical_time_keys", original[["date", "interval_start"]].equals(changed[["date", "interval_start"]]))
        a.check(policy + ".full_test_coverage", len(original) == 12*144)
        earlier = pd.to_datetime(original.interval_start) < cutoff
        frozen = original.date <= str(cutoff.date())
        later = original.date == str((cutoff+pd.Timedelta(days=1)).date())
        columns = original.select_dtypes(include="number").columns
        plan_cols = ["load_forecast", "pv_forecast", "risk_delta", "grid", "reserve"]
        prefix_error = float(np.max(abs(original.loc[earlier, columns].to_numpy()-changed.loc[earlier, columns].to_numpy())))
        frozen_error = float(np.max(abs(original.loc[frozen, plan_cols].to_numpy()-changed.loc[frozen, plan_cols].to_numpy())))
        response = float(np.max(abs(original.loc[later, plan_cols[:-1]].to_numpy()-changed.loc[later, plan_cols[:-1]].to_numpy())))
        a.equal(policy + ".future_does_not_change_prefix", prefix_error)
        a.equal(policy + ".future_does_not_change_frozen_plan", frozen_error)
        a.check(policy + ".positive_control", response > 1e-4, dict(next_day_response_kwh=response))
        record = next(c for c in report["checks"] if c["policy"] == policy)
        for field, expected in [("prefix_max_difference_kwh", prefix_error),
                                ("already_frozen_plans_max_difference_kwh", frozen_error),
                                ("next_day_positive_control_difference_kwh", response), ("prefix_rows", int(earlier.sum()))]:
            a.equal(policy + ".reported." + field, record[field], expected)
    return a.result()


def stress(forecasts, price):
    a = Audit()
    ledger_path, summary_path = ROOT / "stress/ledger.csv", ROOT / "stress/summary.csv"
    if not ledger_path.is_file() or not summary_path.is_file():
        return dict(passed=None, status="not_yet_generated")
    f, summary = csv(ledger_path), csv(summary_path)
    archive = forecasts["linear_harmonic"]
    group_keys = ["target_date", "stress_quantile", "policy"]
    expected_groups = {(str(day.date()), tau, policy)
                       for day in pd.date_range("2025-02-01", "2025-12-01", freq="MS")
                       for tau in (.9, .95) for policy in ("B0", "B1", "P")}
    a.check("stress.summary_groups", set(summary[group_keys].itertuples(index=False, name=None)) == expected_groups)
    a.check("stress.summary_unique", ~summary.duplicated(group_keys))
    a.check("stress.ledger_groups", set(f[group_keys].itertuples(index=False, name=None)) == expected_groups)
    main = {policy: csv(ROOT / "runs" / policy / "ledger.csv") for policy in ("B0", "B1", "P")}
    for (date, tau, policy), rows in f.groupby(group_keys, sort=True):
        tag = date + "." + str(tau) + "." + policy
        day = pd.Timestamp(date)
        a.check(tag + ".slots", rows.slot_id.tolist() == list(range(1, 145)))
        history = archive.loc[(archive.date >= str((day-pd.Timedelta(days=56)).date())) & (archive.date < date) &
                              (pd.to_datetime(archive.residual_available_time) <= day)]
        scores = history.groupby("date").net_residual_kwh.sum().sort_values(kind="stable")
        source_date = scores.index[int(np.ceil(tau*len(scores)))-1]
        source = history.loc[history.date == source_date]
        target = archive.loc[archive.date == date]
        a.check(tag + ".nearest_rank_source", rows.source_date.eq(source_date))
        time_equal(a, rows, "source_available_time", pd.DatetimeIndex([pd.Timestamp(source_date)+pd.Timedelta(days=1)]*144), tag)
        time_equal(a, rows, "issue_time", pd.DatetimeIndex([day]*144), tag)
        a.check(tag + ".source_before_issue", pd.Timestamp(source_date)+pd.Timedelta(days=1) <= day)
        raw_load = target.load_forecast_kwh.to_numpy()+source.load_actual_kwh.to_numpy()-source.load_forecast_kwh.to_numpy()
        raw_pv = target.pv_forecast_kwh.to_numpy()+source.pv_actual_kwh.to_numpy()-source.pv_forecast_kwh.to_numpy()
        load, pv = np.maximum(raw_load, 0), np.maximum(raw_pv, 0)
        a.equal(tag + ".raw_load", rows.raw_load_before_clipping_kwh, raw_load)
        a.equal(tag + ".raw_pv", rows.raw_pv_before_clipping_kwh, raw_pv)
        a.equal(tag + ".clipped_load", rows.load_actual_kwh, load)
        a.equal(tag + ".clipped_pv", rows.pv_actual_kwh, pv)
        main_day = main[policy].loc[main[policy].date == date]
        g = rows.grid_plan_kwh.to_numpy()
        c, d, e0, e1, emergency, surplus = [rows[field].to_numpy() for field in [
            "charge_actual_kwh", "discharge_actual_kwh", "energy_start_actual_kwh", "energy_end_actual_kwh", "emergency_kwh", "surplus_kwh"]]
        p = price.price_yuan_per_kwh.to_numpy()
        a.equal(tag + ".frozen_contract", g, main_day.grid_plan_kwh)
        a.equal(tag + ".fixed_price", rows.price_yuan_per_kwh, p)
        a.equal(tag + ".conditional_initial", e0[0], main_day.energy_start_actual_kwh.iloc[0])
        a.equal(tag + ".balance", g+pv+d+emergency, load+c+surplus)
        a.equal(tag + ".soc", e1, e0+.9*c-d/.9)
        a.equal(tag + ".continuity", e0[1:], e1[:-1])
        a.check(tag + ".bounds", (e0 >= 1200-ETOL) & (e0 <= 10800+ETOL) & (e1 >= 1200-ETOL) & (e1 <= 10800+ETOL))
        a.check(tag + ".nonnegative_flows", np.isfinite(np.column_stack((g, c, d, emergency, surplus))) &
                (np.column_stack((g, c, d, emergency, surplus)) >= -ETOL))
        a.check(tag + ".power", (c <= 5000/6+ETOL) & (d <= 5000/6+ETOL))
        a.check(tag + ".mutual_exclusion", (c <= ETOL) | (d <= ETOL))
        a.equal(tag + ".emergency_use", emergency, np.maximum(load-pv-g-d, 0))
        a.check(tag + ".no_emergency_charge", (emergency <= ETOL) | ((c <= ETOL) & (surplus <= ETOL)))
        net = g+pv-load
        a.equal(tag + ".greedy_charge", c, np.where(net >= 0, np.minimum(np.minimum(net, 5000/6), np.maximum((10800-e0)/.9, 0)), 0))
        a.equal(tag + ".greedy_discharge", d, np.where(net < 0, np.minimum(np.minimum(-net, 5000/6), np.maximum((e0-1200)*.9, 0)), 0))
        a.equal(tag + ".unused_grid", rows.unused_grid_kwh, np.minimum(g, surplus))
        a.equal(tag + ".pv_curtailment", rows.pv_curtailment_kwh, surplus-rows.unused_grid_kwh)
        a.check(tag + ".curtailment_bound", rows.pv_curtailment_kwh <= pv+ETOL)
        a.equal(tag + ".emergency_cost", rows.emergency_cost_yuan, 5*p*emergency, CTOL)
        a.equal(tag + ".total_cost", rows.total_cost_yuan, p*g+5*p*emergency, CTOL)
        record = summary.loc[(summary.target_date == date) & (summary.policy == policy) &
                             (summary.stress_quantile == tau)].iloc[0]
        a.check(tag + ".summary_source", record.source_date == source_date)
        for field, expected in dict(history_days=len(scores), source_cumulative_signed_underforecast_kwh=scores.loc[source_date],
            total_cost_yuan=(p*g+5*p*emergency).sum(), emergency_cost_yuan=(5*p*emergency).sum(),
            initial_energy_kwh=e0[0], final_energy_kwh=e1[-1], load_clipping_kwh=np.maximum(-raw_load, 0).sum(),
            pv_clipping_kwh=np.maximum(-raw_pv, 0).sum()).items():
            a.equal(tag + ".summary." + field, record[field], expected, CTOL)
    return dict(**a.result(), paths=66, rows=len(f),
                artifact_sha256={"ledger.csv": sha(ledger_path), "summary.csv": sha(summary_path)})


def analysis_tables(runs):
    a = Audit()
    required = ["comparison_all.csv", "daily_costs_and_differences.csv", "monthly_costs_and_differences.csv",
                "paired_assumption_sensitivity.csv", "ablation.json", "block_bootstrap.csv",
                "forecast_coverage.csv", "forecast_lead_time.csv", "monthly.csv", "hourly.csv"]
    if not a.check("analysis_artifacts_present", all((ROOT/name).is_file() for name in required)):
        return a.result()
    comparison = csv(ROOT/"comparison_all.csv").set_index("policy")
    paired = csv(ROOT/"paired_assumption_sensitivity.csv")
    daily = csv(ROOT/"daily_costs_and_differences.csv").set_index("date")
    monthly = csv(ROOT/"monthly_costs_and_differences.csv").set_index("month")
    forecast_coverage = csv(ROOT/"forecast_coverage.csv")
    lead_coverage = csv(ROOT/"forecast_lead_time.csv")
    monthly_components, hourly_components = csv(ROOT/"monthly.csv"), csv(ROOT/"hourly.csv")
    config = js(WORK/"configs/emergency_improvement_v1/experiments.json")
    a.check("comparison_all.policies", comparison.index.tolist() == [c["policy"] for c in config["runs"]])
    for cfg in config["runs"]:
        name = cfg["policy"]
        record = runs["runs/"+name]
        total = record["totals"]
        for field, value in total.items():
            if field in comparison:
                a.equal(name+".comparison."+field, comparison.loc[name, field], value, CTOL)
        for baseline in ("B0", "B1"):
            reference_policy = baseline+"_"+cfg["group"] if cfg["group"] in ("terminal", "efficiency", "power") else baseline
            a.check(name+".comparison.reference_"+baseline, comparison.loc[name, "reference_"+baseline+"_policy"] == reference_policy)
            ref = runs["runs/"+reference_policy]["totals"]
            saving = ref["total_cost_yuan"]-total["total_cost_yuan"]
            for field, value in {f"saving_vs_{baseline}_yuan": saving,
                f"saving_vs_{baseline}_percent": 100*saving/ref["total_cost_yuan"],
                f"inventory_adjusted_saving_vs_{baseline}_yuan":
                    ref["inventory_adjusted_cost_yuan"]-total["inventory_adjusted_cost_yuan"]}.items():
                a.equal(name+".comparison."+field, comparison.loc[name, field], value, CTOL)
        run_daily = csv(ROOT/"runs"/name/"daily.csv").set_index("date")
        a.check(name+".daily_dates", run_daily.index.equals(daily.index))
        a.equal(name+".daily_costs", daily[name], run_daily.total_cost_yuan, CTOL)
        f = csv(ROOT/"runs"/name/"ledger.csv")
        mask = f.emergency_kwh > ETOL
        diagnostic = dict(evening_emergency_fee_share=f.loc[mask & (f.slot_id >= 109), "emergency_cost_yuan"].sum()/max(1e-20, total["emergency_cost_yuan"]),
            floor_emergency_fee_share=f.loc[mask & (f.energy_end_actual_kwh <= 1200+ETOL), "emergency_cost_yuan"].sum()/max(1e-20, total["emergency_cost_yuan"]),
            risk_sample_min=f.risk_sample_count.min(), risk_sample_max=f.risk_sample_count.max(),
            risk_cold_start_days=f.groupby("date").risk_cold_start.first().sum())
        for field, value in diagnostic.items():
            a.equal(name+".comparison."+field, comparison.loc[name, field], value, CTOL)
        for column, grouping, table in [("month", f.date.str[:7], monthly_components),
                                        ("hour", (f.slot_id-1)//6, hourly_components)]:
            actual = table.loc[table.policy == name].set_index(column)
            fields = ["planned_cost_yuan", "emergency_cost_yuan", "total_cost_yuan", "emergency_kwh"]
            if column == "month":
                fields += ["surplus_kwh", "unused_grid_kwh"]
            expected = f.groupby(grouping)[fields].sum()
            a.check(name+"."+column+".keys", actual.index.equals(expected.index))
            for field in expected:
                a.equal(name+"."+column+"."+field, actual[field], expected[field], CTOL)
        if cfg["group"] in ("main", "risk_sensitivity"):
            point_error = f.load_actual_kwh-f.pv_actual_kwh-f.load_forecast_kwh+f.pv_forecast_kwh
            error = f.load_actual_kwh-f.pv_actual_kwh-f.plan_load_kwh+f.plan_pv_kwh
            tau = cfg["tau"]
            data = pd.DataFrame(dict(coverage=(error <= 0).astype(float),
                quantile_loss_kwh=np.maximum(tau*error, (tau-1)*error),
                point_pinball_same_tau_kwh=np.maximum(tau*point_error, (tau-1)*point_error),
                point_net_mae_kwh=abs(point_error), risk_net_absolute_error_kwh=abs(error),
                net_underforecast_kwh=np.maximum(error, 0)))
            for group, grouping in [("month", f.date.str[:7]), ("hour", (f.slot_id-1)//6)]:
                expected = data.groupby(grouping).mean()
                actual = forecast_coverage.loc[(forecast_coverage.policy == name) & (forecast_coverage.grouping == group)]
                a.check(name+".coverage."+group+".length", len(actual) == len(expected))
                for field in expected:
                    a.equal(name+".coverage."+group+"."+field, actual[field], expected[field].to_numpy())
                a.equal(name+".coverage."+group+".count", actual.n_intervals, data.groupby(grouping).size().to_numpy(), 0)
            expected = data.groupby(f.slot_id).mean()
            actual = lead_coverage.loc[lead_coverage.policy == name]
            a.equal(name+".lead.slots", actual.slot_id, expected.index.to_numpy(), 0)
            a.equal(name+".lead.minutes", actual.lead_minutes, actual.slot_id*10, 0)
            for field in ["coverage", "quantile_loss_kwh", "point_pinball_same_tau_kwh", "point_net_mae_kwh"]:
                a.equal(name+".lead."+field, actual[field], expected[field].to_numpy())
    for baseline in ("B0", "B1"):
        a.equal("daily.saving."+baseline, daily["P_saving_vs_"+baseline], daily[baseline]-daily.P, CTOL)
    summed = daily.groupby(daily.index.str[:7]).sum()
    a.check("monthly.dates", summed.index.equals(monthly.index))
    a.equal("monthly.all_costs_and_savings", monthly.to_numpy(), summed.to_numpy(), CTOL)
    for row in paired.itertuples():
        suffix = "" if row.setting == "base" else "_"+row.setting
        baseline = runs["runs/"+row.baseline+suffix]["totals"]
        candidate = runs["runs/P"+suffix]["totals"]
        for field, value in dict(baseline_cost_yuan=baseline["total_cost_yuan"],
            P_cost_yuan=candidate["total_cost_yuan"],
            P_saving_yuan=baseline["total_cost_yuan"]-candidate["total_cost_yuan"],
            P_inventory_adjusted_saving_yuan=baseline["inventory_adjusted_cost_yuan"]-candidate["inventory_adjusted_cost_yuan"],
            baseline_final_soc_kwh=baseline["final_energy_kwh"], P_final_soc_kwh=candidate["final_energy_kwh"]).items():
            a.equal(row.setting+"."+row.baseline+"."+field, getattr(row, field), value, CTOL)
    cost = {p: runs["runs/"+p]["totals"]["total_cost_yuan"] for p in ("B0", "P", "E", "PE")}
    ablation = js(ROOT/"ablation.json")
    expected = dict(B0_yuan=cost["B0"], P_yuan=cost["P"], E_conditional_yuan=cost["E"], PE_conditional_yuan=cost["PE"],
        P_saving_vs_B0=cost["B0"]-cost["P"], E_saving_vs_B0=cost["B0"]-cost["E"], PE_saving_vs_B0=cost["B0"]-cost["PE"],
        P_increment_on_E=cost["E"]-cost["PE"], E_increment_on_P=cost["P"]-cost["PE"],
        interaction_extra_saving=(cost["B0"]-cost["PE"])-(cost["B0"]-cost["P"])-(cost["B0"]-cost["E"]))
    for field, value in expected.items():
        a.equal("ablation."+field, ablation[field], value, CTOL)
    bootstrap = csv(ROOT/"block_bootstrap.csv")
    rng = np.random.default_rng(config["bootstrap"]["seed"])
    for baseline in ("B0", "B1"):
        saving = (daily[baseline]-daily.P).to_numpy()
        n = len(saving)
        for length in config["bootstrap"]["block_days"]:
            starts = rng.integers(n, size=(config["bootstrap"]["replicates"], int(np.ceil(n/length))))
            indices = ((starts[:, :, None]+np.arange(length)) % n).reshape(len(starts), -1)[:, :n]
            low, high = np.quantile(saving[indices].sum(axis=1), [.025, .975])
            record = bootstrap.loc[(bootstrap.baseline == baseline) & (bootstrap.block_days == length)].iloc[0]
            for field, value in dict(point_saving_yuan=saving.sum(), ci95_low_yuan=low, ci95_high_yuan=high,
                replicates=config["bootstrap"]["replicates"], seed=config["bootstrap"]["seed"]).items():
                a.equal("bootstrap."+baseline+"."+str(length)+"."+field, record[field], value, CTOL)
    return dict(**a.result(), artifact_sha256={name: sha(ROOT/name) for name in required})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("all", "january", "runs"), default="all")
    args = parser.parse_args()
    actual, price, forecasts, source_checks = sources()
    causality_checks = causality()
    checks = {}
    for scope in (("january", "runs") if args.scope == "all" else (args.scope,)):
        for folder in sorted((ROOT / scope).glob("*")):
            if not folder.is_dir():
                continue
            name = str(folder.relative_to(ROOT))
            try:
                checks[name] = run(folder, actual, price, forecasts)
            except Exception as exc:
                checks[name] = dict(passed=False, audit_exception=type(exc).__name__ + ": " + str(exc))
            print(name, "PASS" if checks[name]["passed"] else "FAIL", flush=True)
    stress_checks = stress(forecasts, price) if args.scope != "january" else dict(passed=None, status="outside_january_gate")
    completeness = Audit()
    if args.scope == "all":
        declared = js(WORK/"configs/emergency_improvement_v1/experiments.json")["runs"]
        expected = {"runs/"+cfg["policy"] for cfg in declared} | {"january/"+name for name in ("B0", "B1", "P", "E", "PE")}
        completeness.check("all_declared_paths_present", set(checks) == expected, dict(expected_count=len(expected), actual_count=len(checks)))
        completeness.check("stress_complete", stress_checks["passed"] is True)
        analysis_checks = analysis_tables(checks) if expected <= set(checks) and all(v["passed"] for v in checks.values()) else dict(passed=False, status="paths_incomplete")
    else:
        analysis_checks = dict(passed=None, status="outside_partial_gate")
    passed = (source_checks["inputs"]["passed"] and all(v["passed"] for v in source_checks["forecasts"].values())
              and causality_checks["passed"] and bool(checks) and all(v["passed"] for v in checks.values())
              and stress_checks["passed"] is not False and completeness.result()["passed"] and analysis_checks["passed"] is not False)
    result = dict(created_utc=datetime.now(timezone.utc).isoformat(), passed=passed, scope=args.scope,
        independence="Standard library, numpy/pandas only; no producer solver/executor/predictor imports.",
        tolerances=dict(physical_kwh=ETOL, cost_yuan=CTOL), **source_checks, causality=causality_checks,
        stress=stress_checks, runs=checks, completeness=completeness.result(), analysis_tables=analysis_checks,
        validator_sha256=sha(Path(__file__)),
        limitations=["Interval-end actual information is the inherited instantaneous-balancing assumption.",
                     "Timestamp/source checks require complementary producer noninterference tests.",
                     "MILP optimality applies to given forecasts; E/PE use conditional discretionary discharge.",
                     "Processed-source snapshots were audited; no raw spreadsheet recleaning was performed."])
    target = REPORT / ("independent_validation.json" if args.scope == "all" else "independent_validation_" + args.scope + ".json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(passed=passed, runs=len(checks), output=str(target)), ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
