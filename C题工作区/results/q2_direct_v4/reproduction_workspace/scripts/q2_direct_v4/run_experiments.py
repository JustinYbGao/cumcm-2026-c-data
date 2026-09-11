import argparse
import json
import time
from policy import WORK,ROOT,INPUTS,np,pd,decision,execute_interval,save_json,LABELS

SUMS=['grid_plan_kwh','planned_cost_yuan','emergency_kwh','emergency_cost_yuan','total_cost_yuan',
      'charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']


def run_one(cfg,stage='runs',actual=None,archive=None):
    folder=ROOT/stage/cfg['policy'];folder.mkdir(parents=True,exist_ok=False)
    save_json(folder/'config.json',cfg)
    actual=pd.read_csv(INPUTS/'actual_10min.csv',float_precision='round_trip') if actual is None else actual
    archive=pd.read_csv(ROOT/'forecasts/linear_harmonic.csv',float_precision='round_trip') if archive is None else archive
    price=pd.read_csv(INPUTS/'fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    frames=[];metadata=[];arrays=[];energy=cfg['initial_energy_kwh'];wall=time.perf_counter()
    for i,day in enumerate(pd.date_range(cfg['start'],cfg['end'])):
        ds=str(day.date()); f=archive.loc[archive.date==ds]
        load_hat=f.load_forecast_kwh.to_numpy();pv_hat=f.pv_forecast_kwh.to_numpy()
        d=decision(archive,day,load_hat,pv_hat,price,energy,cfg);k=d['selected'];q=d['q'][k]
        current=actual.loc[actual.date==ds].copy().reset_index(drop=True)
        current['issue_time']=str(day);current['forecast_history_end']=str(day)
        current['dispatch_time']=current.interval_end;current['decision_input_cutoff']=current.interval_end
        current['price_yuan_per_kwh']=price;current['load_forecast_kwh']=load_hat;current['pv_forecast_kwh']=pv_hat
        current['grid_plan_kwh']=q;current['selected_index']=k;current['selected_candidate']=LABELS[k]
        current['risk_delta_kwh']=d['risk_delta']
        initial=energy;events=[];nominal=[];forecast_energy=energy
        for t in range(144):
            event=execute_interval(float(q[t]),float(current.load_actual_kwh.iloc[t]),float(current.pv_actual_kwh.iloc[t]),energy,.9,.9)
            energy=event['energy_end_actual_kwh'];events.append(event)
            nom=execute_interval(float(q[t]),float(load_hat[t]),float(pv_hat[t]),forecast_energy,.9,.9)
            forecast_energy=nom['energy_end_actual_kwh'];nominal.append(nom)
        for col in events[0]:current[col]=[r[col] for r in events]
        for col in ['emergency_kwh','charge_actual_kwh','discharge_actual_kwh','energy_start_actual_kwh','energy_end_actual_kwh','surplus_kwh']:
            current['forecast_'+col.replace('_actual','')]=[r[col] for r in nominal]
        current['planned_cost_yuan']=price*q;current['emergency_cost_yuan']=5*price*current.emergency_kwh
        current['total_cost_yuan']=current.planned_cost_yuan+current.emergency_cost_yuan
        frames.append(current);arrays.append(d)
        metadata.append({'date':ds,'initial_energy_kwh':initial,'scenario_source_dates':d['source_dates'],
                         'scenario_count':len(d['source_dates']),'selected_index':k,'milp_initializer':d['milp'],
                         'optimizer':d['optimizer']})
        if i%30==0:print(cfg['policy'],ds,'total',sum(f.total_cost_yuan.sum() for f in frames),'seconds',time.perf_counter()-wall,flush=True)
    frame=pd.concat(frames,ignore_index=True);frame.to_csv(folder/'ledger.csv',index=False)
    frame[['date','slot_id','issue_time','forecast_history_end','load_forecast_kwh','pv_forecast_kwh','grid_plan_kwh',
           'risk_delta_kwh','selected_index','selected_candidate']].to_csv(folder/'plans.csv',index=False)
    daily=frame.groupby('date')[SUMS].sum()
    daily['energy_start_actual_kwh']=frame.groupby('date').energy_start_actual_kwh.first()
    daily['energy_end_actual_kwh']=frame.groupby('date').energy_end_actual_kwh.last()
    daily.to_csv(folder/'daily.csv')
    max_s=max(len(a['source_dates']) for a in arrays)
    pad=lambda x,shape:np.pad(x,[(0,n-m) for m,n in zip(x.shape,shape)],constant_values=np.nan)
    np.savez_compressed(folder/'decision_evidence.npz',q=np.stack([a['q'] for a in arrays]),
        initializer_plan=np.stack([a['initializer_plan'] for a in arrays]),
        risk_delta=np.stack([a['risk_delta'] for a in arrays]),scenario_net=np.stack([pad(a['scenarios'],(max_s,144)) for a in arrays]),
        emergency_fee=np.stack([pad(a['emergency_fee'],(6,max_s)) for a in arrays]),
        end_energy=np.stack([pad(a['end_energy'],(6,max_s)) for a in arrays]),
        score=np.stack([a['score'] for a in arrays]),ordinary=np.stack([a['ordinary'] for a in arrays]),
        selected_index=np.asarray([a['selected'] for a in arrays]))
    save_json(folder/'decisions.json',{'candidate_labels':LABELS,'days':metadata})
    summary={col:float(frame[col].sum()) for col in SUMS}
    opts=[o for day in metadata for o in day['optimizer']]
    summary.update(policy=cfg['policy'],days=len(metadata),intervals=len(frame),initial_energy_kwh=cfg['initial_energy_kwh'],
        final_energy_kwh=float(energy),inventory_adjusted_cost_yuan=summary['total_cost_yuan']-.6895775*(energy-cfg['initial_energy_kwh']),
        optimizer_count=len(opts),optimizer_success_count=sum(o['success'] for o in opts),
        optimizer_nfev=sum(o['nfev'] for o in opts),optimizer_total_wall_seconds=sum(o['wall_seconds'] for o in opts),
        optimizer_max_wall_seconds=max(o['wall_seconds'] for o in opts),milp_count=len(metadata),
        milp_total_runtime_seconds=sum(d['milp_initializer']['runtime_seconds'] for d in metadata),
        milp_max_runtime_seconds=max(d['milp_initializer']['runtime_seconds'] for d in metadata),
        wall_seconds=time.perf_counter()-wall)
    save_json(folder/'summary.json',summary)
    print('DONE',stage,cfg['policy'],summary['total_cost_yuan'],summary['emergency_cost_yuan'],flush=True)
    return frame


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['january','runs']);parser.add_argument('--policies',nargs='+')
    parser.add_argument('--refinement',action='store_true')
    args=parser.parse_args()
    for cfg in json.loads((WORK/'configs/q2_direct_v4'/('refinement.json' if args.refinement else 'experiments.json')).read_text())['runs']:
        if args.policies and cfg['policy'] not in args.policies:continue
        if args.stage=='january':cfg=dict(cfg,start='2025-01-15',end='2025-01-18',initial_energy_kwh=6000.)
        run_one(cfg,args.stage)
