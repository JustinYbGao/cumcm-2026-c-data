"""Independent Q4 audit derived from the Q3 constraint audit. No planner/executor imports."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[1]
OUT=WORK/'results/q4'
DATES=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']


def read(path):return pd.read_csv(path,float_precision='round_trip')


def audit_price_models(cfg,actual,prices_saved):
    """Rebuild every OLS matrix from permitted training rows, without forecasting code."""
    checks={};max_errors={'coefficients':0.,'forecasts':0.};sources=actual.actual_price_yuan_per_kwh
    models=json.loads((OUT/'price_models.json').read_text())
    expected=[day+pd.Timedelta(hours=hour) for day in pd.date_range(cfg['evaluation_start'],cfg['evaluation_end']) for hour in [0,6,12,18]]
    checks['all_issue_times']=[pd.Timestamp(m['issue_time']) for m in models]==expected
    checks['unique_forecast_keys']=not prices_saved.index.duplicated().any()
    for meta in models:
        issue=pd.Timestamp(meta['issue_time']);key=str(issue)
        first=max(sources.index[0]+pd.Timedelta(days=7),issue-pd.Timedelta(days=28))
        train=pd.date_range(first,issue,freq='10min',inclusive='left')
        target=pd.date_range(issue,issue.normalize()+pd.Timedelta(days=1),freq='10min',inclusive='left')
        def matrix(times):
            phase=np.array([t.hour*60+t.minute for t in times])/1440
            x=np.empty((len(times),13));x[:,0]=1
            for j in [1,2]:x[:,2*j-1]=np.sin(2*np.pi*j*phase);x[:,2*j]=np.cos(2*np.pi*j*phase)
            x[:,5]=sources.loc[times-pd.Timedelta(days=1)].to_numpy()
            x[:,6]=sources.loc[times-pd.Timedelta(days=7)].to_numpy()
            for j in range(1,7):x[:,6+j]=(times.weekday==j).astype(float)
            return x
        beta,_,rank,s=np.linalg.lstsq(matrix(train),sources.loc[train].to_numpy(),rcond=None)
        coefficient_error=float(np.max(np.abs(beta-np.array(meta['coefficients']))))
        checks[key+'_coefficients']=coefficient_error<=1e-9
        max_errors['coefficients']=max(max_errors['coefficients'],coefficient_error)
        checks[key+'_causal_training']=pd.Timestamp(meta['training_first_start'])==train[0] and pd.Timestamp(meta['training_last_end'])==issue and len(train)==meta['training_rows'] and train[-1]+pd.Timedelta(minutes=10)<=issue
        checks[key+'_known_target_lags']=(target[-1]-pd.Timedelta(days=1)+pd.Timedelta(minutes=10)<=issue)
        checks[key+'_rank']=rank==meta['rank'] and meta['feature_count']==13
        raw=matrix(target)@beta;forecast=np.maximum(raw,cfg['price_floor_yuan_per_kwh'])
        saved=prices_saved.loc[[(issue,t) for t in target]]
        error=float(np.max(np.abs(forecast-saved.price_forecast_yuan_per_kwh.to_numpy())))
        checks[key+'_forecasts']=error<=1e-9;max_errors['forecasts']=max(max_errors['forecasts'],error)
        checks[key+'_forecast_ends']=pd.to_datetime(saved.interval_end).tolist()==(target+pd.Timedelta(minutes=10)).tolist()
        checks[key+'_lag7']=np.max(np.abs(saved.lag7_forecast_yuan_per_kwh.to_numpy()-sources.loc[target-pd.Timedelta(days=7)].to_numpy()))<=1e-12
        checks[key+'_floor']=meta['floor_activations']==int((raw<cfg['price_floor_yuan_per_kwh']).sum()) and meta['floor_yuan_per_kwh']==cfg['price_floor_yuan_per_kwh']
        checks[key+'_extrema']=abs(meta['raw_forecast_min']-raw.min())<=1e-9 and abs(meta['raw_forecast_max']-raw.max())<=1e-9
    checks={k:bool(v) for k,v in checks.items()}
    print('Price models',len(models),'PASS' if all(checks.values()) else 'FAIL',flush=True)
    return {'passed':all(checks.values()),'check_count':len(checks),'checks':checks,'max_errors':max_errors}


def main():
    cfg=json.loads((OUT/'config_snapshot.json').read_text())
    physical=json.loads((OUT/'physical_snapshot.json').read_text())
    b=physical['battery'];ec=b['eta_charge'];ed=b['eta_discharge']
    lo=b['min_energy_kwh'];hi=b['max_energy_kwh']
    mc=b['max_charge_kw']*physical['interval_minutes']/60
    md=b['max_discharge_kw']*physical['interval_minutes']/60
    actual=read(WORK/'data/processed/actual_10min.csv')
    actual.index=pd.to_datetime(actual.interval_start)
    pv=read(WORK/'data/processed/pv_forecast_10min.csv')
    pv.index=pd.MultiIndex.from_arrays([pd.to_datetime(pv.issue_time),pd.to_datetime(pv.interval_start)])
    load=read(WORK/'results/q2/selected/ledger.csv').set_index(['date','slot_id'])
    price=read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy()
    prices_saved=read(OUT/'price_forecasts.csv')
    prices_saved.index=pd.MultiIndex.from_arrays([pd.to_datetime(prices_saved.issue_time),pd.to_datetime(prices_saved.interval_start)])
    initial=json.loads((WORK/'results/q2/selection.json').read_text())['common_evaluation_initial_energy_kwh']
    expected=pd.date_range(cfg['evaluation_start'],pd.Timestamp(cfg['evaluation_end'])+pd.Timedelta(days=1),freq='10min',inclusive='left')
    reports={};summary_totals={}
    for policy,settings in cfg['policies'].items():
        folder=OUT/policy;f=read(folder/'ledger.csv');v=read(folder/'plan_versions.csv')
        statuses=json.loads((folder/'solvers.json').read_text())
        checks={};residuals={}
        def test(key,value):checks[key]=bool(value)
        def near(key,a,z,tol=1e-6):
            a,z=np.asarray(a,dtype=float),np.asarray(z,dtype=float)
            if a.shape!=z.shape and a.size!=1 and z.size!=1:
                test(key,False);return
            r=float(np.max(np.abs(a-z),initial=0))
            residuals[key]=r;test(key,np.isfinite(r) and r<=tol)
        def upper(key,values):
            r=float(max(0.,np.asarray(values).max(initial=0)))
            residuals[key]=r;test(key,np.isfinite(r) and r<=1e-6)
        times=pd.to_datetime(f.interval_start)
        test('complete_time_grid',times.tolist()==expected.tolist() and pd.to_datetime(f.interval_end).tolist()==(expected+pd.Timedelta(minutes=10)).tolist())
        test('date_slot_keys',f.date.tolist()==expected.strftime('%Y-%m-%d').tolist() and f.slot_id.tolist()==list(np.tile(np.arange(1,145),334)))
        test('finite_ledger',np.isfinite(f.select_dtypes('number')).all().all())
        test('finite_plans',np.isfinite(v.select_dtypes('number')).all().all())
        for field in ['load_actual_kwh','pv_actual_kwh']:near('actual_source_'+field,f[field],actual.loc[times,field])
        p=actual.loc[times].actual_price_yuan_per_kwh.to_numpy()
        near('actual_settlement_price',f.price_yuan_per_kwh,p)
        near('actual_price_column',f.price_actual_yuan_per_kwh,p)
        lf=load.loc[pd.MultiIndex.from_frame(f[['date','slot_id']])]
        near('load_frozen_source',f.load_forecast_kwh,lf.load_forecast_kwh)
        test('load_available_at_midnight',pd.to_datetime(lf.issue_time).tolist()==times.dt.normalize().tolist())
        q,q0,c,d,e,w,es,ee=[f[k].to_numpy() for k in ['grid_effective_kwh','grid_original_kwh','charge_actual_kwh','discharge_actual_kwh','emergency_kwh','surplus_kwh','energy_start_actual_kwh','energy_end_actual_kwh']]
        net=q+f.pv_actual_kwh.to_numpy()-f.load_actual_kwh.to_numpy()
        near('actual_balance',net+d+e-c-w,0.)
        near('actual_state',ee,es+ec*c-d/ed)
        near('actual_continuity',es[1:],ee[:-1]);near('common_initial',es[0],initial)
        upper('actual_bounds',np.r_[lo-es,lo-ee,es-hi,ee-hi,c-mc,d-md,-q,-q0,-c,-d,-e,-w])
        near('actual_mutex',np.minimum(c,d),0.)
        intended_c=np.minimum.reduce([np.maximum(net,0),np.full(len(f),mc),np.maximum((hi-es)/ec,0)])
        intended_d=np.minimum.reduce([np.maximum(-net,0),np.full(len(f),md),np.maximum((es-lo)*ed,0)])
        near('feedback_charge',c,intended_c);near('feedback_discharge',d,intended_d)
        near('feedback_emergency',e,np.maximum(-net-intended_d,0))
        near('feedback_surplus',w,np.maximum(net-intended_c,0))
        near('grid_disposal',f.unused_grid_kwh,np.minimum(q,w))
        near('pv_disposal',f.pv_curtailment_kwh,w-np.minimum(q,w))
        upper('pv_disposal_bound',f.pv_curtailment_kwh.to_numpy()-f.pv_actual_kwh.to_numpy())
        sign=-1 if settings['rule']=='A' else 1
        fee_parts={'original_cost_yuan':p*q0,'increase_cost_yuan':1.5*p*np.maximum(q-q0,0),
            'decrease_adjustment_yuan':sign*.5*p*np.maximum(q0-q,0),'emergency_cost_yuan':5*p*e}
        contract=sum(fee_parts[k] for k in ['original_cost_yuan','increase_cost_yuan','decrease_adjustment_yuan'])
        fee_parts.update(contract_cost_yuan=contract,total_cost_yuan=contract+5*p*e)
        for field,values in fee_parts.items():near('fee_'+field,f[field],values)
        if settings['rule']=='B':upper('B_no_reduction_below_original',q0-q)
        hours=[0]+settings['update_hours']
        active=np.array([max(h for h in hours if h<=int(slot)//6) for slot in np.arange(144)])
        near('allowed_execution_version',f.active_issue_hour,np.tile(active,334))
        vi=v.set_index(['date','issue_hour','slot_id'])
        test('unique_version_targets',not vi.index.duplicated().any())
        chosen=vi.loc[pd.MultiIndex.from_frame(f[['date','active_issue_hour','slot_id']])]
        near('executed_commitment_from_latest_version',q,chosen.grid_kwh)
        near('executed_PV_from_latest_version',f.pv_forecast_kwh,chosen.pv_forecast_kwh)
        near('executed_price_forecast',f.price_forecast_yuan_per_kwh,chosen.price_forecast_yuan_per_kwh)
        test('executed_price_metadata',f.price_method.eq(settings['price']).all() and f.price_issue_time.tolist()==chosen.price_issue_time.tolist())
        original=vi.xs(0,level='issue_hour').loc[pd.MultiIndex.from_frame(f[['date','slot_id']])]
        near('original_is_midnight_plan',q0,original.grid_kwh)
        ledger=f.set_index(['date','slot_id'])
        vg=v.groupby(['date','issue_hour'],sort=False)
        wanted_keys=[(date,h) for date in f.date.drop_duplicates() for h in hours]
        test('all_allowed_versions_only',list(vg.groups)==wanted_keys)
        test('solver_metadata_keys',[(s['date'],s['issue_hour']) for s in statuses]==wanted_keys)
        status_map={(s['date'],s['issue_hour']):s for s in statuses}
        for (date,hour),part in vg:
            key=f'{date}_{hour:02d}';issue=pd.Timestamp(date)+pd.Timedelta(hours=hour)
            ts=pd.to_datetime(part.interval_start);te=pd.to_datetime(part.interval_end)
            horizon=pd.date_range(issue,pd.Timestamp(date)+pd.Timedelta(days=1),freq='10min',inclusive='left')
            test(key+'_horizon',ts.tolist()==horizon.tolist() and te.tolist()==(horizon+pd.Timedelta(minutes=10)).tolist())
            test(key+'_issue',pd.to_datetime(part.issue_time).eq(issue).all())
            if settings['branch']=='4-2':
                raw=load.loc[pd.MultiIndex.from_frame(part[['date','slot_id']])]
                near(key+'_Q2_PV_inherited',part.pv_forecast_kwh,raw.pv_forecast_kwh)
                test(key+'_Q2_PV_metadata',part.endpoint_rule.eq('Q2_inherited').all() and pd.to_datetime(part.endpoint_issue_time).eq(pd.Timestamp(date)).all())
            else:
                raw=pv.loc[pd.MultiIndex.from_arrays([[issue]*len(part),ts])]
                near(key+'_PV_source',part.pv_forecast_kwh,raw.pv_forecast_kwh)
                test(key+'_endpoint_metadata',part.endpoint_rule.tolist()==raw.endpoint_rule.tolist() and part.endpoint_issue_time.fillna('').tolist()==raw.endpoint_issue_time.fillna('').tolist())
                endpoint=pd.to_datetime(part.endpoint_issue_time,errors='coerce')
                test(key+'_endpoint_no_future',((endpoint<=issue)|endpoint.isna()).all())
            kind=settings['price'];price_issue=pd.Timestamp(date) if kind=='hold0' else issue
            if kind=='fixed':wanted_price=price[hour*6:]
            elif kind=='perfect':wanted_price=actual.loc[ts].actual_price_yuan_per_kwh.to_numpy()
            else:wanted_price=prices_saved.loc[pd.MultiIndex.from_arrays([[price_issue]*len(part),ts])].price_forecast_yuan_per_kwh.to_numpy()
            near(key+'_planning_price',part.price_forecast_yuan_per_kwh,wanted_price)
            test(key+'_price_metadata',part.price_method.eq(kind).all() and pd.to_datetime(part.price_issue_time).eq(price_issue).all())
            targets=pd.MultiIndex.from_frame(part[['date','slot_id']])
            near(key+'_load_frozen',part.load_forecast_kwh,load.loc[targets].load_forecast_kwh)
            near(key+'_q0_frozen',part.grid_original_kwh,ledger.loc[targets].grid_original_kwh)
            pc,pd_,pw,pg,pe0,pe1,z=[part[k].to_numpy() for k in ['charge_kwh','discharge_kwh','surplus_kwh','grid_kwh','energy_start_kwh','energy_end_kwh','charge_mode']]
            near(key+'_balance',pg+part.pv_forecast_kwh.to_numpy()+pd_-part.load_forecast_kwh.to_numpy()-pc-pw,0.)
            near(key+'_state',pe1,pe0+ec*pc-pd_/ed)
            near(key+'_continuity',pe0[1:],pe1[:-1])
            actual_at_issue=ledger.loc[(date,hour*6+1)].energy_start_actual_kwh
            target=ledger.loc[(date,1)].energy_start_actual_kwh
            near(key+'_initial_actual',pe0[0],actual_at_issue)
            near(key+'_terminal_midnight_target',pe1[-1],target)
            near(key+'_integer',z,np.rint(z),1e-7)
            upper(key+'_bounds',np.r_[lo-pe0,lo-pe1,pe0-hi,pe1-hi,-pg,-pc,-pd_,-pw,-z,z-1,pc-mc*z,pd_-md*(1-z)])
            base=part.grid_original_kwh.to_numpy();prices=part.price_forecast_yuan_per_kwh.to_numpy()
            if settings['rule']=='B' and hour:upper(key+'_B_no_reduction',base-pg)
            fees=prices*(base+1.5*np.maximum(pg-base,0)+sign*.5*np.maximum(base-pg,0))
            near(key+'_forecast_fee',part.contract_cost_forecast_yuan,fees)
            s=status_map[(date,hour)];solver=s['solver']
            test(key+'_solver_status',solver['status']=='Optimal' and not solver['relaxed'])
            test(key+'_solver_price_information',s['price_method']==kind and s['perfect_price_information']==(kind=='perfect') and pd.Timestamp(s['price_issue_time'])==price_issue)
            near(key+'_solver_input',[s['initial_energy_kwh'],s['terminal_target_kwh']],[actual_at_issue,target])
            test(key+'_solver_information',s['horizon_intervals']==len(part) and pd.Timestamp(s['issue_time'])==issue and pd.Timestamp(s['load_issue_time'])==pd.Timestamp(date))
            near(key+'_objective',solver['objective_yuan'],fees.sum(),1e-5)
            near(key+'_solver_objective',solver['solver_objective_yuan'],fees.sum(),1e-5)
            test(key+'_optimality_gap',np.isfinite(solver['mip_gap']) and 0<=solver['mip_gap']<=1e-9 and abs(solver['objective_yuan']-solver['lower_bound_yuan'])<=1e-5 and solver['max_primal_infeasibility']<=1e-6)
        total=json.loads((folder/'summary.json').read_text());summary_totals[policy]=total
        fields=['grid_original_kwh','grid_effective_kwh','emergency_kwh',*fee_parts,
            'charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']
        daily=read(folder/'daily.csv');byday=f.groupby('date',sort=False)
        test('daily_keys',daily.date.tolist()==list(byday.groups))
        for field in fields:
            near('summary_'+field,total[field],f[field].sum(),1e-5)
            near('daily_'+field,daily[field],byday[field].sum(),1e-5)
        near('daily_start',daily.energy_start_actual_kwh,es[::144]);near('daily_end',daily.energy_end_actual_kwh,ee[143::144])
        near('summary_initial_final',[total['initial_energy_kwh'],total['final_energy_kwh']],[es[0],ee[-1]])
        count=f.assign(count=e>1e-6).groupby('date')['count'].sum()
        near('daily_emergency_count',daily.emergency_intervals,count)
        test('summary_counts',total['days']==334 and total['intervals']==len(f) and total['solves']==len(statuses) and total['emergency_intervals']==int((e>1e-6).sum()))
        representative=f.loc[f.date.isin(DATES)]
        t1=read(folder/'table1_representative.csv');wanted=representative.loc[representative.slot_id.isin([61,73,85,97,109,121])]
        test('table1_time',t1.interval_start.tolist()==wanted.interval_start.tolist() and t1.interval_end.tolist()==wanted.interval_end.tolist())
        near('table1_quantities',t1[['grid_original_kwh','grid_effective_kwh']],wanted[['grid_original_kwh','grid_effective_kwh']])
        t2=read(folder/'table2_representative.csv')
        blocks=representative.assign(block=(representative.slot_id-1)//24*240).groupby(['date','block'])[['charge_actual_kwh','discharge_actual_kwh']].sum()
        test('table2_keys',list(zip(t2.date,t2.block_start_minute))==list(blocks.index) and (t2.block_end_minute==t2.block_start_minute+240).all())
        near('table2_quantities',t2[['charge_actual_kwh','discharge_actual_kwh']],blocks)
        for filename,data in [('emergency_events.csv',f),('table3_representative.csv',representative)]:
            events=read(folder/filename);expanded=[];quantities=[]
            timed=data.set_index(pd.to_datetime(data.interval_start))
            for event in events.itertuples():
                interval=pd.date_range(event.interval_start,event.interval_end,freq='10min',inclusive='left')
                expanded.extend(interval.tolist())
                wanted=timed.loc[timed.index.isin(interval)]
                quantities.append(wanted.emergency_kwh.sum())
                test(filename+'_event_'+str(event.Index),len(wanted)==event.intervals==len(interval) and wanted.date.eq(event.date).all() and wanted.emergency_kwh.gt(1e-6).all())
            test(filename+'_coverage',expanded==pd.to_datetime(data.loc[data.emergency_kwh>1e-6].interval_start).tolist())
            near(filename+'_quantity',events.emergency_kwh,quantities)
        reports[policy]={'passed':all(checks.values()),'checks':checks,'max_residuals':residuals}
        failed=[k for k,value in checks.items() if not value]
        print(policy,'PASS' if not failed else 'FAIL',len(checks),'checks',failed[:12],flush=True)
    comparison=read(OUT/'comparison.csv');cross={}
    references={'4-2':summary_totals['q42_fixed']['total_cost_yuan'],'4-3':summary_totals['q43_all_A_fixed']['total_cost_yuan']}
    cross['comparison_policy_keys']=comparison.policy.tolist()==list(cfg['policies'])
    for row in comparison.itertuples():
        total=summary_totals[row.policy]
        for field in ['total_cost_yuan','contract_cost_yuan','emergency_cost_yuan','grid_effective_kwh','emergency_kwh','final_energy_kwh']:
            cross[row.policy+'_'+field]=bool(abs(getattr(row,field)-total[field])<=1e-5)
        expected_inventory=total['total_cost_yuan']-price.mean()*ed*(total['final_energy_kwh']-initial)
        cross[row.policy+'_inventory']=abs(row.inventory_adjusted_cost_yuan-expected_inventory)<=1e-5
        reference=references[row.branch]
        cross[row.policy+'_saving']=abs(row.saving_yuan_vs_branch_fixed-(reference-total['total_cost_yuan']))<=1e-5 and abs(row.saving_percent_vs_branch_fixed-100*(reference-total['total_cost_yuan'])/reference)<=1e-8
    for name,expected_hash in json.loads((OUT/'input_code_hashes.json').read_text()).items():
        cross['hash_'+name]=hashlib.sha256((WORK/name).read_bytes()).hexdigest()==expected_hash
    state=json.loads((OUT/'run_status.json').read_text())
    cross['complete_internal_run']=state['completed'] and state['inputs_unchanged'] and not state['formal_excel_exported'] and state['q4_executed'] and state['future_actual_price_only_in_labeled_perfect_branches']
    price_audit=audit_price_models(cfg,actual,prices_saved)
    cross['independent_price_models']=price_audit['passed']
    cross={key:bool(value) for key,value in cross.items()}
    passed=all(r['passed'] for r in reports.values()) and all(cross.values())
    result={'passed':passed,'check_count':sum(len(r['checks']) for r in reports.values())+len(cross)+price_audit['check_count'],
        'policies':reports,'cross_checks':cross,'price_model_audit':price_audit,'independence':'No imports from planner/executor; independently reconstructed constraints, source joins, feedback and fees.'}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print('Q4 audit',passed,result['check_count'],'checks',flush=True)
    if not passed:sys.exit(1)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--results',default='results/q4')
    args=parser.parse_args();OUT=WORK/args.results
    main()
