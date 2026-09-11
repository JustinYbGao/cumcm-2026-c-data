"""Independent Q2 v3 equation audit. No production predictor/planner/scorer/executor imports.

Shared direct physics equations were copied from the prior independent audit;
v3 calibration, fractional-tail CVaR, masks and selection are reconstructed here.
"""
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
ROOT = WORK / "results/q2_pareto_v3"
REPORT = WORK / "reports/q2_pareto_v3"
CONFIG = WORK / "configs/q2_pareto_v3/experiments.json"
VALIDATOR_SOURCE = Path(__file__).read_bytes()
VALIDATOR_SHA256 = hashlib.sha256(VALIDATOR_SOURCE).hexdigest()
ETOL, CTOL = 1e-6, 1e-5
KEYS = ["date", "slot_id"]
_ARCHIVE_CACHE = {}
PLAN = ["grid_plan_kwh", "charge_plan_kwh", "discharge_plan_kwh",
        "energy_start_plan_kwh", "energy_end_plan_kwh", "pv_curtailment_plan_kwh", "charge_mode_plan"]
SUMS = ["grid_plan_kwh", "emergency_kwh", "planned_cost_yuan", "emergency_cost_yuan",
        "total_cost_yuan", "charge_actual_kwh", "discharge_actual_kwh", "surplus_kwh",
        "unused_grid_kwh", "pv_curtailment_kwh"]
PROFILES = ["anchor", "day_trim", "evening_hedge", "rebalance", "soft", "strong", "morning_hedge"]
REFERENCES = ["B0", "B1", "P", "P_terminal", "P_floor", "S_terminal"]
JANUARY = ["T_rebalance", "R_guard", "R_mean", "R_cost", "R_w28"]

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


def selected_history(archive, date, days):
    day = pd.Timestamp(date)
    identity = id(archive)
    if identity not in _ARCHIVE_CACHE:
        _ARCHIVE_CACHE[identity] = dict(source=archive,dates=archive.date.to_numpy(dtype="U10"),
            available=pd.to_datetime(archive.residual_available_time).to_numpy(),deltas={})
    cached = _ARCHIVE_CACHE[identity]
    return archive.loc[(cached["dates"] >= str((day-pd.Timedelta(days=days)).date())) &
                       (cached["dates"] < date) & (cached["available"] <= day.to_datetime64())]


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


def expected_profiles():
    result = {name: [.8]*24 for name in PROFILES}
    for name, low, high in (("day_trim",.7,None),("evening_hedge",None,.9),
            ("rebalance",.7,.9),("soft",.75,.85),("strong",.65,.95),("morning_hedge",.7,.9)):
        if low is not None:
            result[name][11:18] = [low]*7
        if high is not None:
            result[name][18:22] = [high]*4
    result["morning_hedge"][9:11] = [.85]*2
    return result


def source_audit():
    a = Audit()
    sources = {"actual_10min.csv":"data/processed/actual_10min.csv", "fixed_price.csv":"data/processed/fixed_price.csv",
        "model_baseline.json":"configs/model_baseline.json", "q2_baseline.json":"configs/q2_baseline.json",
        "original_run_q2.py":"scripts/run_q2.py", "original_solve_q1.py":"scripts/solve_q1.py",
        "problem_text.txt":"data/interim/problem_text.txt", "selection.json":"results/q2/selection.json",
        "bzd_quantile_record.json":"reports/emergency_research_v1/bzd_quantile_record.json"}
    for name, path in sources.items():
        a.check("input_copy."+name, sha(ROOT/"inputs"/name) == sha(WORK/path))
    for name, old in (("B0","selected"),("B1","seasonal"),("no_storage","no_storage")):
        a.check("baseline_input_copy."+name, sha(ROOT/"inputs"/("baseline_"+name+".csv")) == sha(WORK/"results/q2"/old/"ledger.csv"))
    reference_hashes = {}
    for name in REFERENCES:
        old = WORK/("results/emergency_improvement_v1/runs" if name in REFERENCES[:4] else "results/q2_cost_aware_v2/runs")/name
        copied = ROOT/"references"/name
        a.check("reference_file_set."+name, {p.name for p in old.iterdir() if p.is_file()} == {p.name for p in copied.iterdir() if p.is_file()})
        reference_hashes[name] = {}
        for path in copied.iterdir():
            if path.is_file():
                digest = sha(path)
                a.check("reference_copy."+name+"."+path.name, digest == sha(old/path.name))
                reference_hashes[name][path.name] = digest
    freeze = js(REPORT/"protocol_freeze.json")
    a.check("protocol_frozen", sha(REPORT/"protocol.md") == freeze["protocol_sha256"])
    a.check("config_frozen", sha(CONFIG) == freeze["config_sha256"])
    cfg = js(CONFIG)
    a.check("main_policy",cfg["primary"] == "R_guard")
    a.check("profiles_exact",cfg["profiles"] == expected_profiles())
    names = ["T_"+name for name in PROFILES[1:]]+["R_guard","R_mean","R_cost","R_w28"]
    a.check("all_ten_runs_frozen",[c["policy"] for c in cfg["runs"]] == names)
    for row in cfg["runs"]:
        name = row["policy"]
        expected = dict(start="2025-02-01",end="2025-12-31",initial_energy_kwh=7268.4231640740745,
            risk_window=28,scenario_window=28 if name == "R_w28" else 56,mu=.38232,terminal_energy_kwh=1200.,
            cvar_alpha=.9,policy=name,profiles=[name[2:]] if name.startswith("T_") else PROFILES,
            guard="tail" if name in ("R_guard","R_w28") else ("mean" if name == "R_mean" else "none"))
        a.check("run_config."+name,row == expected)
    for name, value in dict(emergency_cap_yuan=661273.6528153808,ordinary_cap_yuan=13361564.945683166,
        total_cap_yuan=14022838.598498546,secondary_emergency_cap_yuan=641845.2793936513,
        bootstrap_seed=20260913,bootstrap_replicates=2000).items():
        a.equal("protocol."+name,cfg[name],value,0)
    a.check("bootstrap_blocks",cfg["bootstrap_blocks"] == [7,14])
    protected = js(REPORT/"protected_hashes_before.json")
    changed = [name for name, digest in protected.items() if not (WORK/name).is_file() or sha(WORK/name) != digest]
    a.check("protected_files_unchanged",not changed,dict(count=len(protected),changed=changed))
    actual, price = csv(ROOT/"inputs/actual_10min.csv"), csv(ROOT/"inputs/fixed_price.csv")
    keys(a,actual,"2025-01-01","2025-12-31","actual")
    a.check("price.slots",price.slot_id.tolist() == list(range(1,145)))
    a.equal("price.start_minutes",price.start_minute,np.arange(144)*10)
    a.equal("price.end_minutes",price.end_minute,np.arange(1,145)*10)
    for kind in ("load","pv"):
        a.equal("actual.units."+kind,actual[kind+"_actual_kwh"],actual[kind+"_actual_kw"]/6)
    a.check("actual.nonnegative_finite",np.isfinite(actual[["load_actual_kwh","pv_actual_kwh"]]) & (actual[["load_actual_kwh","pv_actual_kwh"]] >= 0))
    a.check("price.positive_finite",np.isfinite(price.price_yuan_per_kwh) & (price.price_yuan_per_kwh > 0))
    t = pd.to_datetime(actual.date)+pd.to_timedelta((actual.slot_id-1)*10,unit="min")
    for field, expected in (("interval_start",t),("interval_end",t+pd.Timedelta(minutes=10)),("available_time",t+pd.Timedelta(minutes=10))):
        time_equal(a,actual,field,expected,"actual")
    archive = csv(ROOT/"forecasts/linear_harmonic.csv")
    forecast_audit(a,actual,archive,"2025-12-31","archive")
    seasonal = csv(ROOT/"forecasts/seasonal.csv")
    keys(a,seasonal,"2025-01-02","2025-12-31","seasonal")
    loads,pvs = (actual[field].to_numpy().reshape(365,144) for field in ("load_actual_kwh","pv_actual_kwh"))
    a.equal("seasonal.load",seasonal.load_forecast_kwh,np.concatenate([loads[n-7 if n>=7 else n-1] for n in range(1,365)]))
    a.equal("seasonal.pv",seasonal.pv_forecast_kwh,pvs[:-1].ravel())
    return actual,price,archive,dict(**a.result(),reference_sha256=reference_hashes)


