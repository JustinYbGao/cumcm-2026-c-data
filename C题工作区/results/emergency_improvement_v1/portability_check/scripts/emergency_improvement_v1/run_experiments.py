"""Build historical releases, reproduce frozen baselines and replay preregistered Q2 policies."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from policy import ROOT, WORK, INPUTS, forecast_at, risk_adjustment, plan_day, execute, reserve_schedule, write_json

PROTOCOL = WORK/'configs/emergency_improvement_v1/experiments.json'
FIELDS = ['date','slot_id','interval_start','interval_end','available_time','load_actual_kwh','pv_actual_kwh']
PLAN_MAP = {'grid_kwh':'grid_plan_kwh','charge_kwh':'charge_plan_kwh','discharge_kwh':'discharge_plan_kwh',
            'energy_start_kwh':'energy_start_plan_kwh','energy_end_kwh':'energy_end_plan_kwh',
            'curtailment_kwh':'pv_curtailment_plan_kwh','charge_mode':'charge_mode_plan'}
SUMS = ['grid_plan_kwh','emergency_kwh','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan',
        'charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']


def actual_data():
    return pd.read_csv(INPUTS/'actual_10min.csv', usecols=FIELDS, float_precision='round_trip')


def build_forecasts():
    actual = actual_data()
    for kind in ['linear_harmonic','seasonal']:
        folder = ROOT/'forecasts'; folder.mkdir(exist_ok=True)
        frames, metadata = [], []
        for day in pd.date_range('2025-01-02','2025-12-31'):
            load, pv, model = forecast_at(actual, day, kind)
            current = actual.loc[actual.date == str(day.date())].copy()
            current['issue_time'] = str(day)
            current['history_end'] = model['history_end']
            current['load_forecast_kwh'] = load; current['pv_forecast_kwh'] = pv
            current['net_residual_kwh'] = current.load_actual_kwh-current.pv_actual_kwh-load+pv
            current['residual_available_time'] = str(day+pd.Timedelta(days=1))
            frames.append(current)
            metadata.append({'date':str(day.date()), 'forecast':model})
        pd.concat(frames,ignore_index=True).to_csv(folder/f'{kind}.csv',index=False)
        write_json(folder/f'{kind}_models.json', metadata)
        print('FORECASTS',kind,len(metadata),flush=True)


def run_one(cfg, stage='runs'):
    folder = ROOT/stage/cfg['policy']; folder.mkdir(parents=True,exist_ok=False)
    write_json(folder/'config.json',cfg)
    archive = pd.read_csv(ROOT/f"forecasts/{cfg['forecast_model']}.csv", float_precision='round_trip')
    models = {x['date']:x['forecast'] for x in json.loads((ROOT/f"forecasts/{cfg['forecast_model']}_models.json").read_text())}
    actual = actual_data()
    price = pd.read_csv(INPUTS/'fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    energy = cfg['initial_energy_kwh']; frames = []; logs = []; wall = time.perf_counter()
    for day in pd.date_range(cfg['start'],cfg['end']):
        ds = str(day.date())
        current = actual.loc[actual.date==ds].copy().reset_index(drop=True)
        f = archive.loc[archive.date==ds]
        load = f.load_forecast_kwh.to_numpy(); pv = f.pv_forecast_kwh.to_numpy()
        delta, risk = risk_adjustment(archive,day,cfg['residual_days'],cfg['tau'])
        if not cfg['risk']: delta = np.zeros(144)
        if not cfg['risk']:
            risk = {'risk_history_start':'','risk_history_end':'','risk_sample_count':0,'risk_history_days':0,'risk_cold_start':False}
        initial = energy
        plan, status, lr, pr = plan_day(load,pv,delta,price,energy,cfg)
        reserve = reserve_schedule(price,load-pv,plan['grid_kwh'],cfg['eta_discharge']) if cfg['executor']=='reserve' else np.zeros(144)
        current['issue_time'] = str(day)
        current['forecast_history_end'] = models[ds]['history_end']
        current['dispatch_time'] = current.interval_end
        current['decision_input_cutoff'] = current.interval_end
        current['price_yuan_per_kwh'] = price
        current['load_forecast_kwh'] = load; current['pv_forecast_kwh'] = pv
        current['plan_load_kwh'] = lr; current['plan_pv_kwh'] = pr
        current['risk_delta_kwh'] = delta; current['reserve_internal_kwh'] = reserve
        for key,value in risk.items(): current[key] = value
        for key,column in PLAN_MAP.items(): current[column] = plan[key]
        events=[]
        for t in range(144):
            event = execute(max(0.,float(plan['grid_kwh'][t])),float(current.load_actual_kwh.iloc[t]),
                            float(current.pv_actual_kwh.iloc[t]),energy,cfg['eta_charge'],cfg['eta_discharge'],cfg['power_basis'],float(reserve[t]))
            energy = event['energy_end_actual_kwh']; events.append(event)
        for key in events[0]: current[key] = [e[key] for e in events]
        current['planned_cost_yuan'] = price*current.grid_plan_kwh
        current['emergency_cost_yuan'] = 5*price*current.emergency_kwh
        current['total_cost_yuan'] = current.planned_cost_yuan+current.emergency_cost_yuan
        frames.append(current)
        logs.append({'date':ds,'forecast':models[ds],'risk':risk,'solver':status,'initial_energy_kwh':initial})
    frame = pd.concat(frames,ignore_index=True)
    frame.to_csv(folder/'ledger.csv',index=False)
    plan_fields = ['date','slot_id','issue_time','forecast_history_end','load_forecast_kwh','pv_forecast_kwh',
                   'plan_load_kwh','plan_pv_kwh','risk_delta_kwh']+list(PLAN_MAP.values())
    frame[plan_fields].to_csv(folder/'plans.csv',index=False)
    daily = frame.groupby('date')[SUMS].sum()
    daily['energy_start_actual_kwh'] = frame.groupby('date').energy_start_actual_kwh.first()
    daily['energy_end_actual_kwh'] = frame.groupby('date').energy_end_actual_kwh.last()
    daily.to_csv(folder/'daily.csv')
    summary = {key:float(frame[key].sum()) for key in SUMS}
    inventory_unit = float(price.mean()*cfg['eta_discharge'])
    summary.update(policy=cfg['policy'],days=int(frame.date.nunique()),intervals=len(frame),
                   initial_energy_kwh=cfg['initial_energy_kwh'], final_energy_kwh=float(energy),
                   inventory_value_yuan_per_kwh=inventory_unit,
                   inventory_adjusted_cost_yuan=summary['total_cost_yuan']-inventory_unit*(energy-cfg['initial_energy_kwh']),
                   emergency_share_of_load=float(frame.emergency_kwh.sum()/frame.load_actual_kwh.sum()),
                   emergency_intervals=int((frame.emergency_kwh>1e-6).sum()),
                   emergency_days=int(frame.loc[frame.emergency_kwh>1e-6,'date'].nunique()),
                   solver_runtime_seconds=sum(l['solver']['runtime_seconds'] for l in logs),
                   solver_max_runtime_seconds=max(l['solver']['runtime_seconds'] for l in logs),
                   solver_max_mip_gap=max(l['solver']['mip_gap'] for l in logs),
                   solver_failures=0,solver_fallbacks=0,wall_seconds=time.perf_counter()-wall)
    write_json(folder/'summary.json',summary); write_json(folder/'models_and_solvers.json',logs)
    print('DONE',stage,cfg['policy'],f"total={summary['total_cost_yuan']:.9f}",f"emergency={summary['emergency_cost_yuan']:.6f}",flush=True)
    return summary


def compare_original():
    rows=[]
    for policy,old in [('B0','selected'),('B1','seasonal')]:
        a=pd.read_csv(ROOT/f'runs/{policy}/ledger.csv',float_precision='round_trip')
        b=pd.read_csv(INPUTS/f'baseline_{policy}.csv',float_precision='round_trip')
        fields=['load_forecast_kwh','pv_forecast_kwh']+list(PLAN_MAP.values())+SUMS+['energy_start_actual_kwh','energy_end_actual_kwh']
        delta={key:float(np.abs(a[key]-b[key]).max()) for key in dict.fromkeys(fields)}
        rows.append({'policy':policy,'max_segment_difference':max(delta.values()),
                     'total_cost_difference_yuan':float(a.total_cost_yuan.sum()-b.total_cost_yuan.sum()),'column_differences':delta})
    write_json(ROOT/'baseline_reproduction.json',rows)
    print('BASELINE_REPRODUCTION',json.dumps(rows),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['forecasts','baselines','january','january_pe','main','sensitivity'])
    parser.add_argument('--policies', nargs='+', help='Run a declared subset at independent-validation gates')
    args=parser.parse_args(); configs=json.loads(PROTOCOL.read_text())['runs']
    if args.action=='forecasts': build_forecasts();return
    choose={'baselines':['B0','B1'],'january':['B0','B1','P','E'],'january_pe':['PE'],
            'main':['P','E','PE'],'sensitivity':[c['policy'] for c in configs if c['group']!='main']}[args.action]
    if args.policies:
        assert set(args.policies) <= set(choose)
        choose=args.policies
    for original in configs:
        if original['policy'] not in choose: continue
        cfg=dict(original);stage='runs'
        if args.action.startswith('january'):
            cfg.update(start='2025-01-15',end='2025-01-31',initial_energy_kwh=6000.);stage='january'
        run_one(cfg,stage)
    if args.action=='baselines':compare_original()


if __name__=='__main__':main()
