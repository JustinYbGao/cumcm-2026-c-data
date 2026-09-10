"""Independent audit from saved CSVs. Does not import optimization or table-export code."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]


def validate_frames(source, plan, summary, cfg, relaxed=False):
    b, tol = cfg['battery'], cfg['validation']['energy_atol_kwh']
    checks, residuals = {}, {}
    checks['row_count'] = len(source) == len(plan) == 144
    keys = ['slot_id','start_minute','end_minute']
    checks['time_keys'] = source[keys].equals(plan[keys])
    checks['time_grid'] = (source.start_minute.tolist() == list(range(0,1440,10)) and
                           source.end_minute.tolist() == list(range(10,1441,10)))
    cols = ['grid_kwh','charge_kwh','discharge_kwh','curtailment_kwh','energy_start_kwh','energy_end_kwh','charge_mode','cost_yuan']
    checks['finite'] = bool(np.isfinite(plan[cols].to_numpy()).all())
    if not checks['row_count'] or not checks['finite']:
        return {'passed':False,'checks':checks,'residuals':residuals}
    g,c,d,w,e0,e1,z,cost = [plan[k].to_numpy() for k in cols]
    p,l,pv = [source[k].to_numpy() for k in ['price_yuan_per_kwh','load_kwh','pv_forecast_kwh']]
    for key in ['price_yuan_per_kwh','load_kwh','pv_forecast_kwh']:
        checks['input_'+key] = bool(np.allclose(source[key],plan[key],rtol=0,atol=1e-10))
    def residual(name, values, limit=tol):
        r = float(np.max(np.abs(values)))
        residuals[name] = r
        checks[name] = r <= limit
    def upper(name, values, bound):
        r = float(max(0,np.max(np.asarray(values)-bound)))
        residuals[name] = r
        checks[name] = r <= tol
    residual('energy_balance', g+pv-w+d-l-c)
    residual('state_recursion', e1-e0-b['eta_charge']*c+d/b['eta_discharge'])
    residual('state_continuity', e0[1:]-e1[:-1])
    residual('initial_state', e0[0]-b['initial_energy_kwh'])
    residual('terminal_state', e1[-1]-b['initial_energy_kwh'])
    upper('capacity_upper',np.r_[e0,e1],b['max_energy_kwh'])
    upper('capacity_lower',-np.r_[e0,e1],-b['min_energy_kwh'])
    upper('nonnegative',-np.r_[g,c,d,w,z],0.)
    mc = b['max_charge_kw']*cfg['interval_minutes']/60
    md = b['max_discharge_kw']*cfg['interval_minutes']/60
    upper('charge_power',c,mc)
    upper('discharge_power',d,md)
    upper('curtailment_upper',w,pv)
    upper('mode_upper',z,1.)
    upper('charge_mode',c,mc*z)
    upper('discharge_mode',d,md*(1-z))
    if not relaxed:
        residual('integer_mode',z-np.rint(z),cfg['validation']['integer_atol'])
        residual('mutual_exclusion',np.minimum(c,d))
    residuals['simultaneous_charge_discharge_kwh'] = float(np.maximum(np.minimum(c,d),0).max())
    residual('interval_cost',cost-p*g,cfg['validation']['cost_atol_yuan'])
    for key, val in {'cost_yuan':np.dot(p,g), 'grid_kwh':sum(g), 'charge_kwh':sum(c),
                     'discharge_kwh':sum(d),'curtailment_kwh':sum(w)}.items():
        residual('summary_'+key, val-summary[key],cfg['validation']['cost_atol_yuan'] if key=='cost_yuan' else tol)
    return {'passed':all(checks.values()), 'checks':checks, 'residuals':residuals}


def read_csv(path):
    return pd.read_csv(path,float_precision='round_trip')


def main():
    root = WORK / 'results/q1'
    source = read_csv(WORK / 'data/processed/q1_day.csv')
    reports = {}
    sums = {}
    for name in ['baseline','roundtrip_90','baseline_lp','roundtrip_90_lp','no_storage','alternate']:
        folder = root/name
        cfg = json.loads((folder/'config_snapshot.json').read_text())
        plan = read_csv(folder/'schedule.csv')
        summary = json.loads((folder/'summary.json').read_text())
        sums[name] = summary
        r = validate_frames(source,plan,summary,cfg,relaxed=name.endswith('_lp'))
        tol = cfg['validation']['energy_atol_kwh']
        close = lambda a,b: bool(np.allclose(a,b,rtol=0,atol=tol))
        states = read_csv(folder/'states.csv')
        r['checks']['145_states'] = (states.minute.tolist()==list(range(0,1441,10)) and
                                    close(states.energy_kwh, np.r_[plan.energy_start_kwh.iloc[0],plan.energy_end_kwh]))
        t1 = read_csv(folder/'table1_intervals.csv')
        r['checks']['table1_times'] = t1.start_minute.tolist()==[600,720,840,960,1080,1200] and t1.end_minute.tolist()==[610,730,850,970,1090,1210]
        r['checks']['table1_values'] = close(t1.grid_kwh,[plan.loc[plan.start_minute==minute,'grid_kwh'].item() for minute in [600,720,840,960,1080,1200]])
        t2 = read_csv(folder/'table2_blocks.csv')
        r['checks']['table2_times'] = t2.block_start.tolist()==[0,240,480,720,960,1200] and t2.block_end.tolist()==[240,480,720,960,1200,1440]
        for field in ['charge_kwh','discharge_kwh']:
            expected = [plan.loc[(plan.start_minute>=start)&(plan.end_minute<=start+240),field].sum() for start in range(0,1440,240)]
            r['checks']['table2_'+field] = close(t2[field],expected)
        r['checks']['summary_endpoint_states'] = close([summary['initial_energy_kwh'],summary['terminal_energy_kwh']], [plan.energy_start_kwh.iloc[0],plan.energy_end_kwh.iloc[-1]])
        evidence = json.loads((folder/'solver_status.json').read_text())
        if name != 'no_storage':
            r['checks']['solver_optimal'] = evidence['status']=='Optimal'
            r['checks']['solver_objective'] = close(evidence['objective_yuan'],summary['cost_yuan'])
            if name in ['baseline','roundtrip_90']:
                r['checks']['lp_bound_and_gap'] = (-tol <= summary['cost_yuan']-evidence['lp_lower_bound_yuan'] <= tol and
                                                   abs(summary['cost_yuan']-evidence['lower_bound_yuan']) <= tol and evidence['mip_gap']<=1e-9)
        else:
            net = source.load_kwh-source.pv_forecast_kwh
            r['checks']['analytic_baseline'] = close(plan.grid_kwh,np.maximum(net,0)) and close(plan.curtailment_kwh,np.maximum(-net,0)) and close(plan.charge_kwh,0) and close(plan.discharge_kwh,0)
        r['passed'] = all(r['checks'].values())
        reports[name]=r
    comparison = read_csv(root/'comparison.csv').set_index('scenario')
    additional = {}
    for name in ['baseline','roundtrip_90','no_storage']:
        additional[name+'_comparison'] = all(abs(comparison.loc[name,key]-sums[name][key])<=1e-6 for key in ['cost_yuan','grid_kwh','charge_kwh','discharge_kwh','curtailment_kwh'])
        saving = sums['no_storage']['cost_yuan']-sums[name]['cost_yuan']
        additional[name+'_saving'] = abs(comparison.loc[name,'saving_yuan_vs_no_storage']-saving)<=1e-6 and abs(comparison.loc[name,'saving_percent_vs_no_storage']-saving/sums['no_storage']['cost_yuan']*100)<=1e-6
    sensitivity = json.loads((root/'efficiency_sensitivity.json').read_text())
    additional['sensitivity_cost'] = abs(sensitivity['cost_change_yuan']-(sums['roundtrip_90']['cost_yuan']-sums['baseline']['cost_yuan']))<=1e-6
    a = read_csv(root/'baseline/schedule.csv')
    b = read_csv(root/'roundtrip_90/schedule.csv')
    for key in ['grid_kwh','charge_kwh','discharge_kwh','energy_end_kwh']:
        delta=(b[key]-a[key]).abs()
        additional['sensitivity_'+key] = abs(sensitivity[key+'_l1_change']-delta.sum())<=1e-6 and abs(sensitivity[key+'_max_change']-delta.max())<=1e-6
    for name in ['baseline','roundtrip_90']:
        additional[name+'_saved_lp_bound'] = abs(sums[name]['cost_yuan']-sums[name+'_lp']['cost_yuan'])<=1e-6
    witness = json.loads((root/'nonuniqueness.json').read_text())
    alt = read_csv(root/'alternate/schedule.csv')
    fields = ['grid_kwh','charge_kwh','discharge_kwh','energy_end_kwh']
    max_difference = float(np.max(np.abs(alt[fields].to_numpy()-a[fields].to_numpy())))
    additional['alternative_witness'] = (abs(witness['cost_difference_yuan']-(sums['alternate']['cost_yuan']-sums['baseline']['cost_yuan']))<=1e-6
                                          and abs(witness['max_plan_difference_kwh']-max_difference)<=1e-6
                                          and sums['alternate']['cost_yuan']<=witness['cost_cap_yuan']+1e-6)
    before = json.loads((WORK/'logs/q1/input_hashes_before.json').read_text())
    after = json.loads((WORK/'logs/q1/input_hashes_after.json').read_text())
    additional['inputs_unchanged'] = before==after and all(hashlib.sha256((WORK.parent/p).read_bytes()).hexdigest()==v for p,v in before.items())
    output = {'passed':all(v['passed'] for v in reports.values()) and all(additional.values()),
              'scenarios':reports, 'cross_checks':{k:bool(v) for k,v in additional.items()},
              'independence':'separate CSV reader and physical/accounting formulas; no solver import; same source assumptions'}
    (root/'validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    for name,r in reports.items():
        print(name, 'PASS' if r['passed'] else 'FAIL',len(r['checks']),'checks',
              'balance',r['residuals'].get('energy_balance'),'state',r['residuals'].get('state_recursion'))
        for key,passed in r['checks'].items():
            if not passed: print('  FAILED:',key)
    print('Cross checks:', additional)
    sys.exit(0 if output['passed'] else 1)


if __name__ == '__main__':
    main()