def forecast_audit(a,actual,archive,end,tag):
    keys(a,archive,"2025-01-02",end,tag)
    days = pd.to_datetime(archive.date)
    for field,expected in (("issue_time",days),("history_end",days),("residual_available_time",days+pd.Timedelta(days=1))):
        time_equal(a,archive,field,expected,tag)
    truth = actual.set_index(KEYS).reindex(pd.MultiIndex.from_frame(archive[KEYS]))
    for field in ("load_actual_kwh","pv_actual_kwh"):
        a.equal(tag+".source."+field,archive[field],truth[field].to_numpy())
    load,pv = harmonic_predictions(actual)
    load,pv = load[:len(archive)],pv[:len(archive)]
    a.equal(tag+".causal_load",archive.load_forecast_kwh,load)
    a.equal(tag+".causal_pv",archive.pv_forecast_kwh,pv)
    a.equal(tag+".residual",archive.net_residual_kwh,truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()-load+pv)


def hourly_delta(archive,date,profile):
    history = selected_history(archive,date,28)
    if history.date.nunique() < 7:
        raise ValueError("Fewer than seven completed risk days")
    values = history.net_residual_kwh.to_numpy()
    hours = (history.slot_id.to_numpy()-1)//6
    answer = []
    for hour,tau in enumerate(profile):
        pool = np.sort(values[hours == hour])
        position = (len(pool)-1)*tau
        low, high = int(np.floor(position)),int(np.ceil(position))
        answer.extend([pool[low]+(position-low)*(pool[high]-pool[low])]*6)
    return np.asarray(answer)


def fractional_tail_cvar(losses,alpha):
    """Mean of the worst n(1-alpha) equally weighted observations, fractional boundary included."""
    descending = np.sort(np.asarray(losses,dtype=float))[::-1]
    mass = len(descending)*(1-alpha)
    weight = np.clip(mass-np.arange(len(descending)),0,1)
    return float(descending@weight/mass)


def feasible_candidates(ordinary,fees,ends,tails,guard):
    if guard == "none":
        return np.ones(len(ordinary),dtype=bool)
    means = fees.mean(axis=1)
    stocks = ends.mean(axis=1)
    allowed = (ordinary-ordinary[0] <= 1e-7) & (means-means[0] <= 1e-7) & (stocks-stocks[0] >= -1e-6)
    if guard == "tail":
        allowed &= tails-tails[0] <= 1e-7
    return allowed


def first_feasible_minimum(scores,allowed):
    candidates = np.flatnonzero(allowed)
    best = min(scores[candidates])
    return int(next(i for i in candidates if scores[i] <= best+1e-8))


def mathematical_self_tests():
    a = Audit()
    a.equal("fractional_tail",fractional_tail_cvar([0,10,20],.5),50/3,1e-12)
    a.equal("integer_tail",fractional_tail_cvar([0,1,2,3,4],.6),3.5,1e-12)
    a.equal("tied_boundary",fractional_tail_cvar([0,4,4,9],.5),6.5,1e-12)
    a.equal("single_tail",fractional_tail_cvar([1,2,9],.9),9,1e-12)
    ordinary = np.array([10.,9.,9.,9.,9.])
    fees = np.array([[1.,3.],[1.,4.],[0.,4.],[0.,2.],[1.,2.]])
    ends = np.array([[5.,5.],[6.,6.],[6.,6.],[4.,4.],[6.,6.]])
    tails = np.array([3.,4.,4.,2.,2.])
    a.check("mean_constraint_roles",np.array_equal(feasible_candidates(ordinary,fees,ends,tails,"mean"),[True,False,True,False,True]))
    a.check("tail_constraint_roles",np.array_equal(feasible_candidates(ordinary,fees,ends,tails,"tail"),[True,False,False,False,True]))
    a.equal("first_feasible_tie",first_feasible_minimum(np.array([3.,1.+5e-9,1.,0.]),np.array([1,1,1,0],dtype=bool)),1,0)
    records = []
    for day in range(1,8):
        for slot in range(1,145):
            hour,within = divmod(slot-1,6)
            records.append(dict(date=f"2025-01-{day:02d}",slot_id=slot,
                residual_available_time=f"2025-01-{day+1:02d}",net_residual_kwh=100*hour+6*(day-1)+within))
    synthetic = pd.DataFrame(records)
    profile = expected_profiles()["morning_hedge"]
    a.equal("hourly_linear_interpolation",hourly_delta(synthetic,"2025-01-08",profile),
        np.repeat(100*np.arange(24)+41*np.asarray(profile),6),1e-12)
    try:
        hourly_delta(synthetic,"2025-01-07",profile)
        rejected = False
    except ValueError:
        rejected = True
    a.check("short_risk_history_rejected",rejected)
    return a.result()


