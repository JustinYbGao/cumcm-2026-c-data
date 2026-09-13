"""Q1 deterministic AC-bus dispatch. All outputs are internal assumption-based results."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

WORK = Path(__file__).resolve().parents[1]
INTERIM = WORK / 'data/interim/q1'
INTERIM.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(INTERIM)
os.environ['TMP'] = str(INTERIM)
os.environ['TEMP'] = str(INTERIM)
os.environ['MPLCONFIGDIR'] = str(INTERIM / 'cache/matplotlib')
sys.dont_write_bytecode = True

import highspy
import numpy as np
import pandas as pd


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solve_model(data, cfg, relaxed=False, tag=None, cost_cap=None):
    """Return a dispatch plus solver evidence; LP relaxes only mode integrality."""
    n = len(data)
    b = cfg['battery']
    dt = cfg['interval_minutes'] / 60
    mc, md = b['max_charge_kw'] * dt, b['max_discharge_kw'] * dt
    h = highspy.Highs()
    h.setOptionValue('output_flag', bool(tag))
    if tag:
        h.setOptionValue('log_file', str(WORK / f'logs/q1/{tag}.log'))
    for k, v in cfg['solver'].items():
        if k != 'name':
            if h.setOptionValue(k, v) != highspy.HighsStatus.kOk:
                raise ValueError(f'Invalid solver option: {k}')
    p = data.price_yuan_per_kwh.to_numpy()
    load = data.load_kwh.to_numpy()
    pv = data.pv_forecast_kwh.to_numpy()
    g = [h.addVariable(obj=float(p[t]) if cost_cap is None else 0., name=f'g_{t}') for t in range(n)]
    c = [h.addVariable(ub=mc, obj=float(t + 1) if cost_cap is not None else 0., name=f'c_{t}') for t in range(n)]
    d = [h.addVariable(ub=md, name=f'd_{t}') for t in range(n)]
    w = [h.addVariable(ub=float(pv[t]), name=f'w_{t}') for t in range(n)]
    e = [h.addVariable(lb=b['min_energy_kwh'], ub=b['max_energy_kwh'], name=f'E_{t}') for t in range(n+1)]
    z = [h.addVariable(ub=1, type=highspy.HighsVarType.kContinuous if relaxed else highspy.HighsVarType.kInteger,
                       name=f'z_{t}') for t in range(n)]
    h.addConstr(e[0] == b['initial_energy_kwh'], name='initial')
    h.addConstr(e[n] == b['initial_energy_kwh'], name='terminal')
    for t in range(n):
        h.addConstr(g[t] - w[t] + d[t] - c[t] == float(load[t]-pv[t]), name=f'balance_{t}')
        h.addConstr(e[t+1] - e[t] - b['eta_charge'] * c[t] + (1 / b['eta_discharge']) * d[t] == 0., name=f'state_{t}')
        h.addConstr(c[t] <= mc * z[t], name=f'charge_mode_{t}')
        h.addConstr(d[t] + md * z[t] <= md, name=f'discharge_mode_{t}')
    if cost_cap is not None:
        h.addConstr(sum(float(p[t]) * g[t] for t in range(n)) <= cost_cap, name='primary_cost_cap')
    if tag:
        h.writeModel(str(WORK / f'results/q1/{tag}.lp'))
    h.run()
    status = h.modelStatusToString(h.getModelStatus())
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(f'{tag}: {status}; see solver log; no optimal result published')
    sol, info = h.getSolution(), h.getInfo()
    values = lambda vs: np.array([sol.col_value[int(v)] for v in vs])
    ev = values(e)
    x = {'grid_kwh': values(g), 'charge_kwh': values(c), 'discharge_kwh': values(d),
         'curtailment_kwh': values(w), 'energy_start_kwh': ev[:-1], 'energy_end_kwh': ev[1:],
         'charge_mode': values(z)}
    result = {'status': status, 'objective_yuan': float(np.dot(p, x['grid_kwh'])),
              'solver_objective': h.getObjectiveValue(), 'relaxed': relaxed,
              'lower_bound_yuan': h.getObjectiveValue() if relaxed else info.mip_dual_bound,
              'mip_gap': None if relaxed else info.mip_gap,
              'nodes': None if relaxed else info.mip_node_count, 'runtime_seconds': h.getRunTime(),
              'variables': h.getNumCol(), 'constraints': h.getNumRow(),
              'max_primal_infeasibility': info.max_primal_infeasibility,
              'max_integrality_violation': None if relaxed else info.max_integrality_violation,
              'lower_bound_unit': 'secondary_weighted_charge_objective' if cost_cap is not None else 'yuan',
              'primary_cost_cap_yuan': cost_cap}
    if tag:
        h.writeSolution(str(WORK / f'results/q1/{tag}.sol'), 0)
    return x, result


def export_plan(data, x, cfg, name, evidence):
    out = WORK / 'results/q1' / name
    out.mkdir(parents=True, exist_ok=True)
    frame = data.copy()
    for key, val in x.items():
        frame[key] = val
    frame['cost_yuan'] = frame.price_yuan_per_kwh * frame.grid_kwh
    frame.to_csv(out / 'schedule.csv', index=False)
    pd.DataFrame({'minute': np.arange(145)*10,
                  'energy_kwh': np.r_[frame.energy_start_kwh.iloc[0], frame.energy_end_kwh]}).to_csv(out / 'states.csv', index=False)
    summary = {key: float(frame[key].sum()) for key in ['cost_yuan','grid_kwh','charge_kwh','discharge_kwh','curtailment_kwh']}
    summary.update(initial_energy_kwh=float(frame.energy_start_kwh.iloc[0]),
                   terminal_energy_kwh=float(frame.energy_end_kwh.iloc[-1]),
                   status=cfg['status'], scenario=name)
    table1 = frame.loc[frame.start_minute.isin([600,720,840,960,1080,1200]), ['start_minute','end_minute','grid_kwh']]
    table1.to_csv(out / 'table1_intervals.csv', index=False)
    table2 = frame.assign(block_start=frame.start_minute//240*240).groupby('block_start')[['charge_kwh','discharge_kwh']].sum().reset_index()
    table2['block_end'] = table2.block_start+240
    table2[['block_start','block_end','charge_kwh','discharge_kwh']].to_csv(out / 'table2_blocks.csv', index=False)
    save_json(out / 'summary.json', summary)
    save_json(out / 'config_snapshot.json', cfg)
    save_json(out / 'solver_status.json', evidence)
    return frame, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=WORK / 'configs/model_baseline.json')
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    for folder in ['logs/q1','results/q1']:
        (WORK / folder).mkdir(parents=True, exist_ok=True)
    source = WORK / cfg['input']
    data = pd.read_csv(source, float_precision='round_trip')
    if (len(data) != 144 or data.start_minute.tolist() != list(range(0,1440,10))
            or data.end_minute.tolist() != list(range(10,1441,10))):
        raise ValueError('Q1 must preserve the reviewed 144 interval time keys')
    fields = ['price_yuan_per_kwh','load_kwh','pv_forecast_kwh']
    if not np.isfinite(data[fields]).all().all() or (data[fields] < 0).any().any():
        raise ValueError('Nonfinite or negative input')
    if cfg['interval_minutes'] != 10:
        raise ValueError('The reviewed Q1 CSV uses 10 minute intervals')
    preserved = sorted((WORK / 'data/processed').glob('*.csv')) + sorted((WORK / 'raw').glob('*.xlsx'))
    before = {str(p.relative_to(WORK)): digest(p) for p in preserved}
    save_json(WORK / 'logs/q1/input_hashes_before.json', before)
    save_json(WORK / 'logs/q1/environment.json', {'python':sys.version, 'executable':Path(sys.executable).name,
              'platform':platform.platform(), 'highs':highspy.Highs().version(),
              'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','highspy','matplotlib','openpyxl']}})
    summaries, frames = {}, {}
    for name in ['baseline', 'roundtrip_90']:
        current = copy.deepcopy(cfg)
        if name == 'roundtrip_90':
            current['battery'].update(eta_charge=cfg['sensitivity']['eta_charge'], eta_discharge=cfg['sensitivity']['eta_discharge'],
                                      efficiency_basis='roundtrip_0.9_symmetric_working_assumption_not_official')
        x, evidence = solve_model(data, current, tag=name+'_milp')
        xl, lower = solve_model(data, current, relaxed=True, tag=name+'_lp')
        evidence['lp_lower_bound_yuan'] = lower['objective_yuan']
        evidence['milp_minus_lp_yuan'] = evidence['objective_yuan']-lower['objective_yuan']
        frames[name], summaries[name] = export_plan(data, x, current, name, evidence)
        export_plan(data, xl, current, name+'_lp', lower)
    n = len(data)
    net = data.load_kwh-data.pv_forecast_kwh
    zero = np.zeros(n)
    no_battery = {'grid_kwh': np.maximum(net,0), 'charge_kwh':zero, 'discharge_kwh':zero,
                  'curtailment_kwh':np.maximum(-net,0), 'energy_start_kwh':np.full(n,cfg['battery']['initial_energy_kwh']),
                  'energy_end_kwh':np.full(n,cfg['battery']['initial_energy_kwh']), 'charge_mode':zero}
    _, summaries['no_storage'] = export_plan(data,no_battery,cfg,'no_storage',{'status':'Analytic feasible baseline'})
    # Cost-face probe supplies a concrete alternative when the optimum is non-unique.
    cap = summaries['baseline']['cost_yuan'] + 1e-7
    alternate, status = solve_model(data,cfg,tag='alternate_milp',cost_cap=cap)
    alt_frame, _ = export_plan(data,alternate,cfg,'alternate',status)
    keys = ['grid_kwh','charge_kwh','discharge_kwh','energy_end_kwh']
    save_json(WORK / 'results/q1/nonuniqueness.json', {
        'cost_cap_yuan':cap, 'alternate_cost_yuan':float(alt_frame.cost_yuan.sum()),
        'cost_difference_yuan':float(alt_frame.cost_yuan.sum()-summaries['baseline']['cost_yuan']),
        'max_plan_difference_kwh':float(np.max(np.abs(alt_frame[keys].to_numpy()-frames['baseline'][keys].to_numpy()))),
        'interpretation':'cost-face witness within numerical tolerance; no claim of unique dispatch'})
    comparison = pd.DataFrame(summaries.values())
    comparison['saving_yuan_vs_no_storage'] = summaries['no_storage']['cost_yuan'] - comparison.cost_yuan
    comparison['saving_percent_vs_no_storage'] = comparison.saving_yuan_vs_no_storage / summaries['no_storage']['cost_yuan']*100
    comparison.to_csv(WORK / 'results/q1/comparison.csv', index=False)
    sensitivity = {'eta_baseline':0.9, 'eta_alternative':cfg['sensitivity']['eta_charge'],
                   'cost_change_yuan':summaries['roundtrip_90']['cost_yuan']-summaries['baseline']['cost_yuan']}
    for key in keys:
        delta = frames['roundtrip_90'][key]-frames['baseline'][key]
        sensitivity[key+'_l1_change'] = float(delta.abs().sum())
        sensitivity[key+'_max_change'] = float(delta.abs().max())
    save_json(WORK / 'results/q1/efficiency_sensitivity.json', sensitivity)
    after = {str(p.relative_to(WORK)): digest(p) for p in preserved}
    save_json(WORK / 'logs/q1/input_hashes_after.json', after)
    if before != after:
        raise RuntimeError('A protected input changed during this run')
    print(comparison[['scenario','cost_yuan','grid_kwh','saving_percent_vs_no_storage']].to_string(index=False))


if __name__ == '__main__':
    main()
