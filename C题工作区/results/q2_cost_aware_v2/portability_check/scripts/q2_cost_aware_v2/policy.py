"""Finite-plan selection using historical joint errors and causal greedy recourse."""
import ast
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[2]
ROOT = WORK / 'results/q2_cost_aware_v2'
INPUTS = ROOT / 'inputs'
RUNTIME = ROOT / 'runtime'
RUNTIME.mkdir(parents=True, exist_ok=True)
for key in ['TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR']:
    os.environ[key] = str(RUNTIME)

import highspy
import numpy as np
import pandas as pd


def original_functions(filename, names):
    source = (INPUTS / filename).read_text()
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(INPUTS / filename), 'exec'), globals())


original_functions('original_run_q2.py', ['fourier', 'forecast_day', 'execute_interval'])
original_functions('original_solve_q1.py', ['solve_model'])
_source = (INPUTS / 'original_solve_q1.py').read_text()
_node = next(n for n in ast.parse(_source).body if isinstance(n, ast.FunctionDef) and n.name == 'solve_model')
_target = ast.get_source_segment(_source, _node).replace('def solve_model(', 'def solve_target_model(')
assert _target.count("e[n] == b['initial_energy_kwh']") == 1
_target = _target.replace("e[n] == b['initial_energy_kwh']", "e[n] == b['terminal_target_kwh']")
exec(compile(_target, '<fixed-plan-terminal>', 'exec'), globals())

PLAN_KEYS = ['grid_kwh', 'charge_kwh', 'discharge_kwh', 'energy_start_kwh',
             'energy_end_kwh', 'curtailment_kwh', 'charge_mode']
PLAN_COLUMNS = ['grid_plan_kwh', 'charge_plan_kwh', 'discharge_plan_kwh', 'energy_start_plan_kwh',
                'energy_end_plan_kwh', 'pv_curtailment_plan_kwh', 'charge_mode_plan']


def completed_history(archive, day, window):
    day = pd.Timestamp(day)
    dates = pd.to_datetime(archive.date)
    selected = archive.loc[(dates >= day - pd.Timedelta(days=window)) & (dates < day)
                           & (pd.to_datetime(archive.residual_available_time) <= day)]
    return selected.sort_values(['date', 'slot_id'])


def scenario_bank(archive, day, window, forecast_net):
    selected = completed_history(archive, day, window)
    dates = sorted(selected.date.unique().tolist())
    assert all(selected.groupby('date').slot_id.apply(list).apply(lambda x: x == list(range(1, 145))))
    return selected.net_residual_kwh.to_numpy().reshape(len(dates), 144) + forecast_net, dates


def risk_deltas(archive, day, window, taus):
    selected = completed_history(archive, day, window)
    if selected.date.nunique() < 7:
        return {tau: np.zeros(144) for tau in taus}
    values = selected.net_residual_kwh.to_numpy().reshape(-1, 24, 6).transpose(1, 0, 2).reshape(24, -1)
    return {tau: np.repeat(np.quantile(values, tau, axis=1, method='linear'), 6) for tau in taus}


def simulate(grid, scenario_net, price, initial, mu, traces=False):
    """Each candidate shares one q across scenarios; every recourse action uses the current prefix."""
    grid, scenario_net, price = np.asarray(grid), np.asarray(scenario_net), np.asarray(price)
    energy = np.full((len(grid), len(scenario_net)), float(initial))
    emergency_fee = np.zeros_like(energy)
    trace = {key: [] for key in ['charge', 'discharge', 'emergency', 'surplus', 'energy_start', 'energy_end']} if traces else None
    for t in range(grid.shape[1]):
        net = grid[:, t, None] - scenario_net[None, :, t]
        charge = np.minimum(np.minimum(np.maximum(net, 0.), 5000 / 6), np.maximum((10800 - energy) / .9, 0.))
        discharge = np.minimum(np.minimum(np.maximum(-net, 0.), 5000 / 6), np.maximum(.9 * (energy - 1200), 0.))
        emergency = np.maximum(-net - discharge, 0.)
        surplus = np.maximum(net - charge, 0.)
        next_energy = energy + .9 * charge - discharge / .9
        emergency_fee += 5 * price[t] * emergency
        if traces:
            for key, value in zip(trace, [charge, discharge, emergency, surplus, energy, next_energy]):
                trace[key].append(value.copy())
        energy = next_energy
    ordinary = grid @ price
    result = {'ordinary': ordinary, 'emergency_fee': emergency_fee, 'end_energy': energy,
              'score': ordinary + (emergency_fee - mu * (energy - initial)).mean(axis=1)}
    if traces:
        result['trace'] = {key: np.stack(value, axis=-1) for key, value in trace.items()}
    return result


def choose_index(scores):
    return int(np.flatnonzero(np.asarray(scores) <= np.min(scores) + 1e-8)[0])


def decision(archive, day, load_hat, pv_hat, price, energy, cfg):
    deltas = risk_deltas(archive, day, cfg['risk_window'], cfg['taus'])
    scenario_net, source_dates = scenario_bank(archive, day, cfg['scenario_window'], load_hat - pv_hat)
    physical = json.loads((INPUTS / 'model_baseline.json').read_text())
    physical['battery']['initial_energy_kwh'] = float(energy)
    plans, risks, candidates = [], [], []
    for tau in cfg['taus']:
        delta = deltas[tau]
        load_risk = np.maximum(load_hat + delta, 0.)
        pv_risk = pv_hat + np.maximum(-load_hat - delta, 0.)
        data = pd.DataFrame({'price_yuan_per_kwh': price, 'load_kwh': load_risk, 'pv_forecast_kwh': pv_risk})
        for target in cfg['terminals']:
            if target == 'equal_initial':
                plan, status = solve_model(data, physical)
            else:
                physical['battery']['terminal_target_kwh'] = float(target)
                plan, status = solve_target_model(data, physical)
            plan['grid_kwh'] = np.maximum(plan['grid_kwh'], 0.)
            plans.append(np.column_stack([plan[key] for key in PLAN_KEYS]))
            risks.append(delta)
            candidates.append({'tau': tau, 'terminal': target,
                               'terminal_energy_kwh': float(energy if target == 'equal_initial' else target), 'solver': status})
    plans = np.asarray(plans)
    if len(source_dates) < 7:
        raise ValueError('This predeclared run requires at least 7 completed scenario days; stop without issuing an unverified fallback.')
    scores = simulate(plans[:, :, 0], scenario_net, price, energy, cfg['mu'])
    selected = choose_index(scores['score'])
    return {'plans': plans, 'risk_delta': np.asarray(risks), 'scenarios': scenario_net,
            'source_dates': source_dates, 'candidates': candidates, 'selected': selected, **scores}


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
