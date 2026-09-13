"""Matched historical comparisons, with no production model imports or tuning."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[2]
ROOT=WORK/'results/storage_control_v6'
REPORT=WORK/'reports/storage_control_v6'
NU=.6895775

def read(path):return pd.read_csv(path,float_precision='round_trip')
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def paired_record(candidate,reference,purpose,c,r,c_end,r_end):
    if not c.index.equals(r.index):raise ValueError('paired dates differ')
    values=r.total_cost_yuan-c.total_cost_yuan
    month=values.groupby(values.index.str[:7]).sum()
    total=float(values.sum());reference_total=float(r.total_cost_yuan.sum())
    row=dict(candidate=candidate,reference=reference,purpose=purpose,total_saving_yuan=total,
        saving_percent=100*total/reference_total if reference_total else None,
        contract_saving_yuan=float((r.contract_cost_yuan-c.contract_cost_yuan).sum()),
        emergency_saving_yuan=float((r.emergency_cost_yuan-c.emergency_cost_yuan).sum()),
        winning_days=int((values>0).sum()),losing_days=int((values<0).sum()),tied_days=int((values==0).sum()),
        losing_months=','.join(month.index[month<0]),winning_months=int((month>0).sum()),
        inventory_adjusted_saving_yuan=total+NU*(c_end-r_end))
    # Identical resampling draws for every comparison: fixed 20260915 seed.
    rng=np.random.default_rng(20260915)
    for block in [7,14]:
        start=rng.integers(0,len(values),size=(2000,int(np.ceil(len(values)/block))))
        indices=((start[:,:,None]+np.arange(block))%len(values)).reshape(2000,-1)[:,:len(values)]
        low,high=np.quantile(values.to_numpy()[indices].sum(axis=1),[.025,.975])
        row.update({f'block{block}_lower_yuan':float(low),f'block{block}_upper_yuan':float(high),f'block{block}_crosses_zero':bool(low<=0<=high)})
    day_rows=[dict(candidate=candidate,reference=reference,date=k,saving_yuan=float(v)) for k,v in values.items()]
    month_rows=[dict(candidate=candidate,reference=reference,month=k,saving_yuan=float(v)) for k,v in month.items()]
    return row,day_rows,month_rows

def main():
    config=json.loads((WORK/'configs/storage_control_v6/experiments.json').read_text())
    rows=[];daily={};ends={};sources={}
    for name,cfg in config['policies'].items():
        folder=ROOT/'runs'/name
        summary=json.loads((folder/'summary.json').read_text());ledger=read(folder/'ledger.csv')
        if len(ledger)!=48096 or ledger.date.nunique()!=334:raise ValueError('Incomplete annual path '+name)
        row=dict(summary,base_policy=name.rsplit('_',1)[0],stage='matched_v6',source_ledger=str((folder/'ledger.csv').relative_to(WORK)))
        reserve=ledger.reserve_threshold_kwh.to_numpy();energy=ledger.energy_start_actual_kwh.to_numpy()
        deficit=np.maximum(ledger.load_actual_kwh-ledger.pv_actual_kwh-ledger.grid_effective_kwh,0)
        greedy=np.minimum(np.minimum(deficit,5000/6),np.maximum(.9*(energy-1200),0))
        held=np.maximum(greedy-ledger.discharge_actual_kwh,0)
        row.update(reserve_above_floor_intervals=int((reserve>1200+1e-6).sum()),
            deliberate_retention_intervals=int((held>1e-6).sum()),
            withheld_discharge_kwh=float(held.sum()),
            emergency_while_retaining_intervals=int(((held>1e-6)&(ledger.emergency_kwh>1e-6)).sum()),
            emergency_intervals=int((ledger.emergency_kwh>1e-7).sum()))
        rows.append(row);daily[name]=ledger.groupby('date')[['total_cost_yuan','contract_cost_yuan','emergency_cost_yuan']].sum()
        ends[name]=float(ledger.energy_end_actual_kwh.iloc[-1]);sources[name]={'path':row['source_ledger'],'sha256':hashlib.sha256((folder/'ledger.csv').read_bytes()).hexdigest()}
    comparison=pd.DataFrame(rows);comparison.to_csv(ROOT/'comparison_all.csv',index=False)
    selected={'q1':'baseline'}
    for branch in ['q2','q3','q42','q43']:
        eligible=comparison.loc[(comparison.branch==branch)&(comparison.control=='reserve')]
        selected[branch]=eligible.sort_values(['total_cost_yuan','emergency_cost_yuan'],kind='stable').iloc[0].policy
    write(ROOT/'selection.json',dict(rule='minimum unrounded reserve-arm historical total, emergency fee, then frozen matrix order; greedy benchmarks retained separately',selected=selected,historical_exploration=True))
    pairs=[]
    for name in config['policies']:
        if name.endswith('_reserve'):pairs.append((name,name.removesuffix('_reserve')+'_greedy','storage-control freedom; matched four-search protocol'))
    for arm in ['greedy','reserve']:
        pairs.extend([(f'q3_soc_{arm}',f'q3_no_update_{arm}','state feedback and paid revisions'),
            (f'q3_raw_{arm}',f'q3_soc_{arm}','incremental raw PV updates'),
            (f'q3_w28_{arm}',f'q3_raw_{arm}','Q3 PV correction'),
            (f'q42_ols_{arm}',f'q42_fixed_{arm}','Q42 planning-price input'),
            (f'q43_raw_ols_{arm}',f'q43_raw_fixed_{arm}','Q43 planning-price input raw PV'),
            (f'q43_w28_ols_{arm}',f'q43_raw_ols_{arm}','Q43 PV correction OLS price'),
            (f'q43_w28_fixed_{arm}',f'q43_raw_fixed_{arm}','Q43 PV correction fixed price')])
    # Frozen v5 is a named historical reference with its original two-search budget.
    frozen={'q2':'results/q2_direct_v4/runs/D112','q3':'results/unified_direct_v5/runs/q3_raw','q42':'results/unified_direct_v5/runs/q42_fixed','q43':'results/unified_direct_v5/runs/q43_raw_ols'}
    for branch,rel in frozen.items():
        name='frozen_v5_'+branch;path=WORK/rel/'ledger.csv';f=read(path)
        if branch=='q2':f['contract_cost_yuan']=f.planned_cost_yuan
        daily[name]=f.groupby('date')[['total_cost_yuan','contract_cost_yuan','emergency_cost_yuan']].sum();ends[name]=float(f.energy_end_actual_kwh.iloc[-1])
        sources[name]={'path':str(path.relative_to(WORK)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        pairs.append((selected[branch],name,'selected reserve versus frozen two-search v5; combined controller/search/selection change'))
    records=[];day_rows=[];month_rows=[]
    for c,r,purpose in pairs:
        row,days,months=paired_record(c,r,purpose,daily[c],daily[r],ends[c],ends[r]);records.append(row);day_rows.extend(days);month_rows.extend(months)
    pd.DataFrame(records).to_csv(ROOT/'paired_summary.csv',index=False)
    pd.DataFrame(day_rows).to_csv(ROOT/'paired_daily.csv',index=False);pd.DataFrame(month_rows).to_csv(ROOT/'paired_monthly.csv',index=False)
    months=[]
    for name,day in daily.items():
        frame=day.groupby(day.index.str[:7]).sum().reset_index(names='month');frame['policy']=name;months.append(frame)
    pd.concat(months).to_csv(ROOT/'monthly_all.csv',index=False)
    write(REPORT/'analysis_sources.json',dict(sources=sources,bootstrap=dict(seed=20260915,replicates=2000,blocks=[7,14],identical_draws_across_pairs=True,scope='descriptive fixed historical paths, not selection-adjusted or new physical simulations')))
    write(REPORT/'analysis_summary.json',dict(policies=len(rows),pairs=len(records),selected=selected,
        monetary_identity_max_error=max(abs(r['total_saving_yuan']-r['contract_saving_yuan']-r['emergency_saving_yuan']) for r in records),
        original_results_modified=False))
    print(json.dumps(selected,ensure_ascii=False,indent=2));print(comparison[['policy','total_cost_yuan','emergency_cost_yuan','deliberate_retention_intervals']].to_string(index=False))
if __name__=='__main__':main()
