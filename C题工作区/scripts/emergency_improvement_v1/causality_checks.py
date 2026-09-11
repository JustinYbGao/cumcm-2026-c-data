"""Integration metamorphic checks; deliberately perturb future source data, then recompute decisions."""
import hashlib
import json
import numpy as np
import pandas as pd
from policy import ROOT, WORK, forecast_at, risk_adjustment, plan_day, reserve_schedule, execute, write_json
from run_experiments import actual_data


def replay_input(actual, cfg):
    records=[]; out=[]; energy=6000.
    price=pd.read_csv(ROOT/'inputs/fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    for day in pd.date_range('2025-01-02','2025-01-26'):
        load,pv,meta=forecast_at(actual,day,cfg['forecast_model'])
        f=actual.loc[actual.date==str(day.date())].copy()
        if day>=pd.Timestamp('2025-01-15'):
            a=pd.concat(records,ignore_index=True)
            delta,_=risk_adjustment(a,day,cfg['residual_days'],cfg['tau']) if cfg['risk'] else (np.zeros(144),{})
            plan,_,_,_=plan_day(load,pv,delta,price,energy,cfg)
            reserve=reserve_schedule(price,load-pv,plan['grid_kwh'],cfg['eta_discharge']) if cfg['executor']=='reserve' else np.zeros(144)
            for i,(_,row) in enumerate(f.iterrows()):
                e=execute(max(0.,plan['grid_kwh'][i]),row.load_actual_kwh,row.pv_actual_kwh,energy,
                          cfg['eta_charge'],cfg['eta_discharge'],cfg['power_basis'],reserve[i])
                energy=e['energy_end_actual_kwh']
                out.append({'date':str(day.date()),'interval_start':row.interval_start,'load_forecast':load[i],
                            'pv_forecast':pv[i],'risk_delta':delta[i],'grid':plan['grid_kwh'][i],
                            'reserve':reserve[i],**e})
        f['net_residual_kwh']=f.load_actual_kwh-f.pv_actual_kwh-load+pv
        f['residual_available_time']=str(day+pd.Timedelta(days=1))
        records.append(f)
    return pd.DataFrame(out)


def main():
    original=actual_data(); changed=original.copy()
    cutoff=pd.Timestamp('2025-01-25T12:00:00')
    mask=pd.to_datetime(changed.interval_start)>=cutoff
    changed.loc[mask,'load_actual_kwh'] += 800.
    changed.loc[mask,'pv_actual_kwh'] *= .5
    configs=json.loads((WORK/'configs/emergency_improvement_v1/experiments.json').read_text())['runs'][:5]
    checks=[]
    for cfg in configs:
        a=replay_input(original,cfg); b=replay_input(changed,cfg)
        numeric=a.select_dtypes(include='number').columns
        earlier=pd.to_datetime(a.interval_start)<cutoff
        midnight=a.date<='2025-01-25'
        plan_cols=['load_forecast','pv_forecast','risk_delta','grid','reserve']
        diff=float(np.max(np.abs(a.loc[earlier,numeric].to_numpy()-b.loc[earlier,numeric].to_numpy())))
        plan_diff=float(np.max(np.abs(a.loc[midnight,plan_cols].to_numpy()-b.loc[midnight,plan_cols].to_numpy())))
        later=a.date=='2025-01-26'
        response=float(np.max(np.abs(a.loc[later,['load_forecast','pv_forecast','risk_delta','grid']].to_numpy()-b.loc[later,['load_forecast','pv_forecast','risk_delta','grid']].to_numpy())))
        checks.append({'policy':cfg['policy'],'prefix_max_difference_kwh':diff,
                       'already_frozen_plans_max_difference_kwh':plan_diff,'next_day_positive_control_difference_kwh':response,
                       'prefix_rows':int(earlier.sum()),'passed':diff<=1e-6 and plan_diff<=1e-6 and response>1e-4})
        folder=ROOT/'causality';folder.mkdir(exist_ok=True)
        a.to_csv(folder/f"{cfg['policy']}_original.csv",index=False);b.to_csv(folder/f"{cfg['policy']}_future_mutated.csv",index=False)
        print(checks[-1],flush=True)
    write_json(WORK/'reports/emergency_improvement_v1/causality_validation.json',
               {'passed':all(c['passed'] for c in checks),'mutation_cutoff':str(cutoff),
                'mutation':'All future load +800 kWh and future PV ×0.5; in-memory data copy only',
                'method':'Raw source to rolling forecast archive to risk calibration to state-dependent plan to interval execution, rerun independently per input',
                'scope':'Five policies; January boundary test, not exhaustive formal proof. Current-interval realization remains an explicit inherited assumption.',
                'checks':checks,'script_sha256':hashlib.sha256(open(__file__,'rb').read()).hexdigest()})
    assert all(c['passed'] for c in checks)


if __name__=='__main__':main()
