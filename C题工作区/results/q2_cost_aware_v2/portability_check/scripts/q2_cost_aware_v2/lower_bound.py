"""Prescient LP relaxation for a cost lower bound, never a deployable Q2 policy."""
import json
import os
from pathlib import Path
import time
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

WORK = Path(__file__).resolve().parents[2]
ROOT = WORK / 'results/q2_cost_aware_v2'
for key in ['TMPDIR','TMP','TEMP']: os.environ[key] = str(ROOT / 'runtime')


def problem(net, price, initial):
    n = len(net); t = np.arange(n)
    # Column blocks: grid, charge, discharge, surplus, ending energy.
    rows = np.concatenate([t,t,t,t,n+t,n+t,n+t,(n+t)[1:]])
    cols = np.concatenate([t,n+t,2*n+t,3*n+t,n+t,2*n+t,4*n+t,(4*n+t)[:-1]])
    values = np.concatenate([np.ones(n),-np.ones(n),np.ones(n),-np.ones(n),
                             -.9*np.ones(n),np.ones(n)/.9,np.ones(n),-np.ones(n-1)])
    matrix = coo_matrix((values,(rows,cols)),shape=(2*n,5*n)).tocsr()
    rhs = np.r_[net, initial, np.zeros(n-1)]
    objective = np.r_[price,np.zeros(4*n)]
    lower = np.r_[np.zeros(4*n),np.full(n,1200.)]
    upper = np.r_[np.full(n,np.inf),np.full(2*n,5000/6),np.full(n,np.inf),np.full(n,10800.)]
    return objective, matrix, rhs, lower, upper


def solve_relaxation(net, price, initial):
    c, a, b, lo, hi = problem(net, price, initial)
    return linprog(c, A_eq=a, b_eq=b, bounds=np.column_stack([lo,hi]), method='highs',
                   options={'time_limit':300.,'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9})


if __name__ == '__main__':
    folder = ROOT / 'lower_bound'; folder.mkdir(parents=True,exist_ok=False)
    actual = pd.read_csv(ROOT / 'inputs/actual_10min.csv',float_precision='round_trip')
    actual = actual.loc[(actual.date >= '2025-02-01') & (actual.date <= '2025-12-31')].reset_index(drop=True)
    net = (actual.load_actual_kwh-actual.pv_actual_kwh).to_numpy()
    price = np.tile(pd.read_csv(ROOT/'inputs/fixed_price.csv').price_yuan_per_kwh.to_numpy(),334)
    initial = 7268.4231640740745
    start=time.perf_counter(); result=solve_relaxation(net,price,initial); wall=time.perf_counter()-start
    status={'success':bool(result.success),'status':int(result.status),'message':result.message,'wall_seconds':wall,
            'variables':5*len(net),'equality_constraints':2*len(net),'iterations':int(result.nit),
            'scope':'Prescient ordinary-price continuous LP; relaxes information, midnight commitment, daily terminal and charge/discharge exclusivity; final minimum 1200. Not an executable policy or EVPI.'}
    (folder/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    assert result.success,result.message
    c,a,b,lo,hi=problem(net,price,initial)
    y,zl,zu=result.eqlin.marginals,result.lower.marginals,result.upper.marginals
    primal=float(c@result.x); finite=np.isfinite(hi)
    dual=float(b@y+lo@zl+hi[finite]@zu[finite])
    metrics={'primal_cost_yuan':primal,'dual_bound_yuan':dual,'primal_dual_gap_yuan':primal-dual,
             'max_balance_residual_kwh':float(abs(a@result.x-b).max()),
             'max_stationarity_residual':float(abs(c-a.T@y-zl-zu).max()),
             'lower_dual_min':float(zl.min()),'upper_dual_max':float(zu.max()),
             'initial_energy_kwh':initial,'final_energy_kwh':float(result.x[-1])}
    status.update(metrics)
    (folder/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    np.savez_compressed(folder/'certificate.npz',primal=result.x,equality_dual=y,lower_dual=zl,upper_dual=zu,
                        net=net,price=price,initial=np.asarray(initial))
    n=len(net); frame=actual[['date','slot_id']].copy()
    for i,key in enumerate(['grid_kwh','charge_kwh','discharge_kwh','surplus_kwh','energy_end_kwh']):frame[key]=result.x[i*n:(i+1)*n]
    frame['energy_start_kwh']=np.r_[initial,frame.energy_end_kwh.to_numpy()[:-1]]
    frame['ordinary_cost_yuan']=price*frame.grid_kwh
    frame.to_csv(folder/'relaxed_ledger.csv',index=False)
    print(json.dumps(status,indent=2),flush=True)
