"""Independent raw-source, policy-evidence, physical and billing verification.

No production forecast, optimizer, C kernel, dispatch or billing imports.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import openpyxl

WORK = Path(__file__).resolve().parents[2]
OUT = WORK / 'reports/unified_direct_v5'
ROOT = WORK / 'results/unified_direct_v5'
ETOL, CTOL = 1e-6, 1e-5
INITIAL, MU = 7268.4231640740745, .38232
POLICIES = {
    'q3_no_update': ('fixed',False,False,False),
    'q3_soc': ('fixed',True,False,False),
    'q3_raw': ('fixed',True,True,False),
    'q3_w28': ('fixed',True,True,True),
    'q42_ols': ('ols',False,False,False),
    'q42_fixed': ('fixed',False,False,False),
    'q43_raw_ols': ('ols',True,True,False),
    'q43_w28_ols': ('ols',True,True,True),
    'q43_raw_fixed': ('fixed',True,True,False),
    'q43_w28_fixed': ('fixed',True,True,True),
}


def read(path):
    return pd.read_csv(path, float_precision='round_trip')


class Audit:
    def __init__(self):
        self.rows = {}

    def check(self, name, value, **extra):
        value = np.asarray(value, bool)
        row = self.rows.setdefault(name, dict(check=name, passed=True, comparisons=0, failures=0))
        row['passed'] &= bool(value.all())
        row['comparisons'] += int(value.size)
        row['failures'] += int((~value).sum())
        if 'max_abs_error' in extra:
            extra['max_abs_error'] = max(extra['max_abs_error'], row.get('max_abs_error', 0))
        row.update(extra)

    def close(self, name, actual, expected, tol=ETOL):
        actual, expected = np.asarray(actual), np.asarray(expected)
        if actual.shape != expected.shape:
            self.check(name, False, actual_shape=list(actual.shape), expected_shape=list(expected.shape))
            return
        diff = np.abs(actual-expected)
        self.check(name, np.isfinite(diff) & (diff <= tol),
                   max_abs_error=float(np.max(diff, initial=0)), tolerance=tol)

    @property
    def passed(self):
        return all(r['passed'] for r in self.rows.values())


def workbook(path, sheet):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[sheet].values)
    wb.close()
    return rows


class Sources:
    def __init__(self, audit):
        self.audit = audit
        source = WORK.parent / 'CUMCM2026Problems/C题/附件'
        self.hashes = {str(p.relative_to(WORK.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in [source / f'附件{i}.xlsx' for i in range(1, 5)]}
        self.dates = pd.date_range('2025-01-01', '2025-12-31')
        self.actual = read(WORK / 'data/processed/actual_10min.csv')
        arrays = []
        for filename, sheet, key, divisor in [
                ('附件2.xlsx', '小区负载', 'load_actual_kwh', 6),
                ('附件2.xlsx', '光伏发电实际功率', 'pv_actual_kwh', 6),
                ('附件4.xlsx', 'Sheet1', 'actual_price_yuan_per_kwh', 1)]:
            rows = workbook(source / filename, sheet)
            audit.check('source.'+key+'.dates', pd.to_datetime([r[0] for r in rows[1:]]) == self.dates)
            labels = [str(v) for v in rows[0][1:]]
            expected = [f'{m//60:02d}:{m%60:02d}:00' for m in range(10, 1440, 10)]+['0:00+1']
            audit.check('source.'+key+'.endpoint_labels', labels == expected)
            values = np.asarray([r[1:] for r in rows[1:]], float)/divisor
            audit.close('source.'+key+'.raw_workbook', self.actual[key].to_numpy(), values.ravel())
            arrays.append(values)
        self.load, self.pv, self.actual_price = arrays
        self.net = self.load-self.pv
        q1 = workbook(source/'附件1.xlsx', 'Sheet1')
        self.q1 = np.asarray([r[1:] for r in q1[1:]], float)
        self.fixed = self.q1[:, 0]
        audit.close('source.fixed_price', read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh, self.fixed)
        audit.check('source.actual_rows', len(self.actual) == 52560)
        audit.check('source.unique_keys', ~self.actual[['date','slot_id']].duplicated())
        starts = pd.date_range('2025-01-01', periods=52560, freq='10min')
        audit.check('source.interval_start', pd.to_datetime(self.actual.interval_start) == starts)
        audit.check('source.interval_end', pd.to_datetime(self.actual.interval_end) == starts+pd.Timedelta(minutes=10))
        audit.check('source.availability', pd.to_datetime(self.actual.available_time) == starts+pd.Timedelta(minutes=10))
        self.b0 = self.rebuild_b0()
        frozen = read(WORK/'results/q2_direct_v4/forecasts/linear_harmonic.csv')
        audit.close('source.B0.load', frozen.load_forecast_kwh.to_numpy(), self.b0[1:,:,0].ravel())
        audit.close('source.B0.pv', frozen.pv_forecast_kwh.to_numpy(), self.b0[1:,:,1].ravel())
        self.raw = np.full((365, 4, 144), np.nan)
        rows = workbook(source/'附件3.xlsx', 'Sheet1')
        row_date = None
        source_issues = []
        for row in rows[1:]:
            if row[0] is not None and str(row[0]).strip():
                row_date = pd.Timestamp(row[0])
            label = row[1]
            hour = label.hour if hasattr(label,'hour') else int(str(label).split(':')[0])
            source_issues.append(row_date+pd.Timedelta(hours=hour))
        hourly = read(WORK/'data/processed/pv_forecast_hourly.csv')
        powers = np.asarray([r[2:] for r in rows[1:]], float)
        audit.close('source.Appendix3.hourly_power', hourly.pv_forecast_kw.to_numpy(), powers.ravel())
        issues = pd.date_range('2025-01-01', periods=1460, freq='6h')
        audit.check('source.Appendix3.raw_issue_rows',pd.DatetimeIndex(source_issues)==issues)
        audit.check('source.Appendix3.issue_time', pd.to_datetime(hourly.issue_time) == issues.repeat(24))
        earlier = {}
        records = []
        for idx, issue in enumerate(issues):
            day, stage = idx//4, idx%4
            offset = 36*stage
            anchor = earlier.get(issue)
            first = 6 if anchor is None else 0
            knots = np.arange(1,25)*6 if anchor is None else np.arange(25)*6
            points = powers[idx] if anchor is None else np.r_[anchor[1], powers[idx]]
            for t in range(first,144):
                value = (np.interp(t,knots,points)+np.interp(t+1,knots,points))/12
                records.append((issue, issue+pd.Timedelta(minutes=10*t), value,
                                None if t>=6 else anchor[0]))
                if t+offset < 144:
                    self.raw[day,stage,t+offset] = value
            for horizon, power in enumerate(powers[idx],1):
                earlier[issue+pd.Timedelta(hours=horizon)] = (issue,power)
        converted = read(WORK/'data/processed/pv_forecast_10min.csv')
        audit.check('source.Appendix3.interpolation_keys',
                    np.array_equal(pd.to_datetime(converted.interval_start), pd.DatetimeIndex([r[1] for r in records])))
        audit.close('source.Appendix3.trapezoid_energy', converted.pv_forecast_kwh.to_numpy(), np.array([r[2] for r in records]))
        endpoint = pd.to_datetime(converted.endpoint_issue_time)
        expected_endpoint = pd.to_datetime([r[3] for r in records])
        audit.check('source.Appendix3.previous_release_anchor', (endpoint == expected_endpoint) | (endpoint.isna() & expected_endpoint.isna()))
        self.corrected = self.raw.copy()
        self.bias = np.zeros((365,4))
        for day in range(90,365):
            for stage in range(4):
                start = max(0,day-28)
                raw = self.raw[start:day,stage]
                valid = np.isfinite(raw) & (raw>0)
                residual = self.pv[start:day]-raw
                bias = float(residual[valid].mean()) if valid.any() else 0.
                self.bias[day,stage] = bias
                self.corrected[day,stage] = np.where(self.raw[day,stage]>0, np.maximum(self.raw[day,stage]+bias,0), self.raw[day,stage])
        self.price_cache = {}
        price_path = ROOT/'inputs/price_forecasts.csv'
        if price_path.exists():
            archive = read(price_path)
            rebuilt_issues = 0
            for issue,group in archive.groupby('issue_time',sort=False):
                issue = pd.Timestamp(issue)
                day = (issue.normalize()-self.dates[0]).days
                audit.close('source.price_OLS_archive',group.price_forecast_yuan_per_kwh.to_numpy(),self.price(day,issue.hour,'ols'))
                audit.check('source.price_OLS_archive_slots',np.array_equal(group.slot_id,np.arange(issue.hour*6+1,145)))
                rebuilt_issues += 1
            audit.check('source.price_OLS_archive_coverage',rebuilt_issues==334*4)

    def rebuild_b0(self):
        result = np.full((365,144,2), np.nan)
        phase = np.arange(144)*2*np.pi/144
        bases = {k: np.column_stack([np.ones(144)]+[f(j*phase) for j in range(1,k+1) for f in [np.sin,np.cos]]) for k in [2,3]}
        def design(day):
            weekday = np.tile(np.array([self.dates[day].weekday()==j for j in range(1,7)],float),(144,1))
            return np.column_stack([bases[2],self.load[day-1]/1000,self.load[day-7]/1000,weekday])
        for day in range(1,365):
            load = self.load[day-7 if day>=7 else day-1].copy()
            pv = self.pv[day-1].copy()
            if day>=14:
                start = max(7,day-28)
                x = np.vstack([design(j) for j in range(start,day)])
                beta = np.linalg.lstsq(x,self.load[start:day].ravel(),rcond=None)[0]
                load = np.maximum(design(day)@beta,0)
            if day>=2:
                x = np.tile(bases[3],(min(day,7),1))
                values = self.pv[max(0,day-7):day].ravel()
                beta = np.linalg.lstsq(x,values,rcond=None)[0]
                residual = values-x@beta
                denom = residual[:-1]@residual[:-1]
                phi = np.clip(residual[:-1]@residual[1:]/denom if denom>1e-12 else 0,-.99,.99)
                pv = np.maximum(bases[3]@beta+residual[-1]*phi**np.arange(1,145),0)
            result[day,:,0], result[day,:,1] = load,pv
        return result

    def price(self,day,hour,method):
        slot = hour*6
        if method == 'fixed':
            return self.fixed[slot:]
        key = (day,hour,method)
        if key in self.price_cache:
            return self.price_cache[key]
        cut = day*144+slot
        targets = np.arange(cut,(day+1)*144)
        flat = self.actual_price.ravel()
        if 'lag7' in method.lower():
            result = flat[targets-1008]
        else:
            train = np.arange(max(1008,cut-28*144),cut)
            def design(indices):
                phase = (indices%144)/144
                weekday = (indices//144+2)%7
                return np.column_stack([np.ones(len(indices))]+[f(2*np.pi*k*phase) for k in [1,2] for f in [np.sin,np.cos]]+
                                       [flat[indices-144],flat[indices-1008]]+[(weekday==j).astype(float) for j in range(1,7)])
            beta = np.linalg.lstsq(design(train),flat[train],rcond=None)[0]
            result = np.maximum(design(targets)@beta,1e-6)
        self.price_cache[key] = result
        return result

    def forecast(self,day,source_hour,correct,b0=False):
        load = self.b0[day,:,0]
        pv = self.b0[day,:,1] if b0 else (self.corrected if correct else self.raw)[day,source_hour//6]
        return load,pv


def replay(q,net,initial):
    energy = float(initial)
    result = np.zeros((len(q),6))
    for t,(buy,demand) in enumerate(zip(q,net)):
        excess = buy-demand
        charge = min(max(excess,0),5000/6,max((10800-energy)/.9,0))
        discharge = min(max(-excess,0),5000/6,max((energy-1200)*.9,0))
        end = energy+.9*charge-discharge/.9
        result[t] = charge,discharge,max(-excess-discharge,0),max(excess-charge,0),energy,end
        energy = end
    return result


def candidate_values(q,net,price,initial,q0):
    state = np.full((len(q),len(net)),float(initial))
    fee = np.zeros_like(state)
    for t in range(q.shape[1]):
        excess = q[:,t,None]-net[None,:,t]
        charge = np.minimum(np.maximum(excess,0),np.minimum(5000/6,np.maximum((10800-state)/.9,0)))
        discharge = np.minimum(np.maximum(-excess,0),np.minimum(5000/6,np.maximum((state-1200)*.9,0)))
        fee += 5*price[t]*np.maximum(-excess-discharge,0)
        state += .9*charge-discharge/.9
    ordinary = q@price if len(q0)==0 else np.sum(price*(q0+1.5*np.maximum(q-q0,0)-.5*np.maximum(q0-q,0)),axis=1)
    return dict(ordinary=ordinary,emergency_fee=fee,end_energy=state,
                score=ordinary+np.mean(fee-MU*(state-initial),axis=1))


def verifier_self_checks(a):
    example = replay([100,0],[50,50],1200)
    a.close('verifier.hand_replay',example,np.array([[50,0,0,0,1200,1245],[0,40.5,9.5,0,1245,1200]]))
    result = candidate_values(np.array([[100.,0.]]),np.array([[50.,50.]]),np.array([1.,2.]),1200,np.array([80.,20.]))
    a.close('verifier.hand_contract_score',result['score'],np.array([225.]),CTOL)
    rng = np.random.default_rng(20260911)
    for horizon in [36,72,108,144]:
        plans = rng.uniform(0,1500,(7,horizon))
        scenarios = rng.uniform(-1300,2100,(9,horizon))
        price = rng.uniform(.1,1.5,horizon)
        initial = 6400.
        for reference in [np.array([]),rng.uniform(0,1500,horizon)]:
            vector = candidate_values(plans,scenarios,price,initial,reference)
            for k,plan in enumerate(plans):
                ordinary = float(plan@price) if not len(reference) else float(np.dot(price,reference+1.5*np.maximum(plan-reference,0)-.5*np.maximum(reference-plan,0)))
                fees,terminal = [],[]
                for scenario in scenarios:
                    trace = replay(plan,scenario,initial)
                    fees.append(float(5*price@trace[:,2]))
                    terminal.append(float(trace[-1,5]))
                a.close('verifier.vector_scalar_ordinary',vector['ordinary'][k],ordinary,CTOL)
                a.close('verifier.vector_scalar_emergency',vector['emergency_fee'][k],np.array(fees),CTOL)
                a.close('verifier.vector_scalar_terminal',vector['end_energy'][k],np.array(terminal))
                score = ordinary+float(np.mean(np.array(fees)-MU*(np.array(terminal)-initial)))
                a.close('verifier.vector_scalar_score',vector['score'][k],score,CTOL)


def frozen_regression(a,sources):
    frame = read(WORK/'results/q2_direct_v4/runs/D112/ledger.csv')
    values = replay(frame.grid_plan_kwh.to_numpy(),sources.net[31:].ravel(),INITIAL)
    for i,key in enumerate(['charge_actual_kwh','discharge_actual_kwh','emergency_kwh','surplus_kwh','energy_start_actual_kwh','energy_end_actual_kwh']):
        a.close('D112.'+key,frame[key],values[:,i])
    costs = frame.grid_plan_kwh.to_numpy()*np.tile(sources.fixed,334)+5*np.tile(sources.fixed,334)*values[:,2]
    a.close('D112.interval_cost',frame.total_cost_yuan,costs,CTOL)
    a.close('D112.total_regression',np.sum(costs),13913892.481868185,CTOL)
    frame = read(WORK/'results/q1/baseline/schedule.csv')
    charge,discharge = frame.charge_kwh.to_numpy(),frame.discharge_kwh.to_numpy()
    start,end = frame.energy_start_kwh.to_numpy(),frame.energy_end_kwh.to_numpy()
    a.close('Q1.initial',start[0],6000.)
    a.close('Q1.terminal',end[-1],6000.)
    a.close('Q1.state_continuity',start[1:],end[:-1])
    a.close('Q1.state_equation',end,start+.9*charge-discharge/.9)
    a.close('Q1.energy_balance',frame.grid_kwh.to_numpy()+sources.q1[:,2]/6+discharge,
            sources.q1[:,1]/6+charge+frame.curtailment_kwh.to_numpy())
    a.check('Q1.limits',(start>=1200-ETOL)&(start<=10800+ETOL)&(charge>=-ETOL)&(charge<=5000/6+ETOL)&(discharge>=-ETOL)&(discharge<=5000/6+ETOL))
    a.close('Q1.no_simultaneous',charge*discharge,np.zeros(144))
    a.check('Q1.nonnegative_grid',frame.grid_kwh>=-ETOL)
    a.check('Q1.end_limits',(end>=1200-ETOL)&(end<=10800+ETOL))
    a.close('Q1.total_regression',frame.grid_kwh.to_numpy()@sources.fixed,35126.94858928963,CTOL)


def audit_ledger(a,folder,sources):
    tag = folder.name
    frame = read(folder/'ledger.csv')
    summary = json.loads((folder/'summary.json').read_text())
    truth = sources.actual.loc[sources.actual.date.between(frame.date.iloc[0],frame.date.iloc[-1])].reset_index(drop=True)
    a.check(tag+'.annual_rows',len(frame)==48096)
    a.check(tag+'.keys',np.array_equal(frame[['date','slot_id']],truth[['date','slot_id']]))
    a.check(tag+'.unique_keys',~frame[['date','slot_id']].duplicated())
    for key in ['load_actual_kwh','pv_actual_kwh']:
        a.close(tag+'.source_'+key,frame[key],truth[key])
    variable = tag.lower().startswith('q4')
    price = truth.actual_price_yuan_per_kwh.to_numpy() if variable else truth.fixed_price_yuan_per_kwh.to_numpy()
    a.close(tag+'.settlement_price',frame.price_yuan_per_kwh,price)
    net = truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()
    q = frame.grid_effective_kwh.to_numpy()
    a.check(tag+'.nonnegative_commitment',q>=-ETOL)
    values = replay(q,net,INITIAL)
    for i,key in enumerate(['charge_actual_kwh','discharge_actual_kwh','emergency_kwh','surplus_kwh','energy_start_actual_kwh','energy_end_actual_kwh']):
        a.close(tag+'.'+key,frame[key],values[:,i])
    a.close(tag+'.unused_grid',frame.unused_grid_kwh,np.minimum(q,values[:,3]))
    a.close(tag+'.pv_curtailment',frame.pv_curtailment_kwh,np.maximum(values[:,3]-q,0))
    q0 = frame.grid_original_kwh.to_numpy()
    expected = dict(original_cost_yuan=q0*price,increase_cost_yuan=1.5*price*np.maximum(q-q0,0),
                    decrease_adjustment_yuan=-.5*price*np.maximum(q0-q,0),emergency_cost_yuan=5*price*values[:,2])
    expected['contract_cost_yuan'] = expected['original_cost_yuan']+expected['increase_cost_yuan']+expected['decrease_adjustment_yuan']
    expected['total_cost_yuan'] = expected['contract_cost_yuan']+expected['emergency_cost_yuan']
    for key,value in expected.items():
        a.close(tag+'.'+key,frame[key],value,CTOL)
        if key in summary:
            a.close(tag+'.summary.'+key,summary[key],float(value.sum()),CTOL)
    daily = read(folder/'daily.csv')
    for key in daily.columns:
        if key in frame and key not in ['date','slot_id'] and np.issubdtype(daily[key].dtype,np.number):
            if key.endswith('_yuan') or key in ['emergency_kwh','charge_actual_kwh','discharge_actual_kwh','grid_effective_kwh','grid_original_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']:
                a.close(tag+'.daily.'+key,daily[key],frame.groupby('date',sort=False)[key].sum(),CTOL if key.endswith('_yuan') else ETOL)
    for key in ['grid_effective_kwh','grid_original_kwh','emergency_kwh','charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']:
        if key in summary:
            a.close(tag+'.summary.'+key,summary[key],float(frame[key].sum()),ETOL)
    a.close(tag+'.summary.initial',summary['initial_energy_kwh'],INITIAL)
    a.close(tag+'.summary.final',summary['final_energy_kwh'],float(values[-1,-1]))
    a.close(tag+'.summary.inventory_adjusted_cost',summary['inventory_adjusted_cost_yuan'],float(expected['total_cost_yuan'].sum()-.6895775*(values[-1,-1]-INITIAL)),CTOL)
    a.close(tag+'.summary.emergency_margin',summary['emergency_margin_yuan'],float(1000000-expected['emergency_cost_yuan'].sum()),CTOL)
    a.check(tag+'.summary.emergency_reference',summary['passes_emergency_reference']==(float(frame.emergency_cost_yuan.sum())<=1000000))
    a.close(tag+'.daily.initial_energy',daily.energy_start_actual_kwh,frame.groupby('date',sort=False).energy_start_actual_kwh.first())
    a.close(tag+'.daily.final_energy',daily.energy_end_actual_kwh,frame.groupby('date',sort=False).energy_end_actual_kwh.last())
    if tag=='q42_fixed':
        d112 = read(WORK/'results/q2_direct_v4/runs/D112/ledger.csv')
        a.close(tag+'.D112_procurement_regression',q,d112.grid_plan_kwh.to_numpy())
        a.close(tag+'.D112_physical_regression',values[:,5],d112.energy_end_actual_kwh.to_numpy())
    return frame,summary


def audit_evidence(a,folder,sources,ledger):
    tag = folder.name
    decisions = json.loads((folder/'decisions.json').read_text())
    versions = read(folder/'plan_versions.csv')
    total_candidates,total_scenarios = 0,0
    d112 = None
    if tag=='q42_fixed':
        with np.load(WORK/'results/q2_direct_v4/runs/D112/decision_evidence.npz') as z:
            d112 = {k:z[k] for k in ['q','score','risk_delta','selected_index']}
    expected_price,updates,pv_update,corrected = POLICIES[tag]
    expected_hours = [0,6,12,18] if updates else [0]
    expected_keys = [(date,hour) for date in sources.dates[31:].strftime('%Y-%m-%d') for hour in expected_hours]
    a.check(tag+'.complete_decision_schedule',[(m['date'],int(m['issue_hour'])) for m in decisions]==expected_keys)
    a.check(tag+'.version_rows',len(versions)==334*sum(144-6*h for h in expected_hours))
    held = None
    for meta in decisions:
        date,hour = meta['date'],int(meta['issue_hour'])
        day = (pd.Timestamp(date)-sources.dates[0]).days
        slot = hour*6
        path = Path(meta['evidence_file'])
        if not path.is_absolute():
            path = folder/path
        with np.load(path) as z:
            ev = {k:z[k] for k in z.files}
        q,net,price = ev['q'],ev['scenario_net'],ev['price']
        if d112 is not None:
            for key in ['q','score','risk_delta','selected_index']:
                a.close(tag+'.D112_candidate_'+key,ev[key],d112[key][day-31],CTOL if key=='score' else ETOL)
        total_candidates += len(q)
        total_scenarios += len(q)*len(net)
        a.check(tag+'.candidate_shape',q.shape==(6 if hour==0 else 7,144-slot))
        a.check(tag+'.candidate_nonnegative',np.isfinite(q)&(q>=-ETOL))
        source_hour = int(meta['source_hour'])
        correction = bool(meta['correction'])
        a.check(tag+'.source_hour_permission',source_hour==(hour if pv_update else 0))
        a.check(tag+'.correction_permission',correction==corrected)
        a.check(tag+'.price_permission',meta['price_method']==expected_price)
        a.check(tag+'.issue_timestamp',pd.Timestamp(meta['issue_time'])==pd.Timestamp(date)+pd.Timedelta(hours=hour))
        b0 = tag.lower().startswith('q42') or meta.get('pv_method')=='B0'
        load,pv = sources.forecast(day,source_hour,correction,b0)
        a.close(tag+'.load_hat',ev['load_hat'],load[slot:])
        a.close(tag+'.pv_hat',ev['pv_hat'],pv[slot:])
        raw = sources.b0[day,:,1] if b0 else sources.raw[day,source_hour//6]
        a.close(tag+'.raw_pv',ev['raw_pv'],raw[slot:])
        method = meta['price_method']
        a.close(tag+'.planning_price',price,sources.price(day,hour,method))
        pvmeta = meta.get('pv_metadata',{})
        if not b0:
            a.check(tag+'.pv_correction_activation',pvmeta['active']==(corrected and day>=90))
            a.check(tag+'.pv_midnight_cutoff',pd.Timestamp(pvmeta['training_cutoff'])==pd.Timestamp(date))
            a.close(tag+'.pv_bias',pvmeta['bias_kwh'],sources.bias[day,source_hour//6] if corrected else 0.)
            hist_raw = sources.raw[max(0,day-28):day,source_hour//6]
            count = int(np.sum(np.isfinite(hist_raw)&(hist_raw>0))) if corrected and day>=90 else 0
            a.check(tag+'.pv_training_rows',int(pvmeta['training_rows'])==count)
            if pvmeta.get('latest_target_end'):
                a.check(tag+'.pv_latest_completed',pd.Timestamp(pvmeta['latest_target_end'])<=pd.Timestamp(date))
        if method=='ols':
            pm = meta['price_metadata']
            issue = pd.Timestamp(date)+pd.Timedelta(hours=hour)
            a.check(tag+'.price_training_last',pd.Timestamp(pm['training_last_end'])==issue)
            a.check(tag+'.price_training_first',pd.Timestamp(pm['training_first_start'])==max(pd.Timestamp('2025-01-08'),issue-pd.Timedelta(days=28)))
            a.check(tag+'.price_training_rows',int(pm['training_rows'])==min(day*144+slot-1008,4032))
        history = list(range(max(1,day-112),day))
        dates = [str(sources.dates[j].date()) for j in history]
        a.check(tag+'.scenario_source_dates',meta['scenario_source_dates']==dates)
        a.check(tag+'.scenario_count',int(meta['scenario_count'])==len(history)==len(net))
        scenario = []
        residuals = []
        for j in history:
            hl,hp = sources.forecast(j,source_hour,correction,b0)
            residual = sources.net[j]-hl+hp
            scenario.append(load[slot:]-pv[slot:]+residual[slot:])
            if j>=day-28:
                residuals.append(residual)
        a.close(tag+'.scenario_net',net,np.asarray(scenario))
        residuals = np.asarray(residuals)[:,slot:]
        hours = np.arange(slot,144)//6
        risk = np.zeros(144-slot)
        for h in np.unique(hours):
            tau = .85 if 9<=h<11 else .65 if 11<=h<18 else .95 if 18<=h<22 else .8
            cols = hours==h
            risk[cols] = np.quantile(residuals[:,cols].ravel(),tau,method='linear')
        a.close(tag+'.risk_quantiles',ev['risk_delta'],risk)
        current_day = ledger.loc[ledger.date==date].reset_index(drop=True)
        initial = float(current_day.energy_start_actual_kwh.iloc[slot])
        a.close(tag+'.decision_initial_energy',meta['initial_energy_kwh'],initial)
        q0 = ev['q0']
        if hour==0:
            a.check(tag+'.midnight_empty_reference',len(q0)==len(ev['current'])==0)
            held = None
        else:
            a.close(tag+'.midnight_reference',q0,current_day.grid_original_kwh.to_numpy()[slot:])
            a.close(tag+'.keep_current_candidate',q[-1],ev['current'])
            a.close(tag+'.held_commitment_provenance',ev['current'],held[slot:])
        result = candidate_values(q,net,price,initial,q0)
        for key,value in result.items():
            a.close(tag+'.candidate_'+key,ev[key],value,ETOL if key=='end_energy' else CTOL)
        selected = int(np.flatnonzero(result['score']<=result['score'].min()+1e-8)[0])
        a.check(tag+'.selected_tie_first',selected==int(ev['selected_index'])==int(meta['selected_index']))
        a.check(tag+'.candidate_labels',meta['candidate_labels']==['profile_start','profile_incumbent','profile_final','point_start','point_incumbent','point_final','keep_current'][:len(q)])
        a.close(tag+'.point_initializer',q[3],np.maximum(load[slot:]-pv[slot:],0))
        if hour==0:
            held = q[selected].copy()
        else:
            held[slot:] = q[selected]
        logs = meta.get('optimizer',meta.get('optimizer_logs',[]))
        a.check(tag+'.two_optimizer_logs',len(logs)==2)
        for j,log in enumerate(logs):
            trace = np.array(log['evaluation_score_yuan'])
            a.check(tag+'.optimizer_trace_finite',len(trace)>0 and np.isfinite(trace).all())
            a.close(tag+'.optimizer_incumbent',result['score'][3*j+1],float(trace.min()),CTOL)
            a.close(tag+'.optimizer_logged_incumbent',result['score'][3*j+1],float(log['incumbent_score_yuan']),CTOL)
            a.check(tag+'.optimizer_incumbent_le_start',result['score'][3*j+1]<=result['score'][3*j]+CTOL)
            a.check(tag+'.optimizer_trace_count',len(trace)==int(log['nfev']))
        if meta.get('initializer_failure') is None:
            grid = ev['initializer_grid_kwh']
            charge,discharge = ev['initializer_charge_kwh'],ev['initializer_discharge_kwh']
            begin,end = ev['initializer_energy_start_kwh'],ev['initializer_energy_end_kwh']
            surplus = ev.get('initializer_surplus_kwh',ev.get('initializer_curtailment_kwh'))
            a.close(tag+'.profile_initializer',q[0],np.maximum(grid,0))
            a.close(tag+'.initializer_begin',begin[0],initial)
            a.close(tag+'.initializer_terminal',end[-1],1200.)
            a.close(tag+'.initializer_continuity',begin[1:],end[:-1])
            a.close(tag+'.initializer_soc_equation',end,begin+.9*charge-discharge/.9)
            a.close(tag+'.initializer_balance',grid+pv[slot:]+discharge,
                    load[slot:]+risk+charge+surplus)
            a.check(tag+'.initializer_limits',(begin>=1200-ETOL)&(begin<=10800+ETOL)&(charge>=-ETOL)&(charge<=5000/6+ETOL)&(discharge>=-ETOL)&(discharge<=5000/6+ETOL))
            a.check(tag+'.initializer_no_simultaneous',(charge<=ETOL)|(discharge<=ETOL))
        version = versions.loc[(versions.date==date)&(versions.issue_hour==hour)].sort_values('slot_id')
        a.check(tag+'.version_slots',np.array_equal(version.slot_id,np.arange(slot+1,145)))
        a.close(tag+'.version_selected_q',version.grid_kwh.to_numpy(),q[selected])
        a.close(tag+'.version_original_q',version.grid_original_kwh.to_numpy(),current_day.grid_original_kwh.to_numpy()[slot:])
        if hour==0:
            a.close(tag+'.midnight_ledger_q0',current_day.grid_original_kwh.to_numpy(),q[selected])
        next_hours = [int(m['issue_hour']) for m in decisions if m['date']==date and int(m['issue_hour'])>hour]
        stop = min(next_hours)*6 if next_hours else 144
        a.close(tag+'.executed_commitment',current_day.grid_effective_kwh.to_numpy()[slot:stop],q[selected,:stop-slot])
    a.check(tag+'.decision_keys_unique',len({(m['date'],int(m['issue_hour'])) for m in decisions})==len(decisions))
    a.check(tag+'.decision_hours',all(int(m['issue_hour']) in [0,6,12,18] for m in decisions))
    all_logs = [log for m in decisions for log in m['optimizer']]
    summary = json.loads((folder/'summary.json').read_text())
    for key,value in dict(optimizer_count=len(all_logs),optimizer_success_count=sum(bool(log['success']) for log in all_logs),
                          optimizer_non_success_count=sum(not log['success'] for log in all_logs),
                          optimizer_exception_count=sum(log.get('exception') is not None for log in all_logs),
                          initializer_fallback_count=sum(m.get('initializer_failure') is not None for m in decisions),
                          retained_start_selected_count=sum(m['selected_index'] in [0,3] for m in decisions),
                          keep_current_selected_count=sum(m['selected_index']==6 for m in decisions),
                          optimizer_nfev=sum(log['nfev'] for log in all_logs)).items():
        a.check(tag+'.summary.'+key,summary[key]==value)
    return dict(decisions=len(decisions),candidate_vectors=total_candidates,candidate_scenario_paths=total_scenarios)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources-only',action='store_true')
    parser.add_argument('--policy',action='append')
    args = parser.parse_args()
    a = Audit()
    verifier_self_checks(a)
    sources = Sources(a)
    frozen_regression(a,sources)
    metrics = dict(source_actual_rows=52560,B0_rebuilt_days=364,raw_PV_rebuilt_issues=1460,
                   independently_refit_price_issues=len(sources.price_cache),source_hashes=sources.hashes,policies={})
    pending = ['Independent XLSX readback is owned by the workbook reviewer and not asserted here.']
    if not args.sources_only:
        folders = sorted(p for p in (ROOT/'runs').glob('*') if p.is_dir() and p.name in POLICIES)
        if args.policy:
            folders = [ROOT/'runs'/name for name in args.policy]
        if not folders:
            pending.append('Production annual policy results are not yet available.')
        for folder in folders:
            if not (folder/'summary.json').exists():
                pending.append(str(folder.name)+': incomplete run')
                continue
            print('Auditing '+folder.name,flush=True)
            try:
                ledger,summary = audit_ledger(a,folder,sources)
                coverage = audit_evidence(a,folder,sources,ledger)
                metrics['policies'][folder.name] = dict(ledger_rows=len(ledger),total_cost_yuan=summary['total_cost_yuan'],**coverage)
            except Exception as exc:
                a.check(folder.name+'.audit_exception',False,error=f'{type(exc).__name__}: {exc}')
        missing = sorted(set(POLICIES)-set(metrics['policies']))
        if missing:
            pending.append('Annual policy evidence not covered in this invocation: '+', '.join(missing)+'.')
        requested = set(args.policy) if args.policy else set(POLICIES)
        a.check('run.complete_requested_policy_coverage',requested<=set(metrics['policies']))
    else:
        pending.append('Annual policy evidence audit was not requested in this source-only invocation.')
    report = dict(created_utc=datetime.now(timezone.utc).isoformat(),passed=a.passed,
                  scope='sources_and_frozen_regressions' if args.sources_only else 'sources_regressions_and_available_policy_evidence',
                  independence='Raw XLSX, NumPy, pandas and openpyxl; no production imports.',
                  validator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  tolerances=dict(physical_kwh=ETOL,cash_yuan=CTOL),metrics=metrics,
                  checks=list(a.rows.values()),pending=pending)
    suffix = 'independent_sources' if args.sources_only else 'independent_report'
    (OUT/(suffix+'.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    failures = [r for r in a.rows.values() if not r['passed']]
    lines = ['# Independent validation', '', f"Executed scope: {report['scope']}",
             f"Executed checks: {'PASS' if a.passed else 'FAIL'}; {len(failures)} failed check groups.",
             '', 'Original Appendix 1–4 workbooks were independently reconstructed and compared with processed inputs. B0 forecasts were refit from each completed prefix. Appendix 3 interpolation uses the preceding published forecast as first-hour anchor, and historical PV corrections use their own midnight cutoffs, same-day horizons, same issue hour and April 1 activation. Prices are independently refit using causal 28-day OLS.',
             '', 'Working assumptions remain interval-end labels, average interval power, point-power trapezoidal forecasts, end-of-interval actual availability and settlement rule A. These are not newly confirmed interpretations of the original problem.',
             '', 'Frozen Q2 D112 and Q1 regressions are independently recomputed from source prices and physical equations.', '', '## Coverage']
    for name,coverage in metrics['policies'].items():
        lines.append(f"- {name}: {coverage['ledger_rows']} ledger intervals, {coverage['decisions']} decisions, {coverage['candidate_vectors']} candidate vectors, {coverage['candidate_scenario_paths']} candidate-scenario physical paths.")
    lines += ['', '## Failures']+[f"- {r['check']}: {r['failures']} failures; {r.get('error','')}" for r in failures]
    if not failures:
        lines.append('- None in the executed checks.')
    lines += ['', '## Pending / outside scope']+['- '+v for v in pending]
    (OUT/(suffix+'.md')).write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(passed=a.passed,failures=failures,policies=metrics['policies']),indent=2),flush=True)
    raise SystemExit(0 if a.passed else 1)


if __name__=='__main__':
    main()
