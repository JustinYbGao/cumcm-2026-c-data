"""Ten bounded continuous direct-procurement policies; fail rather than overwrite."""
import argparse
import json
import os
import time
from pathlib import Path
import numpy as np
import pandas as pd
from inputs import Inputs,ROOT,WORK
from policy import decision,LABELS
from compat import execute_interval

for key in ['TMPDIR','TMP','TEMP']:os.environ[key]=str(ROOT/'runtime')
POLICIES={
 'q3_no_update':{'branch':'q3','price':'fixed','updates':False,'pv_update':False,'corrected':False},
 'q3_soc':{'branch':'q3','price':'fixed','updates':True,'pv_update':False,'corrected':False},
 'q3_raw':{'branch':'q3','price':'fixed','updates':True,'pv_update':True,'corrected':False},
 'q3_w28':{'branch':'q3','price':'fixed','updates':True,'pv_update':True,'corrected':True},
 'q42_ols':{'branch':'q42','price':'ols','updates':False,'pv_update':False,'corrected':False},
 'q42_fixed':{'branch':'q42','price':'fixed','updates':False,'pv_update':False,'corrected':False},
 'q43_raw_ols':{'branch':'q43','price':'ols','updates':True,'pv_update':True,'corrected':False},
 'q43_w28_ols':{'branch':'q43','price':'ols','updates':True,'pv_update':True,'corrected':True},
 'q43_raw_fixed':{'branch':'q43','price':'fixed','updates':True,'pv_update':True,'corrected':False},
 'q43_w28_fixed':{'branch':'q43','price':'fixed','updates':True,'pv_update':True,'corrected':True},
}
SUMS=['grid_original_kwh','grid_effective_kwh','emergency_kwh','original_cost_yuan','increase_cost_yuan','decrease_adjustment_yuan','contract_cost_yuan','emergency_cost_yuan','total_cost_yuan','charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']


