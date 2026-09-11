"""Independent equation-level Q2 v2 audit; no producer/optimizer imports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[2]
ROOT = WORK / "results/q2_cost_aware_v2"
REPORT = WORK / "reports/q2_cost_aware_v2"
ETOL, CTOL = 1e-6, 1e-5
KEYS = ["date", "slot_id"]
_ARCHIVE_CACHE = {}
PLAN = ["grid_plan_kwh", "charge_plan_kwh", "discharge_plan_kwh",
        "energy_start_plan_kwh", "energy_end_plan_kwh", "pv_curtailment_plan_kwh", "charge_mode_plan"]
SUMS = ["grid_plan_kwh", "emergency_kwh", "planned_cost_yuan", "emergency_cost_yuan",
        "total_cost_yuan", "charge_actual_kwh", "discharge_actual_kwh", "surplus_kwh",
        "unused_grid_kwh", "pv_curtailment_kwh"]

def csv(path):
    return pd.read_csv(path, float_precision="round_trip", dtype={"selected_terminal":str})


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

    def result(self, compact=False):
        result = dict(passed=all(x["passed"] for x in self.checks),
                    checks=[x for x in self.checks if not x["passed"]] if compact else self.checks,
                    check_groups=len(self.checks), comparisons=sum(x["comparisons"] for x in self.checks),
                    failed_groups=sum(not x["passed"] for x in self.checks))
        if compact:
            result["checks_contains"] = "failures_only; all groups included in counts and error maxima"
            result["max_abs_error_by_tolerance"] = {str(tol): max([x.get("detail", {}).get("max_abs_error") or 0
                for x in self.checks if isinstance(x.get("detail"), dict) and x["detail"].get("tolerance") == tol] or [0])
                for tol in (0, ETOL, CTOL)}
        return result


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


def source_audit():
    a = Audit()
    source_map = {"actual_10min.csv": "data/processed/actual_10min.csv",
        "fixed_price.csv": "data/processed/fixed_price.csv", "model_baseline.json": "configs/model_baseline.json",
        "q2_baseline.json": "configs/q2_baseline.json", "original_run_q2.py": "scripts/run_q2.py",
        "original_solve_q1.py": "scripts/solve_q1.py", "problem_text.txt": "data/interim/problem_text.txt",
        "selection.json": "results/q2/selection.json",
        "bzd_quantile_record.json": "reports/emergency_research_v1/bzd_quantile_record.json"}
    for name, original in source_map.items():
        a.check("source_snapshot." + name, sha(ROOT / "inputs" / name) == sha(WORK / original))
    for policy, old in [("B0", "selected"), ("B1", "seasonal"), ("no_storage", "no_storage")]:
        a.check("original_baseline_snapshot." + policy, sha(ROOT / "inputs" / ("baseline_"+policy+".csv")) ==
                sha(WORK / "results/q2" / old / "ledger.csv"))
    for policy in ("B0", "B1", "P", "P_terminal"):
        for name in ("ledger.csv", "plans.csv", "daily.csv", "summary.json", "config.json", "models_and_solvers.json"):
            a.check("previous_verified_copy."+policy+"."+name, sha(ROOT/"references"/policy/name) ==
                    sha(WORK/"results/emergency_improvement_v1/runs"/policy/name))
    freeze = js(REPORT / "protocol_freeze.json")
    a.check("protocol.frozen_sha256", sha(REPORT/"protocol.md") == freeze["protocol_sha256"])
    a.check("config.frozen_sha256", sha(WORK/"configs/q2_cost_aware_v2/experiments.json") == freeze["config_sha256"])
    config = js(WORK/"configs/q2_cost_aware_v2/experiments.json")
    a.check("config.main_predeclared", config["main_policy"] == "S_joint")
    a.check("config.seven_predeclared", [c["policy"] for c in config["runs"]] ==
            ["S_tau","S_terminal","S_joint","S_w14","S_w56","S_no_inventory","P_floor"])
    for cfg in config["runs"]:
        tau_set = [.8] if cfg["policy"] in ("S_terminal","P_floor") else [.5,.6,.7,.8,.9]
        terminals = ["equal_initial"] if cfg["policy"] == "S_tau" else ([1200.] if cfg["policy"] == "P_floor" else ["equal_initial",1200.,6000.])
        a.check("config.library."+cfg["policy"], cfg["taus"] == tau_set and cfg["terminals"] == terminals)
        a.check("config.period."+cfg["policy"], cfg["start"] == "2025-02-01" and cfg["end"] == "2025-12-31")
        a.equal("config.initial."+cfg["policy"], cfg["initial_energy_kwh"], 7268.4231640740745, 0)
        a.check("config.windows."+cfg["policy"], cfg["risk_window"] == 28 and cfg["scenario_window"] ==
                (14 if cfg["policy"] == "S_w14" else (56 if cfg["policy"] == "S_w56" else 28)))
    before = js(REPORT/"protected_hashes_before.json")
    changed = [name for name, digest in before.items() if not (WORK/name).is_file() or sha(WORK/name) != digest]
    a.check("protected_files_unchanged", not changed, dict(count=len(before), changed=changed))
    actual, price = csv(ROOT/"inputs/actual_10min.csv"), csv(ROOT/"inputs/fixed_price.csv")
    keys(a, actual, "2025-01-01", "2025-12-31", "actual")
    a.check("price.slots", price.slot_id.tolist() == list(range(1, 145)))
    a.equal("price.start_minutes", price.start_minute, np.arange(144)*10)
    a.equal("price.end_minutes", price.end_minute, np.arange(1, 145)*10)
    for kind in ("load", "pv"):
        a.equal("actual.units."+kind, actual[kind+"_actual_kwh"], actual[kind+"_actual_kw"]/6)
    a.check("actual.nonnegative", np.isfinite(actual[["load_actual_kwh", "pv_actual_kwh"]]) &
            (actual[["load_actual_kwh", "pv_actual_kwh"]] >= 0))
    a.check("price.positive", np.isfinite(price.price_yuan_per_kwh) & (price.price_yuan_per_kwh > 0))
    t = pd.to_datetime(actual.date)+pd.to_timedelta((actual.slot_id-1)*10, unit="min")
    for field, expected in [("interval_start", t), ("interval_end", t+pd.Timedelta(minutes=10)),
                            ("available_time", t+pd.Timedelta(minutes=10))]:
        time_equal(a, actual, field, expected, "actual")
    f = csv(ROOT/"forecasts/linear_harmonic.csv")
    keys(a, f, "2025-01-02", "2025-12-31", "archive")
    days = pd.to_datetime(f.date)
    for field, expected in [("issue_time", days), ("history_end", days),
                            ("residual_available_time", days+pd.Timedelta(days=1))]:
        time_equal(a, f, field, expected, "archive")
    truth = actual.set_index(KEYS).reindex(pd.MultiIndex.from_frame(f[KEYS]))
    for field in ("load_actual_kwh", "pv_actual_kwh"):
        a.equal("archive.source."+field, f[field], truth[field].to_numpy())
    lh, ph = harmonic_predictions(actual)
    a.equal("archive.load_from_history", f.load_forecast_kwh, lh)
    a.equal("archive.pv_from_history", f.pv_forecast_kwh, ph)
    a.equal("archive.net_error", f.net_residual_kwh,
            truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()-lh+ph)
    seasonal = csv(ROOT/"forecasts/seasonal.csv")
    keys(a, seasonal, "2025-01-02", "2025-12-31", "seasonal")
    loads = actual.load_actual_kwh.to_numpy().reshape(365,144)
    pvs = actual.pv_actual_kwh.to_numpy().reshape(365,144)
    a.equal("seasonal.load_history", seasonal.load_forecast_kwh,
            np.concatenate([loads[n-7 if n >= 7 else n-1] for n in range(1,365)]))
    a.equal("seasonal.pv_history", seasonal.pv_forecast_kwh, pvs[:-1].ravel())
    a.equal("seasonal.net_error",seasonal.net_residual_kwh,
            truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()-seasonal.load_forecast_kwh.to_numpy()+seasonal.pv_forecast_kwh.to_numpy())
    for field,expected_time in (("issue_time",days),("history_end",days),("residual_available_time",days+pd.Timedelta(days=1))):
        time_equal(a,seasonal,field,expected_time,"seasonal")
    extension_file = WORK/"configs/q2_cost_aware_v2/extension.json"
    if extension_file.is_file():
        extension_freeze = js(REPORT/"extension_freeze.json")
        a.check("extension.protocol_frozen",sha(REPORT/"extension_protocol.md") == extension_freeze["protocol_sha256"])
        a.check("extension.config_frozen",sha(extension_file) == extension_freeze["config_sha256"])
    return actual, price, f, a.result()


def selected_history(archive, date, days):
    day = pd.Timestamp(date)
    identity = id(archive)
    if identity not in _ARCHIVE_CACHE:
        _ARCHIVE_CACHE[identity] = dict(source=archive,dates=archive.date.to_numpy(dtype="U10"),
            available=pd.to_datetime(archive.residual_available_time).to_numpy(),deltas={})
    cached = _ARCHIVE_CACHE[identity]
    return archive.loc[(cached["dates"] >= str((day-pd.Timedelta(days=days)).date())) &
                       (cached["dates"] < date) & (cached["available"] <= day.to_datetime64())]


def risk_delta(archive, date, tau):
    if id(archive) in _ARCHIVE_CACHE and (date,tau) in _ARCHIVE_CACHE[id(archive)]["deltas"]:
        return _ARCHIVE_CACHE[id(archive)]["deltas"][(date,tau)],None
    history = selected_history(archive, date, 28)
    if history.date.nunique() < 7:
        return np.zeros(144), history
    values, hours = history.net_residual_kwh.to_numpy(),(history.slot_id.to_numpy()-1)//6
    pools = np.stack([values[hours==hour] for hour in range(24)])
    delta = np.repeat(np.quantile(pools,tau,axis=1,method="linear"),6)
    _ARCHIVE_CACHE[id(archive)]["deltas"][(date,tau)] = delta
    return delta,None


def greedy_from_net(grid, net, initial):
    """Vectorize scenarios only; time remains a forward recurrence without lookahead."""
    net = np.atleast_2d(np.asarray(net, dtype=float))
    state = np.full(net.shape[0], float(initial))
    result = {key: np.empty_like(net) for key in ("charge_actual_kwh", "discharge_actual_kwh",
        "energy_start_actual_kwh", "energy_end_actual_kwh", "emergency_kwh", "surplus_kwh")}
    for t, contract in enumerate(grid):
        surplus = contract-net[:, t]
        charge = np.minimum(np.maximum(surplus, 0), np.minimum(5000/6, np.maximum((10800-state)/.9, 0)))
        discharge = np.minimum(np.maximum(-surplus, 0), np.minimum(5000/6, np.maximum((state-1200)*.9, 0)))
        result["energy_start_actual_kwh"][:, t] = state
        state = state+.9*charge-discharge/.9
        result["energy_end_actual_kwh"][:, t] = state
        result["charge_actual_kwh"][:, t] = charge
        result["discharge_actual_kwh"][:, t] = discharge
        result["emergency_kwh"][:, t] = np.maximum(-surplus-discharge, 0)
        result["surplus_kwh"][:, t] = np.maximum(surplus-charge, 0)
    return result


def physical(a, frame, tag, plan=False):
    suffix = "plan" if plan else "actual"
    cols = ["grid_plan_kwh", "charge_"+suffix+"_kwh", "discharge_"+suffix+"_kwh",
            "energy_start_"+suffix+"_kwh", "energy_end_"+suffix+"_kwh"]
    g, c, d, s0, s1 = (frame[key].to_numpy() for key in cols)
    a.check(tag+".finite_nonnegative", np.isfinite(frame[cols]) & (frame[cols] >= -ETOL))
    a.equal(tag+".soc", s1, s0+.9*c-d/.9)
    a.check(tag+".soc_bounds", (s0 >= 1200-ETOL) & (s1 >= 1200-ETOL) &
            (s0 <= 10800+ETOL) & (s1 <= 10800+ETOL))
    a.check(tag+".power", (c <= 5000/6+ETOL) & (d <= 5000/6+ETOL))
    a.check(tag+".mutex", (c <= ETOL) | (d <= ETOL))
    a.equal(tag+".continuity", s0[1:], s1[:-1])
    if plan:
        z, w = frame.charge_mode_plan.to_numpy(), frame.pv_curtailment_plan_kwh.to_numpy()
        a.check(tag+".binary", (abs(z) <= 1e-7) | (abs(z-1) <= 1e-7))
        a.check(tag+".mode_power", (c <= (5000/6)*z+ETOL) & (d <= (5000/6)*(1-z)+ETOL))
        a.check(tag+".curtailment", np.isfinite(w) & (w >= -ETOL) & (w <= frame.plan_pv_kwh+ETOL))
        a.equal(tag+".balance", g+frame.plan_pv_kwh+d, frame.plan_load_kwh+c+w)
    else:
        emergency, surplus = frame.emergency_kwh.to_numpy(), frame.surplus_kwh.to_numpy()
        a.check(tag+".balancing_flows", np.isfinite(np.column_stack((emergency, surplus))) &
                (np.column_stack((emergency, surplus)) >= -ETOL))
        a.equal(tag+".balance", g+frame.pv_actual_kwh+d+emergency, frame.load_actual_kwh+c+surplus)
        a.equal(tag+".emergency", emergency, np.maximum(frame.load_actual_kwh-frame.pv_actual_kwh-g-d, 0))
        a.check(tag+".no_emergency_charge_dump", (emergency <= ETOL) | ((c <= ETOL) & (surplus <= ETOL)))
        a.equal(tag+".unused_grid", frame.unused_grid_kwh, np.minimum(g, surplus))
        a.equal(tag+".pv_curtailment", frame.pv_curtailment_kwh, surplus-frame.unused_grid_kwh)
        a.check(tag+".curtailment_bound", (frame.pv_curtailment_kwh >= -ETOL) &
                (frame.pv_curtailment_kwh <= frame.pv_actual_kwh+ETOL))
        expected = greedy_from_net(g, frame.load_actual_kwh-frame.pv_actual_kwh, s0[0])
        for field, values in expected.items():
            a.equal(tag+".greedy."+field, frame[field], values[0])


def solver_evidence(a, evidence, price, grid, tag):
    obj = float(np.dot(price, grid))
    a.check(tag+".status", evidence["status"] == "Optimal")
    a.equal(tag+".objective", evidence["objective_yuan"], obj, CTOL)
    a.equal(tag+".internal_objective", evidence["solver_objective"], obj, CTOL)
    bound, gap = evidence["lower_bound_yuan"], evidence["mip_gap"]
    a.check(tag+".bound_and_gap", np.isfinite([bound, gap]).all() and 0 <= gap <= 1.001e-9 and
            bound <= obj+CTOL and obj-bound <= max(CTOL, abs(obj)*(gap+1e-12)))
    a.check(tag+".units", evidence["lower_bound_unit"] == "yuan")
    a.check(tag+".reported_feasibility", evidence["max_primal_infeasibility"] <= ETOL and
            evidence["max_integrality_violation"] <= 1e-7)
    a.check(tag+".runtime", np.isfinite(evidence["runtime_seconds"]) and evidence["runtime_seconds"] >= 0)


def ledger_audit(a, frame, daily, summary, actual, price, cfg):
    keys(a, frame, cfg["start"], cfg["end"], "ledger")
    truth = actual.set_index(KEYS).reindex(pd.MultiIndex.from_frame(frame[KEYS]))
    for field in ("load_actual_kwh", "pv_actual_kwh"):
        a.equal("ledger.source."+field, frame[field], truth[field].to_numpy())
    p = price.set_index("slot_id").loc[frame.slot_id, "price_yuan_per_kwh"].to_numpy()
    a.equal("ledger.source.price", frame.price_yuan_per_kwh, p)
    days = pd.to_datetime(frame.date)
    t = days+pd.to_timedelta((frame.slot_id-1)*10, unit="min")
    for field, expected in [("interval_start", t), ("interval_end", t+pd.Timedelta(minutes=10)),
        ("available_time", t+pd.Timedelta(minutes=10)), ("issue_time", days),
        ("dispatch_time", t+pd.Timedelta(minutes=10)), ("decision_input_cutoff", t+pd.Timedelta(minutes=10))]:
        time_equal(a, frame, field, expected, "ledger")
    physical(a, frame, "actual")
    a.equal("ledger.initial", frame.energy_start_actual_kwh.iloc[0], cfg["initial_energy_kwh"])
    for field, expected in dict(planned_cost_yuan=p*frame.grid_plan_kwh,
        emergency_cost_yuan=5*p*frame.emergency_kwh,
        total_cost_yuan=p*frame.grid_plan_kwh+5*p*frame.emergency_kwh).items():
        a.equal("ledger.fee."+field, frame[field], expected, CTOL)
    a.check("daily.dates", daily.date.tolist() == sorted(frame.date.unique()))
    grouped = frame.groupby("date", sort=True)
    for field in SUMS:
        a.equal("daily."+field, daily[field], grouped[field].sum().to_numpy(), CTOL)
        a.equal("summary."+field, summary[field], frame[field].sum(), CTOL)
    for field, op in (("energy_start_actual_kwh", "first"), ("energy_end_actual_kwh", "last")):
        a.equal("daily."+field, daily[field], getattr(grouped[field], op)().to_numpy())
    initial, final = frame.energy_start_actual_kwh.iloc[0], frame.energy_end_actual_kwh.iloc[-1]
    unit_value = price.price_yuan_per_kwh.mean()*.9
    totals = dict(days=frame.date.nunique(), intervals=len(frame), initial_energy_kwh=initial,
        final_energy_kwh=final, inventory_value_yuan_per_kwh=unit_value,
        inventory_adjusted_cost_yuan=frame.total_cost_yuan.sum()-unit_value*(final-initial),
        emergency_intervals=int((frame.emergency_kwh > ETOL).sum()),
        emergency_days=frame.loc[frame.emergency_kwh > ETOL, "date"].nunique(),
        emergency_share_of_load=frame.emergency_kwh.sum()/frame.load_actual_kwh.sum())
    for field, value in totals.items():
        if field in summary:
            a.equal("summary."+field, summary[field], value, CTOL)
    return {**{key: float(frame[key].sum()) for key in SUMS}, **{key: float(value) for key, value in totals.items()}}


def reference_audit(folder, actual, price, archive):
    a = Audit()
    cfg, summary = js(folder/"config.json"), js(folder/"summary.json")
    frame, plan, daily = csv(folder/"ledger.csv"), csv(folder/"plans.csv"), csv(folder/"daily.csv")
    a.check("same_evaluation_period", (cfg["start"], cfg["end"]) == ("2025-02-01", "2025-12-31"))
    a.equal("same_initial", cfg["initial_energy_kwh"], 7268.4231640740745)
    a.check("same_execution", cfg["eta_charge"] == cfg["eta_discharge"] == .9 and
            cfg["power_basis"] == "AC_bus" and cfg["executor"] == "greedy")
    totals = ledger_audit(a, frame, daily, summary, actual, price, cfg)
    keys(a, plan, cfg["start"], cfg["end"], "plans")
    for field in PLAN+["load_forecast_kwh", "pv_forecast_kwh", "plan_load_kwh", "plan_pv_kwh", "risk_delta_kwh"]:
        a.equal("frozen."+field, frame[field], plan[field])
    published = (csv(ROOT/"forecasts/seasonal.csv") if cfg["forecast_model"] == "seasonal" else archive)
    published = published.set_index(KEYS).reindex(pd.MultiIndex.from_frame(frame[KEYS]))
    for field in ("load_forecast_kwh", "pv_forecast_kwh"):
        a.equal("published."+field, frame[field], published[field].to_numpy())
    models = js(folder/"models_and_solvers.json")
    a.check("models.dates", [m["date"] for m in models] == sorted(frame.date.unique()))
    for model, (date, rows) in zip(models, frame.groupby("date", sort=True)):
        physical(a, rows, date+".plan", plan=True)
        a.equal(date+".plan_initial", rows.energy_start_plan_kwh.iloc[0], rows.energy_start_actual_kwh.iloc[0])
        target = rows.energy_start_actual_kwh.iloc[0] if cfg["terminal_target"] == "equal_initial" else float(cfg["terminal_target"])
        a.equal(date+".plan_terminal", rows.energy_end_plan_kwh.iloc[-1], target)
        delta, _ = risk_delta(archive, date, cfg["tau"]) if cfg["risk"] else (np.zeros(144), None)
        a.equal(date+".risk_delta", rows.risk_delta_kwh, delta)
        a.equal(date+".risk_load", rows.plan_load_kwh, np.maximum(rows.load_forecast_kwh+delta, 0))
        a.equal(date+".risk_pv", rows.plan_pv_kwh, rows.pv_forecast_kwh+np.maximum(-rows.load_forecast_kwh-delta, 0))
        solver_evidence(a, model["solver"], rows.price_yuan_per_kwh, rows.grid_plan_kwh, date+".solver")
    return dict(**a.result(compact=True), totals=totals, artifact_sha256={f.name: sha(f) for f in folder.iterdir() if f.is_file()})


def run_audit(folder, actual, price, archive):
    a = Audit()
    required = ["config.json", "ledger.csv", "plans.csv", "daily.csv", "summary.json", "decisions.json", "decision_evidence.npz"]
    if not a.check("artifacts_present", all((folder/name).is_file() for name in required)):
        return a.result()
    cfg, summary, decisions = (js(folder/name) for name in ("config.json", "summary.json", "decisions.json"))
    ledger, plans, daily = (csv(folder/name) for name in ("ledger.csv", "plans.csv", "daily.csv"))
    arrays = dict(np.load(folder/"decision_evidence.npz", allow_pickle=False))
    declared = js(WORK/"configs/q2_cost_aware_v2/experiments.json")["runs"]
    extension_file = WORK/"configs/q2_cost_aware_v2/extension.json"
    if extension_file.is_file():
        declared += js(extension_file)["runs"]
    frozen = next(c for c in declared if c["policy"] == cfg["policy"])
    if folder.parent.name == "january":
        frozen = dict(frozen, start="2025-01-15", end="2025-01-18", initial_energy_kwh=6000.)
    elif folder.parent.name.startswith("causality_"):
        frozen = dict(frozen, start="2025-01-24", end="2025-01-26", initial_energy_kwh=6000.)
    a.check("config_matches_frozen", cfg == frozen)
    a.check("unchanged_risk_window", cfg["risk_window"] == 28)
    a.equal("declared_mu", cfg["mu"], 0 if cfg["policy"] == "S_no_inventory" else .38232, 0)
    totals = ledger_audit(a, ledger, daily, summary, actual, price, cfg)
    keys(a, plans, cfg["start"], cfg["end"], "plans")
    days = sorted(ledger.date.unique())
    a.check("decision_dates", [m["date"] for m in decisions["days"]] == days)
    a.check("decision_plan_columns", decisions["plan_columns"] == PLAN)
    fields = PLAN+["load_forecast_kwh", "pv_forecast_kwh", "plan_load_kwh", "plan_pv_kwh", "risk_delta_kwh",
                   "selected_index", "selected_tau", "selected_terminal_energy_kwh"]
    for field in fields:
        a.equal("frozen."+field, ledger[field], plans[field])
    a.check("frozen.selected_terminal", ledger.selected_terminal.eq(plans.selected_terminal))
    time_equal(a, plans, "issue_time", pd.to_datetime(plans.date), "plan")
    time_equal(a, plans, "forecast_history_end", pd.to_datetime(plans.date), "plan")
    time_equal(a, ledger, "forecast_history_end", pd.to_datetime(ledger.date), "ledger")
    published = archive.set_index(KEYS).reindex(pd.MultiIndex.from_frame(ledger[KEYS]))
    for field in ("load_forecast_kwh", "pv_forecast_kwh"):
        a.equal("published."+field, ledger[field], published[field].to_numpy())
    combinations = [(tau, terminal) for tau in cfg["taus"] for terminal in cfg["terminals"]]
    D, K = len(days), len(combinations)
    Smax = max(len(selected_history(archive, date, cfg["scenario_window"]))/144 for date in days)
    a.check("scenario_max_integral", Smax == int(Smax))
    Smax = int(Smax)
    shapes = dict(plans=(D,K,144,7), risk_delta=(D,K,144), scenario_net=(D,Smax,144),
                  emergency_fee=(D,K,Smax), end_energy=(D,K,Smax), score=(D,K), ordinary=(D,K), selected_index=(D,))
    a.check("evidence_array_keys", set(arrays) == set(shapes))
    for key, shape in shapes.items():
        a.check("evidence_shape."+key, arrays[key].shape == shape, dict(expected=shape, actual=arrays[key].shape))
    if not a.result()["passed"]:
        return dict(**a.result(compact=True), totals=totals)
    p = price.price_yuan_per_kwh.to_numpy()
    runtimes, gaps = [], []
    selected_scores, candidate_counts, scenario_evaluations = [], 0, 0
    for di, (date, rows) in enumerate(ledger.groupby("date", sort=True)):
        tag, meta = date, decisions["days"][di]
        initial = rows.energy_start_actual_kwh.iloc[0]
        a.equal(tag+".initial", meta["initial_energy_kwh"], initial)
        a.check(tag+".candidate_order", [(c["tau"], c["terminal"]) for c in meta["candidates"]] == combinations)
        history = selected_history(archive, date, cfg["scenario_window"])
        source_dates = sorted(history.date.unique())
        S = len(source_dates)
        a.check(tag+".scenario_count", meta["scenario_count"] == S and S >= 7)
        a.check(tag+".scenario_sources", meta["scenario_source_dates"] == source_dates)
        a.check(tag+".whole_source_days", history.groupby("date").slot_id.apply(list).apply(lambda slots: slots == list(range(1,145))))
        a.check(tag+".past_completed_only", (pd.to_datetime(source_dates)+pd.Timedelta(days=1) <= pd.Timestamp(date)))
        net_hat = rows.load_forecast_kwh.to_numpy()-rows.pv_forecast_kwh.to_numpy()
        scenarios = history.net_residual_kwh.to_numpy().reshape(S,144)+net_hat
        a.equal(tag+".scenario_net", arrays["scenario_net"][di,:S], scenarios)
        for key in ("scenario_net", "emergency_fee", "end_energy"):
            padding = arrays[key][di,S:] if key == "scenario_net" else arrays[key][di,:,S:]
            a.check(tag+".padding."+key, np.isnan(padding))
        scores = []
        for ki, (tau, terminal) in enumerate(combinations):
            ctag, candidate = tag+".candidate_"+str(ki), meta["candidates"][ki]
            candidate_counts += 1
            frame = pd.DataFrame(arrays["plans"][di,ki], columns=PLAN)
            delta, risk_history = risk_delta(archive, date, tau)
            a.equal(ctag+".risk_delta", arrays["risk_delta"][di,ki], delta)
            frame["plan_load_kwh"] = np.maximum(rows.load_forecast_kwh.to_numpy()+delta, 0)
            frame["plan_pv_kwh"] = rows.pv_forecast_kwh.to_numpy()+np.maximum(-rows.load_forecast_kwh.to_numpy()-delta, 0)
            physical(a, frame, ctag+".plan", plan=True)
            target = initial if terminal == "equal_initial" else float(terminal)
            a.equal(ctag+".initial", frame.energy_start_plan_kwh.iloc[0], initial)
            a.equal(ctag+".terminal", frame.energy_end_plan_kwh.iloc[-1], target)
            a.equal(ctag+".reported_terminal", candidate["terminal_energy_kwh"], target)
            grid = frame.grid_plan_kwh.to_numpy()
            solver_evidence(a, candidate["solver"], p, grid, ctag+".solver")
            runtimes.append(candidate["solver"]["runtime_seconds"])
            gaps.append(candidate["solver"]["mip_gap"])
            simulated = greedy_from_net(grid, scenarios, initial)
            scenario_evaluations += S
            emergency_fee = np.sum(simulated["emergency_kwh"]*(5*p), axis=1)
            final = simulated["energy_end_actual_kwh"][:,-1]
            ordinary = float(np.dot(p, grid))
            score = ordinary+np.mean(emergency_fee-cfg["mu"]*(final-initial))
            a.equal(ctag+".scenario_emergency_fee", arrays["emergency_fee"][di,ki,:S], emergency_fee, CTOL)
            a.equal(ctag+".scenario_end_energy", arrays["end_energy"][di,ki,:S], final)
            a.equal(ctag+".ordinary", arrays["ordinary"][di,ki], ordinary, CTOL)
            a.equal(ctag+".score", arrays["score"][di,ki], score, CTOL)
            scores.append(score)
        selected = next(i for i, value in enumerate(scores) if value <= min(scores)+1e-8)
        a.check(tag+".argmin", meta["selected_index"] == selected and arrays["selected_index"][di] == selected)
        a.check(tag+".ledger_selection", rows.selected_index.eq(selected))
        a.equal(tag+".selected_plan", rows[PLAN], arrays["plans"][di,selected])
        a.equal(tag+".selected_delta", rows.risk_delta_kwh, arrays["risk_delta"][di,selected])
        a.equal(tag+".risk_load", rows.plan_load_kwh, np.maximum(rows.load_forecast_kwh+rows.risk_delta_kwh, 0))
        a.equal(tag+".risk_pv", rows.plan_pv_kwh, rows.pv_forecast_kwh+np.maximum(-rows.load_forecast_kwh-rows.risk_delta_kwh, 0))
        tau, terminal = combinations[selected]
        a.equal(tag+".selected_tau", rows.selected_tau, tau, 0)
        a.check(tag+".selected_terminal", rows.selected_terminal.astype(str).eq(str(terminal)))
        a.equal(tag+".selected_terminal_energy", rows.selected_terminal_energy_kwh, initial if terminal == "equal_initial" else terminal)
        record = daily.loc[daily.date == date].iloc[0]
        a.equal(tag+".daily_tau", record.selected_tau, tau, 0)
        a.check(tag+".daily_terminal", str(record.selected_terminal) == str(terminal))
        selected_scores.append(scores[selected])
    statistics = dict(solver_count=candidate_counts, solver_runtime_seconds=sum(runtimes),
        solver_max_runtime_seconds=max(runtimes), solver_max_mip_gap=max(gaps), solver_failures=0, solver_fallbacks=0)
    for key, value in statistics.items():
        a.equal("summary."+key, summary[key], value, CTOL)
    return dict(**a.result(compact=True), totals=totals, candidates_verified=candidate_counts,
        scenario_candidate_replays=scenario_evaluations, solver_statistics=statistics,
        artifact_sha256={name: sha(folder/name) for name in required})


def lower_bound_audit(actual, price):
    """Check the saved LP certificate using direct block equations, no optimizer."""
    a = Audit()
    folder = ROOT/"lower_bound"
    required = ("certificate.npz", "status.json", "relaxed_ledger.csv")
    if not a.check("certificate_present", all((folder/name).is_file() for name in required)):
        return a.result()
    status, ledger = js(folder/"status.json"), csv(folder/"relaxed_ledger.csv")
    evidence = dict(np.load(folder/"certificate.npz", allow_pickle=False))
    truth = actual.loc[(actual.date >= "2025-02-01") & (actual.date <= "2025-12-31")]
    net = truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()
    p, n, initial = np.tile(price.price_yuan_per_kwh, 334), len(net), 7268.4231640740745
    keys(a, ledger, "2025-02-01", "2025-12-31", "relaxed_ledger")
    a.check("solver_success", status["success"] and status["status"] == 0)
    a.check("dimensions", status["variables"] == 5*n and status["equality_constraints"] == 2*n)
    for field, expected in (("net", net), ("price", p), ("initial", initial)):
        a.equal("source."+field, evidence[field], expected)
    x, y, zl, zu = (evidence[key] for key in ("primal", "equality_dual", "lower_dual", "upper_dual"))
    a.check("certificate_shapes", x.shape == zl.shape == zu.shape == (5*n,) and y.shape == (2*n,))
    a.check("certificate_finite", np.isfinite(np.r_[x,y,zl,zu]))
    g, c, d, w, e = np.split(x, 5)
    energy_start = np.r_[initial,e[:-1]]
    a.equal("primal.balance", g-c+d-w, net)
    a.equal("primal.soc", e, energy_start+.9*c-d/.9)
    lo = np.r_[np.zeros(4*n),np.full(n,1200.)]
    hi = np.r_[np.full(n,np.inf),np.full(2*n,5000/6),np.full(n,np.inf),np.full(n,10800.)]
    finite = np.isfinite(hi)
    a.check("primal.lower_bounds", x >= lo-ETOL)
    a.check("primal.upper_bounds", x[finite] <= hi[finite]+ETOL)
    for field, expected in zip(("grid_kwh", "charge_kwh", "discharge_kwh", "surplus_kwh", "energy_end_kwh"), (g,c,d,w,e)):
        a.equal("ledger."+field, ledger[field], expected)
    a.equal("ledger.energy_start", ledger.energy_start_kwh, energy_start)
    a.equal("ledger.fee", ledger.ordinary_cost_yuan, p*g, CTOL)
    balance_dual, state_dual = np.split(y, 2)
    aty = np.r_[balance_dual, -balance_dual-.9*state_dual, balance_dual+state_dual/.9,
                -balance_dual, state_dual-np.r_[state_dual[1:],0.]]
    objective = np.r_[p,np.zeros(4*n)]
    a.equal("dual.stationarity", objective-aty-zl-zu, 0, 1e-9)
    a.check("dual.lower_sign", zl >= -1e-9)
    a.check("dual.upper_sign", zu <= 1e-9)
    a.equal("dual.no_infinite_upper_multiplier", zu[~finite], 0, 1e-9)
    a.equal("dual.lower_complementarity", zl*(x-lo), 0, CTOL)
    a.equal("dual.upper_complementarity", zu[finite]*(hi[finite]-x[finite]), 0, CTOL)
    primal = float(p@g)
    dual = float(net@balance_dual+initial*state_dual[0]+lo@zl+hi[finite]@zu[finite])
    a.equal("optimality.primal_dual_gap", primal, dual, CTOL)
    # A separately reconstructed weak-duality bound, clipping only the free grid/surplus row price.
    # This removes tiny sign violations on variables with infinite upper bounds and uses exact box minima.
    by = np.clip(balance_dual, 0, p)
    rc, rd = by+.9*state_dual, -by-state_dual/.9
    re = -state_dual+np.r_[state_dual[1:],0.]
    box_bound = float(net@by+initial*state_dual[0]+(5000/6)*(np.minimum(rc,0).sum()+np.minimum(rd,0).sum())+
                      np.where(re >= 0,1200.,10800.)@re)
    a.check("dual.box_bound_below_primal", box_bound <= primal+CTOL)
    a.equal("optimality.box_gap", primal, box_bound, CTOL)
    for field, expected in dict(primal_cost_yuan=primal, dual_bound_yuan=dual, primal_dual_gap_yuan=primal-dual,
        initial_energy_kwh=initial, final_energy_kwh=e[-1],
        max_balance_residual_kwh=max(abs(g-c+d-w-net).max(),abs(e-energy_start-.9*c+d/.9).max()),
        max_stationarity_residual=abs(objective-aty-zl-zu).max(),lower_dual_min=zl.min(),upper_dual_max=zu.max()).items():
        a.equal("reported."+field, status[field], expected, CTOL)
    return dict(**a.result(), primal_cost_yuan=primal, dual_bound_yuan=dual, independent_box_dual_bound_yuan=box_bound,
        primal_box_gap_yuan=primal-box_bound, artifact_sha256={name: sha(folder/name) for name in required},
        interpretation="Numerical primal/dual certification of an expanded feasible-set lower bound, not executable Q2 or exact EVPI.")


def causality_audit(actual, price, archive, extension=False):
    a = Audit()
    report_path = REPORT/("causality_extension_validation.json" if extension else "causality_validation.json")
    folder = ROOT/("causality_extension_inputs" if extension else "causality_inputs")
    if not a.check("evidence_present", report_path.is_file()):
        return a.result()
    report = js(report_path)
    cutoff = pd.Timestamp("2025-01-25T12:00:00")
    a.check("cutoff", pd.Timestamp(report["mutation_cutoff"]) == cutoff)
    changed = csv(folder/"future_mutated_actual.csv")
    expected = actual.copy()
    later = pd.to_datetime(expected.interval_start) >= cutoff
    expected.loc[later,"load_actual_kwh"] += 800.
    expected.loc[later,"pv_actual_kwh"] *= .5
    for kind in ("load", "pv"):
        expected[kind+"_actual_kw"] = expected[kind+"_actual_kwh"]*6
    a.check("mutated_source.keys", changed[KEYS].equals(actual[KEYS]))
    for field in actual:
        if pd.api.types.is_numeric_dtype(actual[field]):
            a.equal("mutated_source."+field, changed[field], expected[field])
        else:
            a.check("mutated_source."+field, changed[field].eq(expected[field]))
    archives = [csv(folder/name) for name in ("original_forecasts.csv", "future_mutated_forecasts.csv")]
    for name, source, f in zip(("original", "mutated"), (actual, changed), archives):
        keys(a, f, "2025-01-02", "2025-01-26", name+".releases")
        if extension:
            loads = source.load_actual_kwh.to_numpy().reshape(365,144)
            pvs = source.pv_actual_kwh.to_numpy().reshape(365,144)
            lh = np.concatenate([loads[n-7 if n >= 7 else n-1] for n in range(1,365)])
            ph = pvs[:-1].ravel()
        else:
            lh, ph = harmonic_predictions(source)
        lh, ph = lh[:len(f)], ph[:len(f)]
        a.equal(name+".load_prediction", f.load_forecast_kwh, lh)
        a.equal(name+".pv_prediction", f.pv_forecast_kwh, ph)
        truth = source.set_index(KEYS).reindex(pd.MultiIndex.from_frame(f[KEYS]))
        for field in ("load_actual_kwh", "pv_actual_kwh"):
            a.equal(name+".source."+field, f[field], truth[field].to_numpy())
        a.equal(name+".net_residual", f.net_residual_kwh,
                truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()-lh+ph)
        for field, expected_time in (("issue_time",pd.to_datetime(f.date)), ("history_end",pd.to_datetime(f.date)),
                                    ("residual_available_time",pd.to_datetime(f.date)+pd.Timedelta(days=1))):
            time_equal(a,f,field,expected_time,name)
    policies = [c["policy"] for c in js(WORK/"configs/q2_cost_aware_v2"/("extension.json" if extension else "experiments.json"))["runs"]]
    a.check("all_declared_policies", [row["policy"] for row in report["checks"]] == policies)
    replays = {}
    for name in policies:
        for variant, source, f in zip(("original", "mutated"), (actual, changed), archives):
            result = run_audit(ROOT/("causality_"+variant)/name, source, price, f)
            replays[variant+"/"+name] = result
            a.check(name+"."+variant+".independent_replay", result["passed"])
        paths = [ROOT/("causality_"+variant)/name for variant in ("original", "mutated")]
        ledgers, plans = ([csv(path/file) for path in paths] for file in ("ledger.csv", "plans.csv"))
        left, right = ledgers
        earlier = pd.to_datetime(left.interval_start) < cutoff
        numeric = left.select_dtypes(include="number").columns
        prefix = float(abs(left.loc[earlier,numeric].to_numpy()-right.loc[earlier,numeric].to_numpy()).max())
        left_plan, right_plan = plans
        frozen, next_day = left_plan.date <= "2025-01-25", left_plan.date == "2025-01-26"
        numeric_plan = left_plan.select_dtypes(include="number").columns
        plan_error = float(abs(left_plan.loc[frozen,numeric_plan].to_numpy()-right_plan.loc[frozen,numeric_plan].to_numpy()).max())
        response_fields = ["grid_plan_kwh","load_forecast_kwh","pv_forecast_kwh"]
        response = float(abs(left_plan.loc[next_day,response_fields].to_numpy()-right_plan.loc[next_day,response_fields].to_numpy()).max())
        evidence = [dict(np.load(path/"decision_evidence.npz", allow_pickle=False)) for path in paths]
        evidence_identical = set(evidence[0]) == set(evidence[1]) and all(
            np.array_equal(evidence[0][key][:2],evidence[1][key][:2],equal_nan=True) for key in evidence[0])
        a.equal(name+".noninterference.prefix", prefix, 0)
        a.equal(name+".noninterference.frozen_plan", plan_error, 0)
        a.check(name+".noninterference.candidate_evidence", evidence_identical)
        a.check(name+".positive_control", response > 1e-4)
        record = next(row for row in report["checks"] if row["policy"] == name)
        for key, value in dict(prefix_rows=int(earlier.sum()),prefix_difference_kwh=prefix,
            frozen_plan_difference_kwh=plan_error,next_day_response_kwh=response).items():
            a.equal(name+".reported."+key, record[key], value)
        a.check(name+".reported.evidence_identical", record["earlier_candidate_evidence_identical"] == evidence_identical)
        a.check(name+".reported.passed", record["passed"] is True)
    a.check("reported_pass", report["passed"] is True)
    a.check("script_sha256", report["script_sha256"] == sha(WORK/"scripts/q2_cost_aware_v2/causality_checks.py"))
    prefix_path = folder/"scenario_prefix_evidence.npz"
    if a.check("scenario_prefix.evidence_present", prefix_path.is_file()):
        evidence = dict(np.load(prefix_path, allow_pickle=False))
        a.equal("scenario_prefix.initial", evidence["initial"], 6000, 0)
        a.equal("scenario_prefix.cutoff", evidence["cutoff_index"], 72, 0)
        a.equal("scenario_prefix.price", evidence["price"], price.price_yuan_per_kwh)
        january = dict(np.load(ROOT/"january/S_joint/decision_evidence.npz", allow_pickle=False))
        choice = int(january["selected_index"][0])
        a.equal("scenario_prefix.contract_source", evidence["grid"], january["plans"][0,choice,:,0][None,:])
        jan15 = archive.loc[archive.date == "2025-01-15"]
        history = selected_history(archive,"2025-01-15",28)
        scenario = (history.net_residual_kwh.to_numpy().reshape(-1,144)[:3]+
                    jan15.load_forecast_kwh.to_numpy()-jan15.pv_forecast_kwh.to_numpy())
        a.equal("scenario_prefix.net_source", evidence["net_original"], scenario)
        modified = scenario.copy()
        modified[:,72:] += 800.
        a.equal("scenario_prefix.mutation", evidence["net_mutated"], modified)
        mapping = dict(charge="charge_actual_kwh",discharge="discharge_actual_kwh",emergency="emergency_kwh",
                       surplus="surplus_kwh",energy_start="energy_start_actual_kwh",energy_end="energy_end_actual_kwh")
        for variant, net in (("original",scenario),("mutated",modified)):
            expected_trace = greedy_from_net(evidence["grid"][0],net,6000)
            for short, field in mapping.items():
                a.equal("scenario_prefix.trace."+variant+"."+short, evidence[variant+"_"+short], expected_trace[field][None,:,:])
        prefix_error = max(float(abs(evidence["original_"+key][...,:72]-evidence["mutated_"+key][...,:72]).max()) for key in mapping)
        future_response = max(float(abs(evidence["original_"+key][...,72:]-evidence["mutated_"+key][...,72:]).max()) for key in mapping)
        a.equal("scenario_prefix.noninterference", prefix_error, 0)
        a.check("scenario_prefix.positive_response", future_response > 1e-4)
        reported = report["scenario_prefix_check"]
        a.equal("scenario_prefix.reported_prefix",reported["prefix_max_difference_kwh"],prefix_error)
        a.equal("scenario_prefix.reported_response",reported["future_positive_response_kwh"],future_response)
        a.check("scenario_prefix.reported_pass",reported["passed"] is True)
    return dict(**a.result(), replays=replays,
                artifact_sha256={str(path.relative_to(ROOT)):sha(path) for path in folder.iterdir() if path.is_file()})


def analysis_audit(runs, references, price):
    a = Audit()
    required = ["comparison_all.csv","daily_costs_and_differences.csv","monthly_costs_and_differences.csv",
        "monthly.csv","hourly.csv","daily_selections.csv","selection_counts.csv","scenario_score_diagnostics.csv",
        "win_loss_counts.csv","block_bootstrap.csv","ablation.json"]
    if not a.check("analysis_artifacts", all((ROOT/name).is_file() for name in required)):
        return a.result()
    config = js(WORK/"configs/q2_cost_aware_v2/experiments.json")
    extension = js(WORK/"configs/q2_cost_aware_v2/extension.json")
    names = ["B0","B1","P","P_terminal"]+[c["policy"] for c in config["runs"]+extension["runs"]]
    baselines = names[:4]+["P_floor"]
    comparison = csv(ROOT/"comparison_all.csv").set_index("policy")
    daily = csv(ROOT/"daily_costs_and_differences.csv").set_index("date")
    monthly = csv(ROOT/"monthly_costs_and_differences.csv").set_index("month")
    grouping_tables = {key:csv(ROOT/(key+"ly.csv" if key == "month" else "hourly.csv")) for key in ("month","hour")}
    selected = csv(ROOT/"daily_selections.csv")
    scores = csv(ROOT/"scenario_score_diagnostics.csv")
    a.check("analysis.policy_order", comparison.index.tolist() == names)
    a.check("analysis.complete_dates", daily.index.tolist() == [str(d.date()) for d in pd.date_range("2025-02-01","2025-12-31")])
    a.check("analysis.complete_months", monthly.index.tolist() == [f"2025-{m:02d}" for m in range(2,13)])
    totals = {name:(references[name] if name in names[:4] else runs["runs/"+name])["totals"] for name in names}
    bound = js(ROOT/"lower_bound/status.json")["dual_bound_yuan"]
    frames = {}
    for name in names:
        folder = ROOT/("references" if name in names[:4] else "runs")/name
        frame = csv(folder/"ledger.csv")
        frames[name] = frame
        total = totals[name]
        row = comparison.loc[name]
        for field in SUMS+["days","intervals","initial_energy_kwh","final_energy_kwh","inventory_adjusted_cost_yuan",
                           "emergency_intervals","emergency_days","emergency_share_of_load"]:
            a.equal(name+".comparison."+field,row[field],total[field],CTOL)
        derivatives = dict(emergency_fee_share=total["emergency_cost_yuan"]/total["total_cost_yuan"],
            unused_grid_cost_yuan=(frame.price_yuan_per_kwh*frame.unused_grid_kwh).sum(),
            emergency_premium_yuan=(4*frame.price_yuan_per_kwh*frame.emergency_kwh).sum(),
            days_starting_full=int((frame.loc[frame.slot_id==1,"energy_start_actual_kwh"] >= 10800-ETOL).sum()),
            mean_initial_soc_kwh=frame.loc[frame.slot_id==1,"energy_start_actual_kwh"].mean(),
            gap_to_relaxed_bound_yuan=total["total_cost_yuan"]-bound)
        for field,value in derivatives.items():
            a.equal(name+".comparison."+field,row[field],value,CTOL)
        for baseline in baselines:
            saving = totals[baseline]["total_cost_yuan"]-total["total_cost_yuan"]
            for field,value in {"saving_vs_"+baseline+"_yuan":saving,
                "saving_vs_"+baseline+"_percent":100*saving/totals[baseline]["total_cost_yuan"],
                "inventory_adjusted_saving_vs_"+baseline+"_yuan":
                    totals[baseline]["inventory_adjusted_cost_yuan"]-total["inventory_adjusted_cost_yuan"]}.items():
                a.equal(name+".comparison."+field,row[field],value,CTOL)
        actual_daily = frame.groupby("date").total_cost_yuan.sum()
        a.equal(name+".daily_cost",daily[name],actual_daily,CTOL)
        fields = ["planned_cost_yuan","emergency_cost_yuan","total_cost_yuan","emergency_kwh","unused_grid_kwh"]
        for key, labels in (("month",frame.date.str[:7]),("hour",(frame.slot_id-1)//6)):
            table = grouping_tables[key].loc[grouping_tables[key].policy == name].set_index(key)
            expected = frame.groupby(labels)[fields].sum()
            a.check(name+"."+key+".keys",table.index.equals(expected.index))
            a.equal(name+"."+key+".sums",table[fields],expected[fields],CTOL)
        if name in names[:4]:
            continue
        decisions, evidence = js(folder/"decisions.json")["days"], dict(np.load(folder/"decision_evidence.npz",allow_pickle=False))
        s = selected.loc[selected.policy==name].set_index("date")
        diagnostics = scores.loc[scores.policy==name].set_index("date")
        a.check(name+".selection_dates",s.index.tolist() == daily.index.tolist())
        a.check(name+".score_dates",diagnostics.index.tolist() == daily.index.tolist())
        for di, decision in enumerate(decisions):
            date,k,S = decision["date"],decision["selected_index"],decision["scenario_count"]
            candidate = decision["candidates"][k]
            for field,value in dict(tau=candidate["tau"],initial_soc_kwh=decision["initial_energy_kwh"],
                                   scenario_count=S,selected_index=k).items():
                a.equal(name+"."+date+".selection."+field,s.loc[date,field],value)
            a.check(name+"."+date+".terminal",str(s.loc[date,"terminal"]) == str(candidate["terminal"]))
            dayrows = frame.loc[frame.date==date]
            forecast = evidence["emergency_fee"][di,k,:S].mean()
            realized = dayrows.emergency_cost_yuan.sum()
            for field,value in dict(expected_emergency_yuan=forecast,actual_emergency_yuan=realized,
                emergency_prediction_error_yuan=realized-forecast,selected_proxy_score_yuan=evidence["score"][di,k],
                actual_cost_yuan=dayrows.total_cost_yuan.sum()).items():
                a.equal(name+"."+date+".diagnostics."+field,diagnostics.loc[date,field],value,CTOL)
    for target in ("S_joint","P_B1_floor"):
        for baseline in baselines:
            a.equal("daily.saving."+target+"."+baseline,daily[target+"_saving_vs_"+baseline],daily[baseline]-daily[target],CTOL)
    expected_months = daily.groupby(daily.index.str[:7]).sum()
    a.equal("monthly.all",monthly,expected_months,CTOL)
    expected_counts = selected.groupby(["policy","tau","terminal"]).size().rename("days")
    reported_counts = csv(ROOT/"selection_counts.csv").set_index(["policy","tau","terminal"]).days
    a.check("selection_count.keys",expected_counts.index.equals(reported_counts.index))
    a.equal("selection_count.values",reported_counts,expected_counts,0)
    winloss = csv(ROOT/"win_loss_counts.csv").set_index(["policy","baseline"])
    bootstrap = csv(ROOT/"block_bootstrap.csv").set_index(["policy","baseline","block_days"])
    rng = np.random.default_rng(20260911)
    a.check("bootstrap.fixed_settings", config["bootstrap_seed"] == 20260911 and config["bootstrap_replicates"] == 2000 and config["bootstrap_blocks"] == [7,14])
    for target in ("S_joint","P_B1_floor"):
        for baseline in baselines:
            saving = (daily[baseline]-daily[target]).to_numpy()
            for field,value in dict(wins=int((saving>CTOL).sum()),losses=int((saving < -CTOL).sum()),ties=int((abs(saving)<=CTOL).sum()),
                positive_months=int((monthly[baseline]-monthly[target]>CTOL).sum()),
                worst_day_saving_yuan=saving.min(),best_day_saving_yuan=saving.max()).items():
                a.equal("win_loss."+target+"."+baseline+"."+field,winloss.loc[(target,baseline),field],value,CTOL)
            for length in (7,14):
                n = len(saving)
                starts = rng.integers(n,size=(2000,int(np.ceil(n/length))))
                indices = ((starts[:,:,None]+np.arange(length))%n).reshape(2000,-1)[:,:n]
                low,high = np.quantile(saving[indices].sum(axis=1),[.025,.975])
                for field,value in dict(point_saving_yuan=saving.sum(),ci95_low_yuan=low,ci95_high_yuan=high,replicates=2000,seed=20260911).items():
                    a.equal("bootstrap."+target+"."+baseline+"."+str(length)+"."+field,bootstrap.loc[(target,baseline,length),field],value,CTOL)
    ablation = js(ROOT/"ablation.json")
    costs = {name:totals[name]["total_cost_yuan"] for name in ("P","S_tau","S_terminal","S_joint")}
    expected = dict(**costs,tau_selection_saving=costs["P"]-costs["S_tau"],terminal_selection_saving=costs["P"]-costs["S_terminal"],
        joint_saving=costs["P"]-costs["S_joint"],tau_increment_on_terminal=costs["S_terminal"]-costs["S_joint"],
        terminal_increment_on_tau=costs["S_tau"]-costs["S_joint"],interaction_extra_saving=costs["S_tau"]+costs["S_terminal"]-costs["P"]-costs["S_joint"])
    for field,value in expected.items():
        a.equal("ablation."+field,ablation[field],value,CTOL)
    return dict(**a.result(compact=True),artifact_sha256={name:sha(ROOT/name) for name in required},
                representative=representative_audit(frames),stress=stress_audit(frames,price))


def representative_audit(frames, names=("P","P_terminal","S_joint","P_B1_floor"), base=None):
    a = Audit()
    dates = ["2025-03-20","2025-06-21","2025-09-23","2025-12-21"]
    for name in names:
        folder = (ROOT/"representative" if base is None else base)/name
        required = ["four_days_ledger.csv","table1_intervals.csv","table1_daily.csv","terminal.csv","table2_charge_discharge.csv","table3_emergency.csv"]
        if not a.check(name+".files",all((folder/f).is_file() for f in required)):
            continue
        source = frames[name].loc[frames[name].date.isin(dates)]
        r = csv(folder/"four_days_ledger.csv")
        a.check(name+".four_day_keys",r[KEYS].reset_index(drop=True).equals(source[KEYS].reset_index(drop=True)))
        fields = source.select_dtypes(include="number").columns
        a.equal(name+".four_day_values",r[fields],source[fields].to_numpy())
        table = csv(folder/"table1_intervals.csv")
        expected = source.loc[source.slot_id.isin([61,73,85,97,109,121])]
        a.check(name+".six_time_keys",table[["date","interval_start","interval_end"]].reset_index(drop=True).equals(expected[["date","interval_start","interval_end"]].reset_index(drop=True)))
        a.equal(name+".six_time_values",table[["grid_plan_kwh","planned_cost_yuan"]],expected[["grid_plan_kwh","planned_cost_yuan"]].to_numpy(),CTOL)
        table = csv(folder/"table1_daily.csv").set_index("date")
        a.check(name+".daily_dates",table.index.tolist()==dates)
        a.equal(name+".daily_values",table,source.groupby("date")[table.columns].sum(),CTOL)
        table = csv(folder/"terminal.csv").set_index("date")
        a.check(name+".terminal_dates",table.index.tolist()==dates)
        a.equal(name+".initial",table.initial_energy_kwh,source.groupby("date").energy_start_actual_kwh.first())
        a.equal(name+".final",table.final_energy_kwh,source.groupby("date").energy_end_actual_kwh.last())
        table = csv(folder/"table2_charge_discharge.csv").set_index(["date","block_start_hour"])
        expected = source.assign(block_start_hour=((source.slot_id-1)//24)*4).groupby(["date","block_start_hour"])[["charge_actual_kwh","discharge_actual_kwh"]].sum()
        a.check(name+".blocks",table.index.equals(expected.index))
        a.equal(name+".block_values",table,expected)
        table = csv(folder/"table3_emergency.csv")
        expected = source.loc[source.emergency_kwh>ETOL]
        a.check(name+".emergency_keys",table[["date","interval_start","interval_end"]].reset_index(drop=True).equals(expected[["date","interval_start","interval_end"]].reset_index(drop=True)))
        a.equal(name+".emergency_values",table[["emergency_kwh","emergency_cost_yuan"]],expected[["emergency_kwh","emergency_cost_yuan"]].to_numpy(),CTOL)
    return a.result()


def stress_audit(frames, price):
    a = Audit()
    folder = ROOT/"stress"
    if not a.check("artifacts",all((folder/f).is_file() for f in ("summary.csv","ledger.csv","scope.json"))):
        return a.result()
    ledger, summary = csv(folder/"ledger.csv"),csv(folder/"summary.csv")
    archive = csv(ROOT/"forecasts/linear_harmonic.csv")
    keys = ["date","stress_quantile","policy"]
    expected_keys = {(f"2025-{month:02d}-01",tau,name) for month in range(2,13) for tau in (.9,.95) for name in ("B1","P","P_terminal","S_joint","P_B1_floor")}
    a.check("groups",set(ledger[keys].itertuples(index=False,name=None)) == expected_keys)
    a.check("summary_groups",set(summary[keys].itertuples(index=False,name=None)) == expected_keys)
    a.check("summary_unique",~summary.duplicated(keys))
    p = price.price_yuan_per_kwh.to_numpy()
    for (date,tau,name), rows in ledger.groupby(keys,sort=True):
        tag = date+"."+str(tau)+"."+name
        a.check(tag+".slots",rows.slot_id.tolist()==list(range(1,145)))
        history = selected_history(archive,date,56)
        ranked = history.groupby("date").net_residual_kwh.sum().sort_values(kind="stable")
        source_date = ranked.index[int(np.ceil(tau*len(ranked)))-1]
        f = archive.loc[archive.date==date]
        scenario = f.load_forecast_kwh.to_numpy()-f.pv_forecast_kwh.to_numpy()+history.loc[history.date==source_date,"net_residual_kwh"].to_numpy()
        current = frames[name].loc[frames[name].date==date]
        q,initial = current.grid_plan_kwh.to_numpy(),current.energy_start_actual_kwh.iloc[0]
        a.check(tag+".source",rows.source_date.eq(source_date))
        a.equal(tag+".net",rows.scenario_net_kwh,scenario)
        a.equal(tag+".q",rows.grid_plan_kwh,q)
        a.equal(tag+".price",rows.price_yuan_per_kwh,p)
        trace = greedy_from_net(q,scenario,initial)
        mapping = dict(charge="charge_actual_kwh",discharge="discharge_actual_kwh",emergency="emergency_kwh",
                       surplus="surplus_kwh",energy_start="energy_start_actual_kwh",energy_end="energy_end_actual_kwh")
        for short,field in mapping.items():
            a.equal(tag+".trace."+short,rows[short],trace[field][0])
        record = summary.loc[(summary.date==date)&(summary.stress_quantile==tau)&(summary.policy==name)].iloc[0]
        emergency_fee = float(np.sum(5*p*trace["emergency_kwh"][0]))
        a.check(tag+".summary_source",record.source_date==source_date and pd.Timestamp(record.source_available_time)==pd.Timestamp(source_date)+pd.Timedelta(days=1))
        for field,value in dict(initial_energy_kwh=initial,final_energy_kwh=trace["energy_end_actual_kwh"][0,-1],
                               emergency_cost_yuan=emergency_fee,total_cost_yuan=float(p@q)+emergency_fee).items():
            a.equal(tag+".summary."+field,record[field],value,CTOL)
    return a.result(compact=True)


def followup_audit():
    a = Audit()
    folder = ROOT/"followup_diagnostics"
    primary_path = REPORT/"independent_validation.json"
    primary = js(primary_path)
    snapshot = js(REPORT/"independent_primary_validator_snapshot.json")
    a.check("primary_passed",primary["passed"] is True)
    a.check("primary_validator_exact_source",hashlib.sha256(snapshot["source"].encode()).hexdigest()==snapshot["sha256"]==primary["validator_sha256"])
    required = ["win_loss.csv","block_bootstrap.csv","scope.json"]
    if not a.check("followup_artifacts",all((folder/name).is_file() for name in required)):
        return a.result()
    baselines = ["B0","B1","P","P_terminal","P_floor"]
    frames,costs = {},{}
    for name in baselines+["S_terminal"]:
        source = ROOT/("references" if name in baselines[:4] else "runs")/name/"ledger.csv"
        audited = primary["references"][name] if name in baselines[:4] else primary["runs"]["runs/"+name]
        a.check("unchanged_audited_ledger."+name,sha(source)==audited["artifact_sha256"]["ledger.csv"])
        frames[name]=csv(source)
        costs[name]=frames[name].groupby("date").total_cost_yuan.sum()
    costs=pd.DataFrame(costs)
    a.check("complete_dates",costs.index.tolist()==[str(day.date()) for day in pd.date_range("2025-02-01","2025-12-31")])
    monthly=costs.groupby(costs.index.str[:7]).sum()
    stats=csv(folder/"win_loss.csv").set_index(["policy","baseline"])
    bootstrap=csv(folder/"block_bootstrap.csv").set_index(["policy","baseline","block_days"])
    pairs=[(target,baseline) for target in ("P_floor","S_terminal") for baseline in baselines if target!=baseline]
    a.check("pairs",stats.index.tolist()==pairs)
    a.check("bootstrap_pairs",bootstrap.index.tolist()==[(target,baseline,block) for target,baseline in pairs for block in (7,14)])
    rng=np.random.default_rng(20260912)
    for target,baseline in pairs:
        saving=(costs[baseline]-costs[target]).to_numpy()
        tag=target+"."+baseline
        for field,value in dict(saving_yuan=saving.sum(),winning_days=int((saving>CTOL).sum()),losing_days=int((saving < -CTOL).sum()),
            tied_days=int((abs(saving)<=CTOL).sum()),positive_months=int((monthly[baseline]-monthly[target]>CTOL).sum()),
            worst_day_saving_yuan=saving.min(),best_day_saving_yuan=saving.max()).items():
            a.equal(tag+".stats."+field,stats.loc[(target,baseline),field],value,CTOL)
        for block in (7,14):
            n=len(saving)
            starts=rng.integers(n,size=(2000,int(np.ceil(n/block))))
            indices=((starts[:,:,None]+np.arange(block))%n).reshape(2000,-1)[:,:n]
            low,high=np.quantile(saving[indices].sum(axis=1),[.025,.975])
            for field,value in dict(saving_yuan=saving.sum(),ci95_low_yuan=low,ci95_high_yuan=high,seed=20260912,replicates=2000).items():
                a.equal(tag+".bootstrap."+str(block)+"."+field,bootstrap.loc[(target,baseline,block),field],value,CTOL)
    representative=representative_audit(frames,names=("P_floor","S_terminal"),base=folder/"representative")
    a.check("representative_passed",representative["passed"])
    return dict(**a.result(),representative=representative,primary_report_sha256=sha(primary_path),
        artifact_sha256={str(path.relative_to(ROOT)):sha(path) for path in folder.rglob("*") if path.is_file()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("january", "runs", "all", "sources", "lower_bound", "causality", "references", "followup"), default="all")
    parser.add_argument("--extension",action="store_true",help="Audit the two explicitly post-primary-result follow-up paths separately.")
    args = parser.parse_args()
    if args.scope == "followup":
        result = dict(created_utc=datetime.now(timezone.utc).isoformat(),scope="incremental_followup",**followup_audit(),validator_sha256=sha(Path(__file__)))
        target=REPORT/"independent_validation_followup.json"
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
        print(json.dumps(dict(passed=result["passed"],output=str(target)),ensure_ascii=False))
        return 0 if result["passed"] else 1
    actual, price, archive, sources = source_audit()
    runs, references, completeness = {}, {}, Audit()
    extension_file = WORK/"configs/q2_cost_aware_v2/extension.json"
    extension_names = [c["policy"] for c in js(extension_file)["runs"]] if extension_file.is_file() else []
    for stage in (("january", "runs") if args.scope == "all" else (args.scope,)):
        if stage in ("sources", "lower_bound", "causality", "references"):
            continue
        expected = ["S_tau", "S_terminal", "S_joint", "P_floor"] if stage == "january" else [
            c["policy"] for c in js(WORK/"configs/q2_cost_aware_v2/experiments.json")["runs"]]
        allowed = set(expected+extension_names)
        if args.extension:
            expected = extension_names
        elif args.scope == "all":
            expected += extension_names
        found = {f.name for f in (ROOT/stage).glob("*") if f.is_dir()}
        completeness.check(stage+".path_set",set(expected)<=found<=allowed)
        for name in expected:
            key = stage+"/"+name
            try:
                selected_archive = csv(ROOT/"forecasts/seasonal.csv") if name in extension_names else archive
                runs[key] = run_audit(ROOT/stage/name, actual, price, selected_archive)
            except Exception as exc:
                runs[key] = dict(passed=False, audit_exception=type(exc).__name__+": "+str(exc))
            print(key, "PASS" if runs[key]["passed"] else "FAIL", flush=True)
    if args.scope in ("runs", "all", "references"):
        for name in ("B0", "B1", "P", "P_terminal"):
            try:
                references[name] = reference_audit(ROOT/"references"/name, actual, price, archive)
            except Exception as exc:
                references[name] = dict(passed=False, audit_exception=type(exc).__name__+": "+str(exc))
            print("reference/"+name, "PASS" if references[name]["passed"] else "FAIL", flush=True)
    lower_bound = lower_bound_audit(actual, price) if args.scope in ("all", "lower_bound") else dict(passed=None, status="outside_partial_scope")
    causality = causality_audit(actual, price, archive,extension=args.extension) if args.scope in ("all", "causality") else dict(passed=None,status="outside_partial_scope")
    extension_causality = causality_audit(actual, price, archive,extension=True) if args.scope == "all" else dict(passed=None,status="outside_partial_scope")
    passed = sources["passed"] and completeness.result()["passed"] and all(r["passed"] for r in [*runs.values(), *references.values()]) and lower_bound["passed"] is not False and causality["passed"] is not False and extension_causality["passed"] is not False
    analysis = analysis_audit(runs,references,price) if args.scope == "all" and passed else dict(passed=None,status="outside_full_scope_or_prior_gate_failed")
    if args.scope == "all":
        passed = passed and analysis["passed"] is True and analysis["representative"]["passed"] and analysis["stress"]["passed"]
    result = dict(created_utc=datetime.now(timezone.utc).isoformat(), passed=passed, scope=args.scope,extension=args.extension,
        independence="Only standard library, numpy and pandas; no imports from producer predictor/planner/scorer/executor.",
        tolerances=dict(physical_kwh=ETOL, cost_yuan=CTOL), sources=sources, completeness=completeness.result(),
        runs=runs, references=references, lower_bound=lower_bound, causality=causality,extension_causality=extension_causality,analysis=analysis,validator_sha256=sha(Path(__file__)),
        limitations=["Processed source was independently audited; raw XLSX cleaning was not repeated.",
                     "Solver evidence is checked against independently reconstructed feasible candidates, without rerunning all MILPs.",
                     "Historical replay is not a prospective held-out validation; interval balancing uses the inherited within-slot response assumption."])
    target = REPORT/("independent_validation.json" if args.scope == "all" else "independent_validation_"+args.scope+("_extension" if args.extension else "")+".json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps(dict(passed=passed, paths=len(runs), output=str(target)), ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
