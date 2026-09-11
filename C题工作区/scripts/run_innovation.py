"""Sequential, predeclared innovation ablations; immutable baseline files are inputs."""
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from run_q3 import select_forecast,execute_interval,contract_fee,export_policy
from innovation_core import solve,quantile_fit_predict,risk_prefix,gate_threshold

WORK=Path(__file__).resolve().parents[1];OUT=WORK/'results/innovation'
for k in ['TMPDIR','TMP','TEMP']:os.environ[k]=str(WORK/'data/interim/innovation')
sys.dont_write_bytecode=True
POLICIES={'pv_raw':'pv','pv_bias':'pv','risk_none':'risk','risk_fixed':'risk','risk_g05':'risk','risk_g10':'risk',
    'gate_paid':'gate','gate_q50':'gate','gate_q75':'gate','gate_frozen':'gate','gate_info_frozen':'gate'}

def read(p):return pd.read_csv(p,float_precision='round_trip')
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def bill(f,price):
    delta=f.grid_effective_kwh-f.grid_original_kwh
    f['price_yuan_per_kwh']=price;f['original_cost_yuan']=price*f.grid_original_kwh
    f['increase_cost_yuan']=1.5*price*np.maximum(delta,0)
    f['decrease_adjustment_yuan']=-.5*price*np.maximum(-delta,0)
    f['contract_cost_yuan']=f.original_cost_yuan+f.increase_cost_yuan+f.decrease_adjustment_yuan
    f['emergency_cost_yuan']=5*price*f.emergency_kwh
    f['total_cost_yuan']=f.contract_cost_yuan+f.emergency_cost_yuan
    return f

def replay(q,actual,initial,original,price,ec,ed,target,terminal_penalty):
    energy=initial;emergency=0.
    for i,row in enumerate(actual.itertuples()):
        event=execute_interval(float(max(q[i],0)),row.load_actual_kwh,row.pv_actual_kwh,energy,ec,ed)
        energy=event['energy_end_actual_kwh'];emergency+=5*price[i]*event['emergency_kwh']
    contract=float(contract_fee(original,q,price,'A').sum());proxy=terminal_penalty*abs(energy-target)
    return {'cost_with_terminal_proxy_yuan':contract+emergency+proxy,'contract_cost_yuan':contract,
        'emergency_cost_yuan':float(emergency),'terminal_proxy_yuan':float(proxy),'terminal_energy_kwh':float(energy)}

