"""Read-only diagnosis of existing policies; never optimizes or replaces outputs."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'reports/emergency_research_v1'
POLICIES = {
    'q2_selected':'results/q2/selected/ledger.csv',
    'q2_seasonal':'results/q2/seasonal/ledger.csv',
    'q2_no_storage':'results/q2/no_storage/ledger.csv',
    'q3_no_update':'results/q3/no_update/ledger.csv',
    'q3_corrected':'results/robustness/fixed_w28/ledger.csv',
    'q42':'results/q4/q42_ols/ledger.csv',
    'q43_corrected':'results/robustness/variable_w28/ledger.csv',
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protected = [WORK/x for x in POLICIES.values()]
    protected += [WORK/'data/processed/actual_10min.csv',WORK/'data/processed/fixed_price.csv',
                  WORK/'scripts/run_q2.py',WORK/'scripts/solve_q1.py',WORK/'deliverables/revision_v1_review.zip']
    manifest = json.loads((WORK/'reports/revision_v1/revision_manifest.json').read_text())
    protected += [WORK/p for p in manifest['files']]
    protected = sorted(set(protected))
    before = {str(p.relative_to(WORK)):sha(p) for p in protected}
    for p, record in manifest['files'].items():
        assert before[p] == record['sha256'], f'Existing repair manifest changed before analysis: {p}'
    actual = pd.read_csv(WORK/'data/processed/actual_10min.csv',float_precision='round_trip')
    prices = pd.read_csv(WORK/'data/processed/fixed_price.csv',float_precision='round_trip').set_index('slot_id').price_yuan_per_kwh
    source = actual.set_index(['date','slot_id'])
    summaries, hours, months, binding, checks = [], [], [], [], {}
    for name, rel in POLICIES.items():
        p = WORK/rel
        f = pd.read_csv(p,float_precision='round_trip').sort_values(['date','slot_id']).reset_index(drop=True)
        assert len(f)==48096 and f.date.nunique()==334
        assert f.groupby('date').slot_id.apply(list).map(lambda x:x==list(range(1,145))).all()
        key = pd.MultiIndex.from_frame(f[['date','slot_id']])
        raw = source.loc[key]
        price = raw.actual_price_yuan_per_kwh.to_numpy() if name.startswith('q4') else prices.loc[f.slot_id].to_numpy()
        emergency = f.emergency_kwh.to_numpy()
        fee = 5*price*emergency
        q0 = f.grid_plan_kwh.to_numpy() if 'grid_plan_kwh' in f else f.grid_original_kwh.to_numpy()
        q = f.grid_plan_kwh.to_numpy() if 'grid_plan_kwh' in f else f.grid_effective_kwh.to_numpy()
        contract = price*q0 + 1.5*price*np.maximum(q-q0,0) - .5*price*np.maximum(q0-q,0)
        residuals = {
            'emergency_fee_yuan':float(np.max(np.abs(fee-f.emergency_cost_yuan))),
            'total_fee_yuan':float(np.max(np.abs(contract+fee-f.total_cost_yuan))),
            'source_load_kwh':float(np.max(np.abs(raw.load_actual_kwh.to_numpy()-f.load_actual_kwh))),
            'source_PV_kwh':float(np.max(np.abs(raw.pv_actual_kwh.to_numpy()-f.pv_actual_kwh))),
            'balance_kwh':float(np.max(np.abs(q+f.pv_actual_kwh+f.discharge_actual_kwh+emergency-f.load_actual_kwh-f.charge_actual_kwh-f.surplus_kwh))),
            'SOC_kwh':float(np.max(np.abs(f.energy_end_actual_kwh-f.energy_start_actual_kwh-.9*f.charge_actual_kwh+f.discharge_actual_kwh/.9))),
        }
        assert max(residuals.values())<1e-6, (name,residuals)
        checks[name] = residuals
        f['emergency_fee_recomputed']=fee
        f['hour']=(f.slot_id-1)//6
        f['month']=f.date.str[:7]
        f['hit']=emergency>1e-7
        f['at_energy_floor']=f.energy_end_actual_kwh<=1200+1e-6
        f['at_power_limit']=f.discharge_actual_kwh>=5000/6-1e-6
        category = np.select([f.at_energy_floor & f.at_power_limit, f.at_energy_floor, f.at_power_limit],
                             ['both','energy_floor','power_limit'],default='neither')
        f['binding']=category
        summaries.append({'policy':name,'days':334,'emergency_kwh':float(emergency.sum()),
            'emergency_cost_yuan':float(fee.sum()),'emergency_premium_above_normal_yuan':float((4*price*emergency).sum()),
            'contract_cost_yuan':float(contract.sum()),'total_cost_yuan':float((contract+fee).sum()),
            'emergency_days':int(f.groupby('date').hit.any().sum()),'emergency_intervals':int(f.hit.sum()),
            'emergency_share_of_load':float(emergency.sum()/f.load_actual_kwh.sum()),
            'emergency_share_of_total_cost':float(fee.sum()/(contract+fee).sum()),
            'weighted_emergency_price':float(fee.sum()/emergency.sum()),
            'surplus_kwh':float(f.surplus_kwh.sum()),'unused_paid_grid_kwh':float(f.unused_grid_kwh.sum())})
        for group, collector in [('hour',hours),('month',months)]:
            table=f.groupby(group).agg(emergency_kwh=('emergency_kwh','sum'),emergency_cost_yuan=('emergency_fee_recomputed','sum'),emergency_intervals=('hit','sum')).reset_index()
            table.insert(0,'policy',name);collector.append(table)
        bt=f.loc[f.hit].groupby('binding').agg(intervals=('hit','sum'),emergency_kwh=('emergency_kwh','sum'),emergency_cost_yuan=('emergency_fee_recomputed','sum')).reset_index()
        bt.insert(0,'policy',name);binding.append(bt)
        if name=='q2_selected':
            f['load_underforecast']=f.load_actual_kwh-f.load_forecast_kwh
            f['pv_overforecast']=f.pv_forecast_kwh-f.pv_actual_kwh
            f['net_underforecast']=f.load_underforecast+f.pv_overforecast
            f['charge_difference']=f.charge_actual_kwh-f.charge_plan_kwh
            f['discharge_difference']=f.discharge_plan_kwh-f.discharge_actual_kwh
            f['disposal_difference']=f.surplus_kwh-f.pv_curtailment_plan_kwh
            keys=['load_underforecast','pv_overforecast','charge_difference','discharge_difference','disposal_difference']
            error=float(np.max(np.abs(f[keys].sum(axis=1)-f.emergency_kwh)))
            assert error<1e-6
            checks[name]['signed_decomposition_identity_kwh']=error
            signed=f.loc[f.hit,keys].sum().to_dict()
            signed['emergency_kwh']=float(f.loc[f.hit,'emergency_kwh'].sum())
            signed['warning']='Signed accounting identity on realized emergency intervals; not causal effects or independent additive interventions.'
            (OUT/'q2_signed_decomposition.json').write_text(json.dumps(signed,indent=2)+'\n')
            slot=f.groupby('slot_id').agg(hour=('hour','first'),mean_load_underforecast=('load_underforecast','mean'),mean_pv_overforecast=('pv_overforecast','mean'),mean_net_underforecast=('net_underforecast','mean'),mean_actual_SOC_start=('energy_start_actual_kwh','mean'),mean_planned_SOC_start=('energy_start_plan_kwh','mean'),emergency_cost_yuan=('emergency_fee_recomputed','sum'),emergency_kwh=('emergency_kwh','sum'),emergency_intervals=('hit','sum')).reset_index()
            slot.to_csv(OUT/'q2_slot_diagnosis.csv',index=False)
            daily=f.groupby('date').agg(emergency_cost_yuan=('emergency_fee_recomputed','sum'),emergency_kwh=('emergency_kwh','sum'),load_underforecast=('load_underforecast','sum'),pv_overforecast=('pv_overforecast','sum'),surplus_kwh=('surplus_kwh','sum'),end_SOC=('energy_end_actual_kwh','last')).sort_values('emergency_cost_yuan',ascending=False)
            daily.to_csv(OUT/'q2_daily_diagnosis.csv')
            diagnostics={'net_error_positive_rate':float((f.net_underforecast>0).mean()),
                         'load_MAE_kwh':float(f.load_underforecast.abs().mean()),'PV_MAE_kwh':float(f.pv_overforecast.abs().mean()),
                         'total_load_underforecast_kwh':float(f.load_underforecast.sum()),'total_PV_overforecast_kwh':float(f.pv_overforecast.sum()),
                         'emergency_cost_top10_days_share':float(daily.emergency_cost_yuan.iloc[:10].sum()/fee.sum()),
                         'emergency_cost_18_23h_share':float(f.loc[f.hour>=18,'emergency_fee_recomputed'].sum()/fee.sum()),
                         'net_error_positive_rate_on_emergency':float((f.loc[f.hit,'net_underforecast']>0).mean())}
            (OUT/'q2_diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    pd.DataFrame(summaries).to_csv(OUT/'policy_comparison.csv',index=False)
    for name,frames in [('hourly',hours),('monthly',months),('binding_constraints',binding)]:
        pd.concat(frames,ignore_index=True).to_csv(OUT/f'{name}.csv',index=False)
    after={str(p.relative_to(WORK)):sha(p) for p in protected}
    assert before==after
    (OUT/'analysis_validation.json').write_text(json.dumps({'passed':True,'existing_files_unchanged':len(protected),
        'protected_hashes':before,'checks':checks,'script_sha256':sha(Path(__file__)),
        'scope':'Descriptive analysis of existing ledgers; no new forecasting, optimization, counterfactual replay or result replacement.'},indent=2)+'\n')
    print(pd.DataFrame(summaries)[['policy','emergency_kwh','emergency_cost_yuan','total_cost_yuan','emergency_share_of_load']].to_string(index=False))


if __name__=='__main__':
    main()
