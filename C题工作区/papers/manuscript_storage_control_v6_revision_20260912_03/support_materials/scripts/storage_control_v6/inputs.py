"""Causal forecast provenance; no legacy imports or writes."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from compat import forecast_price

WORK=Path(__file__).resolve().parents[2]
ROOT=WORK/'results/storage_control_v6'


def read(path): return pd.read_csv(path,float_precision='round_trip')


class Inputs:
    def __init__(self,with_pv=True,actual=None,pv_records=None,price_cache=True):
        self.actual=read(WORK/'data/processed/actual_10min.csv') if actual is None else actual.copy()
        for c in ['interval_start','interval_end']:self.actual[c]=pd.to_datetime(self.actual[c])
        self.days={d:f.reset_index(drop=True) for d,f in self.actual.groupby('date',sort=False)}
        self.archive=read(WORK/'results/q2_direct_v4/forecasts/linear_harmonic.csv')
        self.b0={d:f.reset_index(drop=True) for d,f in self.archive.groupby('date',sort=False)}
        self.fixed=read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy()
        self.physical=json.loads((WORK/'configs/model_baseline.json').read_text())
        self.price_config=json.loads((WORK/'configs/q4_baseline.json').read_text())
        self.price_cache={};self.price_meta={};self.pv_cache={};self.with_pv=with_pv
        if price_cache and (ROOT/'inputs/price_forecasts.csv').exists():
            prices=read(ROOT/'inputs/price_forecasts.csv')
            self.price_cache={pd.Timestamp(k):f.price_forecast_yuan_per_kwh.to_numpy() for k,f in prices.groupby('issue_time',sort=False)}
            self.price_meta={pd.Timestamp(k):v for k,v in json.loads((ROOT/'inputs/price_models.json').read_text()).items()}
        if with_pv:
            self.pv=read(WORK/'data/processed/pv_forecast_10min.csv') if pv_records is None else pv_records.copy()
            for c in ['issue_time','interval_start','interval_end']:self.pv[c]=pd.to_datetime(self.pv[c])
            self.pv=self.pv.loc[self.pv.interval_end<=self.pv.issue_time.dt.normalize()+pd.Timedelta(days=1)].copy()
            self.issues={k:f.sort_values('interval_start').reset_index(drop=True) for k,f in self.pv.groupby('issue_time',sort=False)}
            hist=self.pv.loc[self.pv.pv_forecast_kwh>0].merge(self.actual[['interval_start','pv_actual_kwh']],on='interval_start',validate='many_to_one')
            hist['residual_kwh']=hist.pv_actual_kwh-hist.pv_forecast_kwh
            self.pv_history=hist

    def pv_forecast(self,date,hour,corrected):
        key=(date,hour,corrected)
        if key in self.pv_cache:return self.pv_cache[key]
        issue=pd.Timestamp(date)+pd.Timedelta(hours=hour);f=self.issues[issue]
        wanted=pd.date_range(issue,issue.normalize()+pd.Timedelta(days=1),freq='10min',inclusive='left')
        assert np.array_equal(f.interval_start.to_numpy(),wanted.to_numpy())
        raw=f.pv_forecast_kwh.to_numpy();used=raw.copy();bias=0.;count=0;latest=None
        active=corrected and date>='2025-04-01'
        if active:
            cut=issue.normalize();hist=self.pv_history
            eligible=hist.loc[(hist.issue_time<issue)&(hist.issue_time.dt.hour==hour)&(hist.interval_start>=cut-pd.Timedelta(days=28))&(hist.interval_end<=cut)]
            count=len(eligible);bias=float(eligible.residual_kwh.mean()) if count else 0.
            latest=str(eligible.interval_end.max()) if count else None
            used=np.where(raw>0,np.maximum(0,raw+bias),0.)
        meta={'issue_time':str(issue),'active':active,'bias_kwh':bias,'training_rows':count,'training_cutoff':str(issue.normalize()),'latest_target_end':latest}
        self.pv_cache[key]=(used,raw,meta)
        return self.pv_cache[key]

    def prices(self,issue,method):
        issue=pd.Timestamp(issue);slot=issue.hour*6
        if method=='fixed':return self.fixed[slot:],{'method':'fixed','issue_time':str(issue)}
        if issue not in self.price_cache:
            h=self.actual.loc[self.actual.interval_end<=issue,['interval_start','interval_end','actual_price_yuan_per_kwh']]
            self.price_cache[issue],self.price_meta[issue]=forecast_price(h,issue,self.price_config)
        return self.price_cache[issue],self.price_meta[issue]

    def scenarios(self,date,hour,source_hour,corrected):
        day=pd.Timestamp(date);slot=hour*6;load=self.b0[date].load_forecast_kwh.to_numpy()[slot:]
        if self.with_pv:
            used,raw,meta=self.pv_forecast(date,source_hour,corrected)
            used=used[slot-source_hour*6:];raw=raw[slot-source_hour*6:]
        else:
            used=self.b0[date].pv_forecast_kwh.to_numpy()[slot:];raw=used.copy();meta={'source':'B0','issue_time':str(day)}
        dates=[d for d in self.b0 if day-pd.Timedelta(days=112)<=pd.Timestamp(d)<day]
        residuals=[]
        for d in dates:
            base=self.b0[d]
            if self.with_pv:
                past_pv=self.pv_forecast(d,source_hour,corrected)[0][slot-source_hour*6:]
                past_load=base.load_forecast_kwh.to_numpy()[slot:]
                real=self.days[d]
                residual=(real.load_actual_kwh-real.pv_actual_kwh).to_numpy()[slot:]-(past_load-past_pv)
            else:residual=base.net_residual_kwh.to_numpy()[slot:]
            residuals.append(residual)
        residual=np.array(residuals)
        assert len(dates)>=7 and np.all(np.isfinite(residual))
        risk=residual[[pd.Timestamp(d)>=day-pd.Timedelta(days=28) for d in dates]]
        return load,used,raw,load-used+residual,risk,dates,meta


def prepare():
    target=ROOT/'inputs';target.mkdir(exist_ok=True)
    data=Inputs(with_pv=False,price_cache=False);frames=[];metas={}
    for day in pd.date_range('2025-02-01','2025-12-31'):
        for hour in [0,6,12,18]:
            issue=day+pd.Timedelta(hours=hour);p,m=data.prices(issue,'ols');metas[str(issue)]=m
            frames.append(pd.DataFrame({'issue_time':str(issue),'slot_id':np.arange(hour*6+1,145),'price_forecast_yuan_per_kwh':p}))
        if day.day==1:print('price',day.date(),flush=True)
    pd.concat(frames).to_csv(target/'price_forecasts.csv',index=False)
    (target/'price_models.json').write_text(json.dumps(metas,indent=2)+'\n')


if __name__=='__main__':prepare()
