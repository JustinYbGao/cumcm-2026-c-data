"""Q2 controlled changes; original scientific functions loaded without I/O side effects."""
import ast
import copy
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[2]
ROOT = WORK / 'results/emergency_improvement_v1'
INPUTS = ROOT / 'inputs'
RUNTIME = ROOT / 'runtime'
RUNTIME.mkdir(exist_ok=True)
for key in ['TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR']:
    os.environ[key] = str(RUNTIME)

import highspy
import numpy as np
import pandas as pd


def load_original(name, names):
    tree = ast.parse((INPUTS / name).read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(INPUTS/name), 'exec'), globals())


load_original('original_run_q2.py', ['fourier', 'forecast_day', 'execute_interval'])
load_original('original_solve_q1.py', ['solve_model'])
# The terminal sensitivity changes exactly one constraint, leaving main solver intact.
_src = (INPUTS/'original_solve_q1.py').read_text()
_node = next(n for n in ast.parse(_src).body if isinstance(n, ast.FunctionDef) and n.name == 'solve_model')
_target_src = ast.get_source_segment(_src, _node).replace('def solve_model(', 'def solve_target_model(')
assert _target_src.count("e[n] == b['initial_energy_kwh']") == 1
_target_src = _target_src.replace("e[n] == b['initial_energy_kwh']", "e[n] == b['terminal_target_kwh']")
exec(compile(_target_src, '<single-terminal-constraint-variant>', 'exec'), globals())


def risk_adjustment(archive, day, window, tau):
    day = pd.Timestamp(day)
    if len(archive):
        dates = pd.to_datetime(archive.date)
        selected = archive.loc[(dates >= day-pd.Timedelta(days=window)) & (dates < day)
                               & (pd.to_datetime(archive.residual_available_time) <= day)].copy()
    else:
        selected = archive.copy()
    days = selected.date.nunique()
    meta = {'risk_history_start': str(selected.date.min()) if len(selected) else '',
            'risk_history_end': str(selected.date.max()) if len(selected) else '',
            'risk_sample_count': int(len(selected)//24), 'risk_history_days': int(days),
            'risk_cold_start': bool(days < 7)}
    if days < 7:
        return np.zeros(144), meta
    delta = np.zeros(144)
    group = (selected.slot_id.to_numpy()-1)//6
    for hour in range(24):
        delta[hour*6:(hour+1)*6] = np.quantile(selected.net_residual_kwh.to_numpy()[group==hour], tau, method='linear')
    return delta, meta


def reserve_schedule(price, net_forecast, grid, eta_d):
    gap = np.maximum(net_forecast-grid, 0)
    return np.array([min(9600., gap[(np.arange(len(price)) > t) & (price > price[t])].sum()/eta_d)
                     for t in range(len(price))])


def execute(grid, load, pv, energy, eta_c, eta_d, power_basis='AC_bus', reserve=0.):
    if power_basis == 'AC_bus' and reserve == 0.:
        return execute_interval(grid, load, pv, energy, eta_c, eta_d)
    mc = 5000/6/(eta_c if power_basis == 'battery_internal' else 1.)
    md = 5000/6*(eta_d if power_basis == 'battery_internal' else 1.)
    net = grid+pv-load
    c = min(net, mc, max(0., (10800-energy)/eta_c)) if net >= 0 else 0.
    d = min(-net, md, max(0., eta_d*(energy-1200-reserve))) if net < 0 else 0.
    emergency = max(0., -net-d)
    surplus = max(0., net-c)
    unused = min(grid, surplus)
    return {'charge_actual_kwh': c, 'discharge_actual_kwh': d, 'emergency_kwh': emergency,
            'surplus_kwh': surplus, 'unused_grid_kwh': unused, 'pv_curtailment_kwh': surplus-unused,
            'energy_start_actual_kwh': energy, 'energy_end_actual_kwh': energy+eta_c*c-d/eta_d}


def plan_day(load, pv, delta, price, energy, cfg):
    physical = json.loads((INPUTS/'model_baseline.json').read_text())
    b = physical['battery']
    b.update(initial_energy_kwh=energy, eta_charge=cfg['eta_charge'], eta_discharge=cfg['eta_discharge'])
    if cfg['power_basis'] == 'battery_internal':
        b.update(max_charge_kw=5000/cfg['eta_charge'], max_discharge_kw=5000*cfg['eta_discharge'])
    load_risk = np.maximum(load+delta, 0.)
    pv_risk = pv+np.maximum(-load-delta, 0.)
    data = pd.DataFrame({'price_yuan_per_kwh':price, 'load_kwh':load_risk, 'pv_forecast_kwh':pv_risk})
    if cfg['terminal_target'] == 'equal_initial':
        plan, status = solve_model(data, physical)
    else:
        b['terminal_target_kwh'] = float(cfg['terminal_target'])
        plan, status = solve_target_model(data, physical)
    return plan, status, load_risk, pv_risk


def forecast_at(actual, day, kind):
    cfg = json.loads((INPUTS/'q2_baseline.json').read_text())
    history = actual.loc[pd.to_datetime(actual.interval_end) <= pd.Timestamp(day)].copy()
    return forecast_day(history, pd.Timestamp(day), kind, cfg)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