def run_audit(folder,actual,price,archive):
    a = Audit()
    required = ["config.json","ledger.csv","plans.csv","daily.csv","summary.json","decisions.json","decision_evidence.npz"]
    if not a.check("artifacts_present",all((folder/name).is_file() for name in required)):
        return a.result()
    cfg,summary,decisions = (js(folder/name) for name in ("config.json","summary.json","decisions.json"))
    ledger,plans,daily = (csv(folder/name) for name in ("ledger.csv","plans.csv","daily.csv"))
    arrays = dict(np.load(folder/"decision_evidence.npz",allow_pickle=False))
    declared_file = WORK/"configs/q2_pareto_v3/extension.json" if cfg["policy"].startswith("X_") else CONFIG
    frozen = next(c for c in js(declared_file)["runs"] if c["policy"] == cfg["policy"])
    if folder.parent.name.endswith("january"):
        frozen = dict(frozen,start="2025-01-15",end="2025-01-18",initial_energy_kwh=6000.)
    elif "causality_" in folder.parent.name:
        frozen = dict(frozen,start="2025-01-24",end="2025-01-26",initial_energy_kwh=6000.)
    a.check("config_frozen",cfg == frozen)
    totals = ledger_audit(a,ledger,daily,summary,actual,price,cfg)
    keys(a,plans,cfg["start"],cfg["end"],"plans")
    fields = PLAN+["load_forecast_kwh","pv_forecast_kwh","plan_load_kwh","plan_pv_kwh","risk_delta_kwh",
                  "selected_index","selected_tau","selected_terminal_energy_kwh"]
    for field in fields:
        a.equal("frozen."+field,ledger[field],plans[field])
    for field in ("selected_terminal","selected_profile"):
        a.check("frozen."+field,ledger[field].eq(plans[field]))
    for frame,tag in ((plans,"plans"),(ledger,"ledger")):
        for field in ("issue_time","forecast_history_end"):
            time_equal(a,frame,field,pd.to_datetime(frame.date),tag)
    published = archive.set_index(KEYS).reindex(pd.MultiIndex.from_frame(ledger[KEYS]))
    for field in ("load_forecast_kwh","pv_forecast_kwh"):
        a.equal("published."+field,ledger[field],published[field].to_numpy())
    days = sorted(ledger.date.unique())
    a.check("decision_dates",[m["date"] for m in decisions["days"]] == days)
    a.check("plan_columns",decisions["plan_columns"] == PLAN)
    D,K = len(days),len(cfg["profiles"])
    Smax = max(len(selected_history(archive,date,cfg["scenario_window"]))//144 for date in days)
    shapes = dict(plans=(D,K,144,7),risk_delta=(D,K,144),scenario_net=(D,Smax,144),
        emergency_fee=(D,K,Smax),end_energy=(D,K,Smax),score=(D,K),ordinary=(D,K),cvar=(D,K),feasible=(D,K),selected_index=(D,))
    a.check("array_keys",set(arrays) == set(shapes))
    for key,shape in shapes.items():
        a.check("shape."+key,arrays[key].shape == shape)
    if not a.result()["passed"]:
        return dict(**a.result(compact=True),totals=totals)
    p = price.price_yuan_per_kwh.to_numpy()
    profiles = extension_profiles() if cfg["policy"].startswith("X_") else expected_profiles()
    runtimes,gaps = [],[]
    candidate_count,scenario_count = 0,0
    for di,(date,rows) in enumerate(ledger.groupby("date",sort=True)):
        meta = decisions["days"][di]
        initial = float(rows.energy_start_actual_kwh.iloc[0])
        a.equal(date+".initial",meta["initial_energy_kwh"],initial)
        a.check(date+".order",[c["profile"] for c in meta["candidates"]] == cfg["profiles"])
        history = selected_history(archive,date,cfg["scenario_window"])
        source_dates = sorted(history.date.unique())
        S = len(source_dates)
        a.check(date+".scenario_count",meta["scenario_count"] == S and S >= 7)
        a.check(date+".sources",meta["scenario_source_dates"] == source_dates)
        a.check(date+".whole_days",history.groupby("date").slot_id.apply(list).apply(lambda v:v == list(range(1,145))))
        a.check(date+".availability",pd.to_datetime(source_dates)+pd.Timedelta(days=1) <= pd.Timestamp(date))
        net_hat = rows.load_forecast_kwh.to_numpy()-rows.pv_forecast_kwh.to_numpy()
        scenarios = history.net_residual_kwh.to_numpy().reshape(S,144)+net_hat
        a.equal(date+".scenarios",arrays["scenario_net"][di,:S],scenarios)
        for key in ("scenario_net","emergency_fee","end_energy"):
            padding = arrays[key][di,S:] if key == "scenario_net" else arrays[key][di,:,S:]
            a.check(date+".padding."+key,np.isnan(padding))
        scores,ordinary_all,fee_all,end_all,tails = [],[],[],[],[]
        for ki,name in enumerate(cfg["profiles"]):
            tag,candidate = date+"."+name,meta["candidates"][ki]
            delta = hourly_delta(archive,date,profiles[name])
            a.equal(tag+".tau_hours",candidate["tau_hours"],profiles[name],0)
            a.equal(tag+".risk_delta",arrays["risk_delta"][di,ki],delta)
            plan = pd.DataFrame(arrays["plans"][di,ki],columns=PLAN)
            plan["plan_load_kwh"] = np.maximum(rows.load_forecast_kwh.to_numpy()+delta,0)
            plan["plan_pv_kwh"] = rows.pv_forecast_kwh.to_numpy()+np.maximum(-rows.load_forecast_kwh.to_numpy()-delta,0)
            physical(a,plan,tag+".plan",plan=True)
            a.equal(tag+".initial",plan.energy_start_plan_kwh.iloc[0],initial)
            a.equal(tag+".terminal",plan.energy_end_plan_kwh.iloc[-1],1200.)
            a.equal(tag+".reported_terminal",[candidate["terminal"],candidate["terminal_energy_kwh"]],1200.)
            grid = plan.grid_plan_kwh.to_numpy()
            solver_evidence(a,candidate["solver"],p,grid,tag+".solver")
            runtimes.append(candidate["solver"]["runtime_seconds"])
            gaps.append(candidate["solver"]["mip_gap"])
            trace = greedy_from_net(grid,scenarios,initial)
            fees = np.sum(trace["emergency_kwh"]*(5*p),axis=1)
            ends = trace["energy_end_actual_kwh"][:,-1]
            ordinary = float(p@grid)
            score = ordinary+fees.mean()-cfg["mu"]*(ends.mean()-initial)
            tail = fractional_tail_cvar(fees,cfg["cvar_alpha"])
            for key,expected,tolerance in (("emergency_fee",fees,CTOL),("end_energy",ends,ETOL)):
                a.equal(tag+"."+key,arrays[key][di,ki,:S],expected,tolerance)
            for key,expected in (("ordinary",ordinary),("score",score),("cvar",tail)):
                a.equal(tag+"."+key,arrays[key][di,ki],expected,CTOL)
            scores.append(score);ordinary_all.append(ordinary);fee_all.append(fees);end_all.append(ends);tails.append(tail)
            candidate_count += 1;scenario_count += S
        scores,ordinary_all,fee_all,end_all,tails = map(np.asarray,(scores,ordinary_all,fee_all,end_all,tails))
        feasible = feasible_candidates(ordinary_all,fee_all,end_all,tails,cfg["guard"])
        a.check(date+".feasible_mask",np.array_equal(arrays["feasible"][di],feasible))
        a.check(date+".anchor_feasible",feasible[0])
        selected = first_feasible_minimum(scores,feasible)
        a.check(date+".selection",meta["selected_index"] == selected and arrays["selected_index"][di] == selected)
        a.check(date+".ledger_selection",rows.selected_index.eq(selected))
        a.check(date+".profile",rows.selected_profile.eq(cfg["profiles"][selected]))
        a.equal(date+".selected_plan",rows[PLAN],arrays["plans"][di,selected])
        a.equal(date+".selected_delta",rows.risk_delta_kwh,arrays["risk_delta"][di,selected])
        a.equal(date+".selected_tau",rows.selected_tau,np.repeat(profiles[cfg["profiles"][selected]],6),0)
        a.equal(date+".plan_load",rows.plan_load_kwh,np.maximum(rows.load_forecast_kwh+rows.risk_delta_kwh,0))
        a.equal(date+".plan_pv",rows.plan_pv_kwh,rows.pv_forecast_kwh+np.maximum(-rows.load_forecast_kwh-rows.risk_delta_kwh,0))
        a.equal(date+".selected_terminal",rows.selected_terminal,1200.)
        a.equal(date+".selected_terminal_energy",rows.selected_terminal_energy_kwh,1200.)
        record = daily.loc[daily.date == date].iloc[0]
        a.check(date+".daily_profile",record.selected_profile == cfg["profiles"][selected])
        a.equal(date+".daily_terminal",record.selected_terminal,1200.)
    statistics = dict(solver_count=candidate_count,solver_runtime_seconds=sum(runtimes),
        solver_max_runtime_seconds=max(runtimes),solver_max_mip_gap=max(gaps),solver_failures=0,solver_fallbacks=0)
    for key,value in statistics.items():
        a.equal("summary."+key,summary[key],value,CTOL)
    return dict(**a.result(compact=True),totals=totals,candidates_verified=candidate_count,
        scenario_candidate_replays=scenario_count,solver_statistics=statistics,
        artifact_sha256={name:sha(folder/name) for name in required})


def reference_audit(name,actual,price,archive):
    folder = ROOT/"references"/name
    a = Audit()
    cfg,summary = js(folder/"config.json"),js(folder/"summary.json")
    ledger,plans,daily = (csv(folder/file) for file in ("ledger.csv","plans.csv","daily.csv"))
    a.check("same_period",(cfg["start"],cfg["end"]) == ("2025-02-01","2025-12-31"))
    a.equal("same_initial",cfg["initial_energy_kwh"],7268.4231640740745)
    totals = ledger_audit(a,ledger,daily,summary,actual,price,cfg)
    keys(a,plans,cfg["start"],cfg["end"],"plans")
    for field in PLAN+["load_forecast_kwh","pv_forecast_kwh","plan_load_kwh","plan_pv_kwh","risk_delta_kwh"]:
        a.equal("frozen."+field,ledger[field],plans[field])
    published = csv(ROOT/"forecasts/seasonal.csv") if cfg.get("forecast_model") == "seasonal" else archive
    published = published.set_index(KEYS).reindex(pd.MultiIndex.from_frame(ledger[KEYS]))
    for field in ("load_forecast_kwh","pv_forecast_kwh"):
        a.equal("published."+field,ledger[field],published[field].to_numpy())
    for date,rows in ledger.groupby("date",sort=True):
        physical(a,rows,date+".plan",plan=True)
        a.equal(date+".plan_initial",rows.energy_start_plan_kwh.iloc[0],rows.energy_start_actual_kwh.iloc[0])
        target = rows.selected_terminal_energy_kwh.iloc[0] if "selected_terminal_energy_kwh" in rows else (rows.energy_start_actual_kwh.iloc[0] if cfg["terminal_target"] == "equal_initial" else float(cfg["terminal_target"]))
        a.equal(date+".plan_terminal",rows.energy_end_plan_kwh.iloc[-1],target)
    return dict(**a.result(compact=True),totals=totals,artifact_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()},
        scope="Hash-equivalent copies of previously audited reference artifacts; saved ledger and plans independently recomputed, no old optimization rerun.")


