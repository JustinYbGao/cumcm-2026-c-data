"""Direct scenario procurement with release-stage and rule-A contract adapters."""
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from compat import solve_horizon, solve_target_model
from kernel import evaluate as core_evaluate

WORK=Path(__file__).resolve().parents[2]
LABELS=['profile_start','profile_incumbent','profile_final','point_start','point_incumbent','point_final','keep_current']
OPTIONS={'maxiter':180,'maxfun':1600,'maxls':30,'maxcor':10,'ftol':1e-10,'gtol':1e-5}


def evaluate(q,net,price,initial,kappa=5.,mu=.38232,q0=None):
    r=core_evaluate(q,net,price,initial,kappa,mu)
    ordinary=float(np.dot(q,price))
    if q0 is not None:
        delta=np.asarray(q)-q0
        contract=float(np.sum(price*(q0+1.5*np.maximum(delta,0)-.5*np.maximum(-delta,0))))
        r['score']+=contract-ordinary
        r['gradient']+=price*np.where(delta>0,.5,np.where(delta<0,-.5,0.))
        ordinary=contract
    r['ordinary']=ordinary
    return r


def decision(load,pv,net,residual28,price,energy,slot,physical,q0=None,current=None):
    # Hourly risk quantiles are only an initializer, inherited from D112.
    hours=np.arange(slot,144)//6
    delta=np.empty(144-slot)
    for hour in np.unique(hours):
        tau=.85 if 9<=hour<11 else .65 if 11<=hour<18 else .95 if 18<=hour<22 else .8
        cols=hours==hour
        delta[cols]=np.quantile(residual28[:,cols].ravel(),tau,method='linear')
    risk_load=np.maximum(load+delta,0.)
    risk_pv=pv+np.maximum(-load-delta,0.)
    b=json.loads(json.dumps(physical));b['battery'].update(initial_energy_kwh=float(energy),terminal_target_kwh=1200.)
    initializer_failure=None
    try:
        if slot==0:
            profile,milp=solve_target_model(pd.DataFrame({'price_yuan_per_kwh':price,'load_kwh':risk_load,'pv_forecast_kwh':risk_pv}),b)
        else:
            profile,milp=solve_horizon(risk_load,risk_pv,price,energy,1200.,b,original=q0,rule='A')
        start0=np.maximum(profile['grid_kwh'],0.)
    except RuntimeError as exc:
        # A nonnegative point net plan is always valid for the strict emergency executor.
        initializer_failure=str(exc);start0=np.maximum(load-pv,0.)
        profile={};milp={'status':'failed','runtime_seconds':0.,'exception':str(exc)}
    starts=[start0,np.maximum(load-pv,0.)]
    plans=[];logs=[]
    for start in starts:
        incumbent={'score':float('inf'),'q':start.copy()};trace=[]
        def objective(x):
            q=x*1000.;r=evaluate(q,net,price,energy,q0=q0)
            trace.append(r['score'])
            if r['score']<incumbent['score']: incumbent.update(score=r['score'],q=q.copy())
            return r['score']/10000.,r['gradient']*.1
        tic=time.perf_counter()
        try:
            opt=minimize(objective,start/1000.,method='L-BFGS-B',jac=True,bounds=[(0.,None)]*len(start),options=OPTIONS)
            final=np.maximum(opt.x*1000.,0.)
            log={'success':bool(opt.success),'status':int(opt.status),'message':str(opt.message),'nit':int(opt.nit),'nfev':int(opt.nfev),'njev':int(opt.njev),'exception':None}
        except (ValueError,FloatingPointError,AssertionError) as exc:
            final=incumbent['q'].copy();log={'success':False,'status':-99,'message':str(exc),'nit':0,'nfev':len(trace),'njev':len(trace),'exception':str(exc)}
        plans.extend([start.copy(),incumbent['q'].copy(),final])
        log.update(wall_seconds=time.perf_counter()-tic,evaluation_score_yuan=trace,incumbent_score_yuan=float(incumbent['score']))
        logs.append(log)
    if current is not None:plans.append(current.copy())
    values=[evaluate(q,net,price,energy,q0=q0) for q in plans]
    scores=np.array([v['score'] for v in values]);selected=int(np.flatnonzero(scores<=scores.min()+1e-8)[0])
    return {'q':np.array(plans),'risk_delta':delta,'score':scores,'ordinary':np.array([v['ordinary'] for v in values]),
            'emergency_fee':np.array([v['emergency_fee'] for v in values]),'end_energy':np.array([v['end_energy'] for v in values]),
            'selected_index':selected,'optimizer':logs,'milp_initializer':milp,'initializer_failure':initializer_failure,
            'initializer_plan':profile}