class Inputs:
    def __init__(self):
        self.physical=json.loads((WORK/'configs/model_baseline.json').read_text())
        self.b=self.physical['battery'];self.ec=self.b['eta_charge'];self.ed=self.b['eta_discharge']
        self.price=read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy()
        self.penalty=float(self.price.mean()*self.ed)
        actual=read(WORK/'data/processed/actual_10min.csv')
        for c in ['interval_start','interval_end']:actual[c]=pd.to_datetime(actual[c])
        self.actual={d:f.reset_index(drop=True) for d,f in actual.groupby('date')}
        self.truth=actual.set_index('interval_start')
        self.q2=read(WORK/'results/q2/selected/ledger.csv')
        self.days={d:f.reset_index(drop=True) for d,f in self.q2.groupby('date')}
        forecast=read(WORK/'data/processed/pv_forecast_10min.csv')
        for c in ['issue_time','interval_start','interval_end']:forecast[c]=pd.to_datetime(forecast[c])
        self.issues={k:f for k,f in forecast.groupby('issue_time')};self.bias_cache={};self.risk_cache={}
        # Only the same-day portion used by Q3; future targets remain unavailable until completion.
        hist=forecast.loc[(forecast.interval_end<=forecast.issue_time.dt.normalize()+pd.Timedelta(days=1)) &
            forecast.interval_start.isin(self.truth.index) & (forecast.pv_forecast_kwh>0)].copy()
        hist['residual_kwh']=self.truth.loc[hist.interval_start].pv_actual_kwh.to_numpy()-hist.pv_forecast_kwh.to_numpy()
        hist['hour']=hist.issue_time.dt.hour;self.pv_hist=hist
        risks=[]
        for date,f in self.days.items():
            part=f.iloc[72:108];real=self.actual[date].iloc[72:108]
            residual=(real.load_actual_kwh-real.pv_actual_kwh).to_numpy()-(part.load_forecast_kwh-part.pv_forecast_kwh).to_numpy()
            risks.append({'date':date,'available_time':str(pd.Timestamp(date)+pd.Timedelta(days=1)),
                's_kwh':float(risk_prefix(residual)),'x1':float((part.load_forecast_kwh-part.pv_forecast_kwh).mean()/1000),
                'x2':float(part.pv_forecast_kwh.mean()/1000)})
        self.risks=pd.DataFrame(risks);self.risks.to_csv(OUT/'risk_targets.csv',index=False)
        self.feb_initial=json.loads((WORK/'results/q2/selection.json').read_text())['common_evaluation_initial_energy_kwh']
        self.april_initial={'risk':float(self.days['2025-04-01'].energy_start_actual_kwh.iloc[0])}
        q3=read(WORK/'results/q3/all_A/ledger.csv')
        for group in ['pv','gate']:self.april_initial[group]=float(q3.loc[q3.date=='2025-04-01'].energy_start_actual_kwh.iloc[0])
    def forecast(self,issue):return select_forecast(self.issues[issue],issue,issue.normalize()+pd.Timedelta(days=1))
    def corrected(self,issue):
        if issue not in self.bias_cache:
            f=self.forecast(issue);cut=issue.normalize();h=self.pv_hist
            h=h.loc[(h.hour==issue.hour)&(h.interval_end<=cut)&(h.interval_start>=cut-pd.Timedelta(days=28))]
            bias=float(h.residual_kwh.mean()) if len(h) else 0.
            raw=f.pv_forecast_kwh.to_numpy();pred=np.where(raw>0,np.maximum(0,raw+bias),0.)
            meta={'issue_time':str(issue),'training_cutoff':str(cut),'training_rows':len(h),
                'latest_target_end':str(h.interval_end.max()) if len(h) else None,'bias_kwh':bias,
                'clipped_intervals':int(((raw>0)&(raw+bias<0)).sum()),'active_positive_intervals':int((raw>0).sum())}
            self.bias_cache[issue]=(pred,meta)
        return self.bias_cache[issue]
    def risk(self,day):
        if day not in self.risk_cache:
            h=self.risks;avail=pd.to_datetime(h.available_time)
            h=h.loc[(avail<=day)&(pd.to_datetime(h.date)>=day-pd.Timedelta(days=56))]
            target=self.risks.loc[self.risks.date==str(day.date())].iloc[0]
            x=[1.,target.x1,target.x2]
            if len(h)<20:
                pred=None;meta={'fallback':'fixed_2400','training_rows':len(h)}
            else:
                X=np.column_stack([np.ones(len(h)),h.x1,h.x2]);prediction,meta=quantile_fit_predict(X,h.s_kwh.to_numpy()/1000,np.array(x),alpha=.75)
                pred=float(prediction*1000)
            meta.update(issue_time=str(day),training_dates=h.date.tolist(),latest_available_time=str(pd.to_datetime(h.available_time).max()) if len(h) else None,
                features=x,predicted_s_kwh=pred,realized_s_kwh=float(target.s_kwh))
            self.risk_cache[day]=(pred,meta)
        return self.risk_cache[day]

