"""Two-start direct procurement heuristic on completed historical scenarios."""
from base_policy import (WORK, ROOT, INPUTS, np, pd, completed_history, scenario_bank,
    risk_deltas, solve_target_model, execute_interval, forecast_day, save_json, choose_index, PLAN_KEYS)
import json
import time
from scipy.optimize import minimize
from kernel import evaluate

LABELS=['profile_start','profile_incumbent','profile_final','point_start','point_incumbent','point_final']
OPTIONS=json.loads((WORK/'configs/q2_direct_v4/experiments.json').read_text())['optimizer']


def decision(archive, day, load_hat, pv_hat, price, energy, cfg):
    history=completed_history(archive,day,28)
    if history.date.nunique()<7: raise ValueError('Fewer than seven completed risk days')
    net, dates=scenario_bank(archive,day,cfg['scenario_window'],load_hat-pv_hat)
    if len(dates)<7: raise ValueError('Fewer than seven completed scenario days')
    taus=np.array([.85 if 9<=h<11 else .65 if 11<=h<18 else .95 if 18<=h<22 else .8 for h in range(24)])
    deltas=risk_deltas(archive,day,28,sorted(set(taus)))
    delta=np.array([deltas[taus[t//6]][t] for t in range(144)])
    physical=json.loads((INPUTS/'model_baseline.json').read_text())
    physical['battery'].update(initial_energy_kwh=float(energy),terminal_target_kwh=1200.)
    data=pd.DataFrame({'price_yuan_per_kwh':price,'load_kwh':np.maximum(load_hat+delta,0.),
                       'pv_forecast_kwh':pv_hat+np.maximum(-load_hat-delta,0.)})
    profile, milp=solve_target_model(data,physical)
    starts=[np.maximum(profile['grid_kwh'],0.),np.maximum(load_hat-pv_hat,0.)]
    plans=[]; logs=[]
    for start in starts:
        incumbent={'score':float('inf'),'q':start.copy()}; trace=[]
        def objective(x):
            q=x*1000.; r=evaluate(q,net,price,energy,cfg['kappa'],cfg['mu'])
            trace.append(r['score'])
            if r['score']<incumbent['score']: incumbent.update(score=r['score'],q=q.copy())
            return r['score']/10000., r['gradient']*.1
        started=time.perf_counter()
        result=minimize(objective,start/1000.,method='L-BFGS-B',jac=True,
                        bounds=[(0.,None)]*144,options=cfg.get('optimizer',OPTIONS))
        elapsed=time.perf_counter()-started
        plans.extend([start.copy(),incumbent['q'],np.maximum(result.x*1000.,0.)])
        logs.append({'success':bool(result.success),'status':int(result.status),'message':str(result.message),'wall_seconds':elapsed,
                     'nit':int(result.nit),'nfev':int(result.nfev),'njev':int(result.njev),
                     'evaluation_score_yuan':trace,'incumbent_score_yuan':incumbent['score']})
    candidates=[evaluate(q,net,price,energy,cfg['kappa'],cfg['mu']) for q in plans]
    scores=np.array([r['score'] for r in candidates]); selected=choose_index(scores)
    assert scores[selected]<=min(scores[0],scores[3])+1e-8
    return {'q':np.asarray(plans),'risk_delta':delta,'scenarios':net,'source_dates':dates,
            'score':scores,'selected':selected,'optimizer':logs,'milp':milp,
            'initializer_plan':np.column_stack([profile[key] for key in PLAN_KEYS]),
            'ordinary':np.asarray(plans)@price,
            'emergency_fee':np.asarray([r['emergency_fee'] for r in candidates]),
            'end_energy':np.asarray([r['end_energy'] for r in candidates])}
