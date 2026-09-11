"""Append the user-authorized cap analysis without changing original acceptance."""
import json
import math
from policy import WORK,ROOT,np,pd,save_json
from analyze_results import read


def main():
    cfg=json.loads((WORK/'configs/q2_pareto_v3/extension.json').read_text())
    old=json.loads((WORK/'configs/q2_pareto_v3/experiments.json').read_text())
    out=ROOT/'analysis_user_cap';out.mkdir(exist_ok=True)
    refs=['B0','B1','P','P_terminal','P_floor','S_terminal']
    table=read(ROOT/'comparison_all.csv').set_index('policy')
    daily=[read(ROOT/'daily.csv')];monthly=[read(ROOT/'monthly.csv')];hourly=[read(ROOT/'hourly.csv')]
    paired=[read(ROOT/'paired_daily.csv')];counts=[read(ROOT/'win_loss_counts.csv')];boot=[read(ROOT/'block_bootstrap.csv')]
    selections=[read(ROOT/'selection_counts.csv')];rng=np.random.default_rng(cfg['bootstrap_seed'])
    fees=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan'];sums=fees+['emergency_kwh','unused_grid_kwh']
    for config in cfg['runs']:
        name=config['policy'];folder=ROOT/'extension_runs'/name
        f=read(folder/'ledger.csv');s=json.loads((folder/'summary.json').read_text())
        s.update(unused_grid_cost_yuan=float((f.price_yuan_per_kwh*f.unused_grid_kwh).sum()),
                 emergency_days=int(f.loc[f.emergency_kwh>1e-6,'date'].nunique()),
                 emergency_intervals=int((f.emergency_kwh>1e-6).sum()),
                 emergency_share_load=float(f.emergency_kwh.sum()/f.load_actual_kwh.sum()),
                 passes_emergency_cap=bool(s['emergency_cost_yuan']<=old['emergency_cap_yuan']+1e-5),
                 passes_stricter_P_emergency_cap=bool(s['emergency_cost_yuan']<=old['secondary_emergency_cap_yuan']+1e-5))
        s['passes_joint']=bool(s['passes_emergency_cap'] and s['total_cost_yuan']<old['total_cap_yuan']-1e-5 and s['planned_cost_yuan']<old['ordinary_cap_yuan']-1e-5)
        s['passes_stricter_joint']=bool(s['passes_joint'] and s['passes_stricter_P_emergency_cap'])
        for baseline in refs:
            for field,label in [('total_cost_yuan','total'),('planned_cost_yuan','ordinary'),('emergency_cost_yuan','emergency'),('inventory_adjusted_cost_yuan','inventory_adjusted')]:
                s[f'{label}_saving_vs_{baseline}_yuan']=float(table.loc[baseline,field]-s[field])
        table.loc[name]=pd.Series(s)
        d=f.groupby('date')[sums].sum();m=f.assign(month=f.date.str[:7]).groupby('month')[sums].sum()
        daily.append(d.reset_index().assign(policy=name));monthly.append(m.reset_index().assign(policy=name))
        hourly.append(f.assign(hour=(f.slot_id-1)//6).groupby('hour')[sums].sum().reset_index().assign(policy=name))
        selections.append(pd.DataFrame([dict(policy=name,profile=name,days=len(d))]))
        for baseline in ['P_floor','B0','B1','P','P_terminal','S_terminal']:
            a=daily[0].loc[daily[0].policy==baseline].set_index('date');diff=a[fees]-d[fees]
            paired.append(diff.rename(columns={c:c.replace('cost','saving') for c in fees}).reset_index().assign(policy=name,baseline=baseline))
            t=diff.total_cost_yuan;e=diff.emergency_cost_yuan
            counts.append(pd.DataFrame([dict(policy=name,baseline=baseline,total_winning_days=int((t>1e-5).sum()),total_losing_days=int((t< -1e-5).sum()),emergency_worse_days=int((e< -1e-5).sum()),positive_total_months=int((t.groupby(t.index.str[:7]).sum()>1e-5).sum()),emergency_worse_months=int((e.groupby(e.index.str[:7]).sum()< -1e-5).sum()))]))
            if baseline!='P_floor':continue
            for block in cfg['bootstrap_blocks']:
                x=diff.to_numpy();n=len(x);starts=rng.integers(0,n,(cfg['bootstrap_replicates'],math.ceil(n/block)))
                ix=((starts[:,:,None]+np.arange(block))%n).reshape(len(starts),-1)[:,:n]
                samples=x[ix].sum(axis=1);low,high=np.quantile(samples,[.025,.975],axis=0)
                for j,field in enumerate(fees):
                    boot.append(pd.DataFrame([dict(policy=name,baseline=baseline,block_days=block,component=field,saving_yuan=float(x[:,j].sum()),ci95_low_yuan=float(low[j]),ci95_high_yuan=float(high[j]),joint_nonworse_resample_fraction=float(((samples[:,0]>0)&(samples[:,1]>=0)&(samples[:,2]>0)).mean()),seed=cfg['bootstrap_seed'],replicates=len(starts),scope='Descriptive fixed-path single-year blocks; not future joint-pass probability.')]))
        r=f.loc[f.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
        target=out/'representative'/name;target.mkdir(parents=True,exist_ok=True)
        r.to_csv(target/'four_days_ledger.csv',index=False)
        r.loc[r.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_plan_kwh','planned_cost_yuan']].to_csv(target/'table1_intervals.csv',index=False)
        r.groupby('date')[['grid_plan_kwh']+fees].sum().to_csv(target/'table1_daily.csv')
        r.groupby('date').agg(initial_energy_kwh=('energy_start_actual_kwh','first'),final_energy_kwh=('energy_end_actual_kwh','last')).to_csv(target/'terminal.csv')
        r.assign(block_start_hour=((r.slot_id-1)//24)*4).groupby(['date','block_start_hour'])[['charge_actual_kwh','discharge_actual_kwh']].sum().to_csv(target/'table2_charge_discharge.csv')
        r.loc[r.emergency_kwh>1e-6,['date','interval_start','interval_end','emergency_kwh','emergency_cost_yuan']].to_csv(target/'table3_emergency.csv',index=False)
    table['meets_user_emergency_cap']=table.emergency_cost_yuan<=cfg['user_emergency_cap_yuan']+1e-5
    table['passes_user_requirement']=table.meets_user_emergency_cap & (table.total_cost_yuan<old['total_cap_yuan']-1e-5)
    table['study_stage']=['reference' if n in refs else ('original_ten' if n in [r['policy'] for r in old['runs']] else 'extension_eight') for n in table.index]
    table.to_csv(out/'comparison_all.csv')
    for name,frames in [('daily',daily),('monthly',monthly),('hourly',hourly),('paired_daily',paired),('win_loss_counts',counts),('block_bootstrap',boot),('selection_counts',selections)]:
        pd.concat(frames,ignore_index=True).to_csv(out/(name+'.csv'),index=False)
    eligible=table.loc[table.meets_user_emergency_cap].sort_values('total_cost_yuan',kind='stable')
    eligible.to_csv(out/'eligible_ranking.csv')
    best=eligible.index[0]
    save_json(out/'acceptance_user_cap.json',dict(emergency_cap_yuan=cfg['user_emergency_cap_yuan'],ordinary_cost_is_hard_constraint=False,
        total_reference_yuan=old['total_cap_yuan'],best_observed_policy=best,best_total_cost_yuan=float(table.loc[best,'total_cost_yuan']),best_emergency_cost_yuan=float(table.loc[best,'emergency_cost_yuan']),
        passed_new_policies=table.loc[(table.study_stage!='reference')&table.passes_user_requirement].index.tolist(),
        failed_new_policies=table.loc[(table.study_stage!='reference')&~table.passes_user_requirement].index.tolist(),
        interpretation='Observed historical minimum among 24 reported paths; user cap changed before eight extension runs; no future cap guarantee or global optimality claim.'))
    print(table[['total_cost_yuan','planned_cost_yuan','emergency_cost_yuan','passes_user_requirement','passes_joint']].to_string())


if __name__=='__main__':main()
