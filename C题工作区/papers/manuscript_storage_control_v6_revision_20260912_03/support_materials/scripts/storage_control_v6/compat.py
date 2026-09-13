"""Frozen function bodies; source provenance in SOURCE_PROVENANCE.json."""

import highspy
import numpy as np
import pandas as pd

def fourier(k):
    time=np.arange(144)/144
    return np.column_stack([np.ones(144)]+[f(2*np.pi*j*time) for j in range(1,k+1) for f in [np.sin,np.cos]])

def forecast_day(history,day,kind,cfg):
    day=pd.Timestamp(day)
    if len(history) and (pd.to_datetime(history.interval_end)>day).any():
        raise ValueError('future observation in forecast history')
    if len(history)==0:
        return np.full(144,np.nan),np.full(144,np.nan),{'method':'cold_start_zero_commitment','history_end':None}
    if len(history)%144:
        raise ValueError('forecast history requires complete days')
    dates=pd.to_datetime(history.date.unique())
    loads=history.load_actual_kwh.to_numpy().reshape(-1,144)
    pvs=history.pv_actual_kwh.to_numpy().reshape(-1,144)
    n=len(loads)
    load=loads[-7 if n>=7 else -1].copy()
    pv=pvs[-1].copy()
    meta={'method':kind,'history_end':str(pd.Timestamp(history.interval_end.iloc[-1])),
          'load_method':'lag7' if n>=7 else 'lag1','pv_method':'lag1'}
    if kind!='seasonal' and n>=7+cfg['min_load_training_days']:
        f=fourier(cfg['load_harmonics'])
        def design(i,date):
            weekday=np.tile([float(date.weekday()==k) for k in range(1,7)],(144,1))
            return np.column_stack([f,loads[i-1]/1000,loads[i-7]/1000,weekday])
        first=max(7,n-cfg['load_training_days'])
        x=np.vstack([design(i,dates[i]) for i in range(first,n)])
        y=loads[first:].ravel()
        beta,_,rank,s=np.linalg.lstsq(x,y,rcond=None)
        load=np.maximum(design(n,day)@beta,0)
        meta.update(load_method='OLS_lag1_lag7_weekday_fourier',load_coefficients=beta.tolist(),
                    load_rank=int(rank),load_columns=x.shape[1],load_condition=float(s[0]/s[-1]),
                    load_training_first=str(dates[first].date()),load_training_last=str(dates[-1].date()))
    if kind=='linear_harmonic' and n>=2:
        window=min(n,cfg['pv_training_days'])
        f=fourier(cfg['pv_harmonics'])
        x=np.tile(f,(window,1))
        y=pvs[-window:].ravel()
        beta=np.linalg.lstsq(x,y,rcond=None)[0]
        residual=y-x@beta
        denom=float(residual[:-1]@residual[:-1])
        phi=float(np.clip((residual[:-1]@residual[1:])/denom if denom>1e-12 else 0.,-cfg['ar1_bound'],cfg['ar1_bound']))
        pv=np.maximum(f@beta+phi**np.arange(1,145)*residual[-1],0)
        meta.update(pv_method='rolling_harmonic_AR1',pv_coefficients=beta.tolist(),pv_phi=phi,
                    pv_last_residual=float(residual[-1]),pv_training_first=str(dates[-window].date()),
                    pv_training_last=str(dates[-1].date()))
    return load,pv,meta

def execute_interval(grid,load,pv,energy,eta_c,eta_d,storage=True):
    net=grid+pv-load
    c=d=emergency=surplus=0.
    if net>=0:
        c=min(net,5000/6,max(0.,(10800-energy)/eta_c)) if storage else 0.
        surplus=net-c
    else:
        d=min(-net,5000/6,max(0.,eta_d*(energy-1200))) if storage else 0.
        emergency=-net-d
    # Bookkeeping convention: use PV first; disposal of already-paid grid energy is separate.
    unused_grid=min(grid,surplus)
    return {'charge_actual_kwh':c,'discharge_actual_kwh':d,'emergency_kwh':emergency,
            'surplus_kwh':surplus,'unused_grid_kwh':unused_grid,'pv_curtailment_kwh':surplus-unused_grid,
            'energy_start_actual_kwh':energy,'energy_end_actual_kwh':energy+eta_c*c-d/eta_d}

def contract_fee(original,final,price,rule):
    delta=np.asarray(final)-np.asarray(original)
    if rule not in ('A','B'):raise ValueError('Unknown settlement')
    sign=-1 if rule=='A' else 1
    return price*(original+1.5*np.maximum(delta,0)+sign*.5*np.maximum(-delta,0))

