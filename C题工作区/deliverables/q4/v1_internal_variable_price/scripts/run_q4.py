"""Q4 actual-price settlement with causal price forecasts and labeled perfect-price controls."""
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
from run_q3 import WORK,write,solve_horizon,select_forecast,contract_fee,export_policy,execute_interval

for key in ['TMPDIR','TMP','TEMP']:os.environ[key]=str(WORK/'data/interim/q4')


def forecast_price(history,issue,cfg):
    """Only completed observations are accepted; future actual prices cannot be passed."""
    issue=pd.Timestamp(issue);h=history.copy()
    h['interval_start']=pd.to_datetime(h.interval_start);h['interval_end']=pd.to_datetime(h.interval_end)
    if h.interval_end.gt(issue).any():raise ValueError('future actual price in history')
    if h.empty or h.interval_end.iloc[-1]!=issue:raise ValueError('Incomplete price history')
    series=h.set_index('interval_start').actual_price_yuan_per_kwh
    if series.index.has_duplicates or not series.index.equals(pd.date_range(series.index[0],issue,freq='10min',inclusive='left')):
        raise ValueError('Noncontinuous price history')
    start=max(series.index[0]+pd.Timedelta(days=7),issue-pd.Timedelta(days=cfg['price_training_days']))
    train=pd.date_range(start,issue,freq='10min',inclusive='left')
    if len(train)<144:raise ValueError('Insufficient price training history')
    target=pd.date_range(issue,issue.normalize()+pd.Timedelta(days=1),freq='10min',inclusive='left')
    def design(times):
        phase=(times.hour*60+times.minute).to_numpy()/1440
        cols=[np.ones(len(times))]
        for k in range(1,cfg['price_harmonics']+1):cols.extend([np.sin(2*np.pi*k*phase),np.cos(2*np.pi*k*phase)])
        cols.extend([series.loc[times-pd.Timedelta(days=1)].to_numpy(),series.loc[times-pd.Timedelta(days=7)].to_numpy()])
        cols.extend([(times.weekday==k).astype(float) for k in range(1,7)])
        return np.column_stack(cols)
    x=design(train);y=series.loc[train].to_numpy();beta,_,rank,s=np.linalg.lstsq(x,y,rcond=None)
    raw=design(target)@beta;floor=cfg['price_floor_yuan_per_kwh'];values=np.maximum(raw,floor)
    meta={'method':'rolling_OLS','issue_time':str(issue),'training_first_start':str(train[0]),
        'training_last_end':str(train[-1]+pd.Timedelta(minutes=10)),'training_rows':len(train),
        'feature_count':x.shape[1],'rank':int(rank),'condition':float(s[0]/s[-1]) if s[-1]>0 else None,
        'coefficients':beta.tolist(),'floor_yuan_per_kwh':floor,'floor_activations':int((raw<floor).sum()),
        'raw_forecast_min':float(raw.min()),'raw_forecast_max':float(raw.max())}
    return values,meta


def bill(frame,rule):
    f=frame.copy();p=f.price_actual_yuan_per_kwh;delta=f.grid_effective_kwh-f.grid_original_kwh
    f['price_yuan_per_kwh']=p
    f['original_cost_yuan']=p*f.grid_original_kwh
    f['increase_cost_yuan']=1.5*p*np.maximum(delta,0)
    f['decrease_adjustment_yuan']=(-.5 if rule=='A' else .5)*p*np.maximum(-delta,0)
    f['contract_cost_yuan']=f.original_cost_yuan+f.increase_cost_yuan+f.decrease_adjustment_yuan
    f['emergency_cost_yuan']=5*p*f.emergency_kwh
    f['total_cost_yuan']=f.contract_cost_yuan+f.emergency_cost_yuan
    return f


