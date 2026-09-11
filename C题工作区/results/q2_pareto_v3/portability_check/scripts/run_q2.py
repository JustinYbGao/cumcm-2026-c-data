"""Causal Q2 baseline: historical forecasts, daily MILP, fixed commitments and actual replay."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

WORK=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
from solve_q1 import solve_model

for key in ['TMPDIR','TMP','TEMP']:
    os.environ[key]=str(WORK/'data/interim/q2')


def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def fourier(k):
    time=np.arange(144)/144
    return np.column_stack([np.ones(144)]+[f(2*np.pi*j*time) for j in range(1,k+1) for f in [np.sin,np.cos]])


def forecast_day(history,day,kind,cfg):
    day=pd.Timestamp(day)
    if len(history) and (pd.to_datetime(history.interval_end)>day).any():
        raise ValueError('future observation in forecast history')
    if len(history)==0:
        return np.full(144,np.nan),np.full(144,np.nan),{'method':'cold_start_zero_commitment','history_end':None}
    if len(history)%144:
        raise ValueError('forecast history requires complete days')
    dates=pd.to_datetime(history.date.unique())
    loads=history.load_actual_kwh.to_numpy().reshape(-1,144)
    pvs=history.pv_actual_kwh.to_numpy().reshape(-1,144)
    n=len(loads)
    load=loads[-7 if n>=7 else -1].copy()
    pv=pvs[-1].copy()
    meta={'method':kind,'history_end':str(pd.Timestamp(history.interval_end.iloc[-1])),
          'load_method':'lag7' if n>=7 else 'lag1','pv_method':'lag1'}
    if kind!='seasonal' and n>=7+cfg['min_load_training_days']:
        f=fourier(cfg['load_harmonics'])
        def design(i,date):
            weekday=np.tile([float(date.weekday()==k) for k in range(1,7)],(144,1))
            return np.column_stack([f,loads[i-1]/1000,loads[i-7]/1000,weekday])
        first=max(7,n-cfg['load_training_days'])
        x=np.vstack([design(i,dates[i]) for i in range(first,n)])
        y=loads[first:].ravel()
        beta,_,rank,s=np.linalg.lstsq(x,y,rcond=None)
        load=np.maximum(design(n,day)@beta,0)
        meta.update(load_method='OLS_lag1_lag7_weekday_fourier',load_coefficients=beta.tolist(),
                    load_rank=int(rank),load_columns=x.shape[1],load_condition=float(s[0]/s[-1]),
                    load_training_first=str(dates[first].date()),load_training_last=str(dates[-1].date()))
    if kind=='linear_harmonic' and n>=2:
        window=min(n,cfg['pv_training_days'])
        f=fourier(cfg['pv_harmonics'])
        x=np.tile(f,(window,1))
        y=pvs[-window:].ravel()
        beta=np.linalg.lstsq(x,y,rcond=None)[0]
        residual=y-x@beta
        denom=float(residual[:-1]@residual[:-1])
        phi=float(np.clip((residual[:-1]@residual[1:])/denom if denom>1e-12 else 0.,-cfg['ar1_bound'],cfg['ar1_bound']))
        pv=np.maximum(f@beta+phi**np.arange(1,145)*residual[-1],0)
        meta.update(pv_method='rolling_harmonic_AR1',pv_coefficients=beta.tolist(),pv_phi=phi,
                    pv_last_residual=float(residual[-1]),pv_training_first=str(dates[-window].date()),
                    pv_training_last=str(dates[-1].date()))
    return load,pv,meta


def execute_interval(grid,load,pv,energy,eta_c,eta_d,storage=True):
    net=grid+pv-load
    c=d=emergency=surplus=0.
    if net>=0:
        c=min(net,5000/6,max(0.,(10800-energy)/eta_c)) if storage else 0.
        surplus=net-c
    else:
        d=min(-net,5000/6,max(0.,eta_d*(energy-1200))) if storage else 0.
        emergency=-net-d
    # Bookkeeping convention: use PV first; disposal of already-paid grid energy is separate.
    unused_grid=min(grid,surplus)
    return {'charge_actual_kwh':c,'discharge_actual_kwh':d,'emergency_kwh':emergency,
            'surplus_kwh':surplus,'unused_grid_kwh':unused_grid,'pv_curtailment_kwh':surplus-unused_grid,
            'energy_start_actual_kwh':energy,'energy_end_actual_kwh':energy+eta_c*c-d/eta_d}


def summarize(frame):
    d=frame.copy()
    d['load_abs_error_kwh']=(d.load_forecast_kwh-d.load_actual_kwh).abs()
    d['pv_abs_error_kwh']=(d.pv_forecast_kwh-d.pv_actual_kwh).abs()
    sums=['grid_plan_kwh','emergency_kwh','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan',
          'charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']
    daily=d.groupby('date')[sums].sum()
    daily['energy_start_actual_kwh']=d.groupby('date').energy_start_actual_kwh.first()
    daily['energy_end_actual_kwh']=d.groupby('date').energy_end_actual_kwh.last()
    daily['load_mae_kwh']=d.groupby('date').load_abs_error_kwh.mean()
    daily['pv_mae_kwh']=d.groupby('date').pv_abs_error_kwh.mean()
    daily['emergency_intervals']=d.assign(count=d.emergency_kwh>1e-6).groupby('date')['count'].sum()
    return daily.reset_index()


def save_run(folder,frame,meta):
    folder.mkdir(parents=True,exist_ok=True)
    frame.to_csv(folder/'ledger.csv',index=False)
    daily=summarize(frame)
    daily.to_csv(folder/'daily.csv',index=False)
    write_json(folder/'models_and_solvers.json',meta)
    totals={key:float(frame[key].sum()) for key in ['grid_plan_kwh','emergency_kwh','planned_cost_yuan',
            'emergency_cost_yuan','total_cost_yuan','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']}
    totals.update(days=int(frame.date.nunique()),intervals=len(frame),
                  initial_energy_kwh=float(frame.energy_start_actual_kwh.iloc[0]),
                  final_energy_kwh=float(frame.energy_end_actual_kwh.iloc[-1]))
    for source in ['load','pv']:
        error=frame[source+'_forecast_kwh']-frame[source+'_actual_kwh']
        totals[source+'_mae_kwh']=float(error.abs().mean())
        totals[source+'_rmse_kwh']=float(np.sqrt((error**2).mean()))
    positive=frame.pv_actual_kwh>0
    totals['pv_positive_actual_mae_kwh']=float((frame.loc[positive,'pv_forecast_kwh']-frame.loc[positive,'pv_actual_kwh']).abs().mean())
    write_json(folder/'summary.json',totals)
    return totals


def main():
    cfg=json.loads((WORK/'configs/q2_baseline.json').read_text())
    physical=json.loads((WORK/'configs/model_baseline.json').read_text())
    assert physical['battery']['min_energy_kwh']==1200 and physical['battery']['max_energy_kwh']==10800
    assert physical['battery']['max_charge_kw']==physical['battery']['max_discharge_kw']==5000
    out=WORK/'results/q2'
    out.mkdir(parents=True,exist_ok=True)
    files=[WORK/'data/processed/actual_10min.csv',WORK/'data/processed/fixed_price.csv',
           WORK/'configs/q2_baseline.json',WORK/'configs/model_baseline.json',WORK/'scripts/solve_q1.py',
           WORK/'scripts/run_q2.py']
    before={str(f.relative_to(WORK)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    write_json(out/'input_code_hashes.json',before)
    write_json(out/'config_snapshot.json',cfg)
    write_json(out/'physical_snapshot.json',physical)
    fields=['date','slot_id','interval_start','interval_end','available_time','load_actual_kwh','pv_actual_kwh']
    actual=pd.read_csv(files[0],usecols=fields,float_precision='round_trip')
    if len(actual)!=52560 or actual.groupby('date').size().ne(144).any(): raise ValueError('Incomplete annual data')
    price=pd.read_csv(files[1],float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    actual['interval_end']=pd.to_datetime(actual.interval_end)
    actual['interval_start']=pd.to_datetime(actual.interval_start)
    dates=pd.date_range('2025-01-01','2025-12-31')
    cache={}
    eta_c=physical['battery']['eta_charge']
    eta_d=physical['battery']['eta_discharge']
    def run(kind,start,end,initial,storage=True):
        energy=float(initial)
        frames=[]
        models=[]
        for day in pd.date_range(start,end):
            index=(day-dates[0]).days
            current=actual.iloc[index*144:(index+1)*144].reset_index(drop=True).copy()
            key=(kind,str(day.date()))
            if key not in cache:
                # Data boundary: only completed observations enter prediction.
                history=actual.iloc[:index*144].copy()
                cache[key]=forecast_day(history,day,kind,cfg)
            load,pv,model=cache[key]
            model=copy.deepcopy(model)
            params=copy.deepcopy(physical)
            params['battery']['initial_energy_kwh']=energy
            if index==0 or not storage:
                grid=np.zeros(144) if index==0 else np.maximum(load-pv,0)
                plan={'grid_kwh':grid,'charge_kwh':np.zeros(144),'discharge_kwh':np.zeros(144),
                      'energy_start_kwh':np.full(144,energy),'energy_end_kwh':np.full(144,energy),
                      'curtailment_kwh':np.zeros(144) if index==0 else np.maximum(pv-load,0),'charge_mode':np.zeros(144)}
                status={'status':'Cold start zero commitment' if index==0 else 'Analytic no storage','runtime_seconds':0.}
            else:
                data=pd.DataFrame({'price_yuan_per_kwh':price,'load_kwh':load,'pv_forecast_kwh':pv})
                plan,status=solve_model(data,params)
            current['issue_time']=str(day)
            current['price_yuan_per_kwh']=price
            current['load_forecast_kwh']=load
            current['pv_forecast_kwh']=pv
            for key,column in {'grid_kwh':'grid_plan_kwh','charge_kwh':'charge_plan_kwh','discharge_kwh':'discharge_plan_kwh',
                               'energy_start_kwh':'energy_start_plan_kwh','energy_end_kwh':'energy_end_plan_kwh',
                               'curtailment_kwh':'pv_curtailment_plan_kwh','charge_mode':'charge_mode_plan'}.items():
                current[column]=plan[key]
            events=[]
            for slot in range(144):
                event=execute_interval(max(0.,plan['grid_kwh'][slot]),current.load_actual_kwh.iloc[slot],
                                       current.pv_actual_kwh.iloc[slot],energy,eta_c,eta_d,storage)
                energy=event['energy_end_actual_kwh']
                events.append(event)
            for key in events[0]: current[key]=[e[key] for e in events]
            current['planned_cost_yuan']=price*current.grid_plan_kwh
            current['emergency_cost_yuan']=cfg['emergency_price_multiplier']*price*current.emergency_kwh
            current['total_cost_yuan']=current.planned_cost_yuan+current.emergency_cost_yuan
            frames.append(current)
            models.append({'date':str(day.date()),'forecast':model,'solver':status,'initial_energy_kwh':float(params['battery']['initial_energy_kwh'])})
            if day.day==1: print(kind,'storage' if storage else 'no_storage',day.date(),'SOC',round(energy,3),flush=True)
        return pd.concat(frames,ignore_index=True),models
    warm,meta=run('seasonal','2025-01-01','2025-01-31',6000.)
    save_run(out/'warmup',warm,meta)
    jan15=warm.loc[warm.date=='2025-01-15','energy_start_actual_kwh'].iloc[0]
    initial_feb=float(warm.energy_end_actual_kwh.iloc[-1])
    unit_value=float(price.mean()*eta_d)
    calibration=[]
    for kind in cfg['candidates']:
        frame,meta=run(kind,cfg['calibration_start'],cfg['calibration_end'],jan15)
        total=save_run(out/'calibration'/kind,frame,meta)
        calibration.append({'candidate':kind,**total,'inventory_adjusted_score_yuan':total['total_cost_yuan']-unit_value*(total['final_energy_kwh']-total['initial_energy_kwh'])})
    cal=pd.DataFrame(calibration)
    cal.to_csv(out/'calibration/comparison.csv',index=False)
    selected=str(cal.loc[cal.inventory_adjusted_score_yuan.idxmin(),'candidate'])
    write_json(out/'selection.json',{'selected':selected,'frozen_at':'2025-02-01T00:00:00',
               'calibration_last_available_time':'2025-02-01T00:00:00','inventory_value_yuan_per_kwh':unit_value,
               'common_evaluation_initial_energy_kwh':initial_feb,'selection_criterion':cfg['selection']})
    print('Frozen candidate:',selected,'common Feb1 SOC:',initial_feb,flush=True)
    comparisons=[]
    for policy,kind,storage in [('selected',selected,True),('seasonal','seasonal',True),('no_storage',selected,False)]:
        frame,meta=run(kind,cfg['evaluation_start'],cfg['evaluation_end'],initial_feb,storage)
        total=save_run(out/policy,frame,meta)
        total['inventory_adjusted_cost_yuan']=total['total_cost_yuan']-unit_value*(total['final_energy_kwh']-initial_feb)
        comparisons.append({'policy':policy,'forecast_model':kind,**total})
        # Full emergency-event export, plus the four dates and Q1-format tables required by Q2.
        mask=frame.emergency_kwh>1e-6
        events=frame.loc[mask,['date','interval_start','interval_end','emergency_kwh']].copy()
        events.to_csv(out/policy/'emergency_intervals.csv',index=False)
        representative=frame.loc[frame.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])].copy()
        representative.loc[representative.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_plan_kwh']].to_csv(out/policy/'table1_representative.csv',index=False)
        blocks=representative.assign(block_start_minute=(representative.slot_id-1)//24*240).groupby(['date','block_start_minute'])[['charge_actual_kwh','discharge_actual_kwh']].sum().reset_index()
        blocks['block_end_minute']=blocks.block_start_minute+240
        blocks.to_csv(out/policy/'table2_representative.csv',index=False)
        events.loc[events.date.isin(representative.date.unique())].to_csv(out/policy/'table3_representative.csv',index=False)
    pd.DataFrame(comparisons).to_csv(out/'comparison.csv',index=False)
    after={str(f.relative_to(WORK)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    assert before==after,'Input or implementation changed during the run'
    write_json(out/'run_status.json',{'completed':True,'inputs_unchanged':True,'selected':selected,
                                    'evaluation_days':334,'q3_q4_executed':False})
    print(pd.DataFrame(comparisons)[['policy','total_cost_yuan','emergency_kwh','final_energy_kwh']].to_string(index=False),flush=True)


if __name__=='__main__': main()