def solve_horizon(load,pv,price,initial,terminal,physical,original=None,rule='A',relaxed=False):
    """Q1 physical MILP, with separately specified rolling initial and day-end target."""
    n=len(load);b=physical['battery'];dt=physical['interval_minutes']/60
    mc=b['max_charge_kw']*dt;md=b['max_discharge_kw']*dt
    h=highspy.Highs();h.setOptionValue('output_flag',False)
    for key,value in physical['solver'].items():
        if key!='name':
            if h.setOptionValue(key,value)!=highspy.HighsStatus.kOk:raise ValueError(key)
    q=[h.addVariable(lb=float(original[t]) if original is not None and rule=='B' else 0,
        obj=float(price[t]) if original is None else 0,name=f'q_{t}') for t in range(n)]
    c=[h.addVariable(ub=mc,name=f'c_{t}') for t in range(n)]
    d=[h.addVariable(ub=md,name=f'b_{t}') for t in range(n)]
    # Surplus includes PV and paid grid energy: required for the B no-refund case.
    w=[h.addVariable(name=f'w_{t}') for t in range(n)]
    e=[h.addVariable(lb=b['min_energy_kwh'],ub=b['max_energy_kwh'],name=f'E_{t}') for t in range(n+1)]
    z=[h.addVariable(ub=1,type=highspy.HighsVarType.kContinuous if relaxed else highspy.HighsVarType.kInteger,name=f'z_{t}') for t in range(n)]
    h.addConstr(e[0]==initial);h.addConstr(e[-1]==terminal)
    for t in range(n):
        h.addConstr(q[t]+d[t]-c[t]-w[t]==float(load[t]-pv[t]))
        h.addConstr(e[t+1]==e[t]+b['eta_charge']*c[t]-(1/b['eta_discharge'])*d[t])
        h.addConstr(c[t]<=mc*z[t]);h.addConstr(d[t]<=md*(1-z[t]))
        if original is not None:
            v=h.addVariable(obj=1,name=f'fee_{t}')
            p=float(price[t]);base=float(original[t])
            h.addConstr(v>=1.5*p*q[t]-.5*p*base)
            if rule=='A':h.addConstr(v>=.5*p*q[t]+.5*p*base)
            elif rule=='B':h.addConstr(v>=-.5*p*q[t]+1.5*p*base)
            else:raise ValueError('Unknown settlement')
    h.run()
    if h.getModelStatus()!=highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(h.modelStatusToString(h.getModelStatus()))
    solution=h.getSolution();info=h.getInfo()
    values=lambda variables:np.array([solution.col_value[int(v)] for v in variables])
    state=values(e)
    plan={'grid_kwh':values(q),'charge_kwh':values(c),'discharge_kwh':values(d),'surplus_kwh':values(w),
        'energy_start_kwh':state[:-1],'energy_end_kwh':state[1:],'charge_mode':values(z)}
    obj=float(np.dot(price,plan['grid_kwh']) if original is None else contract_fee(original,plan['grid_kwh'],price,rule).sum())
    status={'status':'Optimal','objective_yuan':obj,'solver_objective_yuan':h.getObjectiveValue(),
        'lower_bound_yuan':h.getObjectiveValue() if relaxed else info.mip_dual_bound,
        'mip_gap':None if relaxed else info.mip_gap,'runtime_seconds':h.getRunTime(),
        'max_primal_infeasibility':info.max_primal_infeasibility,'relaxed':relaxed,
        'variables':h.getNumCol(),'constraints':h.getNumRow()}
    return plan,status

def forecast_price(history,issue,cfg):
    """Only completed observations are accepted; future actual prices cannot be passed."""
    issue=pd.Timestamp(issue);h=history.copy()
    h['interval_start']=pd.to_datetime(h.interval_start);h['interval_end']=pd.to_datetime(h.interval_end)
    if h.interval_end.gt(issue).any():raise ValueError('future actual price in history')
    if h.empty or h.interval_end.iloc[-1]!=issue:raise ValueError('Incomplete price history')
    series=h.set_index('interval_start').actual_price_yuan_per_kwh
    if series.index.has_duplicates or not series.index.equals(pd.date_range(series.index[0],issue,freq='10min',inclusive='left')):
        raise ValueError('Noncontinuous price history')
    start=max(series.index[0]+pd.Timedelta(days=7),issue-pd.Timedelta(days=cfg['price_training_days']))
    train=pd.date_range(start,issue,freq='10min',inclusive='left')
    if len(train)<144:raise ValueError('Insufficient price training history')
    target=pd.date_range(issue,issue.normalize()+pd.Timedelta(days=1),freq='10min',inclusive='left')
    def design(times):
        phase=(times.hour*60+times.minute).to_numpy()/1440
        cols=[np.ones(len(times))]
        for k in range(1,cfg['price_harmonics']+1):cols.extend([np.sin(2*np.pi*k*phase),np.cos(2*np.pi*k*phase)])
        cols.extend([series.loc[times-pd.Timedelta(days=1)].to_numpy(),series.loc[times-pd.Timedelta(days=7)].to_numpy()])
        cols.extend([(times.weekday==k).astype(float) for k in range(1,7)])
        return np.column_stack(cols)
    x=design(train);y=series.loc[train].to_numpy();beta,_,rank,s=np.linalg.lstsq(x,y,rcond=None)
    raw=design(target)@beta;floor=cfg['price_floor_yuan_per_kwh'];values=np.maximum(raw,floor)
    meta={'method':'rolling_OLS','issue_time':str(issue),'training_first_start':str(train[0]),
        'training_last_end':str(train[-1]+pd.Timedelta(minutes=10)),'training_rows':len(train),
        'feature_count':x.shape[1],'rank':int(rank),'condition':float(s[0]/s[-1]) if s[-1]>0 else None,
        'coefficients':beta.tolist(),'floor_yuan_per_kwh':floor,'floor_activations':int((raw<floor).sum()),
        'raw_forecast_min':float(raw.min()),'raw_forecast_max':float(raw.max())}
    return values,meta