def main():
    cfg=json.loads((WORK/'configs/q4_baseline.json').read_text())
    physical=json.loads((WORK/'configs/model_baseline.json').read_text());out=WORK/'results/q4'
    if (out/'run_status.json').exists():raise FileExistsError('Preserve completed Q4 result; use a new version')
    names=['data/processed/actual_10min.csv','data/processed/fixed_price.csv','data/processed/pv_forecast_10min.csv',
        'results/q2/selected/ledger.csv','results/q2/selected/models_and_solvers.json','results/q2/selection.json',
        'configs/q4_baseline.json','configs/model_baseline.json','scripts/run_q4.py','scripts/run_q3.py','scripts/run_q2.py','scripts/solve_q1.py']
    hashes={name:hashlib.sha256((WORK/name).read_bytes()).hexdigest() for name in names}
    write(out/'input_code_hashes.json',hashes);write(out/'config_snapshot.json',cfg);write(out/'physical_snapshot.json',physical)
    actual=pd.read_csv(WORK/names[0],float_precision='round_trip')
    for col in ['interval_start','interval_end']:actual[col]=pd.to_datetime(actual[col])
    fixed=pd.read_csv(WORK/names[1],float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    rawpv=pd.read_csv(WORK/names[2],float_precision='round_trip')
    for col in ['issue_time','interval_start','interval_end']:rawpv[col]=pd.to_datetime(rawpv[col])
    bypv={k:f for k,f in rawpv.groupby('issue_time')};days={k:f.reset_index(drop=True) for k,f in actual.groupby('date')}
    q2=pd.read_csv(WORK/names[3],usecols=['date','load_forecast_kwh','pv_forecast_kwh'],float_precision='round_trip')
    byq2={k:f.reset_index(drop=True) for k,f in q2.groupby('date')}
    initial=json.loads((WORK/names[5]).read_text())['common_evaluation_initial_energy_kwh']
    price_cache={};price_frames=[];price_models=[]
    price_history=actual[['interval_start','interval_end','actual_price_yuan_per_kwh']]
    for day in pd.date_range(cfg['evaluation_start'],cfg['evaluation_end']):
        for hour in [0,6,12,18]:
            issue=day+pd.Timedelta(hours=hour)
            predicted,meta=forecast_price(price_history.loc[price_history.interval_end<=issue],issue,cfg)
            price_cache[issue]=predicted;price_models.append(meta)
            targets=pd.date_range(issue,day+pd.Timedelta(days=1),freq='10min',inclusive='left')
            lag=price_history.set_index('interval_start').loc[targets-pd.Timedelta(days=7)].actual_price_yuan_per_kwh.to_numpy()
            price_frames.append(pd.DataFrame({'issue_time':str(issue),'interval_start':targets,
                'interval_end':targets+pd.Timedelta(minutes=10),'price_forecast_yuan_per_kwh':predicted,'lag7_forecast_yuan_per_kwh':lag}))
    pd.concat(price_frames,ignore_index=True).to_csv(out/'price_forecasts.csv',index=False)
    write(out/'price_models.json',price_models)
    print('Price models complete',len(price_models),'floor activations',sum(m['floor_activations'] for m in price_models),flush=True)
    totals=[];b=physical['battery']
    for policy,settings in cfg['policies'].items():
        energy=initial;frames=[];versions=[];statuses=[]
        for day in pd.date_range(cfg['evaluation_start'],cfg['evaluation_end']):
            date=str(day.date());end=day+pd.Timedelta(days=1);rows=days[date]
            load=byq2[date].load_forecast_kwh.to_numpy();day_initial=energy;original=None;events=[]
            actual_prices=rows.actual_price_yuan_per_kwh.to_numpy();hours=[0]+settings['update_hours']
            for slot in range(144):
                if slot in [6*h for h in hours]:
                    issue=day+pd.Timedelta(minutes=10*slot)
                    if settings['branch']=='4-2':
                        f=pd.DataFrame({'interval_start':rows.interval_start.iloc[slot:].to_numpy(),
                            'interval_end':rows.interval_end.iloc[slot:].to_numpy(),
                            'pv_forecast_kwh':byq2[date].pv_forecast_kwh.to_numpy()[slot:],
                            'endpoint_rule':'Q2_inherited','endpoint_issue_time':str(day)})
                    else:f=select_forecast(bypv[issue],issue,end)
                    kind=settings['price'];price_issue=day if kind=='hold0' else issue
                    if kind=='fixed':prices=fixed[slot:]
                    elif kind=='perfect':prices=actual_prices[slot:]
                    else:prices=price_cache[price_issue][slot:] if kind=='hold0' else price_cache[issue]
                    if np.any(prices<=0):raise ValueError('Planner requires strictly positive prices; inspect source')
                    plan,status=solve_horizon(load[slot:],f.pv_forecast_kwh.to_numpy(),prices,energy,day_initial,physical,
                        original=None if original is None else original[slot:],rule=settings['rule'])
                    if original is None:original=plan['grid_kwh'].copy()
                    version=pd.DataFrame({'date':date,'issue_hour':slot//6,'issue_time':str(issue),'price_issue_time':str(price_issue),
                        'price_method':kind,'price_forecast_yuan_per_kwh':prices,'slot_id':np.arange(slot+1,145),
                        'interval_start':f.interval_start,'interval_end':f.interval_end,'load_forecast_kwh':load[slot:],
                        'pv_forecast_kwh':f.pv_forecast_kwh,'endpoint_rule':f.endpoint_rule,'endpoint_issue_time':f.endpoint_issue_time,
                        'grid_original_kwh':original[slot:]})
                    for key,value in plan.items():version[key]=value
                    version['contract_cost_forecast_yuan']=contract_fee(original[slot:],plan['grid_kwh'],prices,settings['rule'])
                    versions.append(version)
                    statuses.append({'date':date,'issue_hour':slot//6,'issue_time':str(issue),'price_issue_time':str(price_issue),
                        'price_method':kind,'perfect_price_information':kind=='perfect','horizon_intervals':144-slot,
                        'initial_energy_kwh':energy,'terminal_target_kwh':day_initial,'load_issue_time':str(day),'solver':status})
                    active=slot
                k=slot-active;row=rows.iloc[slot];q=max(0.,float(plan['grid_kwh'][k]))
                event=execute_interval(q,row.load_actual_kwh,row.pv_actual_kwh,energy,b['eta_charge'],b['eta_discharge'])
                energy=event['energy_end_actual_kwh']
                event.update(date=date,slot_id=slot+1,interval_start=str(row.interval_start),interval_end=str(row.interval_end),
                    active_issue_hour=active//6,price_method=kind,price_issue_time=str(price_issue),
                    price_actual_yuan_per_kwh=actual_prices[slot],price_forecast_yuan_per_kwh=float(prices[k]),
                    load_actual_kwh=row.load_actual_kwh,pv_actual_kwh=row.pv_actual_kwh,load_forecast_kwh=load[slot],
                    pv_forecast_kwh=float(f.pv_forecast_kwh.iloc[k]),grid_original_kwh=float(original[slot]),grid_effective_kwh=q)
                events.append(event)
            frames.append(bill(pd.DataFrame(events),settings['rule']))
            if day.day==1:print(policy,date,'actual SOC',round(energy,3),flush=True)
        total=export_policy(out/policy,pd.concat(frames,ignore_index=True),pd.concat(versions,ignore_index=True),statuses,settings['rule'])
        total.update(policy=policy,branch=settings['branch'],price_method=settings['price'],
            inventory_adjusted_cost_yuan=total['total_cost_yuan']-fixed.mean()*b['eta_discharge']*(energy-initial))
        totals.append(total);print(policy,'actual cost',total['total_cost_yuan'],flush=True)
    comparison=pd.DataFrame(totals)
    refs={'4-2':float(comparison.loc[comparison.policy=='q42_fixed','total_cost_yuan'].iloc[0]),
        '4-3':float(comparison.loc[comparison.policy=='q43_all_A_fixed','total_cost_yuan'].iloc[0])}
    comparison['saving_yuan_vs_branch_fixed']=comparison.branch.map(refs)-comparison.total_cost_yuan
    comparison['saving_percent_vs_branch_fixed']=100*comparison.saving_yuan_vs_branch_fixed/comparison.branch.map(refs)
    comparison.to_csv(out/'comparison.csv',index=False)
    assert hashes=={name:hashlib.sha256((WORK/name).read_bytes()).hexdigest() for name in names}
    write(out/'run_status.json',{'completed':True,'inputs_unchanged':True,'policies':list(cfg['policies']),
        'evaluation_days':334,'formal_excel_exported':False,'q4_executed':True,'future_actual_price_only_in_labeled_perfect_branches':True})
    print(comparison[['policy','total_cost_yuan','emergency_kwh','saving_percent_vs_branch_fixed']].to_string(index=False),flush=True)


if __name__=='__main__':main()
