"""Reopen CSVs and independently reconcile to raw workbook cells and time grids."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
import openpyxl
from prepare_data import WORK, ROOT, SOURCE, OUT, history_at, forecasts_at

CHECKS = []


def check(name, condition, detail=''):
    ok = bool(condition)
    CHECKS.append({'check':name,'passed':ok,'detail':str(detail)})
    print(f'{"PASS" if ok else "FAIL"} {name} {detail}',flush=True)


def close(a,b):
    return np.allclose(np.asarray(a,dtype=float),np.asarray(b,dtype=float),rtol=1e-13,atol=1e-10)


def read(name):
    df = pd.read_csv(OUT/f'{name}.csv',float_precision='round_trip')
    for c in ['interval_start','interval_end','issue_time','target_time','available_time','endpoint_issue_time']:
        if c in df:
            df[c] = pd.to_datetime(df[c],errors='raise')
            check(f'{name}: {c} timezone-naive',df[c].dt.tz is None)
    return df


def source_values(file,sheet):
    wb = openpyxl.load_workbook(SOURCE/file,read_only=True,data_only=True)
    rows = list(wb[sheet].values)
    wb.close()
    return rows


def validate_q1():
    q,f = read('q1_day'),read('fixed_price')
    raw = np.array([r[1:] for r in source_values('附件1.xlsx','Sheet1')[1:]],dtype=float)
    for name,d in [('Q1',q),('fixed_price',f)]:
        check(f'{name}: 144 slots unique and ordered',len(d)==144 and d.slot_id.tolist()==list(range(1,145)))
        check(f'{name}: complete relative day intervals',d.start_minute.tolist()==list(range(0,1440,10)) and d.end_minute.tolist()==list(range(10,1441,10)))
        check(f'{name}: required values nonmissing',not d.isna().any().any())
    check('Q1: all original numeric cells preserved',close(q[['price_yuan_per_kwh','load_kw','pv_forecast_kw']],raw))
    check('Q1: energy and signed net load',close(q.load_kwh,raw[:,1]/6) and close(q.pv_forecast_kwh,raw[:,2]/6) and close(q.net_load_forecast_kwh,(raw[:,1]-raw[:,2])/6))
    check('Q1: fixed price identical',close(f.price_yuan_per_kwh,raw[:,0]))
    check('Q1: negative net and zeros preserved',int((q.net_load_forecast_kwh<0).sum())==int((raw[:,1]<raw[:,2]).sum()) and int((q.pv_forecast_kw==0).sum())==int((raw[:,2]==0).sum()),
          f'negative net={(q.net_load_forecast_kwh<0).sum()}, PV zero={(q.pv_forecast_kw==0).sum()}')
    return q,f


def validate_all(f):
    a,h,d = read('actual_10min'),read('pv_forecast_hourly'),read('pv_forecast_10min')
    expected = pd.date_range('2025-01-01',periods=52560,freq='10min')
    check('Actual: 52560 unique contiguous intervals',len(a)==52560 and pd.DatetimeIndex(a.interval_start).equals(expected))
    check('Actual: every day 144 slots',a.groupby('date').slot_id.apply(lambda x:x.tolist()==list(range(1,145))).all() and a.date.nunique()==365)
    check('Actual: end/start and year-end business date',a.interval_end.eq(a.interval_start+pd.Timedelta(minutes=10)).all() and a.date.eq(a.interval_start.dt.strftime('%Y-%m-%d')).all() and a.interval_end.iloc[-1]==pd.Timestamp('2026-01-01') and a.date.iloc[-1]=='2025-12-31')
    check('Actual: no missing data or unexpected join loss',not a.isna().any().any() and len(a)==52560)
    for file,sheet,col,prefix in [('附件2.xlsx','小区负载','load_actual_kw','load'),('附件2.xlsx','光伏发电实际功率','pv_actual_kw','pv'),('附件4.xlsx','Sheet1','actual_price_yuan_per_kwh','price')]:
        rows = source_values(file,sheet)
        values = np.array([r[1:] for r in rows[1:]],dtype=float).reshape(-1)
        check(f'Actual: all {col} raw cells reconcile',close(a[col],values))
        check(f'Actual: {prefix} source rows reconcile',a[f'{prefix}_source_row'].tolist()==np.repeat(np.arange(2,367),144).tolist())
        check(f'Actual: {col} zeros preserved',int(a[col].eq(0).sum())==int((values==0).sum()))
    check('Actual: energy and signed net conversion',close(a.load_actual_kwh,a.load_actual_kw/6) and close(a.pv_actual_kwh,a.pv_actual_kw/6) and close(a.net_load_actual_kwh,(a.load_actual_kw-a.pv_actual_kw)/6) and close(a.net_load_actual_kw,a.load_actual_kw-a.pv_actual_kw))
    check('Actual: negative net preserved',int((a.net_load_actual_kwh<0).sum())==int((a.load_actual_kw<a.pv_actual_kw).sum()),f'negative net={(a.net_load_actual_kwh<0).sum()}')
    check('Actual: fixed price mapping',close(a.fixed_price_yuan_per_kwh,np.tile(f.price_yuan_per_kwh,365)))
    check('Actual: availability is interval end',a.available_time.eq(a.interval_end).all())
    check('Hourly: 35040 unique version-target keys',len(h)==35040 and not h.duplicated(['issue_time','target_time']).any())
    check('Hourly: 1460 issue times / 24 horizons',pd.DatetimeIndex(h.issue_time.drop_duplicates()).equals(pd.date_range('2025-01-01',periods=1460,freq='6h')) and h.groupby('issue_time').horizon_h.apply(lambda x:x.tolist()==list(range(1,25))).all())
    check('Hourly: target equals issue plus horizon',h.target_time.eq(h.issue_time+pd.to_timedelta(h.horizon_h,unit='h')).all())
    rows = source_values('附件3.xlsx','Sheet1')
    check('Hourly: every original power preserved',close(h.pv_forecast_kw,np.array([r[2:] for r in rows[1:]],dtype=float).reshape(-1)))
    check('Hourly: date fills recorded',int(h.date_was_filled.sum())==1095*24)
    source_blanks = np.array([r[0] is None or str(r[0]).strip()=='' for r in rows[1:]])
    check('Hourly: date-fill flags map to exact source rows',np.array_equal(h.date_was_filled,np.repeat(source_blanks,24)))
    changes = pd.read_csv(WORK/'data/interim/transformation_log.csv')
    check('Hourly: all 1095 date-fill source cells logged',len(changes)==1095 and changes.source_cell.tolist()==[f'A{i+2}' for i,blank in enumerate(source_blanks) if blank])
    check('Hourly: overlapping versions and cross-year retained',h.target_time.duplicated().any() and h.target_time.max()==pd.Timestamp('2026-01-01 18:00'),f'targets after actual end={(h.target_time>a.interval_end.max()).sum()}')
    check('10min: 210234 rows and unique version-interval keys',len(d)==210234 and not d.duplicated(['issue_time','interval_start']).any())
    counts = d.groupby('issue_time').size()
    check('10min: initial issue 138 intervals, remaining 1459 issues 144',counts.iloc[0]==138 and len(counts)==1460 and counts.iloc[1:].eq(144).all())
    check('10min: all intervals 10min and within 24h',d.interval_end.eq(d.interval_start+pd.Timedelta(minutes=10)).all() and (d.interval_start>=d.issue_time).all() and (d.interval_end<=d.issue_time+pd.Timedelta(hours=24)).all())
    check('10min: no internal gaps per version',d.groupby('issue_time').interval_start.diff().dropna().eq(pd.Timedelta(minutes=10)).all())
    check('10min: missing initial hour not invented',d.loc[d.issue_time==pd.Timestamp('2025-01-01'),'interval_start'].min()==pd.Timestamp('2025-01-01 01:00'))
    check('10min: business date and slot',d.date.eq(d.interval_start.dt.strftime('%Y-%m-%d')).all() and d.slot_id.eq(d.interval_start.dt.hour*6+d.interval_start.dt.minute//10+1).all())
    first = d.horizon_start_min<60
    check('10min: endpoint source older by 6h',d.loc[first,'endpoint_issue_time'].eq(d.loc[first,'issue_time']-pd.Timedelta(hours=6)).all() and d.loc[~first,'endpoint_issue_time'].isna().all())
    # Independent closed-form integral, using source points rather than the conversion function.
    lookup = h.set_index(['issue_time','horizon_h']).pv_forecast_kw
    source_lookup = h.set_index(['issue_time','target_time']).pv_forecast_kw
    expected_energy = []
    for row in d.itertuples():
        k = row.horizon_start_min//60
        p0 = source_lookup.loc[(row.endpoint_issue_time,row.issue_time)] if k==0 else lookup.loc[(row.issue_time,k)]
        p1 = lookup.loc[(row.issue_time,k+1)]
        midpoint_fraction = (row.horizon_start_min%60+5)/60
        expected_energy.append((p0+(p1-p0)*midpoint_fraction)/6)
    check('10min: every interval independently integrates raw forecast powers',close(d.pv_forecast_kwh,expected_energy))
    check('10min: finite nonnegative derived values',np.isfinite(d.pv_forecast_kwh).all() and d.pv_forecast_kwh.ge(0).all())
    # Exact boundaries plus deterministic arbitrary non-grid decision timestamps.
    rng = np.random.default_rng(2026)
    times = [pd.Timestamp('2025-01-01'),pd.Timestamp('2025-02-01'),pd.Timestamp('2026-01-01')]
    times += list(pd.to_datetime(rng.integers(pd.Timestamp('2025-01-01').value//10**9,pd.Timestamp('2026-01-01').value//10**9,20),unit='s'))
    causal = True
    for t in times:
        hist, forecasts, derived = history_at(a,t), forecasts_at(h,t), forecasts_at(d,t)
        causal &= (hist.available_time<=t).all() and (forecasts.issue_time<=t).all() and (forecasts.target_time>t).all()
        causal &= (derived.issue_time<=t).all() and (derived.interval_start>=t).all()
        causal &= len(hist)==int((a.interval_end<=t).sum())
    check('Causal access: 23 decision timestamps, future rows excluded',causal)
    check('Causal access: February 1 uses all January and none of February',len(history_at(a,'2025-02-01'))==31*144)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['q1','all'],default='all')
    args = parser.parse_args()
    _,f = validate_q1()
    if args.stage=='all':
        validate_all(f)
        suite = unittest.defaultTestLoader.discover(str(WORK/'tests'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        check('Synthetic boundary/units/version/isolation tests',result.wasSuccessful(),f'{result.testsRun} tests')
    manifest = json.loads((WORK/'data/interim/source_manifest.json').read_text())
    check('All original workbooks including templates unchanged',all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in manifest.items()))
    (WORK/f'reports/validation_{args.stage}.json').write_text(json.dumps(CHECKS,ensure_ascii=False,indent=2))
    lines = [f'# {args.stage} 数据验证', '', '验证对象为重新读取的 CSV；任何未通过项均保留。', '', '| 检查 | 结果 | 证据 |','|---|---|---|']
    lines += [f'| {c["check"]} | {"通过" if c["passed"] else "失败"} | {c["detail"]} |' for c in CHECKS]
    (WORK/f'reports/validation_{args.stage}.md').write_text('\n'.join(lines)+'\n')
    if not all(c['passed'] for c in CHECKS):
        raise SystemExit(1)


if __name__=='__main__':
    main()
