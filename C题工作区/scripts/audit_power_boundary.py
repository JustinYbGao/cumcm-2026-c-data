"""Four Q1 physical-convention scenarios; no frozen source/result mutation."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from solve_q1 import solve_model

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'results/revision_v1/power_boundary'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    config_path = WORK / 'configs/model_baseline.json'
    cfg = json.loads(config_path.read_text())
    source = WORK / cfg['input']
    data = pd.read_csv(source, float_precision='round_trip')
    summaries = []
    for efficiency in ('each_90', 'roundtrip_90'):
        for boundary in ('AC_bus', 'battery_internal'):
            current = copy.deepcopy(cfg)
            eta = 0.9 if efficiency == 'each_90' else np.sqrt(0.9)
            current['battery'].update(eta_charge=eta, eta_discharge=eta)
            if boundary == 'battery_internal':
                # Internal charge = eta*c; internal discharge = b/eta.
                current['battery'].update(max_charge_kw=5000/eta, max_discharge_kw=5000*eta)
            name = f'{efficiency}_{boundary}'
            dispatch, status = solve_model(data, current)
            _, lp = solve_model(data, current, relaxed=True)
            frame = data.copy()
            for key, value in dispatch.items():
                frame[key] = value
            c, b, q, w = [frame[k].to_numpy() for k in ('charge_kwh','discharge_kwh','grid_kwh','curtailment_kwh')]
            e0, e1 = frame.energy_start_kwh.to_numpy(), frame.energy_end_kwh.to_numpy()
            measured_c = c if boundary == 'AC_bus' else eta*c
            measured_b = b if boundary == 'AC_bus' else b/eta
            balance = q + data.pv_forecast_kwh.to_numpy() + b - data.load_kwh.to_numpy() - c - w
            checks = {
                'balance_kwh': float(np.max(np.abs(balance))),
                'state_kwh': float(np.max(np.abs(e1-e0-eta*c+b/eta))),
                'continuity_kwh': float(np.max(np.abs(e1[:-1]-e0[1:]))),
                'terminal_kwh': float(abs(e1[-1]-6000)),
                'initial_kwh': float(abs(e0[0]-6000)),
                'charge_limit_kw': float(max(0, np.max(measured_c)*6-5000)),
                'discharge_limit_kw': float(max(0, np.max(measured_b)*6-5000)),
                'lower_energy_kwh': float(max(0,1200-min(e0.min(),e1.min()))),
                'upper_energy_kwh': float(max(0,max(e0.max(),e1.max())-10800)),
                'mutex_kwh': float(np.max(np.minimum(c,b))),
                'negative_flows_kwh': float(max(0, -min(q.min(),c.min(),b.min(),w.min()))),
                'pv_disposal_bound_kwh': float(max(0,np.max(w-data.pv_forecast_kwh.to_numpy()))),
            }
            assert max(checks.values()) < 1e-6, checks
            assert abs(status['objective_yuan']-lp['objective_yuan']) < 1e-6
            frame.to_csv(OUT / f'{name}.csv', index=False)
            detail = {'scenario':name, 'physical_config':current, 'milp':status, 'lp_same_model':lp,
                      'independent_algebra_checks':checks,
                      'lp_note':'LP uses the same model builder; algebra checks independently recompute exported dispatch constraints.'}
            (OUT / f'{name}.json').write_text(json.dumps(detail, indent=2) + '\n')
            summaries.append({'scenario':name,'cost_yuan':status['objective_yuan'],'grid_kwh':float(q.sum()),
                              'eta_charge':eta,'eta_discharge':eta,'power_boundary':boundary,
                              'max_residual':max(checks.values()),'lp_gap_yuan':status['objective_yuan']-lp['objective_yuan']})
    comparison = pd.DataFrame(summaries)
    comparison['delta_vs_base_yuan'] = comparison.cost_yuan - comparison.cost_yuan.iloc[0]
    comparison.to_csv(OUT / 'comparison.csv', index=False)
    original = json.loads((WORK/'results/q1/baseline/summary.json').read_text())['cost_yuan']
    alternative = json.loads((WORK/'results/q1/roundtrip_90/summary.json').read_text())['cost_yuan']
    assert abs(comparison.cost_yuan.iloc[0]-original) < 1e-6
    assert abs(comparison.cost_yuan.iloc[2]-alternative) < 1e-6
    evidence = {'passed':True,'milp_solves':4,'lp_solves':4,'algebra_checks':48,
                'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
                'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'baseline_cost_reproduced':True,'roundtrip_cost_reproduced':True,
                'scope':'Q1 one-day physical convention sensitivity, not annual robustness or a choice of official convention.'}
    (OUT/'validation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(comparison.to_string(index=False))


if __name__ == '__main__':
    main()