def run_policy(data,policy,start,end,phase,history):
    group=POLICIES[policy];energy=data.feb_initial if phase=='calibration' else data.april_initial[group]
    all_rows=[];all_plans=[];statuses=[];decisions=[];candidate_rows=[]
    for day in pd.date_range(start,end):
        date=str(day.date());truth=data.actual[date];base=data.days[date];load=base.load_forecast_kwh.to_numpy()
        initial=energy;original=None;current=None;events=[];day_history=[]
        hours=[0] if group=='risk' or policy=='gate_frozen' else [0,6,12,18]
        for slot in range(144):
            if slot in [h*6 for h in hours]:
                issue=day+pd.Timedelta(minutes=slot*10);hour=slot//6
                if group=='risk':
                    pv=base.pv_forecast_kwh.to_numpy();raw=pv.copy();metadata={'pv_source':'Q2_selected'}
                else:
                    f=data.forecast(issue);raw=f.pv_forecast_kwh.to_numpy();pv=raw.copy();metadata={'pv_source':'raw_appendix3'}
                    if policy=='pv_bias':pv,bias=data.corrected(issue);metadata={'pv_source':'bias_corrected_appendix3','bias':bias}
                reserve=None
                if group=='risk' and policy!='risk_none':
                    amount=2400.;risk_meta=None
                    if policy.startswith('risk_g'):
                        prediction,risk_meta=data.risk(day)
                        if prediction is not None:amount=min(9600.,(.5 if policy=='risk_g05' else 1.)*prediction/data.ed)
                    reserve={'index':72,'amount_kwh':float(amount),'penalty_yuan_per_kwh':data.penalty}
                    metadata.update(reserve=reserve,risk_model=risk_meta)
                soft=group=='gate';kwargs={'soft_terminal':soft}
                if soft:kwargs['terminal_penalty']=data.penalty
                accepted=True;decision=None
                if policy in ['gate_frozen','gate_info_frozen'] and slot>0:
                    # Information without control has no effect under the unchanged greedy executor.
                    plan,status=solve(load[slot:],pv,data.price[slot:],energy,initial,data.physical,original=original[slot:],fixed_grid=current[slot:],**kwargs)
                    accepted=False
                else:
                    plan,status=solve(load[slot:],pv,data.price[slot:],energy,initial,data.physical,original=None if slot==0 else original[slot:],reserve=reserve,**kwargs)
                if soft and slot>0 and policy not in ['gate_frozen','gate_info_frozen']:
                    hold,hold_status=solve(load[slot:],pv,data.price[slot:],energy,initial,data.physical,original=original[slot:],fixed_grid=current[slot:],**kwargs)
                    vhat=float(hold_status['objective_yuan']-status['objective_yuan'])
                    assert vhat>=-1e-5,'Free update must contain hold feasible set'
                    alpha=.5 if policy=='gate_q50' else .75
                    tau,threshold=gate_threshold(history,issue,hour,alpha=alpha,window_days=56,min_samples=20)
                    enabled=policy!='gate_paid' and threshold['active']
                    accepted=not enabled or vhat>tau+1e-7
                    for label,choice,st in [('hold',hold,hold_status),('update',plan,status)]:
                        frame=pd.DataFrame({'date':date,'issue_hour':hour,'alternative':label,'slot_id':np.arange(slot+1,145),
                            'load_forecast_kwh':load[slot:],'pv_forecast_kwh':pv,'price_yuan_per_kwh':data.price[slot:],
                            'grid_original_kwh':original[slot:]})
                        for key,value in choice.items():frame[key]=value
                        candidate_rows.append(frame)
                    hold_actual=replay(hold['grid_kwh'],truth.iloc[slot:],energy,original[slot:],data.price[slot:],data.ec,data.ed,initial,data.penalty)
                    update_actual=replay(plan['grid_kwh'],truth.iloc[slot:],energy,original[slot:],data.price[slot:],data.ec,data.ed,initial,data.penalty)
                    vreplay=hold_actual['cost_with_terminal_proxy_yuan']-update_actual['cost_with_terminal_proxy_yuan']
                    decision={'date':date,'issue_time':str(issue),'issue_hour':hour,'available_time':str(day+pd.Timedelta(days=1)),
                        'initial_energy_kwh':float(energy),'terminal_target_kwh':float(initial),'vhat_yuan':vhat,'vreplay_yuan':float(vreplay),
                        'zeta_yuan':float(vhat-vreplay),'tau_yuan':float(tau),'threshold_enabled':bool(enabled),'accepted':bool(accepted),
                        'threshold_model':threshold,'hold_solver':hold_status,'update_solver':status,
                        'hold_replay':hold_actual,'update_replay':update_actual,
                        'proposed_change_kwh':float(np.abs(plan['grid_kwh']-current[slot:]).sum())}
                    decisions.append(decision);day_history.append(decision)
                    if not accepted:plan,status=hold,hold_status
                if slot==0:
                    original=np.maximum(0.,plan['grid_kwh']);current=original.copy()
                else:current[slot:]=np.maximum(0.,plan['grid_kwh'])
                version=pd.DataFrame({'date':date,'issue_hour':hour,'issue_time':str(issue),'slot_id':np.arange(slot+1,145),
                    'interval_start':truth.interval_start.iloc[slot:].to_numpy(),'interval_end':truth.interval_end.iloc[slot:].to_numpy(),
                    'load_forecast_kwh':load[slot:],'pv_forecast_kwh':pv,'pv_raw_forecast_kwh':raw,
                    'grid_original_kwh':original[slot:],'accepted':accepted})
                for key,value in plan.items():version[key]=value
                all_plans.append(version)
                statuses.append({'date':date,'issue_hour':hour,'issue_time':str(issue),'initial_energy_kwh':float(energy),
                    'terminal_target_kwh':float(initial),'metadata':metadata,'solver':status})
                active_slot=slot;active_hour=hour;active_pv=pv
            row=truth.iloc[slot];q=max(0.,float(current[slot]))
            event=execute_interval(q,row.load_actual_kwh,row.pv_actual_kwh,energy,data.ec,data.ed);energy=event['energy_end_actual_kwh']
            # gate_frozen still uses the last accepted forecast only for reporting; execution sees actuals.
            event.update(date=date,slot_id=slot+1,interval_start=str(row.interval_start),interval_end=str(row.interval_end),
                active_issue_hour=active_hour,load_actual_kwh=row.load_actual_kwh,pv_actual_kwh=row.pv_actual_kwh,
                load_forecast_kwh=float(load[slot]),pv_forecast_kwh=float(active_pv[slot-active_slot]),
                grid_original_kwh=float(original[slot]),grid_effective_kwh=q)
            events.append(event)
        # Paired future truth was used only for diagnostics; it becomes eligible now, after the day.
        history.extend(day_history)
        all_rows.append(bill(pd.DataFrame(events),data.price))
        if day.day==1:print(phase,policy,date,'SOC',round(energy,2),flush=True)
    folder=OUT/phase/policy
    total=export_policy(folder,pd.concat(all_rows,ignore_index=True),pd.concat(all_plans,ignore_index=True),statuses,'A')
    write(folder/'decisions.json',decisions)
    if candidate_rows:pd.concat(candidate_rows,ignore_index=True).to_csv(folder/'candidate_versions.csv',index=False)
    total['policy']=policy;total['group']=group;total['inventory_adjusted_cost_yuan']=total['total_cost_yuan']-data.penalty*(energy-total['initial_energy_kwh'])
    total['gate_decisions']=len(decisions);total['accepted_updates']=sum(d['accepted'] for d in decisions)
    total['accepted_change_kwh']=sum(d['proposed_change_kwh'] for d in decisions if d['accepted'])
    write(folder/'innovation_summary.json',total)
    print(phase,policy,'cost',round(total['total_cost_yuan'],2),flush=True)
    return total

