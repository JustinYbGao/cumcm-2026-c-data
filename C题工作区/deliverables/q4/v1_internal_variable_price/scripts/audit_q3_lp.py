"""Independent matrix LP lower bounds for four prescribed days and both rules.

Uses scipy.linprog rather than the planner's symbolic model; relaxes mode variables
to charge/mc + discharge/md <= 1. This is a bound, not an alternative controller.
"""
import json
import os
from pathlib import Path
import sys
import time

WORK=Path(__file__).resolve().parents[1]
os.environ['TMPDIR']=str(WORK/'data/interim/q3')
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix


def independent_lp(frame,prices,initial,target,battery,minutes,rule,hour):
    n=len(frame);updating=hour>0;m=5*n+1+(n if updating else 0)
    ec=battery['eta_charge'];ed=battery['eta_discharge']
    mc=battery['max_charge_kw']*minutes/60;md=battery['max_discharge_kw']*minutes/60
    objective=np.zeros(m)
    bounds=[(0,None)]*m
    for t in range(n):
        bounds[n+t]=(0,mc);bounds[2*n+t]=(0,md)
        if updating and rule=='B':bounds[t]=(float(frame.grid_original_kwh.iloc[t]),None)
        if updating:objective[5*n+1+t]=1
        else:objective[t]=prices[t]
    for t in range(n+1):bounds[4*n+t]=(battery['min_energy_kwh'],battery['max_energy_kwh'])
    eq=lil_matrix((2*n+2,m));rhs=np.zeros(2*n+2)
    for t in range(n):
        eq[t,t]=1;eq[t,n+t]=-1;eq[t,2*n+t]=1;eq[t,3*n+t]=-1
        rhs[t]=frame.load_forecast_kwh.iloc[t]-frame.pv_forecast_kwh.iloc[t]
        eq[n+t,4*n+t+1]=1;eq[n+t,4*n+t]=-1
        eq[n+t,n+t]=-ec;eq[n+t,2*n+t]=1/ed
    eq[2*n,4*n]=1;rhs[2*n]=initial
    eq[2*n+1,5*n]=1;rhs[2*n+1]=target
    ub=lil_matrix((n+(2*n if updating else 0),m));limit=np.ones(ub.shape[0])
    for t in range(n):
        ub[t,n+t]=1/mc;ub[t,2*n+t]=1/md
        if updating:
            base=frame.grid_original_kwh.iloc[t];p=prices[t];v=5*n+1+t
            ub[n+t,t]=1.5*p;ub[n+t,v]=-1;limit[n+t]=.5*p*base
            ub[2*n+t,t]=(.5 if rule=='A' else -.5)*p;ub[2*n+t,v]=-1
            limit[2*n+t]=(-.5 if rule=='A' else -1.5)*p*base
    result=linprog(objective,A_ub=ub.tocsr(),b_ub=limit,A_eq=eq.tocsr(),b_eq=rhs,bounds=bounds,method='highs',options={'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
    if not result.success:raise RuntimeError(result.message)
    x=result.x
    equality=float(np.max(np.abs(eq@x-rhs)))
    inequality=float(max(0,np.max(ub@x-limit)))
    bound_violation=float(max([0]+[max(0,low-x[j],0 if high is None else x[j]-high) for j,(low,high) in enumerate(bounds)]))
    return float(result.fun),equality,inequality,bound_violation


def main():
    out=WORK/'results/q3';cfg=json.loads((out/'physical_snapshot.json').read_text())
    prices=pd.read_csv(WORK/'data/processed/fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    rows=[];dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    for policy,rule in [('no_update','A'),('all_A','A'),('all_B','B')]:
        versions=pd.read_csv(out/policy/'plan_versions.csv',float_precision='round_trip')
        by_version=versions.groupby(['date','issue_hour'])
        for status in json.loads((out/policy/'solvers.json').read_text()):
            if status['date'] not in dates:continue
            hour=status['issue_hour'];f=by_version.get_group((status['date'],hour));started=time.perf_counter()
            lower,eq,ub,bounds=independent_lp(f,prices[hour*6:],status['initial_energy_kwh'],status['terminal_target_kwh'],cfg['battery'],cfg['interval_minutes'],rule,hour)
            mip=status['solver']['objective_yuan'];gap=mip-lower
            rows.append({'policy':policy,'date':status['date'],'issue_hour':hour,'horizon_intervals':len(f),
                'milp_objective_yuan':mip,'independent_lp_bound_yuan':lower,'milp_minus_lp_yuan':gap,
                'lp_equality_residual_kwh':eq,'lp_inequality_violation':ub,'lp_bound_violation':bounds,
                'runtime_seconds':time.perf_counter()-started,
                'passed':bool(gap>=-1e-5 and max(eq,ub,bounds)<=1e-6)})
    frame=pd.DataFrame(rows);frame.to_csv(out/'independent_lp_audit.csv',index=False)
    report={'passed':bool(frame.passed.all() and len(frame)==36),'sample_count':len(frame),
        'max_milp_minus_lp_yuan':float(frame.milp_minus_lp_yuan.max()),
        'max_lp_primal_violation':float(frame[['lp_equality_residual_kwh','lp_inequality_violation','lp_bound_violation']].to_numpy().max()),
        'method':'Independent scipy.linprog sparse matrix LP relaxation; same HiGHS algorithm family, independently assembled constraints. Not an independent solver vendor.',
        'scope':'Four prescribed dates; no_update midnight and all_A/all_B 00/06/12/18. Bounds apply only to these forecast horizons.'}
    (out/'independent_lp_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['passed']:sys.exit(1)


if __name__=='__main__':main()
