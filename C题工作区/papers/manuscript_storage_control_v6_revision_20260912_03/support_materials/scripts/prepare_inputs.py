"""Prepare raw attachments and historical forecast releases; no dispatch optimization."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import prepare_data

WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK/'scripts/storage_control_v6'))
from compat import forecast_day

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-price-cache',action='store_true')
    args=parser.parse_args()
    expected=json.loads((WORK/'raw/required_files.json').read_text())
    for name,identity in expected.items():
        source=WORK/'raw'/name
        if not source.exists():raise FileNotFoundError(f'Place the original attachment at raw/{name}; see raw/README.md')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=identity['sha256']:
            raise ValueError(f'Attachment identity differs: {name}; do not silently change the published experiment input')
    for rel in ['data/processed','data/interim','results/q2_direct_v4/forecasts','results/storage_control_v6/inputs','reports/storage_control_v6']:
        (WORK/rel).mkdir(parents=True,exist_ok=True)
    _,fixed=prepare_data.prepare_q1()
    actual=prepare_data.prepare_actual(fixed)
    hourly=prepare_data.prepare_hourly()
    prepare_data.write(prepare_data.convert_forecasts(hourly),'pv_forecast_10min')
    # Build every historical release from its own completed history and parameters.
    source=pd.read_csv(WORK/'data/processed/actual_10min.csv',float_precision='round_trip')
    fields=['date','slot_id','interval_end','interval_start','load_actual_kwh','pv_actual_kwh','available_time']
    source=source[fields]
    ends=pd.to_datetime(source.interval_end)
    cfg=json.loads((WORK/'configs/q2_baseline.json').read_text())
    frames=[];models=[]
    for day in pd.date_range('2025-01-02','2025-12-31'):
        history=source.loc[ends<=day]
        load,pv,meta=forecast_day(history,day,'linear_harmonic',cfg)
        frame=source.loc[source.date==str(day.date())].copy()
        frame['issue_time']=str(day);frame['history_end']=meta['history_end']
        frame['load_forecast_kwh']=load;frame['pv_forecast_kwh']=pv
        frame['net_residual_kwh']=frame.load_actual_kwh-frame.pv_actual_kwh-load+pv
        frame['residual_available_time']=str(day+pd.Timedelta(days=1))
        frames.append(frame);models.append({'date':str(day.date()),**meta})
    archive=pd.concat(frames,ignore_index=True)
    archive.to_csv(WORK/'results/q2_direct_v4/forecasts/linear_harmonic.csv',index=False)
    (WORK/'results/q2_direct_v4/forecasts/models.json').write_text(json.dumps(models,indent=2)+'\n')
    if not args.without_price_cache:
        from inputs import prepare
        prepare()
    print(json.dumps({'actual_intervals':len(actual),'historical_forecast_intervals':len(archive),
                      'annual_dispatch_optimizations_run':0,'price_cache_prepared':not args.without_price_cache}))

if __name__=='__main__':main()