def main():
    if (OUT/'run_status.json').exists():raise FileExistsError('Use a new version; preserve completed innovation results')
    paths=['configs/model_baseline.json','scripts/run_innovation.py','scripts/innovation_core.py','scripts/run_q3.py','scripts/run_q2.py','scripts/solve_q1.py',
        'data/processed/actual_10min.csv','data/processed/fixed_price.csv','data/processed/pv_forecast_10min.csv',
        'results/q2/selected/ledger.csv','results/q2/selection.json','results/q3/all_A/ledger.csv','reports/innovation/execution_plan.md']
    hashes={p:sha(WORK/p) for p in paths};write(OUT/'input_code_hashes.json',hashes)
    data=Inputs();write(OUT/'config_snapshot.json',{'policies':POLICIES,'calibration_start':'2025-02-01','selection_start':'2025-03-01','selection_end':'2025-03-31',
        'evaluation_start':'2025-04-01','evaluation_end':'2025-12-31','feb_initial':data.feb_initial,'april_initial':data.april_initial,
        'proxy_penalty_yuan_per_kwh':data.penalty,'risk_alpha':.75,'fixed_reserve_kwh':2400.,'risk_window':[72,108],
        'retrospective':True,'formal_submission':False})
    histories={p:[] for p in POLICIES};cal=[];evaluation=[]
    for policy in POLICIES:cal.append(run_policy(data,policy,'2025-02-01','2025-03-31','calibration',histories[policy]))
    scores=[]
    for policy,group in POLICIES.items():
        d=read(OUT/'calibration'/policy/'daily.csv');score=float(d.loc[d.date>='2025-03-01','total_cost_yuan'].sum())
        scores.append({'policy':policy,'group':group,'march_cost_yuan':score})
    scores=pd.DataFrame(scores);scores.to_csv(OUT/'calibration_scores.csv',index=False)
    eligible={'pv':['pv_raw','pv_bias'],'risk':['risk_none','risk_fixed','risk_g05','risk_g10'],'gate':['gate_paid','gate_q50','gate_q75']}
    selected={g:min(names,key=lambda p:(float(scores.set_index('policy').loc[p,'march_cost_yuan']),names.index(p))) for g,names in eligible.items()}
    selection={'selected':selected,'eligible':eligible,'available_time':'2025-04-01 00:00:00','criterion':'Minimum March actual bill; ordered simpler candidate breaks exact ties',
        'scores_sha256':sha(OUT/'calibration_scores.csv'),'selected_before_evaluation':True}
    write(OUT/'selection.json',selection);selection_hash=sha(OUT/'selection.json')
    for policy in POLICIES:evaluation.append(run_policy(data,policy,'2025-04-01','2025-12-31','evaluation',histories[policy]))
    pd.DataFrame(cal).to_csv(OUT/'calibration_comparison.csv',index=False);pd.DataFrame(evaluation).to_csv(OUT/'comparison.csv',index=False)
    write(OUT/'pv_bias_models.json',[v[1] for _,v in sorted(data.bias_cache.items())]);write(OUT/'risk_models.json',[v[1] for _,v in sorted(data.risk_cache.items())])
    assert hashes=={p:sha(WORK/p) for p in paths};assert sha(OUT/'selection.json')==selection_hash
    write(OUT/'run_status.json',{'completed':True,'inputs_unchanged':True,'selection_unchanged':True,'policies':list(POLICIES),'evaluation_days':275,'formal_excel_exported':False})
    print(pd.DataFrame(evaluation)[['policy','total_cost_yuan','emergency_kwh','accepted_updates']].to_string(index=False),flush=True)

if __name__=='__main__':main()