def causality_audit(actual, price, archive, extension=False):
    path_prefix = "extension_" if extension else ""
    a = Audit()
    report_path = REPORT/(path_prefix+"causality_validation.json")
    folder = ROOT/"causality_inputs"
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
    policies = [c["policy"] for c in js(WORK/"configs/q2_pareto_v3/extension.json" if extension else CONFIG)["runs"]]
    a.check("all_declared_policies", [row["policy"] for row in report["checks"]] == policies)
    replays = {}
    for name in policies:
        for variant, source, f in zip(("original", "mutated"), (actual, changed), archives):
            result = run_audit(ROOT/(path_prefix+"causality_"+variant)/name, source, price, f)
            replays[variant+"/"+name] = result
            a.check(name+"."+variant+".independent_replay", result["passed"])
        paths = [ROOT/(path_prefix+"causality_"+variant)/name for variant in ("original", "mutated")]
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
    a.check("script_sha256", report["script_sha256"] == sha(WORK/"scripts/q2_pareto_v3/causality_checks.py"))
    prefix_path = folder/(path_prefix+"scenario_prefix_evidence.npz")
    if a.check("scenario_prefix.evidence_present", prefix_path.is_file()):
        evidence = dict(np.load(prefix_path, allow_pickle=False))
        a.equal("scenario_prefix.initial", evidence["initial"], 6000, 0)
        a.equal("scenario_prefix.cutoff", evidence["cutoff_index"], 72, 0)
        a.equal("scenario_prefix.price", evidence["price"], price.price_yuan_per_kwh)
        january = dict(np.load(ROOT/"january/R_guard/decision_evidence.npz", allow_pickle=False))
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope",choices=("selftest","sources","january","runs","references","causality","analysis","all","extension_january","extension_runs","extension_causality","extension_analysis","extension_all"),default="all")
    args = parser.parse_args()
    tests = mathematical_self_tests()
    if args.scope == "selftest":
        result = dict(scope=args.scope,**tests)
    else:
        actual,price,archive,sources = source_audit()
        extension = extension_source_audit() if args.scope.startswith("extension_") else dict(passed=None,status="outside_scope")
        paths,refs,complete = {},{},Audit()
        for stage in (("january","runs") if args.scope == "all" else (("extension_january","extension_runs") if args.scope == "extension_all" else (args.scope,))):
            if stage not in ("january","runs","extension_january","extension_runs"):
                continue
            expected = [c["policy"] for c in js(WORK/"configs/q2_pareto_v3/extension.json")["runs"]] if stage.startswith("extension_") else (JANUARY if stage == "january" else [c["policy"] for c in js(CONFIG)["runs"]])
            found = {p.name for p in (ROOT/stage).iterdir() if p.is_dir()}
            complete.check(stage+".exact_path_set",set(expected) == found)
            for name in expected:
                try:
                    paths[stage+"/"+name] = run_audit(ROOT/stage/name,actual,price,archive)
                except Exception as exc:
                    paths[stage+"/"+name] = dict(passed=False,audit_exception=type(exc).__name__+": "+str(exc))
                print(stage+"/"+name,"PASS" if paths[stage+"/"+name]["passed"] else "FAIL",flush=True)
        if args.scope in ("references","runs","all"):
            for name in REFERENCES:
                try:
                    refs[name] = reference_audit(name,actual,price,archive)
                except Exception as exc:
                    refs[name] = dict(passed=False,audit_exception=type(exc).__name__+": "+str(exc))
                print("reference/"+name,"PASS" if refs[name]["passed"] else "FAIL",flush=True)
        causality = causality_audit(actual,price,archive,extension=args.scope.startswith("extension_")) if args.scope in ("causality","all","extension_causality","extension_all") else dict(passed=None,status="outside_scope")
        if args.scope in ("runs","all"):
            complete.equal("annual_candidate_count",sum(v.get("candidates_verified",0) for k,v in paths.items() if k.startswith("runs/")),11356,0)
        if args.scope in ("extension_runs","extension_all"):
            complete.equal("extension_candidate_count",sum(v.get("candidates_verified",0) for k,v in paths.items() if k.startswith("extension_runs/")),2672,0)
        analysis = analysis_audit(price) if args.scope in ("analysis","all") else (user_cap_audit(price) if args.scope in ("extension_analysis","extension_all") else dict(passed=None,status="outside_scope"))
        result = dict(passed=all(x["passed"] for x in [tests,sources,complete.result(),*paths.values(),*refs.values()]) and causality["passed"] is not False and analysis["passed"] is not False and extension["passed"] is not False,
            scope=args.scope,self_tests=tests,sources=sources,completeness=complete.result(),runs=paths,references=refs,causality=causality,analysis=analysis,extension_sources=extension)
    source_unchanged = sha(Path(__file__)) == VALIDATOR_SHA256
    result["passed"] = result["passed"] and source_unchanged
    result.update(created_utc=datetime.now(timezone.utc).isoformat(),validator_sha256=VALIDATOR_SHA256,
        validator_source_unchanged_during_run=source_unchanged,
        independence="Only standard library, numpy and pandas; no production prediction, planning, scoring or dispatch function imports.",
        producer_sha256={p.name:sha(p) for p in (WORK/"scripts/q2_pareto_v3").glob("*.py") if p.name != "independent_verify.py"},
        tolerances=dict(physical_kwh=ETOL,cost_yuan=CTOL),
        limitations=["Processed source and frozen copies audited; raw XLSX cleaning not repeated.",
            "All saved candidate constraints checked without repeating MILP optimization; solver metadata is not an independently rerun optimality certificate.",
            "Historical exploration and short tail samples do not guarantee future or whole-year fee caps."])
    output = REPORT/("independent_validation.json" if args.scope == "all" else "independent_validation_"+args.scope+".json")
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps(dict(passed=result["passed"],output=str(output)),ensure_ascii=False))
    return 0 if result["passed"] else 1



