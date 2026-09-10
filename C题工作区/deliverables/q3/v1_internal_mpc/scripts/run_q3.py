"""Q3 causal PV-update MPC with explicit final-volume settlement A/B.

The Q2 load forecast is frozen at midnight; no current-day actual enters a solve.
Only the common quasi-static executor receives actual interval demand and PV.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
WORK=Path(__file__).resolve().parents[1]
import highspy
import numpy as np
import pandas as pd
from run_q2 import execute_interval

for key in ['TMPDIR','TMP','TEMP']:os.environ[key]=str(WORK/'data/interim/q3')


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def contract_fee(original,final,price,rule):
    delta=np.asarray(final)-np.asarray(original)
    if rule not in ('A','B'):raise ValueError('Unknown settlement')
    sign=-1 if rule=='A' else 1
    return price*(original+1.5*np.maximum(delta,0)+sign*.5*np.maximum(-delta,0))


def select_forecast(forecasts,issue,end):
    issue=pd.Timestamp(issue);end=pd.Timestamp(end)
    f=forecasts.loc[(forecasts.issue_time==issue)&(forecasts.interval_start>=issue)&
        (forecasts.interval_end<=end)].sort_values('interval_start').copy()
    wanted=pd.date_range(issue,end,freq='10min',inclusive='left')
    if (len(f)!=len(wanted) or not np.array_equal(pd.to_datetime(f.interval_start),wanted)
        or not np.array_equal(pd.to_datetime(f.interval_end),wanted+pd.Timedelta(minutes=10))):
        raise ValueError('PV forecast coverage mismatch; never fill from future issues')
    return f.reset_index(drop=True)


def solve_horizon(load,pv,price,initial,terminal,physical,original=None,rule='A',relaxed=False):
    """Q1 physical MILP, with separately specified rolling initial and day-end target."""
    n=len(load);b=physical['battery'];dt=physical['interval_minutes']/60
    mc=b['max_charge_kw']*dt;md=b['max_discharge_kw']*dt
    h=highspy.Highs();h.setOptionValue('output_flag',False)
    for key,value in physical['solver'].items():
        if key!='name':
            if h.setOptionValue(key,value)!=highspy.HighsStatus.kOk:raise ValueError(key)
    q=[h.addVariable(lb=float(original[t]) if original is not None and rule=='B' else 0,
        obj=float(price[t]) if original is None else 0,name=f'q_{t}') for t in range(n)]
    c=[h.addVariable(ub=mc,name=f'c_{t}') for t in range(n)]
    d=[h.addVariable(ub=md,name=f'b_{t}') for t in range(n)]
    # Surplus includes PV and paid grid energy: required for the B no-refund case.
    w=[h.addVariable(name=f'w_{t}') for t in range(n)]
    e=[h.addVariable(lb=b['min_energy_kwh'],ub=b['max_energy_kwh'],name=f'E_{t}') for t in range(n+1)]
    z=[h.addVariable(ub=1,type=highspy.HighsVarType.kContinuous if relaxed else highspy.HighsVarType.kInteger,name=f'z_{t}') for t in range(n)]
    h.addConstr(e[0]==initial);h.addConstr(e[-1]==terminal)
    for t in range(n):
        h.addConstr(q[t]+d[t]-c[t]-w[t]==float(load[t]-pv[t]))
        h.addConstr(e[t+1]==e[t]+b['eta_charge']*c[t]-(1/b['eta_discharge'])*d[t])
        h.addConstr(c[t]<=mc*z[t]);h.addConstr(d[t]<=md*(1-z[t]))
        if original is not None:
            v=h.addVariable(obj=1,name=f'fee_{t}')
            p=float(price[t]);base=float(original[t])
            h.addConstr(v>=1.5*p*q[t]-.5*p*base)
            if rule=='A':h.addConstr(v>=.5*p*q[t]+.5*p*base)
            elif rule=='B':h.addConstr(v>=-.5*p*q[t]+1.5*p*base)
            else:raise ValueError('Unknown settlement')
    h.run()
    if h.getModelStatus()!=highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(h.modelStatusToString(h.getModelStatus()))
    solution=h.getSolution();info=h.getInfo()
    values=lambda variables:np.array([solution.col_value[int(v)] for v in variables])
    state=values(e)
    plan={'grid_kwh':values(q),'charge_kwh':values(c),'discharge_kwh':values(d),'surplus_kwh':values(w),
        'energy_start_kwh':state[:-1],'energy_end_kwh':state[1:],'charge_mode':values(z)}
    obj=float(np.dot(price,plan['grid_kwh']) if original is None else contract_fee(original,plan['grid_kwh'],price,rule).sum())
    status={'status':'Optimal','objective_yuan':obj,'solver_objective_yuan':h.getObjectiveValue(),
        'lower_bound_yuan':h.getObjectiveValue() if relaxed else info.mip_dual_bound,
        'mip_gap':None if relaxed else info.mip_gap,'runtime_seconds':h.getRunTime(),
        'max_primal_infeasibility':info.max_primal_infeasibility,'relaxed':relaxed,
        'variables':h.getNumCol(),'constraints':h.getNumRow()}
    return plan,status


def export_policy(folder,ledger,versions,solvers,rule):
    folder.mkdir(parents=True,exist_ok=True)
    ledger.to_csv(folder/'ledger.csv',index=False)
    versions.to_csv(folder/'plan_versions.csv',index=False)
    write(folder/'solvers.json',solvers)
    fields=['grid_original_kwh','grid_effective_kwh','emergency_kwh','original_cost_yuan',
        'increase_cost_yuan','decrease_adjustment_yuan','contract_cost_yuan','emergency_cost_yuan','total_cost_yuan',
        'charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']
    daily=ledger.groupby('date')[fields].sum()
    daily['energy_start_actual_kwh']=ledger.groupby('date').energy_start_actual_kwh.first()
    daily['energy_end_actual_kwh']=ledger.groupby('date').energy_end_actual_kwh.last()
    daily['emergency_intervals']=ledger.assign(event=ledger.emergency_kwh>1e-6).groupby('date').event.sum()
    daily.to_csv(folder/'daily.csv')
    total={c:float(ledger[c].sum()) for c in fields}
    total.update(days=int(ledger.date.nunique()),intervals=len(ledger),rule=rule,
        initial_energy_kwh=float(ledger.energy_start_actual_kwh.iloc[0]),
        final_energy_kwh=float(ledger.energy_end_actual_kwh.iloc[-1]),
        emergency_intervals=int((ledger.emergency_kwh>1e-6).sum()),
        solves=len(solvers),solver_seconds=sum(s['solver']['runtime_seconds'] for s in solvers),
        max_mip_gap=max(s['solver']['mip_gap'] or 0 for s in solvers))
    write(folder/'summary.json',total)
    representative=ledger.loc[ledger.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
    representative.loc[representative.slot_id.isin([61,73,85,97,109,121]),
        ['date','interval_start','interval_end','grid_original_kwh','grid_effective_kwh']].to_csv(folder/'table1_representative.csv',index=False)
    blocks=representative.assign(block_start_minute=(representative.slot_id-1)//24*240).groupby(['date','block_start_minute'])[['charge_actual_kwh','discharge_actual_kwh']].sum().reset_index()
    blocks['block_end_minute']=blocks.block_start_minute+240
    blocks.to_csv(folder/'table2_representative.csv',index=False)
    events=[]
    for day,f in ledger.groupby('date',sort=False):
        active=f.loc[f.emergency_kwh>1e-6]
        for _,part in active.groupby(active.slot_id.diff().ne(1).cumsum()):
            events.append({'date':day,'interval_start':part.interval_start.iloc[0],
                'interval_end':part.interval_end.iloc[-1],'intervals':len(part),'emergency_kwh':float(part.emergency_kwh.sum())})
    events=pd.DataFrame(events,columns=['date','interval_start','interval_end','intervals','emergency_kwh'])
    events.to_csv(folder/'emergency_events.csv',index=False)
    events.loc[events.date.isin(representative.date.unique())].to_csv(folder/'table3_representative.csv',index=False)
    return total


def main():
    cfg=json.loads((WORK/'configs/q3_baseline.json').read_text())
    physical=json.loads((WORK/'configs/model_baseline.json').read_text())
    out=WORK/'results/q3'
    if (out/'run_status.json').exists():raise FileExistsError('Preserve completed Q3 run; use a new version')
    files=[WORK/p for p in ['data/processed/actual_10min.csv','data/processed/fixed_price.csv',
        'data/processed/pv_forecast_10min.csv','configs/q3_baseline.json','configs/model_baseline.json',
        'results/q2/selected/ledger.csv','results/q2/selection.json','results/q2/selected/models_and_solvers.json',
        'scripts/run_q3.py','scripts/run_q2.py','scripts/solve_q1.py']]
    hashes={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    write(out/'input_code_hashes.json',hashes);write(out/'config_snapshot.json',cfg);write(out/'physical_snapshot.json',physical)
    actual=pd.read_csv(files[0],usecols=['date','slot_id','interval_start','interval_end','load_actual_kwh','pv_actual_kwh'],float_precision='round_trip')
    price=pd.read_csv(files[1],float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    forecast=pd.read_csv(files[2],float_precision='round_trip')
    for col in ['issue_time','interval_start','interval_end']:forecast[col]=pd.to_datetime(forecast[col])
    by_issue={key:group for key,group in forecast.groupby('issue_time',sort=False)}
    loads=pd.read_csv(files[5],usecols=['date','slot_id','load_forecast_kwh','issue_time'],float_precision='round_trip')
    load_days={date:f.load_forecast_kwh.to_numpy() for date,f in loads.groupby('date',sort=False)}
    selection=json.loads(files[6].read_text());initial=selection['common_evaluation_initial_energy_kwh']
    actual_days={date:f.reset_index(drop=True) for date,f in actual.groupby('date',sort=False)}
    ec=physical['battery']['eta_charge'];ed=physical['battery']['eta_discharge']
    comparisons=[]
    for policy,settings in cfg['policies'].items():
        energy=initial;frames=[];all_versions=[];statuses=[]
        for day in pd.date_range(cfg['evaluation_start'],cfg['evaluation_end']):
            date=str(day.date());day_initial=energy;day_end=day+pd.Timedelta(days=1)
            load=load_days[date];actual_day=actual_days[date]
            scheduled=[0]+settings['update_hours'];original=None;events=[]
            for slot in range(144):
                if slot in [hour*6 for hour in scheduled]:
                    issue=day+pd.Timedelta(minutes=slot*10)
                    f=select_forecast(by_issue[issue],issue,day_end)
                    plan,status=solve_horizon(load[slot:],f.pv_forecast_kwh.to_numpy(),price[slot:],
                        energy,day_initial,physical,original=None if original is None else original[slot:],rule=settings['rule'])
                    if original is None:original=plan['grid_kwh'].copy()
                    version=pd.DataFrame({'date':date,'issue_hour':slot//6,'issue_time':str(issue),
                        'slot_id':np.arange(slot+1,145),'interval_start':f.interval_start,'interval_end':f.interval_end,
                        'load_forecast_kwh':load[slot:],'pv_forecast_kwh':f.pv_forecast_kwh,
                        'endpoint_rule':f.endpoint_rule,'endpoint_issue_time':f.endpoint_issue_time,
                        'grid_original_kwh':original[slot:]})
                    for key,value in plan.items():version[key]=value
                    version['contract_cost_forecast_yuan']=contract_fee(original[slot:],plan['grid_kwh'],price[slot:],settings['rule'])
                    all_versions.append(version)
                    statuses.append({'date':date,'issue_hour':slot//6,'issue_time':str(issue),
                        'horizon_intervals':144-slot,'initial_energy_kwh':energy,'terminal_target_kwh':day_initial,
                        'load_issue_time':date+' 00:00:00','solver':status})
                    active_slot=slot;active_hour=slot//6
                k=slot-active_slot;row=actual_day.iloc[slot]
                q=max(0.,float(plan['grid_kwh'][k]))
                event=execute_interval(q,row.load_actual_kwh,row.pv_actual_kwh,energy,ec,ed)
                energy=event['energy_end_actual_kwh']
                event.update(date=date,slot_id=slot+1,interval_start=row.interval_start,interval_end=row.interval_end,
                    active_issue_hour=active_hour,load_actual_kwh=row.load_actual_kwh,pv_actual_kwh=row.pv_actual_kwh,
                    load_forecast_kwh=load[slot],pv_forecast_kwh=float(f.pv_forecast_kwh.iloc[k]),
                    grid_original_kwh=float(original[slot]),grid_effective_kwh=q,price_yuan_per_kwh=price[slot])
                events.append(event)
            frame=pd.DataFrame(events)
            delta=frame.grid_effective_kwh-frame.grid_original_kwh
            frame['original_cost_yuan']=price*frame.grid_original_kwh
            frame['increase_cost_yuan']=1.5*price*np.maximum(delta,0)
            frame['decrease_adjustment_yuan']=(-.5 if settings['rule']=='A' else .5)*price*np.maximum(-delta,0)
            frame['contract_cost_yuan']=frame.original_cost_yuan+frame.increase_cost_yuan+frame.decrease_adjustment_yuan
            frame['emergency_cost_yuan']=5*price*frame.emergency_kwh
            frame['total_cost_yuan']=frame.contract_cost_yuan+frame.emergency_cost_yuan
            frames.append(frame)
            if day.day==1:print(policy,date,'actual SOC',round(energy,3),flush=True)
        total=export_policy(out/policy,pd.concat(frames,ignore_index=True),pd.concat(all_versions,ignore_index=True),statuses,settings['rule'])
        total['inventory_adjusted_cost_yuan']=total['total_cost_yuan']-price.mean()*ed*(total['final_energy_kwh']-initial)
        comparisons.append({'policy':policy,**total})
        print(policy,'cost',round(total['total_cost_yuan'],2),'emergency',round(total['emergency_kwh'],2),flush=True)
    comparison=pd.DataFrame(comparisons)
    reference=float(comparison.loc[comparison.policy=='no_update','total_cost_yuan'].iloc[0])
    comparison['saving_yuan_vs_no_update']=reference-comparison.total_cost_yuan
    comparison['saving_percent_vs_no_update']=100*comparison.saving_yuan_vs_no_update/reference
    comparison.to_csv(out/'comparison.csv',index=False)
    after={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert after==hashes,'Inputs or implementation changed during execution'
    write(out/'run_status.json',{'completed':True,'inputs_unchanged':True,'policies':list(cfg['policies']),
        'evaluation_days':334,'formal_excel_exported':False,'q4_executed':False})
    print(comparison[['policy','total_cost_yuan','saving_percent_vs_no_update','emergency_kwh']].to_string(index=False),flush=True)


if __name__=='__main__':main()
