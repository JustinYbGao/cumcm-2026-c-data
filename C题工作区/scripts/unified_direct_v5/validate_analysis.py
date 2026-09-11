"""Independent recalculation of comparison tables from ledger commitments and source prices."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import openpyxl

WORK=Path(__file__).resolve().parents[2];ROOT=WORK/'results/unified_direct_v5'


def read(p):return pd.read_csv(p,float_precision='round_trip')


def main():
    source=WORK.parent/'CUMCM2026Problems/C题/附件'
    wb=openpyxl.load_workbook(source/'附件1.xlsx',read_only=True,data_only=True);fixed=np.array([r[1] for r in list(wb['Sheet1'].values)[1:]],float);wb.close()
    wb=openpyxl.load_workbook(source/'附件4.xlsx',read_only=True,data_only=True);prices=np.array([r[1:] for r in list(wb['Sheet1'].values)[1:]],float)[31:].ravel();wb.close()
    table=read(ROOT/'comparison_all.csv');daily={};costerr=0.;physics=[];optional_missing=[]
    for _,row in table.iterrows():
        f=read(WORK/row.source_ledger);q0=f.grid_plan_kwh.to_numpy() if 'grid_plan_kwh' in f else f.grid_original_kwh.to_numpy()
        q=q0 if 'grid_plan_kwh' in f else f.grid_effective_kwh.to_numpy();p=np.tile(fixed,334) if row.branch in ['q2','q3'] else prices
        initial=f.energy_start_actual_kwh.to_numpy();end=f.energy_end_actual_kwh.to_numpy();c=f.charge_actual_kwh.to_numpy();d=f.discharge_actual_kwh.to_numpy();u=f.emergency_kwh.to_numpy();w=f.surplus_kwh.to_numpy()
        balance=q+f.pv_actual_kwh.to_numpy()+d+u-f.load_actual_kwh.to_numpy()-c-w
        residual=end-initial-.9*c+d/.9
        state_error=float(np.max(np.abs(initial[1:]-end[:-1])));balance_error=float(np.max(np.abs(balance)));recurrence_error=float(np.max(np.abs(residual)))
        assert state_error<=1e-6 and balance_error<=1e-6 and recurrence_error<=1e-6
        numeric=f.select_dtypes(include='number')
        optional=[] if row.stage=='new_direct' else ['risk_history_start','risk_history_end','pv_window_days']
        assert np.all(np.isfinite(numeric.drop(columns=optional,errors='ignore').to_numpy()))
        for column in optional:
            if column in numeric and numeric[column].isna().any():
                optional_missing.append({'policy':row.policy,'column':column,'missing_rows':int(numeric[column].isna().sum()),'reason':'inapplicable historical diagnostic; all physical/fee columns remain required'})
        assert np.min(initial)>=1200-1e-6 and np.max(initial)<=10800+1e-6 and np.min(end)>=1200-1e-6 and np.max(end)<=10800+1e-6
        assert np.min(np.r_[c,d,u,q,q0,w])>=-1e-6 and max(c.max(),d.max())<=5000/6+1e-6
        assert np.all((c<=1e-6)|(d<=1e-6)) and np.all((c<=1e-6)|(u<=1e-6))
        fees={'original_cost_yuan':p*q0,'increase_cost_yuan':p*1.5*np.maximum(q-q0,0),'decrease_adjustment_yuan':-p*.5*np.maximum(q0-q,0),'emergency_cost_yuan':5*p*u}
        fees['contract_cost_yuan']=fees['original_cost_yuan']+fees['increase_cost_yuan']+fees['decrease_adjustment_yuan'];fees['total_cost_yuan']=fees['contract_cost_yuan']+fees['emergency_cost_yuan']
        for key,values in fees.items():costerr=max(costerr,abs(float(row[key])-values.sum()));assert abs(float(row[key])-values.sum())<=1e-5
        totals=fees['total_cost_yuan'].reshape(334,144).sum(axis=1);daily[row.policy]=pd.Series(totals,index=pd.date_range('2025-02-01','2025-12-31').strftime('%Y-%m-%d'))
        physics.append({'policy':row.policy,'balance_max_kwh':balance_error,'recurrence_max_kwh':recurrence_error,'cross_interval_max_kwh':state_error})
    summary=read(ROOT/'paired_summary.csv');days=read(ROOT/'paired_daily.csv');months=read(ROOT/'paired_monthly.csv');rng=np.random.default_rng(20260915);staterr=0.
    for _,row in summary.iterrows():
        v=daily[row.reference]-daily[row.candidate];m=v.groupby(v.index.str[:7]).sum()
        expected=[v.sum(),(v>0).sum(),(v<0).sum(),(v==0).sum(),(m>0).sum()]
        actual=[row.total_saving_yuan,row.winning_days,row.losing_days,row.tied_days,row.winning_months]
        err=float(np.max(np.abs(np.array(expected)-actual)));staterr=max(staterr,err);assert err<1e-5
        assert ('' if pd.isna(row.losing_months) else row.losing_months)==','.join(m.index[m<0])
        selected=days.loc[(days.candidate==row.candidate)&(days.reference==row.reference)]
        # Duplicate pair purposes in the public table repeat identical rows, rather than being summed.
        selected=selected.drop_duplicates('date').set_index('date').saving_yuan
        assert np.max(np.abs(selected-v))<=1e-5
        selected=months.loc[(months.candidate==row.candidate)&(months.reference==row.reference)].drop_duplicates('month').set_index('month').saving_yuan
        assert np.max(np.abs(selected-m))<=1e-5
        for length in [7,14]:
            samples=[]
            for repeat in range(2000):
                starts=rng.integers(0,334,size=int(np.ceil(334/length)))
                indexes=np.concatenate([(s+np.arange(length))%334 for s in starts])[:334]
                samples.append(float(v.iloc[indexes].sum()))
            quantiles=np.quantile(samples,[.025,.975]);saved=[row[f'block{length}_lower_yuan'],row[f'block{length}_upper_yuan']]
            err=float(np.max(np.abs(quantiles-saved)));staterr=max(staterr,err);assert err<1e-5
    monthly=read(ROOT/'monthly_all.csv')
    for name,series in daily.items():
        saved=monthly.loc[monthly.policy==name].set_index('month').total_cost_yuan
        assert np.max(np.abs(saved-series.groupby(series.index.str[:7]).sum()))<=1e-5
    selection=json.loads((ROOT/'selection.json').read_text())['selected']
    for branch in ['q3','q42','q43']:
        t=table.loc[(table.branch==branch)&(table.stage=='new_direct')].sort_values(['total_cost_yuan','emergency_cost_yuan'],kind='stable')
        assert selection[branch]==t.iloc[0].policy
    same=[]
    for a,b in [('q3_raw','q43_raw_fixed'),('q3_w28','q43_w28_fixed')]:
        left=read(ROOT/'runs'/a/'ledger.csv');right=read(ROOT/'runs'/b/'ledger.csv');cols=['grid_original_kwh','grid_effective_kwh','energy_start_actual_kwh','energy_end_actual_kwh']
        diff=float(np.max(np.abs(left[cols].to_numpy()-right[cols].to_numpy())));assert diff<1e-6;same.append({'pair':[a,b],'max_plan_state_difference_kwh':diff})
    result={'passed':True,'comparison_policies':len(table),'source_fee_max_error_yuan':costerr,'paired_statistics_max_error_yuan':staterr,'paired_comparisons':len(summary),'physics':physics,'historical_optional_diagnostics':optional_missing,'fixed_planning_cross_price_consistency':same,'bootstrap':'Independent loop reconstruction, seed20260915/2000 circular blocks7,14, same frozen pair order'}
    (WORK/'reports/unified_direct_v5/analysis_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='physics'},indent=2))


if __name__=='__main__':main()