def representative_audit(frames, names=("P_floor","S_terminal","T_rebalance","R_guard","R_mean","R_cost","R_w28"), base=None):
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


def analysis_audit(price):
    a = Audit()
    required = ["comparison_all.csv","daily.csv","monthly.csv","hourly.csv","daily_selections.csv",
        "selection_counts.csv","daily_guard_diagnostics.csv","paired_daily.csv","win_loss_counts.csv",
        "block_bootstrap.csv","ablation.json","acceptance.json"]
    if not a.check("artifacts_present",all((ROOT/name).is_file() for name in required)):
        return a.result()
    config = js(CONFIG)
    new_names = [c["policy"] for c in config["runs"]]
    names = REFERENCES+new_names
    columns = ["planned_cost_yuan","emergency_cost_yuan","total_cost_yuan","emergency_kwh","unused_grid_kwh"]
    fees = columns[:3]
    comparison = csv(ROOT/"comparison_all.csv").set_index("policy")
    a.check("comparison_order",comparison.index.tolist() == names)
    grouping_tables = {name:csv(ROOT/(name+".csv")) for name in ("daily","monthly","hourly")}
    selections = csv(ROOT/"daily_selections.csv").set_index(["policy","date"])
    counts = csv(ROOT/"selection_counts.csv").set_index(["policy","profile"])
    diagnostics = csv(ROOT/"daily_guard_diagnostics.csv").set_index(["policy","date"])
    paired = csv(ROOT/"paired_daily.csv").set_index(["policy","baseline","date"])
    win_loss = csv(ROOT/"win_loss_counts.csv").set_index(["policy","baseline"])
    boot = csv(ROOT/"block_bootstrap.csv").set_index(["policy","baseline","block_days","component"])
    dates = [str(date.date()) for date in pd.date_range("2025-02-01","2025-12-31")]
    selection_keys = [(name,date) for name in new_names for date in dates]
    a.check("selection_keys",selections.index.tolist() == selection_keys)
    a.check("diagnostic_keys",diagnostics.index.tolist() == selection_keys)
    baseline_order = ["P_floor","B0","B1","P","P_terminal","S_terminal"]
    pairs = [(name,base) for name in new_names for base in baseline_order]
    a.check("paired_keys",paired.index.tolist() == [(name,base,date) for name,base in pairs for date in dates])
    a.check("win_loss_pairs",win_loss.index.tolist() == pairs)
    paired = paired.sort_index()
    a.check("bootstrap_keys",boot.index.tolist() == [(name,"P_floor",block,field) for name in new_names for block in (7,14) for field in fees])
    frames,day_totals,totals,selection_records = {},{},{},[]
    joint_passes,stricter_passes = [],[]
    for name in names:
        folder = ROOT/("references" if name in REFERENCES else "runs")/name
        f = csv(folder/"ledger.csv")
        frames[name] = f
        keys(a,f,"2025-02-01","2025-12-31",name+".source_keys")
        row = comparison.loc[name]
        source_total = {key:float(f[key].sum()) for key in SUMS}
        source_total.update(days=f.date.nunique(),intervals=len(f),initial_energy_kwh=f.energy_start_actual_kwh.iloc[0],
            final_energy_kwh=f.energy_end_actual_kwh.iloc[-1],
            inventory_adjusted_cost_yuan=float(f.total_cost_yuan.sum()-price.price_yuan_per_kwh.mean()*.9*(f.energy_end_actual_kwh.iloc[-1]-f.energy_start_actual_kwh.iloc[0])),
            unused_grid_cost_yuan=float((f.price_yuan_per_kwh*f.unused_grid_kwh).sum()),
            emergency_days=int(f.loc[f.emergency_kwh > ETOL,"date"].nunique()),
            emergency_intervals=int((f.emergency_kwh > ETOL).sum()),
            emergency_share_load=float(f.emergency_kwh.sum()/f.load_actual_kwh.sum()))
        totals[name] = source_total
        for field,value in source_total.items():
            a.equal(name+".comparison."+field,row[field],value,CTOL)
        pass_emergency = source_total["emergency_cost_yuan"] <= config["emergency_cap_yuan"]+CTOL
        pass_stricter = source_total["emergency_cost_yuan"] <= config["secondary_emergency_cap_yuan"]+CTOL
        joint = pass_emergency and source_total["planned_cost_yuan"] < config["ordinary_cap_yuan"]-CTOL and source_total["total_cost_yuan"] < config["total_cap_yuan"]-CTOL
        a.check(name+".cap_flags",bool(row.passes_emergency_cap) == pass_emergency and bool(row.passes_stricter_P_emergency_cap) == pass_stricter and
            bool(row.passes_joint) == joint and bool(row.passes_stricter_joint) == (joint and pass_stricter))
        if name in new_names and joint:
            joint_passes.append(name)
            if pass_stricter:
                stricter_passes.append(name)
        day_totals[name] = f.groupby("date")[columns].sum()
        for table,key,values in (("daily","date",f.date),("monthly","month",f.date.str[:7]),("hourly","hour",(f.slot_id-1)//6)):
            observed = grouping_tables[table].loc[grouping_tables[table].policy == name].set_index(key)
            expected = f.assign(**{key:values}).groupby(key)[columns].sum()
            a.check(name+"."+table+".keys",observed.index.tolist() == expected.index.tolist())
            a.equal(name+"."+table+".values",observed[columns],expected[columns],CTOL)
        if name in REFERENCES:
            continue
        decision = js(folder/"decisions.json")["days"]
        evidence = dict(np.load(folder/"decision_evidence.npz",allow_pickle=False))
        for i,meta in enumerate(decision):
            date,k = meta["date"],meta["selected_index"]
            profile = meta["candidates"][k]["profile"]
            selected = selections.loc[(name,date)]
            a.check(name+"."+date+".selected_profile",selected.profile == profile)
            a.equal(name+"."+date+".selected_counts",selected[["scenario_count","selected_index"]],[meta["scenario_count"],k],0)
            selection_records.append((name,profile))
            diagnostic = diagnostics.loc[(name,date)]
            a.check(name+"."+date+".guard_profile",diagnostic.selected_profile == profile)
            S = meta["scenario_count"]
            for field,value in dict(feasible_candidates=int(evidence["feasible"][i].sum()),
                expected_emergency_yuan=float(evidence["emergency_fee"][i,k,:S].mean()),expected_cvar_yuan=float(evidence["cvar"][i,k]),
                actual_emergency_yuan=float(day_totals[name].loc[date,"emergency_cost_yuan"])).items():
                a.equal(name+"."+date+".diagnostic."+field,diagnostic[field],value,CTOL)
    for table,key in (("daily","date"),("monthly","month"),("hourly","hour")):
        expected_keys = [(name,value) for name in names for value in (dates if key == "date" else ([f"2025-{m:02d}" for m in range(2,13)] if key == "month" else range(24)))]
        a.check(table+".all_keys",list(grouping_tables[table][["policy",key]].itertuples(index=False,name=None)) == expected_keys)
    expected_counts = pd.DataFrame(selection_records,columns=["policy","profile"]).groupby(["policy","profile"]).size()
    a.check("selection_count_keys",counts.index.tolist() == expected_counts.index.tolist())
    a.equal("selection_count_values",counts.days,expected_counts,0)
    for name in names:
        for baseline in REFERENCES:
            for field,label in (("total_cost_yuan","total"),("planned_cost_yuan","ordinary"),("emergency_cost_yuan","emergency"),("inventory_adjusted_cost_yuan","inventory_adjusted")):
                a.equal(name+".saving."+baseline+"."+field,comparison.loc[name,label+"_saving_vs_"+baseline+"_yuan"],totals[baseline][field]-totals[name][field],CTOL)
    rng = np.random.default_rng(config["bootstrap_seed"])
    for name,baseline in pairs:
        saving = day_totals[baseline][fees]-day_totals[name][fees]
        observed = paired.loc[(name,baseline)]
        expected_columns = [field.replace("cost","saving") for field in fees]
        a.equal(name+"."+baseline+".paired",observed[expected_columns],saving[fees],CTOL)
        total,emergency = saving.total_cost_yuan,saving.emergency_cost_yuan
        record = win_loss.loc[(name,baseline)]
        for field,value in dict(total_winning_days=int((total > CTOL).sum()),total_losing_days=int((total < -CTOL).sum()),
            emergency_worse_days=int((emergency < -CTOL).sum()),positive_total_months=int((total.groupby(total.index.str[:7]).sum() > CTOL).sum()),
            emergency_worse_months=int((emergency.groupby(emergency.index.str[:7]).sum() < -CTOL).sum())).items():
            a.equal(name+"."+baseline+".win_loss."+field,record[field],value,0)
        if baseline != "P_floor":
            continue
        for block in (7,14):
            values = saving[fees].to_numpy()
            n = len(values)
            starts = rng.integers(0,n,size=(2000,int(np.ceil(n/block))))
            indices = ((starts[:,:,None]+np.arange(block))%n).reshape(2000,-1)[:,:n]
            resamples = values[indices].sum(axis=1)
            low,high = np.quantile(resamples,[.025,.975],axis=0)
            joint_fraction = float(((resamples[:,0] > 0)&(resamples[:,1] >= 0)&(resamples[:,2] > 0)).mean())
            for j,field in enumerate(fees):
                row = boot.loc[(name,baseline,block,field)]
                for metric,value in dict(saving_yuan=values[:,j].sum(),ci95_low_yuan=low[j],ci95_high_yuan=high[j],
                    joint_nonworse_resample_fraction=joint_fraction,seed=20260913,replicates=2000).items():
                    a.equal(name+".bootstrap."+str(block)+"."+field+"."+metric,row[metric],value,CTOL)
                a.check(name+".bootstrap_scope."+str(block)+"."+field,"not future joint-pass probability" in row.scope)
    ablation = js(ROOT/"ablation.json")
    mapping = dict(P_floor="P_floor",day_trim="T_day_trim",evening_hedge="T_evening_hedge",rebalance="T_rebalance",R_guard="R_guard",R_mean="R_mean",R_cost="R_cost",R_w28="R_w28")
    for block,field in (("total_cost","total_cost_yuan"),("emergency_cost","emergency_cost_yuan")):
        a.check("ablation."+block+".keys",list(ablation[block]) == list(mapping))
        for label,name in mapping.items():
            a.equal("ablation."+block+"."+label,ablation[block][label],totals[name][field],CTOL)
    acceptance = js(ROOT/"acceptance.json")
    a.check("acceptance.primary",acceptance["primary"] == "R_guard" and acceptance["primary_passed"] == ("R_guard" in joint_passes))
    a.check("acceptance.caps",acceptance["caps"] == {k:v for k,v in config.items() if "cap_yuan" in k})
    a.check("acceptance.all_joint",acceptance["new_joint_passes"] == joint_passes)
    a.check("acceptance.all_stricter",acceptance["new_stricter_joint_passes"] == stricter_passes)
    representative = representative_audit(frames)
    a.check("representative.pass",representative["passed"])
    return dict(**a.result(compact=True),joint_passes=joint_passes,stricter_joint_passes=stricter_passes,
        representative=representative,artifact_sha256={name:sha(ROOT/name) for name in required},
        ledger_sha256={name:sha(ROOT/("references" if name in REFERENCES else "runs")/name/"ledger.csv") for name in names},
        interpretation="Descriptive paired circular blocks on frozen observed paths; candidate search and future parameter uncertainty are not resampled.")



def extension_profiles():
    result = {}
    for name,morning,day,evening in (("X_morning90",.9,.7,.9),("X_strong_morning85",.85,.65,.95),
            ("X_day60",.8,.6,.95),("X_day50",.8,.5,.95),("X_day60_morning85",.85,.6,.95),("X_evening85_day60",.8,.6,.85)):
        profile = [.8]*24
        profile[9:11],profile[11:18],profile[18:22] = [morning]*2,[day]*7,[evening]*4
        result[name] = profile
    result["X_uniform70"],result["X_uniform75"] = [.7]*24,[.75]*24
    return result


def extension_source_audit():
    a = Audit()
    folder = WORK/"configs/q2_pareto_v3"
    cfg,freeze = js(folder/"extension.json"),js(REPORT/"extension_freeze.json")
    for name,digest in freeze["files"].items():
        a.check("frozen."+name,sha(WORK/name) == digest)
    expected = extension_profiles()
    a.check("eight_profiles_order",[c["policy"] for c in cfg["runs"]] == list(expected))
    for row in cfg["runs"]:
        name = row["policy"]
        target = dict(start="2025-02-01",end="2025-12-31",initial_energy_kwh=7268.4231640740745,
            risk_window=28,scenario_window=56,mu=.38232,terminal_energy_kwh=1200.,cvar_alpha=.9,
            policy=name,profiles=[name],guard="none",profile_definitions={name:expected[name]})
        a.check("run_config."+name,row == target)
    a.equal("new_user_cap",cfg["user_emergency_cap_yuan"],1000000.,0)
    a.check("ordinary_not_hard_constraint",cfg["ordinary_cost_is_hard_constraint"] is False)
    a.check("primary_metric",cfg["primary_metric"] == "actual total purchase cost")
    a.equal("bootstrap_seed",cfg["bootstrap_seed"],20260914,0)
    a.equal("bootstrap_replicates",cfg["bootstrap_replicates"],2000,0)
    a.check("bootstrap_blocks",cfg["bootstrap_blocks"] == [7,14])
    return dict(**a.result(),artifact_sha256={"extension.json":sha(folder/"extension.json"),"extension_protocol.md":sha(REPORT/"extension_protocol.md")})



def identical_frame(a,name,observed,expected):
    try:
        pd.testing.assert_frame_equal(observed,expected,check_dtype=False,check_exact=True)
        a.check(name,True)
    except AssertionError as exc:
        a.check(name,False,str(exc)[:600])


def user_cap_audit(price):
    a = Audit()
    folder = ROOT/"analysis_user_cap"
    files = ["comparison_all.csv","eligible_ranking.csv","acceptance_user_cap.json","daily.csv","monthly.csv",
        "hourly.csv","paired_daily.csv","win_loss_counts.csv","block_bootstrap.csv","selection_counts.csv"]
    if not a.check("artifacts_present",all((folder/name).is_file() for name in files)):
        return a.result()
    old,new = js(CONFIG),js(WORK/"configs/q2_pareto_v3/extension.json")
    old_names = REFERENCES+[row["policy"] for row in old["runs"]]
    new_names = [row["policy"] for row in new["runs"]]
    all_names = old_names+new_names
    table = csv(folder/"comparison_all.csv").set_index("policy")
    original_table = csv(ROOT/"comparison_all.csv").set_index("policy")
    a.check("24_policy_order",table.index.tolist() == all_names)
    identical_frame(a,"old_comparison_values_preserved",table.loc[old_names,original_table.columns],original_table)
    inherited = ["daily","monthly","hourly","paired_daily","win_loss_counts","block_bootstrap","selection_counts"]
    frames = {}
    for name in inherited:
        frames[name] = csv(folder/(name+".csv"))
        prior = csv(ROOT/(name+".csv"))
        identical_frame(a,"original_rows_preserved."+name,frames[name].iloc[:len(prior)].reset_index(drop=True),prior)
    fees = ["planned_cost_yuan","emergency_cost_yuan","total_cost_yuan"]
    sums = fees+["emergency_kwh","unused_grid_kwh"]
    baselines = ["P_floor","B0","B1","P","P_terminal","S_terminal"]
    dates = [str(day.date()) for day in pd.date_range("2025-02-01","2025-12-31")]
    for name,key,values in (("daily","date",dates),("monthly","month",[f"2025-{m:02d}" for m in range(2,13)]),("hourly","hour",range(24))):
        a.check(name+".complete_keys",list(frames[name][["policy",key]].itertuples(index=False,name=None)) == [(policy,value) for policy in all_names for value in values])
    extended_pairs = [(name,base) for name in new_names for base in baselines]
    a.check("paired.extension_keys",list(frames["paired_daily"].loc[frames["paired_daily"].policy.isin(new_names),["policy","baseline","date"]].itertuples(index=False,name=None)) == [(name,base,date) for name,base in extended_pairs for date in dates])
    a.check("win_loss.extension_pairs",list(frames["win_loss_counts"].loc[frames["win_loss_counts"].policy.isin(new_names),["policy","baseline"]].itertuples(index=False,name=None)) == extended_pairs)
    a.check("bootstrap.extension_keys",list(frames["block_bootstrap"].loc[frames["block_bootstrap"].policy.isin(new_names),["policy","baseline","block_days","component"]].itertuples(index=False,name=None)) == [(name,"P_floor",block,field) for name in new_names for block in (7,14) for field in fees])
    expected_selection = pd.DataFrame([dict(policy=name,profile=name,days=334) for name in new_names])
    identical_frame(a,"selection_extension",frames["selection_counts"].loc[frames["selection_counts"].policy.isin(new_names)].reset_index(drop=True),expected_selection)
    paired = frames["paired_daily"].set_index(["policy","baseline","date"]).sort_index()
    win_loss = frames["win_loss_counts"].set_index(["policy","baseline"])
    boot = frames["block_bootstrap"].set_index(["policy","baseline","block_days","component"])
    daily_original = csv(ROOT/"daily.csv")
    source_frames = {}
    rng = np.random.default_rng(20260914)
    for name in new_names:
        f = csv(ROOT/"extension_runs"/name/"ledger.csv")
        source_frames[name] = f
        keys(a,f,"2025-02-01","2025-12-31",name+".source_keys")
        row = table.loc[name]
        quantities = {field:float(f[field].sum()) for field in SUMS}
        quantities.update(days=334,intervals=48096,initial_energy_kwh=7268.4231640740745,
            final_energy_kwh=f.energy_end_actual_kwh.iloc[-1],
            inventory_adjusted_cost_yuan=float(f.total_cost_yuan.sum()-price.price_yuan_per_kwh.mean()*.9*(f.energy_end_actual_kwh.iloc[-1]-7268.4231640740745)),
            unused_grid_cost_yuan=float((f.price_yuan_per_kwh*f.unused_grid_kwh).sum()),
            emergency_days=int(f.loc[f.emergency_kwh > ETOL,"date"].nunique()),
            emergency_intervals=int((f.emergency_kwh > ETOL).sum()),emergency_share_load=float(f.emergency_kwh.sum()/f.load_actual_kwh.sum()))
        for field,value in quantities.items():
            a.equal(name+".comparison."+field,row[field],value,CTOL)
        old_emergency = quantities["emergency_cost_yuan"] <= old["emergency_cap_yuan"]+CTOL
        stricter = quantities["emergency_cost_yuan"] <= old["secondary_emergency_cap_yuan"]+CTOL
        old_joint = old_emergency and quantities["planned_cost_yuan"] < old["ordinary_cap_yuan"]-CTOL and quantities["total_cost_yuan"] < old["total_cap_yuan"]-CTOL
        a.check(name+".old_gate",bool(row.passes_emergency_cap) == old_emergency and bool(row.passes_stricter_P_emergency_cap) == stricter and
            bool(row.passes_joint) == old_joint and bool(row.passes_stricter_joint) == (old_joint and stricter))
        for baseline in REFERENCES:
            for field,label in (("total_cost_yuan","total"),("planned_cost_yuan","ordinary"),("emergency_cost_yuan","emergency"),("inventory_adjusted_cost_yuan","inventory_adjusted")):
                a.equal(name+".saving."+baseline+"."+field,row[label+"_saving_vs_"+baseline+"_yuan"],original_table.loc[baseline,field]-quantities[field],CTOL)
        grouped = {}
        for kind,key,values in (("daily","date",f.date),("monthly","month",f.date.str[:7]),("hourly","hour",(f.slot_id-1)//6)):
            grouped[kind] = f.assign(**{key:values}).groupby(key)[sums].sum()
            observed = frames[kind].loc[frames[kind].policy == name].set_index(key)
            a.equal(name+"."+kind,observed[sums],grouped[kind][sums],CTOL)
        for baseline in baselines:
            ref = daily_original.loc[daily_original.policy == baseline].set_index("date")
            saving = ref[fees]-grouped["daily"][fees]
            a.equal(name+".paired."+baseline,paired.loc[(name,baseline),[field.replace("cost","saving") for field in fees]],saving[fees],CTOL)
            total,emergency = saving.total_cost_yuan,saving.emergency_cost_yuan
            record = win_loss.loc[(name,baseline)]
            for field,value in dict(total_winning_days=int((total > CTOL).sum()),total_losing_days=int((total < -CTOL).sum()),
                emergency_worse_days=int((emergency < -CTOL).sum()),positive_total_months=int((total.groupby(total.index.str[:7]).sum() > CTOL).sum()),
                emergency_worse_months=int((emergency.groupby(emergency.index.str[:7]).sum() < -CTOL).sum())).items():
                a.equal(name+".win_loss."+baseline+"."+field,record[field],value,0)
            if baseline != "P_floor":
                continue
            for block in (7,14):
                values = saving[fees].to_numpy()
                starts = rng.integers(0,334,size=(2000,int(np.ceil(334/block))))
                ix = ((starts[:,:,None]+np.arange(block))%334).reshape(2000,-1)[:,:334]
                sampled = values[ix].sum(axis=1)
                low,high = np.quantile(sampled,[.025,.975],axis=0)
                joint = float(((sampled[:,0] > 0)&(sampled[:,1] >= 0)&(sampled[:,2] > 0)).mean())
                for j,component in enumerate(fees):
                    row = boot.loc[(name,baseline,block,component)]
                    for field,value in dict(saving_yuan=values[:,j].sum(),ci95_low_yuan=low[j],ci95_high_yuan=high[j],
                        joint_nonworse_resample_fraction=joint,seed=20260914,replicates=2000).items():
                        a.equal(name+".bootstrap."+str(block)+"."+component+"."+field,row[field],value,CTOL)
    eligible,passed,failed = [],[],[]
    for name in all_names:
        row = table.loc[name]
        meets = row.emergency_cost_yuan <= 1000000.+CTOL
        improves = meets and row.total_cost_yuan < old["total_cap_yuan"]-CTOL
        stage = "reference" if name in REFERENCES else ("original_ten" if name in old_names else "extension_eight")
        a.check(name+".user_requirement",bool(row.meets_user_emergency_cap) == meets and bool(row.passes_user_requirement) == improves and row.study_stage == stage)
        if meets:
            eligible.append(name)
        if name not in REFERENCES:
            (passed if improves else failed).append(name)
    eligible.sort(key=lambda name:table.loc[name,"total_cost_yuan"])
    ranking = csv(folder/"eligible_ranking.csv").set_index("policy")
    identical_frame(a,"eligible_rank_order_and_values",ranking,table.loc[eligible])
    best = eligible[0]
    acceptance = js(folder/"acceptance_user_cap.json")
    a.equal("new_cap_exact",acceptance["emergency_cap_yuan"],1000000.,0)
    a.equal("reference_total_exact",acceptance["total_reference_yuan"],14022838.598498546,0)
    a.check("ordinary_not_hard",acceptance["ordinary_cost_is_hard_constraint"] is False)
    a.check("best_observed",acceptance["best_observed_policy"] == best)
    a.equal("best_cost",acceptance["best_total_cost_yuan"],table.loc[best,"total_cost_yuan"],CTOL)
    a.equal("best_emergency",acceptance["best_emergency_cost_yuan"],table.loc[best,"emergency_cost_yuan"],CTOL)
    a.check("passed_new_policies",acceptance["passed_new_policies"] == passed)
    a.check("failed_new_policies",acceptance["failed_new_policies"] == failed)
    representative = representative_audit(source_frames,names=new_names,base=folder/"representative")
    a.check("representative.pass",representative["passed"])
    return dict(**a.result(compact=True),best_observed_policy=best,best_total_cost_yuan=float(table.loc[best,"total_cost_yuan"]),
        best_emergency_cost_yuan=float(table.loc[best,"emergency_cost_yuan"]),passed_new_policies=passed,failed_new_policies=failed,
        representative=representative,artifact_sha256={name:sha(folder/name) for name in files},
        scope="New one-million-yuan user cap; original three-condition analysis retained without redefinition.")


if __name__ == "__main__":
    raise SystemExit(main())
