"""Post-primary diagnostic: isolate PV refresh from feedback/reoptimization.

The additional control is specified after inspecting the six main policies. It
is explanatory ablation, not a newly selected policy on an untouched test set.
"""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
from run_q3 import WORK,write,solve_horizon,select_forecast,contract_fee,export_policy,execute_interval


def main():
    out=WORK/'results/q3_feedback_control'
    if (out/'run_status.json').exists():raise FileExistsError('Preserve finished diagnostic')
    cfg=json.loads((WORK/'configs/q3_baseline.json').read_text())
    cfg.update(policies={'state_feedback_only_A':{'rule':'A','update_hours':[6,12,18]}},pv_refresh=False,
        pv_forecast='Keep the midnight PV forecast at every decision; update actual state only',
        design_disclosure='Additional retrospective diagnostic specified after the six primary Q3 outcomes; not policy tuning or untouched-test evidence')
    physical=json.loads((WORK/'configs/model_baseline.json').read_text())
    files=['data/processed/actual_10min.csv','data/processed/fixed_price.csv','data/processed/pv_forecast_10min.csv',
        'results/q2/selected/ledger.csv','results/q2/selection.json','results/q3/no_update/summary.json',
        'configs/model_baseline.json','configs/q3_baseline.json','scripts/run_q3_feedback_control.py','scripts/run_q3.py','scripts/run_q2.py','scripts/solve_q1.py']
    hashes={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in files}
    write(out/'input_code_hashes.json',hashes);write(out/'config_snapshot.json',cfg);write(out/'physical_snapshot.json',physical)
    actual=pd.read_csv(WORK/files[0],float_precision='round_trip').groupby('date')
    prices=pd.read_csv(WORK/files[1],float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    forecasts=pd.read_csv(WORK/files[2],float_precision='round_trip')
    for col in ['issue_time','interval_start','interval_end']:forecasts[col]=pd.to_datetime(forecasts[col])
    by_issue=forecasts.groupby('issue_time')
    loads=pd.read_csv(WORK/files[3],usecols=['date','load_forecast_kwh'],float_precision='round_trip').groupby('date')
    initial=json.loads((WORK/files[4]).read_text())['common_evaluation_initial_energy_kwh']
    energy=initial;frames=[];versions=[];solvers=[];b=physical['battery']
    for day in pd.date_range(cfg['evaluation_start'],cfg['evaluation_end']):
        date=str(day.date());day_initial=energy;rows=actual.get_group(date).reset_index(drop=True)
        load=loads.get_group(date).load_forecast_kwh.to_numpy()
        forecast=select_forecast(by_issue.get_group(day),day,day+pd.Timedelta(days=1))
        original=None;events=[]
        for slot in range(144):
            if slot%36==0:
                issue=day+pd.Timedelta(minutes=10*slot);f=forecast.iloc[slot:].reset_index(drop=True)
                plan,status=solve_horizon(load[slot:],f.pv_forecast_kwh.to_numpy(),prices[slot:],energy,day_initial,physical,
                    original=None if original is None else original[slot:],rule='A')
                if original is None:original=plan['grid_kwh'].copy()
                version=pd.DataFrame({'date':date,'issue_hour':slot//6,'issue_time':str(issue),'pv_issue_time':str(day),
                    'slot_id':np.arange(slot+1,145),'interval_start':f.interval_start,'interval_end':f.interval_end,
                    'load_forecast_kwh':load[slot:],'pv_forecast_kwh':f.pv_forecast_kwh,
                    'endpoint_rule':f.endpoint_rule,'endpoint_issue_time':f.endpoint_issue_time,'grid_original_kwh':original[slot:]})
                for key,value in plan.items():version[key]=value
                version['contract_cost_forecast_yuan']=contract_fee(original[slot:],plan['grid_kwh'],prices[slot:],'A')
                versions.append(version)
                solvers.append({'date':date,'issue_hour':slot//6,'issue_time':str(issue),'pv_issue_time':str(day),
                    'horizon_intervals':144-slot,'initial_energy_kwh':energy,'terminal_target_kwh':day_initial,
                    'load_issue_time':date+' 00:00:00','solver':status})
                active=slot
            k=slot-active;row=rows.iloc[slot];q=max(0.,float(plan['grid_kwh'][k]))
            event=execute_interval(q,row.load_actual_kwh,row.pv_actual_kwh,energy,b['eta_charge'],b['eta_discharge'])
            energy=event['energy_end_actual_kwh']
            event.update(date=date,slot_id=slot+1,interval_start=row.interval_start,interval_end=row.interval_end,
                active_issue_hour=active//6,load_actual_kwh=row.load_actual_kwh,pv_actual_kwh=row.pv_actual_kwh,
                load_forecast_kwh=load[slot],pv_forecast_kwh=float(f.pv_forecast_kwh.iloc[k]),pv_issue_time=str(day),
                grid_original_kwh=float(original[slot]),grid_effective_kwh=q,price_yuan_per_kwh=prices[slot])
            events.append(event)
        frame=pd.DataFrame(events);delta=frame.grid_effective_kwh-frame.grid_original_kwh
        frame['original_cost_yuan']=prices*frame.grid_original_kwh
        frame['increase_cost_yuan']=1.5*prices*np.maximum(delta,0)
        frame['decrease_adjustment_yuan']=-.5*prices*np.maximum(-delta,0)
        frame['contract_cost_yuan']=frame.original_cost_yuan+frame.increase_cost_yuan+frame.decrease_adjustment_yuan
        frame['emergency_cost_yuan']=5*prices*frame.emergency_kwh
        frame['total_cost_yuan']=frame.contract_cost_yuan+frame.emergency_cost_yuan
        frames.append(frame)
        if day.day==1:print(date,'actual SOC',energy,flush=True)
    policy='state_feedback_only_A'
    total=export_policy(out/policy,pd.concat(frames,ignore_index=True),pd.concat(versions,ignore_index=True),solvers,'A')
    baseline=json.loads((WORK/'results/q3/no_update/summary.json').read_text())['total_cost_yuan']
    total.update(policy=policy,inventory_adjusted_cost_yuan=total['total_cost_yuan']-prices.mean()*b['eta_discharge']*(energy-initial),
        saving_yuan_vs_no_update=baseline-total['total_cost_yuan'],saving_percent_vs_no_update=100*(baseline-total['total_cost_yuan'])/baseline)
    pd.DataFrame([total]).to_csv(out/'comparison.csv',index=False)
    assert hashes=={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in files}
    write(out/'run_status.json',{'completed':True,'inputs_unchanged':True,'policies':[policy],'evaluation_days':334,
        'formal_excel_exported':False,'q4_executed':False})
    print(json.dumps(total,indent=2),flush=True)


if __name__=='__main__':main()
