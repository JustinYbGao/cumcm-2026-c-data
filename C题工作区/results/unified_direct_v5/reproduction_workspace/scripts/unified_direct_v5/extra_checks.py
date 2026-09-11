"""Independent finite differences, boundary checks and controlled future perturbations."""
import json
import builtins
from contextlib import contextmanager
from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd
from inputs import Inputs,ROOT,WORK
from policy import evaluate
from run import run_one,POLICIES,write
from compat import forecast_day
from independent_verify import candidate_values,replay

REPORT=WORK/'reports/unified_direct_v5'


@contextmanager
def forbid_appendix3():
    original_open=builtins.open
    blocked={'pv_forecast_10min.csv','pv_forecast_hourly.csv','附件3.xlsx'}
    evidence={'active':True,'positive_control_blocked':False,'production_forbidden_reads':0}
    def guard(file,*args,**kwargs):
        if isinstance(file,(str,Path)) and Path(file).name in blocked:
            evidence['production_forbidden_reads']+=1
            raise AssertionError('Q4-2 attempted to read Appendix 3: '+str(file))
        return original_open(file,*args,**kwargs)
    with patch('builtins.open',guard),patch('io.open',guard):
        try:open(WORK/'data/processed/pv_forecast_10min.csv')
        except AssertionError:evidence['positive_control_blocked']=True
        assert evidence['positive_control_blocked']
        evidence['production_forbidden_reads']=0
        yield evidence
    assert evidence['production_forbidden_reads']==0


def controlled_run(name,stage,start,end,cut,kind):
    if POLICIES[name]['branch']=='q42':
        with forbid_appendix3() as guard:
            ledger=run_one(name,stage,start,end,6000.,altered(kind,False,cut,end))
        return ledger,guard
    return run_one(name,stage,start,end,6000.,altered(kind,True,cut,end)),None


def numerical():
    rng=np.random.default_rng(31823);records=[]
    for T in [36,72,108,144]:
        q=rng.uniform(50,400,T);net=rng.uniform(-1600,1900,(11,T));p=rng.uniform(.2,1.5,T);q0=q+rng.choice([-1,1],T)*20
        result=evaluate(q,net,p,6173.43,q0=q0)
        audit=candidate_values(q[None,:],net,p,6173.43,q0)
        changes=[]
        for t in range(T):
            up=q.copy();dn=q.copy();up[t]+=.001;dn[t]-=.001
            changes.append((candidate_values(up[None,:],net,p,6173.43,q0)['score'][0]-candidate_values(dn[None,:],net,p,6173.43,q0)['score'][0])/.002)
        error=float(np.max(np.abs(result['gradient']-changes)));score_error=abs(result['score']-audit['score'][0])
        assert error<1e-5 and score_error<1e-5
        records.append({'horizon':T,'coordinates':T,'finite_difference_step_kwh':.001,'max_gradient_error_yuan_per_kwh':error,'objective_error_yuan':score_error,'scaled_gradient_error':error*.1})
    boundary=[]
    for initial in [1200.,10800.,6000.]:
        for q,net in [(np.zeros(6),np.array([[1000.,0.,-1000.,10000.,-10000.,0.]])),(np.full(6,5000/6),np.zeros((1,6)))]:
            p=np.array([.2,.3,.4,.5,.6,.7]);r=evaluate(q,net,p,initial);v=candidate_values(q[None],net,p,initial,np.array([]))
            err=abs(r['score']-v['score'][0]);assert err<1e-5
            boundary.append({'initial_kwh':initial,'objective_error_yuan':err,'end_error_kwh':float(abs(r['end_energy'][0]-v['end_energy'][0,0]))})
    write(REPORT/'numerical_checks.json',{'passed':True,'derivatives':records,'boundary_checks':boundary,'fold_points':'no uniqueness claimed at folds; finite differences use nonfold random points'})


def altered(kind,with_pv,cut,end):
    actual=pd.read_csv(WORK/'data/processed/actual_10min.csv',float_precision='round_trip')
    starts=pd.to_datetime(actual.interval_start);mask=starts>=cut
    if kind=='load_actual':actual.loc[mask,'load_actual_kwh']+=800.
    if kind=='pv_actual':actual.loc[mask,'pv_actual_kwh']*=.5
    if kind=='actual_price':actual.loc[mask,'actual_price_yuan_per_kwh']*=1.35
    pv=None
    if with_pv:
        pv=pd.read_csv(WORK/'data/processed/pv_forecast_10min.csv',float_precision='round_trip')
        if kind=='pv_release':
            selected=(pd.to_datetime(pv.issue_time)>=cut)&(pv.pv_forecast_kwh>0)
            pv.loc[selected,'pv_forecast_kwh']+=200.
    data=Inputs(with_pv=with_pv,actual=actual,pv_records=pv,price_cache=False)
    if kind in ['load_actual','pv_actual']:
        cfg=json.loads((WORK/'configs/q2_baseline.json').read_text())
        for date in data.b0:
            day=pd.Timestamp(date)
            if day<cut.normalize() or day>pd.Timestamp(end):continue
            f=data.b0[date].copy()
            if day>cut.normalize():
                history=data.actual.loc[data.actual.interval_end<=day]
                load,pv_hat,meta=forecast_day(history,day,'linear_harmonic',cfg)
                f['load_forecast_kwh']=load;f['pv_forecast_kwh']=pv_hat
            truth=data.days[date]
            f['net_residual_kwh']=(truth.load_actual_kwh-truth.pv_actual_kwh).to_numpy()-(f.load_forecast_kwh-f.pv_forecast_kwh).to_numpy()
            data.b0[date]=f
    return data


