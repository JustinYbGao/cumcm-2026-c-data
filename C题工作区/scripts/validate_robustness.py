"""Independent saved-file checks; never imports a planner or actual executor."""
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'results/robustness'
for name in ('TMPDIR', 'TMP', 'TEMP'):
    os.environ[name] = str(WORK / 'data/interim/robustness')
POLICIES = ['fixed_raw','fixed_w28','fixed_w14','fixed_w56','efficiency_raw',
            'efficiency_w28','soft_raw','soft_w28','variable_raw','variable_w28']
INITIAL = 7268.4231640740745
DATES = ['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
SUMS = ['grid_original_kwh','grid_effective_kwh','emergency_kwh','original_cost_yuan',
        'increase_cost_yuan','decrease_adjustment_yuan','contract_cost_yuan','emergency_cost_yuan',
        'total_cost_yuan','charge_actual_kwh','discharge_actual_kwh','surplus_kwh',
        'unused_grid_kwh','pv_curtailment_kwh']


def read(path):
    return pd.read_csv(path, float_precision='round_trip')


def load(path):
    return json.loads(path.read_text())


def settlement_a(original, final, price):
    return price * (original + 1.5 * np.maximum(final-original, 0)
                    - .5 * np.maximum(original-final, 0))


class Audit:
    def __init__(self):
        self.checks = {}
        self.residuals = {}

    def test(self, key, value):
        self.checks[key] = bool(value)

    def close(self, key, actual, expected, tol=1e-6):
        a, b = np.asarray(actual), np.asarray(expected)
        if (a.ndim and b.ndim and a.shape != b.shape) or not (np.isfinite(a).all() and np.isfinite(b).all()):
            self.checks[key] = False
            self.residuals[key] = None
            return
        residual = float(np.max(np.abs(a-b), initial=0))
        self.residuals[key] = residual
        self.test(key, residual <= tol)

    def frame(self, key, actual, expected):
        self.test(key+'_columns', actual.columns.tolist() == expected.columns.tolist())
        self.test(key+'_rows', len(actual) == len(expected))
        if actual.shape != expected.shape:
            return
        for col in expected:
            if pd.api.types.is_bool_dtype(expected[col]):
                self.test(key+'_'+col, actual[col].tolist() == expected[col].tolist())
            elif pd.api.types.is_numeric_dtype(expected[col]):
                missing=expected[col].isna()
                self.test(key+'_'+col+'_missing',actual[col].isna().tolist()==missing.tolist())
                self.close(key+'_'+col, actual.loc[~missing,col], expected.loc[~missing,col], 1e-5)
            else:
                self.test(key+'_'+col, actual[col].fillna('').astype(str).tolist() == expected[col].fillna('').astype(str).tolist())


def main():
    a = Audit()
    physical = load(WORK/'configs/model_baseline.json')
    b = physical['battery']; lo=b['min_energy_kwh']; hi=b['max_energy_kwh']
    mc=b['max_charge_kw']*physical['interval_minutes']/60
    md=b['max_discharge_kw']*physical['interval_minutes']/60
    fixed = read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy()
    penalty = .9*fixed.mean()
    truth = read(WORK/'data/processed/actual_10min.csv')
    actual = truth.set_index(['date','slot_id'])
    actual_times = truth.set_index('interval_start'); actual_times.index=pd.to_datetime(actual_times.index)
    q2 = read(WORK/'results/q2/selected/ledger.csv').set_index(['date','slot_id'])
    for m in load(WORK/'results/q2/selected/models_and_solvers.json'):
        a.test('load_history_'+m['date'],pd.Timestamp(m['forecast']['history_end'])<=pd.Timestamp(m['date']))
    pv=read(WORK/'data/processed/pv_forecast_10min.csv')
    for c in ['issue_time','interval_start','interval_end']:pv[c]=pd.to_datetime(pv[c])
    raw=pv.set_index(['issue_time','interval_start'])
    hist=pv.loc[(pv.interval_end<=pv.issue_time.dt.normalize()+pd.Timedelta(days=1)) &
                pv.interval_start.isin(actual_times.index) & (pv.pv_forecast_kwh>0)].copy()
    hist['residual']=actual_times.loc[hist.interval_start].pv_actual_kwh.to_numpy()-hist.pv_forecast_kwh.to_numpy()
    hist_hours={h:g for h,g in hist.groupby(hist.issue_time.dt.hour)}
    bias_cache={}
    prices=read(WORK/'results/q4/price_forecasts.csv')
    for c in ['issue_time','interval_start']:prices[c]=pd.to_datetime(prices[c])
    prices=prices.set_index(['issue_time','interval_start'])
    price_models={m['issue_time']:m for m in load(WORK/'results/q4/price_models.json')}
    expected_time=pd.date_range('2025-02-01','2026-01-01',freq='10min',inclusive='left')
    ledger_archive={}; summary_archive={}; expected_bias_records=[]
    config=load(OUT/'config_snapshot.json')
    a.test('config_snapshot',config==load(WORK/'configs/robustness.json'))
    a.test('config_scope',list(config['policies'])==POLICIES and config['evaluation_start']=='2025-02-01' and config['evaluation_end']=='2025-12-31' and config['correction_start']=='2025-04-01' and config['update_hours']==[0,6,12,18] and config['settlement_rule']=='A')
    a.close('config_initial',config['initial_energy_kwh'],INITIAL)
    for policy in POLICIES:
        folder=OUT/policy; f=read(folder/'ledger.csv'); v=read(folder/'plan_versions.csv'); sts=load(folder/'solvers.json')
        ledger_archive[policy]=f
        efficiency=np.sqrt(.9) if policy.startswith('efficiency_') else .9
        soft=policy.startswith('soft_'); variable=policy.startswith('variable_')
        window=0 if policy.endswith('_raw') else int(policy.rsplit('w',1)[1])
        key=policy; ec=ed=efficiency
        a.test(key+'_time',pd.to_datetime(f.interval_start).tolist()==expected_time.tolist() and pd.to_datetime(f.interval_end).tolist()==(expected_time+pd.Timedelta(minutes=10)).tolist())
        a.test(key+'_keys',not f.duplicated(['date','slot_id']).any() and f.slot_id.tolist()==list(range(1,145))*334)
        a.test(key+'_date_keys',f.date.tolist()==expected_time.strftime('%Y-%m-%d').tolist())
        real=actual.loc[list(zip(f.date,f.slot_id))]
        p=real.actual_price_yuan_per_kwh.to_numpy() if variable else np.tile(fixed,334)
        q=f.grid_effective_kwh.to_numpy(); q0=f.grid_original_kwh.to_numpy(); s=f.energy_start_actual_kwh.to_numpy(); e=f.energy_end_actual_kwh.to_numpy()
        c=f.charge_actual_kwh.to_numpy(); d=f.discharge_actual_kwh.to_numpy(); u=f.emergency_kwh.to_numpy(); w=f.surplus_kwh.to_numpy()
        a.close(key+'_truth_load',f.load_actual_kwh,real.load_actual_kwh);a.close(key+'_truth_pv',f.pv_actual_kwh,real.pv_actual_kwh)
        a.close(key+'_initial',s[0],INITIAL);a.close(key+'_continuous',s[1:],e[:-1]);a.close(key+'_state',e,s+ec*c-d/ed)
        net=q+real.pv_actual_kwh.to_numpy()-real.load_actual_kwh.to_numpy()
        expectedc=np.minimum.reduce([np.maximum(net,0),np.full(len(f),mc),np.maximum(0,(hi-s)/ec)])
        expectedd=np.minimum.reduce([np.maximum(-net,0),np.full(len(f),md),np.maximum(0,ed*(s-lo))])
        a.close(key+'_charge',c,expectedc);a.close(key+'_discharge',d,expectedd);a.close(key+'_emergency',u,np.maximum(-net-expectedd,0))
        a.close(key+'_balance',q+u+real.pv_actual_kwh.to_numpy()+d-real.load_actual_kwh.to_numpy()-c-w,0)
        a.test(key+'_bounds',min(s.min(),e.min())>=lo-1e-6 and max(s.max(),e.max())<=hi+1e-6 and min(q.min(),q0.min(),u.min(),w.min())>=-1e-6)
        a.close(key+'_unused_grid',f.unused_grid_kwh,np.minimum(q,w));a.close(key+'_curtailment',f.pv_curtailment_kwh,w-np.minimum(q,w))
        a.close(key+'_price',f.price_yuan_per_kwh,p);a.close(key+'_settlement_price',f.settlement_price_yuan_per_kwh,p)
        a.close(key+'_actual_price',f.actual_price_yuan_per_kwh,real.actual_price_yuan_per_kwh)
        a.close(key+'_original_fee',f.original_cost_yuan,p*q0)
        a.close(key+'_increase_fee',f.increase_cost_yuan,1.5*p*np.maximum(q-q0,0))
        a.close(key+'_decrease_fee',f.decrease_adjustment_yuan,-.5*p*np.maximum(q0-q,0))
        a.close(key+'_contract',f.contract_cost_yuan,settlement_a(q0,q,p));a.close(key+'_emergency_fee',f.emergency_cost_yuan,5*p*u)
        a.close(key+'_bill',f.total_cost_yuan,settlement_a(q0,q,p)+5*p*u)
        a.close(key+'_load_source',f.load_forecast_kwh,q2.loc[list(zip(f.date,f.slot_id))].load_forecast_kwh)
        groups=v.groupby(['date','issue_hour'],sort=False); midnight=v.loc[v.issue_hour==0].set_index(['date','slot_id'])
        a.test(key+'_plan_count',len(groups)==len(sts)==334*4 and not v.duplicated(['date','issue_hour','slot_id']).any())
        a.close(key+'_q0_source',q0,midnight.loc[list(zip(f.date,f.slot_id))].grid_kwh)
        a.close(key+'_active_hour',f.active_issue_hour,((f.slot_id-1)//36)*6)
        latest=v.set_index(['date','issue_hour','slot_id']).loc[list(zip(f.date,f.active_issue_hour,f.slot_id))]
        for outcol,plancol in [('grid_effective_kwh','grid_kwh'),('pv_forecast_kwh','pv_forecast_kwh'),('pv_raw_forecast_kwh','pv_raw_forecast_kwh'),('pv_corrected_forecast_kwh','pv_forecast_kwh'),('planning_price_yuan_per_kwh','planning_price_yuan_per_kwh')]:
            a.close(key+'_active_'+outcol,f[outcol],latest[plancol])
        day_starts=f.groupby('date').energy_start_actual_kwh.first(); event_states=f.set_index(['date','slot_id']).energy_start_actual_kwh
        for st in sts:
            date=st['date'];hour=int(st['issue_hour']);issue=pd.Timestamp(st['issue_time']);part=groups.get_group((date,hour));label=key+'_'+str(issue)
            a.test(label+'_horizon',hour in [0,6,12,18] and part.slot_id.tolist()==list(range(hour*6+1,145)))
            targets=pd.date_range(issue,pd.Timestamp(date)+pd.Timedelta(days=1),freq='10min',inclusive='left')
            a.test(label+'_time',pd.to_datetime(part.interval_start).tolist()==targets.tolist() and pd.to_datetime(part.interval_end).tolist()==(targets+pd.Timedelta(minutes=10)).tolist())
            expectedpv=raw.loc[[(issue,t) for t in targets]].pv_forecast_kwh.to_numpy()
            rawpv=expectedpv.copy()
            a.close(label+'_raw_pv',part.pv_raw_forecast_kwh,expectedpv)
            active=window>0 and issue>=pd.Timestamp('2025-04-01')
            correction=st['correction'];a.test(label+'_active',correction['active']==active)
            a.test(label+'_correction_identity',pd.Timestamp(correction['issue_time'])==issue and correction['issue_hour']==hour and correction['window_days']==(window or None))
            if active:
                ck=(str(issue),window)
                if ck not in bias_cache:
                    h=hist_hours[hour];cut=issue.normalize();h=h.loc[(h.issue_time<issue)&(h.interval_end<=cut)&(h.interval_start>=cut-pd.Timedelta(days=window))]
                    bias_cache[ck]=(float(h.residual.mean()) if len(h) else 0.,len(h),None if h.empty else str(h.interval_end.max()))
                bias,n,last=bias_cache[ck]
                a.close(label+'_bias',correction['bias_kwh'],bias)
                a.test(label+'_bias_window',correction['window_days']==window and correction['training_rows']==n and correction['latest_target_end']==last and pd.Timestamp(correction['training_cutoff'])==issue.normalize())
                a.test(label+'_bias_counts',correction['positive_training_rows']==n and correction['active_positive_intervals']==int((rawpv>0).sum()) and correction['clipped_intervals']==int(((rawpv>0)&(rawpv+bias<0)).sum()))
                expectedpv=np.where(expectedpv>0,np.maximum(0,expectedpv+bias),0.)
                expected_bias_records.append({'policy':policy,**correction})
            else:
                a.test(label+'_inactive_history',correction['training_rows']==0 and correction['bias_kwh']==0 and correction['latest_target_end'] is None)
            a.close(label+'_pv',part.pv_forecast_kwh,expectedpv)
            a.close(label+'_pv_alias',part.pv_corrected_forecast_kwh,expectedpv)
            a.close(label+'_load',part.load_forecast_kwh,q2.loc[list(zip(part.date,part.slot_id))].load_forecast_kwh)
            planprice=prices.loc[[(issue,t) for t in targets]].price_forecast_yuan_per_kwh.to_numpy() if variable else fixed[hour*6:]
            a.close(label+'_planning_price',part.planning_price_yuan_per_kwh,planprice)
            if variable:
                m=price_models[str(issue)]
                a.test(label+'_price_causal',pd.Timestamp(m['training_last_end'])==issue and pd.Timestamp(m['training_first_start'])<issue)
            splan=part.energy_start_kwh.to_numpy();eplan=part.energy_end_kwh.to_numpy();cplan=part.charge_kwh.to_numpy();dplan=part.discharge_kwh.to_numpy();qplan=part.grid_kwh.to_numpy();uplan=part.emergency_plan_kwh.to_numpy();wplan=part.surplus_kwh.to_numpy()
            q0plan=midnight.loc[list(zip(part.date,part.slot_id))].grid_kwh.to_numpy()
            a.close(label+'_q0',part.grid_original_kwh,q0plan);a.close(label+'_initial',splan[0],event_states.loc[(date,hour*6+1)])
            a.close(label+'_saved_initial',st['initial_energy_kwh'],splan[0]);a.close(label+'_target',st['terminal_target_kwh'],day_starts.loc[date])
            a.close(label+'_state',eplan,splan+ec*cplan-dplan/ed);a.close(label+'_continuous',splan[1:],eplan[:-1])
            a.close(label+'_balance',qplan+uplan+expectedpv+dplan-part.load_forecast_kwh.to_numpy()-cplan-wplan,0)
            a.test(label+'_bounds',min(splan.min(),eplan.min())>=lo-1e-6 and max(splan.max(),eplan.max())<=hi+1e-6 and min(qplan.min(),cplan.min(),dplan.min(),uplan.min(),wplan.min())>=-1e-6 and cplan.max()<=mc+1e-6 and dplan.max()<=md+1e-6)
            a.test(label+'_mutex',np.all((cplan<=1e-6)|(dplan<=1e-6)) and np.all((cplan<=1e-6)|(uplan<=1e-6)))
            a.test(label+'_emergency_bound',np.all(uplan<=part.load_forecast_kwh+1e-6))
            a.close(label+'_charge_mode',part.charge_mode,np.rint(part.charge_mode))
            a.close(label+'_efficiency_c',part.eta_charge,ec);a.close(label+'_efficiency_d',part.eta_discharge,ed)
            a.test(label+'_setting',st['soft_terminal']==soft and part.soft_terminal.eq(soft).all() and st['planning_price_method']==('q4_causal_ols' if variable else 'fixed') and st['settlement_price_method']==('actual_variable' if variable else 'fixed'))
            a.test(label+'_load_issue',pd.Timestamp(st['load_issue_time'])==pd.Timestamp(date))
            if soft:a.close(label+'_penalty',part.terminal_penalty_yuan_per_kwh,penalty);a.close(label+'_saved_penalty',st['terminal_penalty_yuan_per_kwh'],penalty)
            else:a.test(label+'_no_penalty',st['terminal_penalty_yuan_per_kwh'] is None and part.terminal_penalty_yuan_per_kwh.isna().all())
            if not soft:a.close(label+'_terminal',eplan[-1],day_starts.loc[date]);a.close(label+'_no_planned_emergency',uplan,0)
            contract=settlement_a(q0plan,qplan,planprice);term=penalty*abs(eplan[-1]-day_starts.loc[date]) if soft else 0.
            a.close(label+'_contract',part.contract_cost_forecast_yuan,contract)
            objective=float(contract.sum()+np.dot(5*planprice,uplan)+term)
            a.close(label+'_objective',st['solver']['objective_yuan'],objective,1e-5)
            a.test(label+'_optimal',st['solver']['status']=='Optimal' and st['solver']['mip_gap']<=1e-9 and st['solver']['lower_bound_yuan']<=objective+1e-5)
        daily=f.groupby('date')[SUMS].sum()
        daily['energy_start_actual_kwh']=f.groupby('date').energy_start_actual_kwh.first();daily['energy_end_actual_kwh']=f.groupby('date').energy_end_actual_kwh.last()
        daily['emergency_intervals']=f.assign(event=f.emergency_kwh>1e-6).groupby('date').event.sum()
        a.frame(key+'_daily',read(folder/'daily.csv'),daily.reset_index())
        summary=load(folder/'summary.json');summary_archive[policy]=summary
        for col in SUMS:a.close(key+'_summary_'+col,summary[col],f[col].sum(),1e-5)
        a.close(key+'_summary_start',summary['initial_energy_kwh'],INITIAL);a.close(key+'_summary_end',summary['final_energy_kwh'],e[-1])
        a.test(key+'_summary_scope',summary['days']==334 and summary['intervals']==334*144 and summary['rule']=='A')
        april=f.loc[f.date>='2025-04-01'];april_start=float(april.energy_start_actual_kwh.iloc[0])
        expected_summary={'inventory_reference_yuan_per_kwh':penalty,
            'inventory_adjustment_yuan':-penalty*(e[-1]-INITIAL),
            'inventory_adjusted_cost_yuan':float(f.total_cost_yuan.sum())-penalty*(e[-1]-INITIAL),
            'april_december_cost_yuan':float(april.total_cost_yuan.sum()),
            'april_december_initial_energy_kwh':april_start,'april_december_final_energy_kwh':e[-1],
            'april_december_inventory_adjustment_yuan':-penalty*(e[-1]-april_start),
            'april_december_inventory_adjusted_cost_yuan':float(april.total_cost_yuan.sum())-penalty*(e[-1]-april_start)}
        for col,value in expected_summary.items():a.close(key+'_summary_'+col,summary[col],value,1e-5)
        a.test(key+'_summary_identity',summary['policy']==policy and summary['terminal']==('soft' if soft else 'hard') and summary['pv_window_days']==(window or None))
        a.close(key+'_summary_efficiency',summary['eta_charge'],ec);a.close(key+'_summary_discharge_efficiency',summary['eta_discharge'],ed)
        a.test(key+'_summary_solver_count',summary['solves']==len(sts))
        a.close(key+'_summary_solver_time',summary['solver_seconds'],sum(st['solver']['runtime_seconds'] for st in sts))
        representative=f.loc[f.date.isin(DATES)]
        t1=representative.loc[representative.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_original_kwh','grid_effective_kwh']]
        a.frame(key+'_table1',read(folder/'table1_representative.csv'),t1.reset_index(drop=True))
        t2=representative.assign(block_start_minute=(representative.slot_id-1)//24*240).groupby(['date','block_start_minute'])[['charge_actual_kwh','discharge_actual_kwh']].sum().reset_index();t2['block_end_minute']=t2.block_start_minute+240
        a.frame(key+'_table2',read(folder/'table2_representative.csv'),t2)
        events=[]
        for date,g in f.groupby('date',sort=False):
            active_rows=g.loc[g.emergency_kwh>1e-6]
            for _,part in active_rows.groupby(active_rows.slot_id.diff().ne(1).cumsum()):
                events.append({'date':date,'interval_start':part.interval_start.iloc[0],'interval_end':part.interval_end.iloc[-1],'intervals':len(part),'emergency_kwh':float(part.emergency_kwh.sum())})
        events=pd.DataFrame(events,columns=['date','interval_start','interval_end','intervals','emergency_kwh'])
        a.frame(key+'_events',read(folder/'emergency_events.csv'),events)
        a.frame(key+'_table3',read(folder/'table3_representative.csv'),events.loc[events.date.isin(DATES)].reset_index(drop=True))
        print(policy,'PASS' if all(value for k,value in a.checks.items() if k.startswith(policy+'_')) else 'FAIL',flush=True)
    # Switching correction on April 1 must preserve each setting's common prior state.
    for corrected in [p for p in POLICIES if not p.endswith('_raw')]:
        rawname=corrected.split('_')[0]+'_raw';r=ledger_archive[rawname];f=ledger_archive[corrected];mask=f.date<'2025-04-01'
        for col in ['grid_effective_kwh','total_cost_yuan','energy_end_actual_kwh']:
            a.close(corrected+'_pre_switch_'+col,f.loc[mask,col],r.loc[mask,col])
    a.test('bias_model_archive',load(OUT/'pv_bias_models.json')==expected_bias_records)
    a.frame('comparison',read(OUT/'comparison.csv'),pd.DataFrame([summary_archive[p] for p in POLICIES]))
    pairs=[('fixed_w14','fixed_raw','fixed',14),('fixed_w28','fixed_raw','fixed',28),
           ('fixed_w56','fixed_raw','fixed',56),('efficiency_w28','efficiency_raw','efficiency',28),
           ('soft_w28','soft_raw','soft_terminal',28),('variable_w28','variable_raw','variable_price',28)]
    expected_pairs=[]
    for corrected,rawname,setting,window in pairs:
        r=summary_archive[rawname];c=summary_archive[corrected]
        expected_pairs.append({'setting':setting,'window_days':window,'raw_policy':rawname,'corrected_policy':corrected,
            'april_december_raw_cost_yuan':r['april_december_cost_yuan'],
            'april_december_corrected_cost_yuan':c['april_december_cost_yuan'],
            'april_december_saving_yuan':r['april_december_cost_yuan']-c['april_december_cost_yuan'],
            'april_december_raw_inventory_adjusted_cost_yuan':r['april_december_inventory_adjusted_cost_yuan'],
            'april_december_corrected_inventory_adjusted_cost_yuan':c['april_december_inventory_adjusted_cost_yuan'],
            'april_december_inventory_adjusted_saving_yuan':r['april_december_inventory_adjusted_cost_yuan']-c['april_december_inventory_adjusted_cost_yuan'],
            'full_334_raw_cost_yuan':r['total_cost_yuan'],'full_334_corrected_cost_yuan':c['total_cost_yuan'],
            'full_334_saving_yuan':r['total_cost_yuan']-c['total_cost_yuan'],
            'is_final_deployed_w28_comparison':corrected=='fixed_w28'})
    a.frame('paired_comparison',read(OUT/'paired_comparison.csv'),pd.DataFrame(expected_pairs))
    old=read(WORK/'results/q3/all_A/ledger.csv');current=ledger_archive['fixed_raw']
    for col in ['grid_effective_kwh','total_cost_yuan','energy_start_actual_kwh','energy_end_actual_kwh']:
        a.close('fixed_raw_baseline_'+col,current[col],old[col])
    before=load(OUT/'input_code_hashes_before.json');after=load(OUT/'input_code_hashes_after.json')
    a.test('before_after_hashes',before==after)
    for path,digest in before.items():a.test('source_'+path,hashlib.sha256((WORK/path).read_bytes()).hexdigest()==digest)
    status=load(OUT/'run_status.json')
    a.test('completed',status['completed'] and status['inputs_unchanged'] and status['policy_count']==10 and status['evaluation_days_each']==334 and status['policies']==POLICIES)
    for phase in ['before','after']:
        a.test('status_hash_'+phase,status['input_code_hashes_'+phase+'_sha256']==hashlib.sha256((OUT/('input_code_hashes_'+phase+'.json')).read_bytes()).hexdigest())
    numeric=[x for x in a.residuals.values() if x is not None]
    report={'passed':all(a.checks.values()),'check_count':len(a.checks),'failed':[k for k,v in a.checks.items() if not v],
            'max_residual':max(numeric,default=0),'checks':a.checks,'residuals':a.residuals,
            'independence':'No planner, correction or executor imports; saved source forecasts and causal metadata checked, all saved physical plans and actual bills reconstructed.'}
    (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('Robustness audit',report['passed'],report['check_count'],'checks',report['failed'][:20],flush=True)
    if not report['passed']:sys.exit(1)


if __name__=='__main__':
    main()
