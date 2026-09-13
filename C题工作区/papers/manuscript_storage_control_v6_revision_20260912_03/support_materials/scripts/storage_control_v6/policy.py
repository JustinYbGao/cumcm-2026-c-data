"""Shared causal procurement/reserve candidates with matched finite search budgets."""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from compat import solve_horizon, solve_target_model
from kernel import evaluate as core_evaluate, legacy_evaluate

WORK = Path(__file__).resolve().parents[2]
LABELS = ['profile_start', 'profile_incumbent', 'profile_final',
          'point_start', 'point_incumbent', 'point_final',
          'extra_profile_start', 'extra_profile_incumbent', 'extra_profile_final',
          'extra_greedy_best_start', 'extra_greedy_best_incumbent', 'extra_greedy_best_final',
          'keep_current']
LEGACY_LABELS = LABELS[:6] + ['keep_current']
OPTIONS = {'maxiter':180, 'maxfun':1600, 'maxls':30, 'maxcor':10, 'ftol':1e-10, 'gtol':1e-5}
FLOOR, CEILING = 1200., 10800.


def evaluate(q, reserve, net, price, initial, kappa=5., mu=.38232, q0=None, legacy=False):
    """Rule A changes procurement cash/gradient, never the reserve gradient."""
    if legacy:
        if not np.all(np.asarray(reserve) == FLOOR):
            raise ValueError('legacy scoring requires reserve=1200')
        result = legacy_evaluate(q, net, price, initial, kappa, mu)
        result['reserve_gradient'] = np.zeros_like(q, dtype=float)
    else:
        result = core_evaluate(q, reserve, net, price, initial, kappa, mu)
    ordinary = float(np.dot(q, price))
    if q0 is not None:
        delta = np.asarray(q) - q0
        contract = float(np.sum(price * (q0 + 1.5 * np.maximum(delta, 0) - .5 * np.maximum(-delta, 0))))
        result['score'] += contract - ordinary
        result['gradient'] += price * np.where(delta > 0, .5, np.where(delta < 0, -.5, 0.))
        ordinary = contract
    result['ordinary'] = ordinary
    return result


def _selected(scores):
    scores = np.asarray(scores)
    if not np.isfinite(scores).all():
        raise FloatingPointError('nonfinite retained candidate score')
    return int(np.flatnonzero(scores <= scores.min() + 1e-8)[0])