def solve_target_model(data, cfg, relaxed=False, tag=None, cost_cap=None):
    """Return a dispatch plus solver evidence; LP relaxes only mode integrality."""
    n = len(data)
    b = cfg['battery']
    dt = cfg['interval_minutes'] / 60
    mc, md = b['max_charge_kw'] * dt, b['max_discharge_kw'] * dt
    h = highspy.Highs()
    h.setOptionValue('output_flag', bool(tag))
    if tag:
        h.setOptionValue('log_file', str(WORK / f'logs/q1/{tag}.log'))
    for k, v in cfg['solver'].items():
        if k != 'name':
            if h.setOptionValue(k, v) != highspy.HighsStatus.kOk:
                raise ValueError(f'Invalid solver option: {k}')
    p = data.price_yuan_per_kwh.to_numpy()
    load = data.load_kwh.to_numpy()
    pv = data.pv_forecast_kwh.to_numpy()
    g = [h.addVariable(obj=float(p[t]) if cost_cap is None else 0., name=f'g_{t}') for t in range(n)]
    c = [h.addVariable(ub=mc, obj=float(t + 1) if cost_cap is not None else 0., name=f'c_{t}') for t in range(n)]
    d = [h.addVariable(ub=md, name=f'd_{t}') for t in range(n)]
    w = [h.addVariable(ub=float(pv[t]), name=f'w_{t}') for t in range(n)]
    e = [h.addVariable(lb=b['min_energy_kwh'], ub=b['max_energy_kwh'], name=f'E_{t}') for t in range(n+1)]
    z = [h.addVariable(ub=1, type=highspy.HighsVarType.kContinuous if relaxed else highspy.HighsVarType.kInteger,
                       name=f'z_{t}') for t in range(n)]
    h.addConstr(e[0] == b['initial_energy_kwh'], name='initial')
    h.addConstr(e[n] == b['terminal_target_kwh'], name='terminal')
    for t in range(n):
        h.addConstr(g[t] - w[t] + d[t] - c[t] == float(load[t]-pv[t]), name=f'balance_{t}')
        h.addConstr(e[t+1] - e[t] - b['eta_charge'] * c[t] + (1 / b['eta_discharge']) * d[t] == 0., name=f'state_{t}')
        h.addConstr(c[t] <= mc * z[t], name=f'charge_mode_{t}')
        h.addConstr(d[t] + md * z[t] <= md, name=f'discharge_mode_{t}')
    if cost_cap is not None:
        h.addConstr(sum(float(p[t]) * g[t] for t in range(n)) <= cost_cap, name='primary_cost_cap')
    if tag:
        h.writeModel(str(WORK / f'results/q1/{tag}.lp'))
    h.run()
    status = h.modelStatusToString(h.getModelStatus())
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        raise RuntimeError(f'{tag}: {status}; see solver log; no optimal result published')
    sol, info = h.getSolution(), h.getInfo()
    values = lambda vs: np.array([sol.col_value[int(v)] for v in vs])
    ev = values(e)
    x = {'grid_kwh': values(g), 'charge_kwh': values(c), 'discharge_kwh': values(d),
         'curtailment_kwh': values(w), 'energy_start_kwh': ev[:-1], 'energy_end_kwh': ev[1:],
         'charge_mode': values(z)}
    result = {'status': status, 'objective_yuan': float(np.dot(p, x['grid_kwh'])),
              'solver_objective': h.getObjectiveValue(), 'relaxed': relaxed,
              'lower_bound_yuan': h.getObjectiveValue() if relaxed else info.mip_dual_bound,
              'mip_gap': None if relaxed else info.mip_gap,
              'nodes': None if relaxed else info.mip_node_count, 'runtime_seconds': h.getRunTime(),
              'variables': h.getNumCol(), 'constraints': h.getNumRow(),
              'max_primal_infeasibility': info.max_primal_infeasibility,
              'max_integrality_violation': None if relaxed else info.max_integrality_violation,
              'lower_bound_unit': 'secondary_weighted_charge_objective' if cost_cap is not None else 'yuan',
              'primary_cost_cap_yuan': cost_cap}
    if tag:
        h.writeSolution(str(WORK / f'results/q1/{tag}.sol'), 0)
    return x, result