def causal():
    chosen=json.loads((ROOT/'selection.json').read_text())['selected']
    names=list(dict.fromkeys([chosen['q3'],chosen['q42'],chosen['q43'],'q42_fixed','q42_ols']))
    start,end='2025-07-14','2025-07-16';cut=pd.Timestamp('2025-07-15 12:00');records=[]
    for name in names:
        original,base_guard=controlled_run(name,'causality/original',start,end,cut,'none')
        base_folder=ROOT/'causality/original'/name
        base_meta=json.loads((base_folder/'decisions.json').read_text())
        for kind in ['load_actual','pv_actual','pv_release','actual_price']:
            other,other_guard=controlled_run(name,'causality/'+kind,start,end,cut,kind)
            folder=ROOT/'causality'/kind/name
            prefix=pd.to_datetime(original.interval_end)<=cut
            physical=['grid_original_kwh','grid_effective_kwh','charge_actual_kwh','discharge_actual_kwh','energy_start_actual_kwh','energy_end_actual_kwh','total_cost_yuan']
            error=float(np.max(np.abs(original.loc[prefix,physical].to_numpy()-other.loc[prefix,physical].to_numpy())))
            assert error<=1e-6
            before=[];after=[];input_errors={key:0. for key in ['price','load_hat','pv_hat','raw_pv','scenario_net','risk_delta','q0','current','initial_energy_kwh']}
            other_meta=json.loads((folder/'decisions.json').read_text())
            assert len(base_meta)==len(other_meta)
            for meta,changed_meta in zip(base_meta,other_meta):
                assert meta['issue_time']==changed_meta['issue_time']
                issue=pd.Timestamp(meta['issue_time']);a=np.load(base_folder/meta['evidence_file']);b=np.load(folder/meta['evidence_file'])
                diff=float(np.max(np.abs(a['q']-b['q'])));qdiff=float(np.max(np.abs(a['q'][int(a['selected_index'])]-b['q'][int(b['selected_index'])])))
                # Observations beginning at cut are unavailable at cut; PV publication is available at cut.
                pre=issue<cut if kind=='pv_release' else issue<=cut
                if pre:
                    before.append(diff)
                    for key in input_errors:
                        if key=='initial_energy_kwh':value=abs(meta[key]-changed_meta[key])
                        else:
                            assert a[key].shape==b[key].shape
                            value=float(np.max(np.abs(a[key]-b[key]))) if a[key].size else 0.
                        input_errors[key]=max(input_errors[key],value)
                else:after.append(qdiff)
            assert max(before,default=0.)<=1e-6
            assert max(input_errors.values())<=1e-12,input_errors
            branch=POLICIES[name]['branch'];irrelevant=(kind=='pv_release' and branch=='q42') or (kind=='actual_price' and POLICIES[name]['price']=='fixed')
            response=max(after,default=0.)
            if irrelevant:assert response<=1e-6
            else:assert response>1e-6,(name,kind,'missing positive control')
            frozen_error=None
            if not POLICIES[name]['updates']:
                selected=original.date=='2025-07-15'
                frozen_error=float(np.max(np.abs(original.loc[selected,'grid_effective_kwh']-other.loc[selected,'grid_effective_kwh'])))
                assert frozen_error<=1e-6
            ledger_delta=float(other.total_cost_yuan.sum()-original.total_cost_yuan.sum())
            records.append({'policy':name,'mutation':kind,'cutoff':str(cut),'initial_kwh':6000.,'prefix_intervals':int(prefix.sum()),'prefix_max_error':error,'pre_available_candidate_max_error_kwh':max(before,default=0.),'pre_available_information_max_errors':input_errors,'appendix3_read_guards':[base_guard,other_guard] if base_guard else [],'post_available_plan_response_kwh':response,'irrelevant_channel_negative_control':irrelevant,'midnight_frozen_q_error_kwh':frozen_error,'actual_bill_difference_yuan':ledger_delta})
    write(REPORT/'causality_checks.json',{'passed':True,'records':records,'scope':'counterfactual implementation controls on three-day July paths; not annual economic or general robustness evidence','mutation_definitions':{'load_actual':'all intervals starting at cut load +800 kWh','pv_actual':'all intervals starting at cut PV times .5','pv_release':'positive-PV forecasts issued at/after cut +200 kWh','actual_price':'all actual price intervals starting at cut times1.35'},'test_initial_state_kwh':6000.})


if __name__=='__main__':
    import sys
    numerical()
    if '--numerical-only' not in sys.argv:causal()
