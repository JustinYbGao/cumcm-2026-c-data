"""Additional fresh kernel and mature-window causality probes in the audit copy."""
import json
import sys
import numpy as np
import pandas as pd
from audit import OUT, ROOT, WORK, csv, forecasts, replay

SHADOW=OUT/'replay_workspace'
sys.path.insert(0,str(SHADOW/'scripts/q2_direct_v4'))
from kernel import evaluate
from run_experiments import run_one


def main():
    rng=np.random.default_rng(20260911)
    price=csv(ROOT/'inputs/fixed_price.csv').price_yuan_per_kwh.to_numpy()
    gradient_results=[]
    for kappa,mu in [(5.,.38232),(6.25,.38232),(5.,0.)]:
        q=rng.uniform(50,1300,144);net=rng.uniform(-250,1800,(5,144));initial=5700.
        def cost(buy):
            paths=[replay(buy,path,initial) for path in net]
            return float(price@buy+np.mean([kappa*price@p[:,4]-mu*(p[-1,1]-initial) for p in paths]))
        r=evaluate(q,net,price,initial,kappa,mu);h=1e-3;derivatives=[]
        for i in range(144):
            a=q.copy();b=q.copy();a[i]+=h;b[i]-=h
            derivatives.append((cost(a)-cost(b))/(2*h))
        error=float(np.max(np.abs(np.array(derivatives)-r['gradient'])))
        assert abs(cost(q)-r['score'])<1e-6 and error<1e-5,(kappa,mu,error)
        gradient_results.append({'kappa':kappa,'mu':mu,'max_fd_error':error,'score_difference':abs(cost(q)-r['score']),'step_kwh':h})
    # Unlike the supplied January test, July exercises a full 112-day scenario pool.
    original=csv(ROOT/'inputs/actual_10min.csv');mutated=original.copy()
    cutoff=pd.Timestamp('2025-07-15T12:00:00')
    mask=pd.to_datetime(mutated.interval_start)>=cutoff
    mutated.loc[mask,'load_actual_kwh']+=800
    mutated.loc[mask,'pv_actual_kwh']*=.5
    for field in ['load','pv']:mutated[field+'_actual_kw']=6*mutated[field+'_actual_kwh']
    mutated['net_load_actual_kwh']=mutated.load_actual_kwh-mutated.pv_actual_kwh
    mutated['net_load_actual_kw']=6*mutated.net_load_actual_kwh
    base_archive=csv(ROOT/'forecasts/linear_harmonic.csv')
    archives=[]
    for source in [original,mutated]:
        archive=base_archive.copy();pred=forecasts(source).reshape(-1,2)
        archive['load_forecast_kwh']=pred[:,0];archive['pv_forecast_kwh']=pred[:,1]
        truth=source.loc[source.date>='2025-01-02']
        archive['load_actual_kwh']=truth.load_actual_kwh.to_numpy()
        archive['pv_actual_kwh']=truth.pv_actual_kwh.to_numpy()
        archive['net_residual_kwh']=archive.load_actual_kwh-archive.pv_actual_kwh-pred[:,0]+pred[:,1]
        archives.append(archive)
    cfg=next(c for c in json.loads((WORK/'configs/q2_direct_v4/experiments.json').read_text())['runs'] if c['policy']=='D112')
    cfg=dict(cfg,start='2025-07-14',end='2025-07-16',initial_energy_kwh=6000.)
    frames=[]
    for stage,source,archive in zip(['audit_causality_original','audit_causality_mutated'],[original,mutated],archives):
        frames.append(run_one(cfg,stage,source,archive))
    a,b=frames;early=pd.to_datetime(a.interval_start)<cutoff
    fields=['grid_plan_kwh','charge_actual_kwh','discharge_actual_kwh','emergency_kwh','energy_end_actual_kwh','total_cost_yuan']
    prefix=float(np.abs(a.loc[early,fields].to_numpy()-b.loc[early,fields].to_numpy()).max())
    frozen=a.date<='2025-07-15';nextday=a.date=='2025-07-16'
    planerr=float(np.abs(a.loc[frozen,'grid_plan_kwh'].to_numpy()-b.loc[frozen,'grid_plan_kwh'].to_numpy()).max())
    response=float(np.abs(a.loc[nextday,'grid_plan_kwh'].to_numpy()-b.loc[nextday,'grid_plan_kwh'].to_numpy()).max())
    path=SHADOW/'results/q2_direct_v4'
    with np.load(path/'audit_causality_original/D112/decision_evidence.npz') as x,np.load(path/'audit_causality_mutated/D112/decision_evidence.npz') as y:
        evidence=all(np.array_equal(x[k][:2],y[k][:2],equal_nan=True) for k in x.files)
    assert prefix<=1e-6 and planerr==0 and response>1e-4 and evidence
    result={'passed':True,'gradient_checks':gradient_results,'causality':{'policy':'D112','cutoff':str(cutoff),'initial_kwh':6000.,'scenario_count':112,'prefix_rows':int(early.sum()),'prefix_max_error':prefix,'frozen_plan_error':planerr,'first_two_days_candidate_arrays_identical':evidence,'next_day_q_response_kwh':response,'scope':'Additional counterfactual implementation test, not an annual economic experiment or universal causality proof.'}}
    (OUT/'extra_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
