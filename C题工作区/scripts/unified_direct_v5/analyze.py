"""Historical selection and paired comparisons without parameter search."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from run import POLICIES,SUMS,write
from inputs import WORK,ROOT,read
from markdown_table import markdown

REPORT=WORK/'reports/unified_direct_v5'
OLD={
 'Q2_D112':('q2','results/q2_direct_v4/runs/D112'),
 'Q2_B0':('q2','results/q2_direct_v4/references/B0'),
 'Q2_B1':('q2','results/q2_direct_v4/references/B1'),
 'Q2_v3_best':('q2','results/q2_direct_v4/references/X_strong_morning85'),
 'Q2_D56_risk625':('q2','results/q2_direct_v4/runs/D56_risk625'),
 'old_q3_no_update':('q3','results/q3/no_update'),
 'old_q3_soc':('q3','results/q3_feedback_control/state_feedback_only_A'),
 'old_q3_raw':('q3','results/robustness/fixed_raw'),
 'old_q3_w28':('q3','results/robustness/fixed_w28'),
 'old_q42_ols':('q42','results/q4/q42_ols'),
 'old_q42_fixed':('q42','results/q4/q42_fixed'),
 'old_q43_raw_ols':('q43','results/robustness/variable_raw'),
 'old_q43_w28_ols':('q43','results/robustness/variable_w28'),
 'old_q43_raw_fixed':('q43','results/q4/q43_all_A_fixed'),
}


def normalize(folder):
    f=read(folder/'ledger.csv')
    if 'grid_plan_kwh' in f:
        f['grid_original_kwh']=f.grid_plan_kwh;f['grid_effective_kwh']=f.grid_plan_kwh
        f['original_cost_yuan']=f.planned_cost_yuan;f['contract_cost_yuan']=f.planned_cost_yuan
        f['increase_cost_yuan']=0.;f['decrease_adjustment_yuan']=0.
    return f


def main():
    paths={k:(v['branch'],ROOT/'runs'/k,'new_direct') for k,v in POLICIES.items()}
    paths.update({k:(group,WORK/path,'old_reference') for k,(group,path) in OLD.items()})
    rows=[];daily={};ledgers={}
    for name,(branch,path,stage) in paths.items():
        f=normalize(path);ledgers[name]=f;d=f.groupby('date')[SUMS].sum();daily[name]=d
        source=json.loads((path/'summary.json').read_text())
        row={key:float(f[key].sum()) for key in SUMS}
        start=float(f.energy_start_actual_kwh.iloc[0]);end=float(f.energy_end_actual_kwh.iloc[-1])
        row.update(policy=name,branch=branch,stage=stage,source_ledger=str((path/'ledger.csv').relative_to(WORK)),
            initial_energy_kwh=start,final_energy_kwh=end,days=f.date.nunique(),intervals=len(f),
            normal_cost_yuan=row['contract_cost_yuan'] if branch in ['q2','q42'] else None,
            unused_grid_cost_yuan=float((f.unused_grid_kwh*f.price_yuan_per_kwh).sum()),
            inventory_adjusted_cost_yuan=row['total_cost_yuan']-.6895775*(end-start),
            emergency_margin_yuan=1e6-row['emergency_cost_yuan'],passes_emergency_reference=row['emergency_cost_yuan']<=1e6,
            emergency_days=int((d.emergency_kwh>1e-7).sum()),emergency_intervals=int((f.emergency_kwh>1e-7).sum()))
        for key in ['wall_seconds','optimizer_count','optimizer_success_count','optimizer_non_success_count','optimizer_exception_count','initializer_fallback_count','retained_start_selected_count','keep_current_selected_count','optimizer_nfev','optimizer_total_wall_seconds','milp_total_runtime_seconds']:
            row[key]=source.get(key)
        if row['optimizer_non_success_count'] is None and source.get('optimizer_count') is not None:row['optimizer_non_success_count']=source['optimizer_count']-source['optimizer_success_count']
        rows.append(row)
    comparison=pd.DataFrame(rows);comparison.to_csv(ROOT/'comparison_all.csv',index=False)
    selected={}
    for branch in ['q3','q42','q43']:
        eligible=comparison.loc[(comparison.branch==branch)&(comparison.stage=='new_direct')]
        selected[branch]=eligible.sort_values(['total_cost_yuan','emergency_cost_yuan'],kind='stable').iloc[0].policy
    selected['q2']='Q2_D112';selected['q1']='baseline'
    write(ROOT/'selection.json',{'rule':'minimum unrounded historical total, emergency fee, then frozen matrix order','selected':selected,'historical_exploration':True})
    pairs=[('q3_soc','q3_no_update','SOC feedback'),('q3_raw','q3_soc','new PV incremental'),('q3_w28','q3_raw','PV correction'),
           ('q3_raw','old_q3_raw','direct family raw migration'),('q3_w28','old_q3_w28','direct family corrected migration'),
           ('q42_ols','q42_fixed','Q42 planning price'),('q42_ols','old_q42_ols','Q42 migration'),
           ('q43_w28_ols','q43_raw_ols','Q43 PV correction OLS'),('q43_w28_fixed','q43_raw_fixed','Q43 PV correction fixed'),
           ('q43_raw_ols','q43_raw_fixed','Q43 planning price raw'),('q43_w28_ols','q43_w28_fixed','Q43 planning price corrected')]
    pairs += [(selected[b],old,'selected versus previous deployed') for b,old in [('q3','old_q3_w28'),('q42','old_q42_ols'),('q43','old_q43_w28_ols')]]
    unique={}
    for candidate,reference,purpose in pairs:
        key=(candidate,reference)
        unique[key]=unique[key]+'; '+purpose if key in unique else purpose
    pairs=[(c,r,purpose) for (c,r),purpose in unique.items()]
    records=[];day_records=[];month_records=[];rng=np.random.default_rng(20260915)
    for candidate,reference,purpose in pairs:
        c,r=daily[candidate],daily[reference];v=r.total_cost_yuan-c.total_cost_yuan
        month=v.groupby(v.index.str[:7]).sum()
        record={'candidate':candidate,'reference':reference,'purpose':purpose,'total_saving_yuan':float(v.sum()),
            'contract_saving_yuan':float((r.contract_cost_yuan-c.contract_cost_yuan).sum()),
            'emergency_saving_yuan':float((r.emergency_cost_yuan-c.emergency_cost_yuan).sum()),
            'winning_days':int((v>0).sum()),'losing_days':int((v<0).sum()),'tied_days':int((v==0).sum()),
            'losing_months':','.join(month.index[month<0]),'winning_months':int((month>0).sum()),
            'inventory_adjusted_saving_yuan':float(comparison.set_index('policy').loc[reference,'inventory_adjusted_cost_yuan']-comparison.set_index('policy').loc[candidate,'inventory_adjusted_cost_yuan'])}
        for block in [7,14]:
            offsets=rng.integers(0,len(v),size=(2000,int(np.ceil(len(v)/block))))
            idx=((offsets[:,:,None]+np.arange(block))%len(v)).reshape(2000,-1)[:,:len(v)]
            sampled=v.to_numpy()[idx].sum(axis=1);low,high=np.quantile(sampled,[.025,.975])
            record.update({f'block{block}_lower_yuan':float(low),f'block{block}_upper_yuan':float(high),f'block{block}_crosses_zero':bool(low<=0<=high)})
        records.append(record)
        for date,value in v.items():day_records.append({'candidate':candidate,'reference':reference,'date':date,'saving_yuan':value})
        for date,value in month.items():month_records.append({'candidate':candidate,'reference':reference,'month':date,'saving_yuan':value})
    pd.DataFrame(records).to_csv(ROOT/'paired_summary.csv',index=False)
    pd.DataFrame(day_records).to_csv(ROOT/'paired_daily.csv',index=False);pd.DataFrame(month_records).to_csv(ROOT/'paired_monthly.csv',index=False)
    combined=[]
    for name,d in daily.items():
        m=d.groupby(d.index.str[:7]).sum();m['policy']=name;combined.append(m.reset_index(names='month'))
    pd.concat(combined).to_csv(ROOT/'monthly_all.csv',index=False)
    view=comparison[['policy','branch','contract_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_margin_yuan','final_energy_kwh','optimizer_non_success_count']]
    (REPORT/'cost_tables.md').write_text('# 全部策略费用（元）\n\n'+markdown(view)+'\n\n# 成对历史比较\n\n'+markdown(pd.DataFrame(records))+'\n')
    print(json.dumps(selected,ensure_ascii=False));print(view.to_string(index=False))


if __name__=='__main__':main()
