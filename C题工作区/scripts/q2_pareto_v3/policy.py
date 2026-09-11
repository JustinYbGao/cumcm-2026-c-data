"""Time-specific risk allocation with auditable empirical fee constraints."""
from base_policy import *


def empirical_cvar(losses, alpha):
    values=np.asarray(losses)
    index=int(np.ceil(values.shape[1]*alpha))-1
    eta=np.sort(values,axis=1)[:,index]
    return eta+np.maximum(values-eta[:,None],0.).mean(axis=1)/(1-alpha)


def guard_mask(ordinary, emergency, end_energy, guard, alpha):
    if guard=='none':return np.ones(len(ordinary),dtype=bool)
    fees=emergency.mean(axis=1);stock=end_energy.mean(axis=1)
    allowed=(ordinary<=ordinary[0]+1e-7)&(fees<=fees[0]+1e-7)&(stock>=stock[0]-1e-6)
    if guard=='tail':
        tail=empirical_cvar(emergency,alpha)
        allowed&=tail<=tail[0]+1e-7
    return allowed


def checked_risk_deltas(archive,day,taus):
    if completed_history(archive,day,28).date.nunique()<7:
        raise ValueError('At least seven completed risk-history days are required.')
    return risk_deltas(archive,day,28,taus)


def profile_delta(archive, day, profile):
    values=checked_risk_deltas(archive,day,sorted(set(profile)))
    return np.concatenate([values[tau][h*6:(h+1)*6] for h,tau in enumerate(profile)])


def decision(archive,day,load_hat,pv_hat,price,energy,cfg):
    definitions=cfg.get('profile_definitions') or json.loads((WORK/'configs/q2_pareto_v3/experiments.json').read_text())['profiles']
    taus=sorted({tau for name in cfg['profiles'] for tau in definitions[name]})
    deltas=checked_risk_deltas(archive,day,taus)
    scenarios,dates=scenario_bank(archive,day,cfg['scenario_window'],load_hat-pv_hat)
    if len(dates)<7:raise ValueError('At least seven completed scenario days are required.')
    physical=json.loads((INPUTS/'model_baseline.json').read_text())
    physical['battery']['initial_energy_kwh']=float(energy)
    physical['battery']['terminal_target_kwh']=cfg['terminal_energy_kwh']
    plans=[];risks=[];candidates=[]
    for name in cfg['profiles']:
        profile=definitions[name]
        delta=np.concatenate([deltas[tau][6*h:6*(h+1)] for h,tau in enumerate(profile)])
        frame=pd.DataFrame({'price_yuan_per_kwh':price,'load_kwh':np.maximum(load_hat+delta,0.),
                            'pv_forecast_kwh':pv_hat+np.maximum(-load_hat-delta,0.)})
        plan,status=solve_target_model(frame,physical)
        plan['grid_kwh']=np.maximum(plan['grid_kwh'],0.)
        plans.append(np.column_stack([plan[key] for key in PLAN_KEYS]));risks.append(delta)
        candidates.append({'profile':name,'tau_hours':profile,'terminal':cfg['terminal_energy_kwh'],
                           'terminal_energy_kwh':cfg['terminal_energy_kwh'],'solver':status})
    plans=np.asarray(plans)
    scores=simulate(plans[:,:,0],scenarios,price,energy,cfg['mu'])
    tail=empirical_cvar(scores['emergency_fee'],cfg['cvar_alpha'])
    feasible=guard_mask(scores['ordinary'],scores['emergency_fee'],scores['end_energy'],cfg['guard'],cfg['cvar_alpha'])
    assert feasible[0]
    selected=choose_index(np.where(feasible,scores['score'],np.inf))
    return {'plans':plans,'risk_delta':np.asarray(risks),'scenarios':scenarios,'source_dates':dates,
            'candidates':candidates,'selected':selected,'cvar':tail,'feasible':feasible,**scores}
