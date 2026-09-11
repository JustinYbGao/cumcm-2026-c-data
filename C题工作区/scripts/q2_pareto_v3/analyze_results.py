"""Report all declared paths, both bill components and explicit emergency caps."""
import json
import math
from policy import WORK,ROOT,np,pd,save_json


def read(path):return pd.read_csv(path,float_precision='round_trip',dtype={'selected_terminal':str})


def main():
    cfg=json.loads((WORK/'configs/q2_pareto_v3/experiments.json').read_text())
    refs=['B0','B1','P','P_terminal','P_floor','S_terminal'];names=refs+[x['policy'] for x in cfg['runs']]
    summaries=[];daily=[];monthly=[];hourly=[];selection=[];gate=[]
    for name in names:
        folder=ROOT/('references' if name in refs else 'runs')/name
        f=read(folder/'ledger.csv');s=json.loads((folder/'summary.json').read_text())
        s.update(policy=name,unused_grid_cost_yuan=float((f.price_yuan_per_kwh*f.unused_grid_kwh).sum()),
                 emergency_days=int(f.loc[f.emergency_kwh>1e-6,'date'].nunique()),
                 emergency_intervals=int((f.emergency_kwh>1e-6).sum()),
                 emergency_share_load=float(f.emergency_kwh.sum()/f.load_actual_kwh.sum()),
                 passes_emergency_cap=bool(s['emergency_cost_yuan']<=cfg['emergency_cap_yuan']+1e-5),
                 passes_stricter_P_emergency_cap=bool(s['emergency_cost_yuan']<=cfg['secondary_emergency_cap_yuan']+1e-5))
        s['passes_joint']=bool(s['passes_emergency_cap'] and s['total_cost_yuan']<cfg['total_cap_yuan']-1e-5 and s['planned_cost_yuan']<cfg['ordinary_cap_yuan']-1e-5)
        s['passes_stricter_joint']=bool(s['passes_joint'] and s['passes_stricter_P_emergency_cap'])
        summaries.append(s)
        columns=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh','unused_grid_kwh']
        for out,key,values in [(daily,'date',f.date),(monthly,'month',f.date.str[:7]),(hourly,'hour',(f.slot_id-1)//6)]:
            g=f.assign(**{key:values}).groupby(key)[columns].sum().reset_index();g['policy']=name;out.append(g)
        if name not in refs:
            m=json.loads((folder/'decisions.json').read_text())['days'];e=np.load(folder/'decision_evidence.npz')
            for i,d in enumerate(m):
                k=d['selected_index'];n=d['scenario_count'];candidate=d['candidates'][k]
                selection.append({'policy':name,'date':d['date'],'profile':candidate['profile'],'scenario_count':n,'selected_index':k})
                gate.append({'policy':name,'date':d['date'],'selected_profile':candidate['profile'],'feasible_candidates':int(e['feasible'][i].sum()),
                             'expected_emergency_yuan':float(e['emergency_fee'][i,k,:n].mean()),'expected_cvar_yuan':float(e['cvar'][i,k]),
                             'actual_emergency_yuan':float(f.loc[f.date==d['date'],'emergency_cost_yuan'].sum())})
        if name in ['P_floor','S_terminal','T_rebalance','R_guard','R_mean','R_cost','R_w28']:
            r=f.loc[f.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
            target=ROOT/'representative'/name;target.mkdir(parents=True,exist_ok=True)
            r.to_csv(target/'four_days_ledger.csv',index=False)
            r.loc[r.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_plan_kwh','planned_cost_yuan']].to_csv(target/'table1_intervals.csv',index=False)
            r.groupby('date')[['grid_plan_kwh','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']].sum().to_csv(target/'table1_daily.csv')
            r.groupby('date').agg(initial_energy_kwh=('energy_start_actual_kwh','first'),final_energy_kwh=('energy_end_actual_kwh','last')).to_csv(target/'terminal.csv')
            r.assign(block_start_hour=((r.slot_id-1)//24)*4).groupby(['date','block_start_hour'])[['charge_actual_kwh','discharge_actual_kwh']].sum().to_csv(target/'table2_charge_discharge.csv')
            r.loc[r.emergency_kwh>1e-6,['date','interval_start','interval_end','emergency_kwh','emergency_cost_yuan']].to_csv(target/'table3_emergency.csv',index=False)
    table=pd.DataFrame(summaries).set_index('policy')
    for baseline in refs:
        for field,label in [('total_cost_yuan','total'),('planned_cost_yuan','ordinary'),('emergency_cost_yuan','emergency'),('inventory_adjusted_cost_yuan','inventory_adjusted')]:
            table[f'{label}_saving_vs_{baseline}_yuan']=table.loc[baseline,field]-table[field]
    table.to_csv(ROOT/'comparison_all.csv')
    day=pd.concat(daily,ignore_index=True);day.to_csv(ROOT/'daily.csv',index=False)
    month=pd.concat(monthly,ignore_index=True);month.to_csv(ROOT/'monthly.csv',index=False)
    pd.concat(hourly,ignore_index=True).to_csv(ROOT/'hourly.csv',index=False)
    selections=pd.DataFrame(selection);selections.to_csv(ROOT/'daily_selections.csv',index=False)
    selections.groupby(['policy','profile']).size().rename('days').reset_index().to_csv(ROOT/'selection_counts.csv',index=False)
    pd.DataFrame(gate).to_csv(ROOT/'daily_guard_diagnostics.csv',index=False)
    paired=[];counts=[];boot=[];rng=np.random.default_rng(cfg['bootstrap_seed'])
    for name in names[len(refs):]:
        for baseline in ['P_floor','B0','B1','P','P_terminal','S_terminal']:
            a=day.loc[day.policy==baseline].set_index('date');b=day.loc[day.policy==name].set_index('date')
            fields=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan'];diff=a[fields]-b[fields]
            z=diff.rename(columns={c:c.replace('cost','saving') for c in fields}).reset_index();z['policy']=name;z['baseline']=baseline;paired.append(z)
            d=diff.total_cost_yuan;em=diff.emergency_cost_yuan
            counts.append({'policy':name,'baseline':baseline,'total_winning_days':int((d>1e-5).sum()),'total_losing_days':int((d< -1e-5).sum()),
                           'emergency_worse_days':int((em< -1e-5).sum()),'positive_total_months':int((d.groupby(d.index.str[:7]).sum()>1e-5).sum()),
                           'emergency_worse_months':int((em.groupby(em.index.str[:7]).sum()< -1e-5).sum())})
            if baseline!='P_floor':continue
            for block in cfg['bootstrap_blocks']:
                x=diff.to_numpy();n=len(x);starts=rng.integers(0,n,(cfg['bootstrap_replicates'],math.ceil(n/block)))
                ix=((starts[:,:,None]+np.arange(block))%n).reshape(len(starts),-1)[:,:n]
                samples=x[ix].sum(axis=1);low,high=np.quantile(samples,[.025,.975],axis=0)
                for j,field in enumerate(fields):
                    boot.append({'policy':name,'baseline':baseline,'block_days':block,'component':field,'saving_yuan':float(x[:,j].sum()),
                                 'ci95_low_yuan':float(low[j]),'ci95_high_yuan':float(high[j]),
                                 'joint_nonworse_resample_fraction':float(((samples[:,0]>0)&(samples[:,1]>=0)&(samples[:,2]>0)).mean()),
                                 'seed':cfg['bootstrap_seed'],'replicates':len(starts),'scope':'Descriptive fixed-path single-year blocks; not future joint-pass probability.'})
    pd.concat(paired,ignore_index=True).to_csv(ROOT/'paired_daily.csv',index=False)
    pd.DataFrame(counts).to_csv(ROOT/'win_loss_counts.csv',index=False);pd.DataFrame(boot).to_csv(ROOT/'block_bootstrap.csv',index=False)
    c=table.total_cost_yuan;e=table.emergency_cost_yuan
    save_json(ROOT/'ablation.json',{'total_cost':{'P_floor':c.P_floor,'day_trim':c.T_day_trim,'evening_hedge':c.T_evening_hedge,'rebalance':c.T_rebalance,
        'R_guard':c.R_guard,'R_mean':c.R_mean,'R_cost':c.R_cost,'R_w28':c.R_w28},
        'emergency_cost':{'P_floor':e.P_floor,'day_trim':e.T_day_trim,'evening_hedge':e.T_evening_hedge,'rebalance':e.T_rebalance,
        'R_guard':e.R_guard,'R_mean':e.R_mean,'R_cost':e.R_cost,'R_w28':e.R_w28},
        'scope':'Continuous independent trajectories include state feedback; library contrasts do not prove separable causal contributions.'})
    save_json(ROOT/'acceptance.json',{'primary':'R_guard','primary_passed':bool(table.loc['R_guard','passes_joint']),
        'caps':{k:v for k,v in cfg.items() if 'cap_yuan' in k},
        'new_joint_passes':table.loc[names[len(refs):]].index[table.loc[names[len(refs):],'passes_joint']].tolist(),
        'new_stricter_joint_passes':table.loc[names[len(refs):]].index[table.loc[names[len(refs):],'passes_stricter_joint']].tolist(),
        'scope':'Observed 334-day joint criterion; all candidates and failures retained, no future guarantee.'})
    print(table[['total_cost_yuan','planned_cost_yuan','emergency_cost_yuan','passes_joint','passes_stricter_joint']].to_string())


if __name__=='__main__':main()
