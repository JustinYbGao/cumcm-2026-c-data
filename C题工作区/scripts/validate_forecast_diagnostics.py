"""Independent readback checks for retrospective PV hourly-energy diagnostics."""
import json
import numpy as np
import pandas as pd
from prepare_data import WORK, OUT
from diagnose_forecasts import errors_at


def main():
    evidence = []
    def check(name,ok):
        evidence.append({'check':name,'passed':bool(ok)})
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    e = pd.read_csv(OUT/'pv_forecast_hourly_evaluation.csv',parse_dates=['issue_time','target_time','interval_start','error_available_time'],dtype={'actual_positive_pv':'boolean'},float_precision='round_trip')
    h = pd.read_csv(OUT/'pv_forecast_hourly.csv',parse_dates=['issue_time','target_time'],float_precision='round_trip')
    d = pd.read_csv(OUT/'pv_forecast_10min.csv',parse_dates=['issue_time','interval_start'],float_precision='round_trip')
    a = pd.read_csv(OUT/'actual_10min.csv',parse_dates=['interval_start'],float_precision='round_trip')
    keys = ['issue_time','target_time']
    check('35040 keys exactly match original hourly versions',len(e)==35040 and not e.duplicated(keys).any() and set(map(tuple,e[keys].to_numpy()))==set(map(tuple,h[keys].to_numpy())))
    check('Hourly targets and business dates',e.target_time.eq(e.issue_time+pd.to_timedelta(e.horizon_h,unit='h')).all() and e.interval_start.eq(e.target_time-pd.Timedelta(hours=1)).all() and e.target_business_date.eq(e.interval_start.dt.strftime('%Y-%m-%d')).all())
    check('Release hour and lead-block labels match time keys',e.issue_hour.eq(e.issue_time.dt.hour).all() and e.lead_block.eq((e.horizon_h-1)//6+1).all())
    check('Expected 35003 comparable, 1 missing forecast, 36 missing actual',e.comparison_status.value_counts().to_dict()=={'comparable':35003,'missing_actual':36,'missing_forecast':1})
    actual_by_hour = a.groupby(a.interval_start.dt.floor('h')).pv_actual_kwh.sum()
    independently_actual = e.interval_start.map(actual_by_hour)
    check('All actual hourly energies independently sum six original intervals',np.allclose(e.actual_hour_kwh,independently_actual,equal_nan=True,rtol=1e-13,atol=1e-10))
    d['target_time'] = d.interval_start.dt.floor('h')+pd.Timedelta(hours=1)
    independent_forecast = d.groupby(keys).pv_forecast_kwh.sum(min_count=6).reindex(pd.MultiIndex.from_frame(e[keys])).to_numpy()
    check('All forecast hourly energies independently sum six derived intervals',np.allclose(e.forecast_hour_kwh,independent_forecast,equal_nan=True,rtol=1e-13,atol=1e-10))
    check('Error equals forecast minus actual, missing remains missing',np.allclose(e.error_kwh,e.forecast_hour_kwh-e.actual_hour_kwh,equal_nan=True,rtol=1e-13,atol=1e-10))
    valid = e.loc[e.comparison_status=='comparable']
    missing = e.loc[e.comparison_status!='comparable']
    check('Unmatched rows never have errors or error availability',missing.error_kwh.isna().all() and missing.error_available_time.isna().all())
    check('Availability at hour end and timestamp timezone-naive',valid.error_available_time.eq(valid.target_time).all() and all(e[c].dt.tz is None for c in keys+['error_available_time','interval_start']))
    zero = valid.actual_hour_kwh.eq(0)
    check('True zero-PV hours retained and evaluated',zero.any() and valid.loc[zero,'error_kwh'].notna().all())
    common = pd.read_csv(WORK/'reports/pv_forecast_common_targets.csv',parse_dates=keys)
    check('Common targets have exactly four distinct release hours and lead blocks',not common.duplicated(keys).any() and common.groupby('target_time').size().eq(4).all() and common.groupby('target_time').issue_hour.nunique().eq(4).all() and common.groupby('target_time').lead_block.nunique().eq(4).all())
    common_e = valid.merge(common[keys],on=keys,validate='one_to_one')
    check('Common-key file contains only comparable records',len(common_e)==len(common))
    labels = common.merge(valid[keys+['issue_hour','lead_block']],on=keys,validate='one_to_one',suffixes=('_saved','_evaluation'))
    check('Common-file grouping labels match evaluation records',labels.issue_hour_saved.eq(labels.issue_hour_evaluation).all() and labels.lead_block_saved.eq(labels.lead_block_evaluation).all())
    expected_common = valid.groupby('target_time').size()
    expected_targets = set(expected_common.loc[expected_common==4].index)
    check('Common target set is complete, not a selected subset',set(common.target_time)==expected_targets and len(expected_targets)==8742)
    summary = pd.read_csv(WORK/'reports/pv_forecast_error_summary.csv',dtype={'group_value':str},float_precision='round_trip')
    expected_summary_keys = set()
    for scope in ['all_comparable','same_target_four_versions']:
        groups = {'overall':['all'],'issue_hour':['0','6','12','18'],'lead_block':['1','2','3','4']}
        if scope=='all_comparable':
            groups['horizon_h'] = [str(i) for i in range(1,25)]
        for population in ['all_hours','actual_pv_positive']:
            for grouping,values in groups.items():
                expected_summary_keys.update((scope,population,grouping,value) for value in values)
    summary_keys = ['scope','population','grouping','group_value']
    check('All 84 required summary groups present exactly once',len(summary)==84 and not summary.duplicated(summary_keys).any() and set(map(tuple,summary[summary_keys].to_numpy()))==expected_summary_keys)
    metrics_ok = True
    for row in summary.itertuples():
        data = valid if row.scope=='all_comparable' else common_e
        if row.population=='actual_pv_positive':
            data = data.loc[data.actual_hour_kwh>0]
        if row.grouping!='overall':
            data = data.loc[data[row.grouping]==int(row.group_value)]
        errors = (data.forecast_hour_kwh-data.actual_hour_kwh).to_numpy()
        metrics_ok &= row.n==len(data) and row.target_hour_count==data.target_time.nunique()
        metrics_ok &= np.allclose([row.bias_kwh,row.mae_kwh,row.rmse_kwh],[np.mean(errors),np.mean(np.abs(errors)),np.sqrt(np.mean(errors**2))],rtol=1e-13,atol=1e-10)
    check('Every summary sample count and MAE/RMSE/bias independently recomputed',metrics_ok)
    causal = True
    decisions = [pd.Timestamp('2025-01-01'),pd.Timestamp('2025-02-01'),pd.Timestamp('2026-01-01'),pd.Timestamp('2026-01-02')]
    decisions += list(pd.date_range('2025-01-01 00:59:59',periods=365,freq='D'))
    for t in decisions:
        selected = errors_at(e,t)
        causal &= len(selected)==len(valid.loc[valid.target_time<=t]) and selected.error_available_time.le(t).all() and selected.issue_time.le(t).all()
    check('369 decision times exclude future and permanently unmatched errors',causal)
    (WORK/'reports/validation_forecast_diagnostics.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    if not all(item['passed'] for item in evidence):
        raise SystemExit(1)


if __name__=='__main__':
    main()