def decision(load, pv, net, residual28, price, energy, slot, physical,
             q0=None, current=None, current_reserve=None, control='reserve'):
    if control not in ('legacy', 'greedy', 'reserve'):
        raise ValueError('unknown storage control')
    n = 144 - slot
    if current is not None and current_reserve is None:
        if control == 'reserve':
            raise ValueError('current_reserve is required with a held reserve policy')
        current_reserve = np.full(n, FLOOR)
    if (current is None) != (current_reserve is None):
        raise ValueError('current and current_reserve must be supplied together')
    if current is not None and (np.shape(current) != (n,) or np.shape(current_reserve) != (n,)):
        raise ValueError('held q/reserve horizon mismatch')
    if control != 'reserve' and current_reserve is not None and not np.all(current_reserve == FLOOR):
        raise ValueError('greedy/legacy held reserve must be 1200')
    for value in (load, pv, net, residual28, price, q0, current, current_reserve):
        if value is not None and not np.isfinite(value).all():
            raise ValueError('nonfinite decision input')
    if current is not None and (np.any(current < 0) or np.any(current_reserve < FLOOR) or np.any(current_reserve > CEILING)):
        raise ValueError('infeasible held q/reserve pair')

    # Hourly risk quantiles initialize procurement; they do not constrain final q/R.
    hours = np.arange(slot, 144) // 6
    delta = np.empty(n)
    for hour in np.unique(hours):
        tau = .85 if 9 <= hour < 11 else .65 if 11 <= hour < 18 else .95 if 18 <= hour < 22 else .8
        cols = hours == hour
        delta[cols] = np.quantile(residual28[:, cols].ravel(), tau, method='linear')
    risk_load = np.maximum(load + delta, 0.)
    risk_pv = pv + np.maximum(-load - delta, 0.)
    physical = json.loads(json.dumps(physical))
    physical['battery'].update(initial_energy_kwh=float(energy), terminal_target_kwh=FLOOR)
    initializer_failure = None
    try:
        if slot == 0:
            profile, milp = solve_target_model(pd.DataFrame({'price_yuan_per_kwh':price,
                'load_kwh':risk_load, 'pv_forecast_kwh':risk_pv}), physical)
        else:
            profile, milp = solve_horizon(risk_load, risk_pv, price, energy, FLOOR,
                                          physical, original=q0, rule='A')
        start0 = np.maximum(profile['grid_kwh'], 0.)
    except RuntimeError as exc:
        initializer_failure = str(exc)
        start0 = np.maximum(load - pv, 0.)
        profile = {}
        milp = {'status':'failed', 'runtime_seconds':0., 'exception':str(exc)}

    plans, reserves, logs = [], [], []
    floor = np.full(n, FLOOR)

    def search(start, reserve_start, joint_reserve, label):
        incumbent = {'score':float('inf'), 'q':start.copy(), 'reserve':reserve_start.copy()}
        trace = []
        greedy_score = not joint_reserve
        def unpack(x):
            return x[:n] * 1000., FLOOR + x[n:] * 1000. if joint_reserve else floor.copy()
        def objective(x):
            q, reserve = unpack(x)
            if not np.isfinite(q).all() or not np.isfinite(reserve).all():
                raise FloatingPointError('nonfinite optimizer iterate')
            result = evaluate(q, reserve, net, price, energy, q0=q0, legacy=greedy_score)
            gradient = np.r_[result['gradient'], result['reserve_gradient']] if joint_reserve else result['gradient']
            if not np.isfinite(result['score']) or not np.isfinite(gradient).all():
                raise FloatingPointError('nonfinite optimizer score/gradient')
            trace.append(float(result['score']))
            if result['score'] < incumbent['score']:
                incumbent.update(score=float(result['score']), q=q.copy(), reserve=reserve.copy())
            return result['score'] / 10000., gradient * .1
        x0 = np.r_[start / 1000., (reserve_start - FLOOR) / 1000.] if joint_reserve else start / 1000.
        bounds = [(0., None)] * n + ([(0., (CEILING - FLOOR) / 1000.)] * n if joint_reserve else [])
        # Evaluate the start before entering scipy so exceptional exits always have a finite fallback.
        initial_value = evaluate(start, reserve_start, net, price, energy, q0=q0, legacy=greedy_score)
        if not np.isfinite(initial_value['score']):
            raise FloatingPointError('nonfinite search start')
        tic = time.perf_counter()
        returned_problem = None
        try:
            opt = minimize(objective, x0, method='L-BFGS-B', jac=True, bounds=bounds, options=OPTIONS)
            returned_q, returned_reserve = unpack(opt.x)
            if not np.isfinite(returned_q).all() or not np.isfinite(returned_reserve).all():
                returned_problem = 'nonfinite optimizer returned candidate'
            elif np.any(returned_q < -1e-7) or np.any(returned_reserve < FLOOR - 1e-7) or np.any(returned_reserve > CEILING + 1e-7):
                returned_problem = 'infeasible optimizer returned candidate'
            else:
                returned_q = np.maximum(returned_q, 0.)
                returned_reserve = np.clip(returned_reserve, FLOOR, CEILING)
                returned_value = evaluate(returned_q, returned_reserve, net, price, energy, q0=q0, legacy=greedy_score)
                if not np.isfinite(returned_value['score']):
                    returned_problem = 'nonfinite optimizer returned score'
            log = {'success':bool(opt.success), 'status':int(opt.status), 'message':str(opt.message),
                   'nit':int(opt.nit), 'nfev':int(opt.nfev), 'njev':int(opt.njev), 'exception':None}
        except (ValueError, FloatingPointError, AssertionError) as exc:
            returned_problem = 'optimizer exception: ' + str(exc)
            log = {'success':False, 'status':-99, 'message':str(exc), 'nit':0,
                   'nfev':len(trace), 'njev':len(trace), 'exception':str(exc)}
        if not np.isfinite(incumbent['score']):
            incumbent['score'] = float(initial_value['score'])
        if returned_problem is not None:
            returned_q, returned_reserve = incumbent['q'].copy(), incumbent['reserve'].copy()
        plans.extend([start.copy(), incumbent['q'].copy(), returned_q.copy()])
        reserves.extend([reserve_start.copy(), incumbent['reserve'].copy(), returned_reserve.copy()])
        log.update(label=label, joint_reserve=joint_reserve, options=OPTIONS.copy(),
            wall_seconds=time.perf_counter() - tic, evaluation_score_yuan=trace,
            incumbent_score_yuan=float(incumbent['score']), returned_candidate_replaced=returned_problem is not None,
            returned_candidate_problem=returned_problem)
        logs.append(log)

    search(start0, floor, False, 'profile')
    search(np.maximum(load - pv, 0.), floor, False, 'point')
    legacy_scores = [evaluate(q, reserve, net, price, energy, q0=q0, legacy=True)['score']
                     for q, reserve in zip(plans, reserves)]
    best_greedy = plans[_selected(legacy_scores)].copy()
    if control != 'legacy':
        nominal = np.asarray(profile.get('energy_end_kwh', floor))
        reserve_seed = np.clip(nominal, FLOOR, CEILING) if control == 'reserve' else floor
        search(start0, reserve_seed, control == 'reserve', 'extra_profile')
        search(best_greedy, floor, control == 'reserve', 'extra_greedy_best')
    if current is not None:
        plans.append(current.copy())
        reserves.append(current_reserve.copy())
    values = [evaluate(q, reserve, net, price, energy, q0=q0, legacy=control == 'legacy')
              for q, reserve in zip(plans, reserves)]
    scores = np.array([v['score'] for v in values])
    labels = (LEGACY_LABELS if control == 'legacy' else LABELS)[:len(plans)]
    return {'q':np.array(plans), 'reserve':np.array(reserves), 'risk_delta':delta,
        'score':scores, 'ordinary':np.array([v['ordinary'] for v in values]),
        'emergency_fee':np.array([v['emergency_fee'] for v in values]),
        'end_energy':np.array([v['end_energy'] for v in values]), 'candidate_labels':labels,
        'selected_index':_selected(scores), 'optimizer':logs, 'milp_initializer':milp,
        'initializer_failure':initializer_failure, 'initializer_plan':profile}