def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def run_one(name,stage='runs',start='2025-02-01',end='2025-12-31',initial=7268.4231640740745,data=None):
    cfg=POLICIES[name];folder=ROOT/stage/name;folder.mkdir(parents=True,exist_ok=False);(folder/'evidence').mkdir()
    write(folder/'config.json',dict(policy=name,**cfg,start=start,end=end,initial_energy_kwh=initial,scenario_window=112,kappa=5,mu=.38232))
    data=Inputs(with_pv=cfg['branch']!='q42') if data is None else data
    energy=initial;frames=[];versions=[];metadata=[];tic=time.perf_counter()
    for date in pd.date_range(start,end).strftime('%Y-%m-%d'):
        rows=data.days[date];q0=None;current=None;events=[];issuehours=[0,6,12,18] if cfg['updates'] else [0]
        for slot in range(144):
            if slot in [6*h for h in issuehours]:
                hour=slot//6;source_hour=hour if cfg['pv_update'] else 0;issue=pd.Timestamp(date)+pd.Timedelta(hours=hour)
                load,pv,raw,net,risk,dates,pvmeta=data.scenarios(date,hour,source_hour,cfg['corrected'])
                price,price_meta=data.prices(issue,cfg['price'])
                base=None if q0 is None else q0[slot:].copy();held=None if current is None else current[slot:].copy()
                d=decision(load,pv,net,risk,price,energy,slot,data.physical,base,held)
                selected=int(d['selected_index']);q=d['q'][selected]
                if q0 is None:q0=q.copy();current=q.copy()
                else:current[slot:]=q
                relative='evidence/'+date+f'_{hour:02d}.npz'
                arrays={key:d[key] for key in ['q','risk_delta','score','ordinary','emergency_fee','end_energy','selected_index']}
                arrays.update(scenario_net=net,price=price,load_hat=load,pv_hat=pv,raw_pv=raw,q0=np.array([]) if base is None else base,current=np.array([]) if held is None else held)
                arrays.update({'initializer_'+k:v for k,v in d['initializer_plan'].items()})
                np.savez_compressed(folder/relative,**arrays)
                metadata.append({'date':date,'issue_hour':hour,'source_hour':source_hour,'correction':cfg['corrected'],'price_method':cfg['price'],
                    'initial_energy_kwh':float(energy),'scenario_source_dates':dates,'scenario_count':len(dates),'selected_index':selected,
                    'candidate_labels':LABELS[:len(d['q'])],'evidence_file':relative,'optimizer':d['optimizer'],'milp_initializer':d['milp_initializer'],
                    'initializer_failure':d['initializer_failure'],'pv_metadata':pvmeta,'price_metadata':price_meta,'issue_time':str(issue)})
                versions.append(pd.DataFrame({'date':date,'issue_hour':hour,'issue_time':str(issue),'slot_id':np.arange(slot+1,145),
                    'interval_start':rows.interval_start.iloc[slot:].to_numpy(),'interval_end':rows.interval_end.iloc[slot:].to_numpy(),
                    'grid_original_kwh':q0[slot:],'grid_kwh':q,'load_forecast_kwh':load,'pv_forecast_kwh':pv,'pv_raw_forecast_kwh':raw,
                    'price_forecast_yuan_per_kwh':price,'selected_index':selected}))
                active_slot=slot;active_hour=hour
            row=rows.iloc[slot];event=execute_interval(float(current[slot]),float(row.load_actual_kwh),float(row.pv_actual_kwh),energy,.9,.9)
            energy=event['energy_end_actual_kwh']
            event.update(date=date,slot_id=slot+1,interval_start=str(row.interval_start),interval_end=str(row.interval_end),
                active_issue_hour=active_hour,load_actual_kwh=float(row.load_actual_kwh),pv_actual_kwh=float(row.pv_actual_kwh),
                load_forecast_kwh=float(load[slot-active_slot]),pv_forecast_kwh=float(pv[slot-active_slot]),
                grid_original_kwh=float(q0[slot]),grid_effective_kwh=float(current[slot]),
                price_yuan_per_kwh=float(data.fixed[slot] if cfg['branch']=='q3' else row.actual_price_yuan_per_kwh))
            events.append(event)
        f=pd.DataFrame(events);p=f.price_yuan_per_kwh;delta=f.grid_effective_kwh-f.grid_original_kwh
        f['original_cost_yuan']=p*f.grid_original_kwh;f['increase_cost_yuan']=1.5*p*np.maximum(delta,0)
        f['decrease_adjustment_yuan']=-.5*p*np.maximum(-delta,0);f['contract_cost_yuan']=f.original_cost_yuan+f.increase_cost_yuan+f.decrease_adjustment_yuan
        f['emergency_cost_yuan']=5*p*f.emergency_kwh;f['total_cost_yuan']=f.contract_cost_yuan+f.emergency_cost_yuan
        frames.append(f)
        if date.endswith('-01'):print(name,date,'seconds',round(time.perf_counter()-tic,2),flush=True)
    ledger=pd.concat(frames,ignore_index=True);ledger.to_csv(folder/'ledger.csv',index=False)
    pd.concat(versions,ignore_index=True).to_csv(folder/'plan_versions.csv',index=False);write(folder/'decisions.json',metadata)
    daily=ledger.groupby('date')[SUMS].sum();daily['energy_start_actual_kwh']=ledger.groupby('date').energy_start_actual_kwh.first();daily['energy_end_actual_kwh']=ledger.groupby('date').energy_end_actual_kwh.last();daily.to_csv(folder/'daily.csv')
    opts=[o for d in metadata for o in d['optimizer']]
    summary={key:float(ledger[key].sum()) for key in SUMS}
    summary.update(policy=name,branch=cfg['branch'],price_method=cfg['price'],days=len(frames),intervals=len(ledger),initial_energy_kwh=initial,final_energy_kwh=float(energy),
        optimizer_count=len(opts),optimizer_success_count=sum(o['success'] for o in opts),optimizer_non_success_count=sum(not o['success'] for o in opts),
        optimizer_exception_count=sum(o['exception'] is not None for o in opts),initializer_fallback_count=sum(d['initializer_failure'] is not None for d in metadata),
        retained_start_selected_count=sum(d['selected_index'] in [0,3] for d in metadata),keep_current_selected_count=sum(d['selected_index']==6 for d in metadata),
        optimizer_nfev=sum(o['nfev'] for o in opts),optimizer_total_wall_seconds=sum(o['wall_seconds'] for o in opts),
        milp_total_runtime_seconds=sum(d['milp_initializer']['runtime_seconds'] for d in metadata),wall_seconds=time.perf_counter()-tic,
        inventory_adjusted_cost_yuan=summary['total_cost_yuan']-.6895775*(energy-initial),
        emergency_margin_yuan=1000000.-summary['emergency_cost_yuan'],passes_emergency_reference=summary['emergency_cost_yuan']<=1000000.)
    write(folder/'summary.json',summary)
    print('DONE',name,summary['total_cost_yuan'],summary['emergency_cost_yuan'],flush=True)
    return ledger


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--policies',nargs='+',default=list(POLICIES));parser.add_argument('--stage',default='runs');parser.add_argument('--start',default='2025-02-01');parser.add_argument('--end',default='2025-12-31');parser.add_argument('--initial',type=float,default=7268.4231640740745);args=parser.parse_args()
    for name in args.policies:run_one(name,args.stage,args.start,args.end,args.initial)
