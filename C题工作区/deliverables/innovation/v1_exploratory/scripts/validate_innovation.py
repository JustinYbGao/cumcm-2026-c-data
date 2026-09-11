"""Read-back innovation audit: no planner, forecast, gate or executor imports."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.optimize import linprog

WORK=Path(__file__).resolve().parents[1];OUT=WORK/'results/innovation'
def read(p):return pd.read_csv(p,float_precision='round_trip')
def load(p):return json.loads(p.read_text())
def fee(q0,q,p):return p*(q0+1.5*np.maximum(q-q0,0)-.5*np.maximum(q0-q,0))

def main():
    checks={};errors={}
    def test(k,v):checks[k]=bool(v)
    def close(k,a,b,tol=1e-6):
        value=float(np.max(np.abs(np.asarray(a)-np.asarray(b)),initial=0));errors[k]=value;test(k,value<=tol)
    cfg=load(OUT/'config_snapshot.json');physical=load(WORK/'configs/model_baseline.json');b=physical['battery']
    ec=b['eta_charge'];ed=b['eta_discharge'];lo=b['min_energy_kwh'];hi=b['max_energy_kwh'];mc=b['max_charge_kw']/6;md=b['max_discharge_kw']/6
    price=read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy();penalty=price.mean()*ed
    actual=read(WORK/'data/processed/actual_10min.csv').set_index(['date','slot_id']);q2=read(WORK/'results/q2/selected/ledger.csv').set_index(['date','slot_id'])
    pv=read(WORK/'data/processed/pv_forecast_10min.csv')
    for c in ['issue_time','interval_start','interval_end']:pv[c]=pd.to_datetime(pv[c])
    raw=pv.set_index(['issue_time','interval_start']);truth=actual.reset_index().set_index('interval_start');truth.index=pd.to_datetime(truth.index)
    bias={m['issue_time']:m for m in load(OUT/'pv_bias_models.json')};risk={m['issue_time']:m for m in load(OUT/'risk_models.json')}
    risk_data=read(OUT/'risk_targets.csv').set_index('date');frames={};saved_decisions={};decision_archive={}
    def actual_replay(q,real,initial,q0,p,target):
        e=initial;emergency=0.
        for j,row in enumerate(real.itertuples()):
            net=max(0.,q[j])+row.pv_actual_kwh-row.load_actual_kwh
            if net>=0:c=min(net,mc,(hi-e)/ec);d=0.;u=0.
            else:c=0.;d=min(-net,md,ed*(e-lo));u=max(0.,-net-d)
            e+=ec*c-d/ed;emergency+=5*p[j]*u
        return float(fee(q0,q,p).sum()+emergency+penalty*abs(e-target))
    def plan_check(key,f,st,initial,target,reserve,soft):
        p=price[f.slot_id.to_numpy()-1];q=f.grid_kwh.to_numpy();c=f.charge_kwh.to_numpy();d=f.discharge_kwh.to_numpy();u=f.emergency_plan_kwh.to_numpy()
        s=f.energy_start_kwh.to_numpy();e=f.energy_end_kwh.to_numpy();w=f.surplus_kwh.to_numpy()
        close(key+'_balance',q+u+f.pv_forecast_kwh+d-f.load_forecast_kwh-c-w,0)
        close(key+'_state',e,s+ec*c-d/ed);close(key+'_continuity',s[1:],e[:-1]);close(key+'_initial',s[0],initial)
        test(key+'_bounds',min(s.min(),e.min())>=lo-1e-6 and max(s.max(),e.max())<=hi+1e-6 and c.min()>=-1e-6 and d.min()>=-1e-6 and c.max()<=mc+1e-6 and d.max()<=md+1e-6 and min(q.min(),u.min(),w.min())>=-1e-6)
        test(key+'_mutex',np.all((c<=1e-6)|(d<=1e-6)) and np.all((u<=1e-6)|(c<=1e-6)))
        test(key+'_emergency_bound',np.all(u<=f.load_forecast_kwh+1e-6))
        close(key+'_integer',f.charge_mode,np.rint(f.charge_mode))
        if not soft:close(key+'_terminal',e[-1],target)
        ref_cost=0.
        if reserve:
            at=int(reserve['index'])-int(f.slot_id.iloc[0])+1
            states=np.r_[s[0],e];short=max(0.,lo+reserve['amount_kwh']-states[at]);ref_cost=short*reserve['penalty_yuan_per_kwh']
            close(key+'_reserve_shortfall',st['reserve_shortfall_kwh'],short)
        contract=float(fee(f.grid_original_kwh.to_numpy(),q,p).sum());emergency=float((5*p*u).sum());term=penalty*abs(e[-1]-target) if soft else 0.
        close(key+'_objective',st['objective_yuan'],contract+emergency+ref_cost+term,1e-5)
        test(key+'_optimal',st['status']=='Optimal' and st['mip_gap']<=1e-9 and st['lower_bound_yuan']<=st['objective_yuan']+1e-5)
    for phase,start,end in [('calibration','2025-02-01','2025-03-31'),('evaluation','2025-04-01','2025-12-31')]:
        for policy,group in cfg['policies'].items():
            key=phase+'_'+policy;folder=OUT/phase/policy;f=read(folder/'ledger.csv');v=read(folder/'plan_versions.csv');sts=load(folder/'solvers.json')
            frames[(phase,policy)]=f
            expected=pd.date_range(start,pd.Timestamp(end)+pd.Timedelta(days=1),freq='10min',inclusive='left')
            test(key+'_time',pd.to_datetime(f.interval_start).tolist()==expected.tolist() and pd.to_datetime(f.interval_end).tolist()==(expected+pd.Timedelta(minutes=10)).tolist())
            test(key+'_keys',not f.duplicated(['date','slot_id']).any() and f.slot_id.tolist()==list(range(1,145))*(len(f)//144))
            real=actual.loc[list(zip(f.date,f.slot_id))];p=np.tile(price,len(f)//144);s=f.energy_start_actual_kwh.to_numpy();e=f.energy_end_actual_kwh.to_numpy()
            c=f.charge_actual_kwh.to_numpy();d=f.discharge_actual_kwh.to_numpy();q=f.grid_effective_kwh.to_numpy();u=f.emergency_kwh.to_numpy()
            close(key+'_actual_load',f.load_actual_kwh,real.load_actual_kwh);close(key+'_actual_pv',f.pv_actual_kwh,real.pv_actual_kwh)
            close(key+'_balance',q+u+f.pv_actual_kwh+d-f.load_actual_kwh-c-f.surplus_kwh,0)
            close(key+'_soc',e,s+ec*c-d/ed);close(key+'_continuity',s[1:],e[:-1])
            close(key+'_initial',s[0],cfg['feb_initial'] if phase=='calibration' else cfg['april_initial'][group])
            net=q+f.pv_actual_kwh.to_numpy()-f.load_actual_kwh.to_numpy()
            wantc=np.minimum.reduce([np.maximum(net,0),np.full(len(f),mc),np.maximum(0,(hi-s)/ec)])
            wantd=np.minimum.reduce([np.maximum(-net,0),np.full(len(f),md),np.maximum(0,ed*(s-lo))])
            close(key+'_greedy_charge',c,wantc);close(key+'_greedy_discharge',d,wantd);close(key+'_greedy_emergency',u,np.maximum(0,-net-wantd))
            test(key+'_physical',min(s.min(),e.min())>=lo-1e-6 and max(s.max(),e.max())<=hi+1e-6 and np.all((c<=1e-6)|(d<=1e-6)))
            close(key+'_fee',f.contract_cost_yuan,fee(f.grid_original_kwh.to_numpy(),q,p));close(key+'_emergency_fee',f.emergency_cost_yuan,5*p*u)
            close(key+'_actual_bill',f.total_cost_yuan,f.contract_cost_yuan+5*p*u)
            close(key+'_price',f.price_yuan_per_kwh,p)
            loads=q2.loc[list(zip(f.date,f.slot_id))].load_forecast_kwh;close(key+'_load_frozen',f.load_forecast_kwh,loads)
            idx=v.set_index(['date','issue_hour','slot_id']);latest=idx.loc[list(zip(f.date,f.active_issue_hour,f.slot_id))]
            close(key+'_latest_q',q,latest.grid_kwh);close(key+'_latest_pv',f.pv_forecast_kwh,latest.pv_forecast_kwh)
            groups=v.groupby(['date','issue_hour']);test(key+'_versions_unique',not v.duplicated(['date','issue_hour','slot_id']).any() and len(sts)==len(groups))
            ledger_day=f.groupby('date');initial_days=ledger_day.energy_start_actual_kwh.first();midnight=v.loc[v.issue_hour==0].set_index(['date','slot_id'])
            for st in sts:
                date=st['date'];hour=st['issue_hour'];part=groups.get_group((date,hour));label=key+'_'+date+'_'+str(hour);issue=pd.Timestamp(st['issue_time'])
                test(label+'_horizon',part.slot_id.tolist()==list(range(hour*6+1,145)) and pd.to_datetime(part.interval_start.iloc[0])==issue)
                close(label+'_q0',part.grid_original_kwh,midnight.loc[list(zip(part.date,part.slot_id))].grid_kwh)
                close(label+'_current_state',st['initial_energy_kwh'],f.loc[(f.date==date)&(f.slot_id==hour*6+1),'energy_start_actual_kwh'].iloc[0])
                close(label+'_target',st['terminal_target_kwh'],initial_days.loc[date])
                expectedload=q2.loc[list(zip(part.date,part.slot_id))].load_forecast_kwh;close(label+'_load',part.load_forecast_kwh,expectedload)
                if group=='risk':expectedpv=q2.loc[list(zip(part.date,part.slot_id))].pv_forecast_kwh.to_numpy()
                else:expectedpv=raw.loc[[(issue,t) for t in pd.to_datetime(part.interval_start)]].pv_forecast_kwh.to_numpy()
                close(label+'_raw_source',part.pv_raw_forecast_kwh,expectedpv)
                if policy=='pv_bias':
                    bm=bias[str(issue)];expectedpv=np.where(expectedpv>0,np.maximum(0,expectedpv+bm['bias_kwh']),0.)
                    test(label+'_bias_causal',pd.Timestamp(bm['training_cutoff'])<=issue and (bm['latest_target_end'] is None or pd.Timestamp(bm['latest_target_end'])<=issue))
                close(label+'_forecast',part.pv_forecast_kwh,expectedpv)
                reserve=st['metadata'].get('reserve')
                if group=='risk' and policy!='risk_none':
                    amount=2400.
                    if policy.startswith('risk_g'):
                        model=risk[str(issue)];prediction=model['predicted_s_kwh']
                        if prediction is not None:amount=min(9600,(.5 if policy=='risk_g05' else 1)*prediction/ed)
                    close(label+'_reserve',reserve['amount_kwh'],amount);test(label+'_boundary',reserve['index']==72)
                plan_check(label,part,st['solver'],st['initial_energy_kwh'],st['terminal_target_kwh'],reserve,group=='gate')
            summary=load(folder/'summary.json');daily=read(folder/'daily.csv')
            for col in ['total_cost_yuan','contract_cost_yuan','emergency_cost_yuan','emergency_kwh']:
                close(key+'_summary_'+col,summary[col],f[col].sum(),1e-5);close(key+'_daily_'+col,daily[col],f.groupby('date')[col].sum(),1e-5)
            records=load(folder/'decisions.json');previous=decision_archive.get(policy,[]);allrecords=previous+records
            saved_decisions[(phase,policy)]=records
            if records:
                alternatives=read(folder/'candidate_versions.csv').groupby(['date','issue_hour','alternative'])
                for i,r in enumerate(records):
                    label=key+'_gate_'+r['issue_time'];issue=pd.Timestamp(r['issue_time']);hour=r['issue_hour'];real=actual.loc[r['date']].loc[hour*6+1:]
                    selected=groups.get_group((r['date'],hour)).reset_index(drop=True)
                    event_initial=f.loc[(f.date==r['date'])&(f.slot_id==hour*6+1),'energy_start_actual_kwh'].iloc[0]
                    day_target=initial_days.loc[r['date']]
                    close(label+'_decision_initial',r['initial_energy_kwh'],event_initial)
                    close(label+'_decision_target',r['terminal_target_kwh'],day_target)
                    local={}
                    for alternative in ['hold','update']:
                        part=alternatives.get_group((r['date'],hour,alternative)).reset_index(drop=True)
                        test(label+'_'+alternative+'_slot_keys',part.date.eq(r['date']).all() and
                            part.issue_hour.eq(hour).all() and part.slot_id.tolist()==selected.slot_id.tolist())
                        close(label+'_'+alternative+'_load_source',part.load_forecast_kwh,selected.load_forecast_kwh)
                        close(label+'_'+alternative+'_pv_source',part.pv_forecast_kwh,selected.pv_forecast_kwh)
                        close(label+'_'+alternative+'_q0_source',part.grid_original_kwh,selected.grid_original_kwh)
                        q0=selected.grid_original_kwh.to_numpy()
                        plan_check(label+'_'+alternative,part,r[alternative+'_solver'],event_initial,day_target,None,True)
                        local[alternative]=actual_replay(part.grid_kwh.to_numpy(),real,event_initial,q0,price[hour*6:],day_target)
                        close(label+'_'+alternative+'_replay',local[alternative],r[alternative+'_replay']['cost_with_terminal_proxy_yuan'],1e-5)
                    close(label+'_vhat',r['vhat_yuan'],r['hold_solver']['objective_yuan']-r['update_solver']['objective_yuan'],1e-5)
                    close(label+'_vreplay',r['vreplay_yuan'],local['hold']-local['update'],1e-5);close(label+'_zeta',r['zeta_yuan'],r['vhat_yuan']-r['vreplay_yuan'],1e-5)
                    hist=[(j,t) for j,t in enumerate(allrecords) if pd.Timestamp(t['available_time'])<=issue and issue-pd.Timedelta(days=56)<=pd.Timestamp(t['issue_time'])<issue and t['issue_hour']==hour]
                    alpha=.5 if policy=='gate_q50' else .75;active=len(hist)>=20
                    tau=max(0.,float(np.quantile([t['zeta_yuan'] for _,t in hist],alpha,method='higher'))) if active else 0.
                    close(label+'_tau',r['tau_yuan'],tau,1e-5)
                    test(label+'_history',r['threshold_model']['n']==len(hist) and r['threshold_model']['record_ids']==[str(j) for j,_ in hist])
                    test(label+'_enabled',r['threshold_enabled']==(policy!='gate_paid' and active))
                    test(label+'_choice',r['accepted']==(not r['threshold_enabled'] or r['vhat_yuan']>tau+1e-7))
                    test(label+'_available',pd.Timestamp(r['available_time'])==issue.normalize()+pd.Timedelta(days=1))
                    # Hold really is the previously effective commitment, including earlier rejections.
                    earlier=max(h for d,h in groups.groups if d==r['date'] and h<hour)
                    preceding=groups.get_group((r['date'],earlier));held=alternatives.get_group((r['date'],hour,'hold'))
                    close(label+'_hold_current',held.grid_kwh,preceding.loc[preceding.slot_id>=hour*6+1,'grid_kwh'])
                    chosen=alternatives.get_group((r['date'],hour,'update' if r['accepted'] else 'hold'))
                    close(label+'_accepted_q',groups.get_group((r['date'],hour)).grid_kwh,chosen.grid_kwh)
            decision_archive[policy]=allrecords
            print(key,'PASS' if all(v for k,v in checks.items() if k.startswith(key)) else 'FAIL',flush=True)
    # Rebuild all risk targets and fit-objective checks independently.
    for date,target in risk_data.iterrows():
        fore=q2.loc[date].loc[73:108];real=actual.loc[date].loc[73:108]
        residual=(real.load_actual_kwh-real.pv_actual_kwh).to_numpy()-(fore.load_forecast_kwh-fore.pv_forecast_kwh).to_numpy()
        close('risk_target_'+date,target.s_kwh,max(0,float(np.cumsum(residual).max())))
        close('risk_x1_'+date,target.x1,(fore.load_forecast_kwh-fore.pv_forecast_kwh).mean()/1000)
        close('risk_x2_'+date,target.x2,fore.pv_forecast_kwh.mean()/1000)
        test('risk_available_'+date,pd.Timestamp(target.available_time)==pd.Timestamp(date)+pd.Timedelta(days=1))
    for issue,m in risk.items():
        day=pd.Timestamp(issue);h=risk_data.loc[(pd.to_datetime(risk_data.available_time)<=day)&(pd.to_datetime(risk_data.index)>=day-pd.Timedelta(days=56))]
        test('risk_training_'+issue,m['training_dates']==h.index.tolist());test('risk_fallback_'+issue,(m['predicted_s_kwh'] is None)==(len(h)<20))
        current=risk_data.loc[str(day.date())]
        close('risk_features_'+issue,m['features'],[1.,current.x1,current.x2])
        close('risk_realized_'+issue,m['realized_s_kwh'],current.s_kwh)
        latest=None if len(h)==0 else str(pd.Timestamp(h.available_time.max()))
        test('risk_latest_'+issue,m['latest_available_time']==latest)
        if len(h)>=20:
            X=np.column_stack([np.ones(len(h)),h.x1,h.x2]);y=h.s_kwh.to_numpy()/1000;beta=np.array(m['beta']);res=y-X@beta
            cost=float((.75*np.maximum(res,0)+.25*np.maximum(-res,0)).sum())
            rank=int(np.linalg.matrix_rank(X));test('risk_rank_'+issue,m['rank']==rank and m['n']==len(h))
            close('risk_declared_objective_'+issue,m['objective'],cost,1e-6)
            if m['source']=='pinball_lp':
                test('risk_LP_eligible_'+issue,rank==X.shape[1] and len(h)>X.shape[1])
                n=len(y);lp=linprog(np.r_[np.zeros(3),np.full(n,.75),np.full(n,.25)],A_eq=np.c_[X,np.eye(n),-np.eye(n)],b_eq=y,bounds=[(None,None)]*3+[(0,None)]*(2*n),method='highs')
                test('risk_LP_'+issue,lp.success);close('risk_fit_objective_'+issue,cost,lp.fun,1e-6)
            elif m['source']=='empirical_quantile':
                test('risk_empirical_eligible_'+issue,rank<X.shape[1] or len(h)<=X.shape[1])
                quantile=float(np.quantile(y,.75,method='higher'))
                close('risk_empirical_beta_'+issue,beta,[quantile,0.,0.])
                residual=y-quantile;expected_cost=float((.75*np.maximum(residual,0)+.25*np.maximum(-residual,0)).sum())
                close('risk_empirical_objective_'+issue,m['objective'],expected_cost,1e-6)
            else:test('risk_source_'+issue,False)
            close('risk_prediction_'+issue,m['predicted_s_kwh'],max(0,float(np.array(m['features'])@beta))*1000)
    hist=pv.loc[(pv.interval_end<=pv.issue_time.dt.normalize()+pd.Timedelta(days=1)) & pv.interval_start.isin(truth.index) & (pv.pv_forecast_kwh>0)].copy()
    hist['residual']=truth.loc[hist.interval_start].pv_actual_kwh.to_numpy()-hist.pv_forecast_kwh.to_numpy()
    for issue,m in bias.items():
        k=pd.Timestamp(issue);cut=k.normalize();h=hist.loc[(hist.issue_time.dt.hour==k.hour)&(hist.interval_end<=cut)&(hist.interval_start>=cut-pd.Timedelta(days=28))]
        close('bias_value_'+issue,m['bias_kwh'],h.residual.mean() if len(h) else 0.)
        test('bias_rows_'+issue,m['training_rows']==len(h))
    for phase in ['calibration','evaluation']:
        a=frames[(phase,'gate_frozen')];bframe=frames[(phase,'gate_info_frozen')]
        for col in ['grid_effective_kwh','total_cost_yuan','energy_end_actual_kwh']:
            close(phase+'_info_without_action_'+col,a[col],bframe[col])
    scores=read(OUT/'calibration_scores.csv').set_index('policy');selection=load(OUT/'selection.json')
    for policy in cfg['policies']:
        f=frames[('calibration',policy)];close('selection_score_'+policy,scores.loc[policy,'march_cost_yuan'],f.loc[f.date>='2025-03-01','total_cost_yuan'].sum(),1e-5)
    for group,names in selection['eligible'].items():
        expected=min(names,key=lambda p:(scores.loc[p,'march_cost_yuan'],names.index(p)));test('selection_'+group,selection['selected'][group]==expected)
    test('selection_cutoff',selection['available_time']=='2025-04-01 00:00:00')
    # Reconcile every table consumed by the report to independently verified ledgers.
    aggregates=['grid_original_kwh','grid_effective_kwh','emergency_kwh','original_cost_yuan',
        'increase_cost_yuan','decrease_adjustment_yuan','contract_cost_yuan','emergency_cost_yuan',
        'total_cost_yuan','charge_actual_kwh','discharge_actual_kwh','surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']
    for phase,filename,days in [('calibration','calibration_comparison.csv',59),('evaluation','comparison.csv',275)]:
        comparison=read(OUT/filename)
        test(phase+'_comparison_identity',comparison.policy.tolist()==list(cfg['policies']) and
            not comparison.policy.duplicated().any() and comparison.group.tolist()==list(cfg['policies'].values()))
        table=comparison.set_index('policy')
        for policy,group in cfg['policies'].items():
            key=phase+'_reported_'+policy;ledger=frames[(phase,policy)];row=table.loc[policy]
            summary=load(OUT/phase/policy/'innovation_summary.json');records=saved_decisions[(phase,policy)]
            for col in aggregates:
                expected=float(ledger[col].sum());close(key+'_comparison_'+col,row[col],expected,1e-5);close(key+'_summary_'+col,summary[col],expected,1e-5)
            start=float(ledger.energy_start_actual_kwh.iloc[0]);end=float(ledger.energy_end_actual_kwh.iloc[-1])
            emergency_intervals=int((ledger.emergency_kwh>1e-6).sum())
            accepted=sum(bool(r['accepted']) for r in records)
            changed=sum(float(r['proposed_change_kwh']) for r in records if r['accepted'])
            expected_inventory=float(ledger.total_cost_yuan.sum()-penalty*(end-start))
            for source_name,source in [('comparison',row),('summary',summary)]:
                source_policy=policy if source_name=='comparison' else source['policy']
                test(key+'_'+source_name+'_identity',source_policy==policy and source['group']==group and source['rule']=='A')
                test(key+'_'+source_name+'_scope',int(source['days'])==days and int(source['intervals'])==days*144)
                close(key+'_'+source_name+'_initial',source['initial_energy_kwh'],start)
                close(key+'_'+source_name+'_final',source['final_energy_kwh'],end)
                close(key+'_'+source_name+'_inventory',source['inventory_adjusted_cost_yuan'],expected_inventory,1e-5)
                test(key+'_'+source_name+'_emergency_intervals',int(source['emergency_intervals'])==emergency_intervals)
                test(key+'_'+source_name+'_gate_decisions',int(source['gate_decisions'])==len(records))
                test(key+'_'+source_name+'_accepted_updates',int(source['accepted_updates'])==accepted)
                close(key+'_'+source_name+'_accepted_change',source['accepted_change_kwh'],changed,1e-5)
    for name,value in load(OUT/'input_code_hashes.json').items():test('source_'+name,hashlib.sha256((WORK/name).read_bytes()).hexdigest()==value)
    test('completed',load(OUT/'run_status.json')['completed'])
    result={'passed':all(checks.values()),'check_count':len(checks),'failed':[k for k,v in checks.items() if not v],
        'max_residual':max(errors.values()),'checks':checks,'residuals':errors,'independence':'No planner/executor/forecast/gate imports; reconstructed sources, history, physics, replay and fees'}
    write=OUT/'validation.json';write.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Innovation audit',result['passed'],len(checks),'checks',result['failed'][:20],flush=True)
    if not result['passed']:sys.exit(1)

if __name__=='__main__':main()
