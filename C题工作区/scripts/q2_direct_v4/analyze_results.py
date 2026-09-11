"""Complete fixed-grid comparison; cap and primary choice were frozen before runs."""
import argparse
import json
import math
from policy import WORK,ROOT,np,pd,save_json

REFS=['B0','B1','P_floor','X_strong_morning85']
FIELDS=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    out=ROOT/'analysis_all' if args.all else ROOT
    out.mkdir(exist_ok=True)
    cfg=json.loads((WORK/'configs/q2_direct_v4/experiments.json').read_text())
    if args.all:cfg['runs']+=json.loads((WORK/'configs/q2_direct_v4/refinement.json').read_text())['runs']
    names=REFS+[r['policy'] for r in cfg['runs']]
    rows=[];daily=[];monthly=[];hourly=[];opts=[]
    for name in names:
        folder=ROOT/('references' if name in REFS else 'runs')/name
        f=pd.read_csv(folder/'ledger.csv',float_precision='round_trip');s=json.loads((folder/'summary.json').read_text())
        s.update(policy=name,stage='reference' if name in REFS else 'direct',
            unused_grid_cost_yuan=float((f.price_yuan_per_kwh*f.unused_grid_kwh).sum()),
            emergency_share_load=float(f.emergency_kwh.sum()/f.load_actual_kwh.sum()),
            emergency_days=int(f.loc[f.emergency_kwh>1e-6,'date'].nunique()),
            emergency_intervals=int((f.emergency_kwh>1e-6).sum()),
            emergency_at_soc_floor_share=float(f.loc[f.energy_end_actual_kwh<=1200+1e-6,'emergency_cost_yuan'].sum()/f.emergency_cost_yuan.sum()),
            final_energy_kwh=float(f.energy_end_actual_kwh.iloc[-1]),
            passes_emergency_cap=bool(f.emergency_cost_yuan.sum()<=cfg['emergency_cap_yuan']))
        s['inventory_adjusted_cost_yuan']=s['total_cost_yuan']-.6895775*(s['final_energy_kwh']-7268.4231640740745)
        s['passes_improvement']=bool(s['passes_emergency_cap'] and s['total_cost_yuan']<cfg['reference_total_yuan']-1e-5)
        rows.append(s)
        for collection,key,value in [(daily,'date',f.date),(monthly,'month',f.date.str[:7]),(hourly,'hour',(f.slot_id-1)//6)]:
            g=f.assign(**{key:value}).groupby(key)[FIELDS+['emergency_kwh','grid_plan_kwh','unused_grid_kwh']].sum().reset_index()
            g['policy']=name;collection.append(g)
        if name not in REFS:
            m=json.loads((folder/'decisions.json').read_text())['days'];e=np.load(folder/'decision_evidence.npz')
            for i,d in enumerate(m):
                for j,o in enumerate(d['optimizer']):
                    opts.append(dict(policy=name,date=d['date'],start=j,success=o['success'],status=o['status'],message=o['message'],
                        nit=o['nit'],nfev=o['nfev'],initial_score_yuan=float(e['score'][i,3*j]),
                        incumbent_score_yuan=float(e['score'][i,3*j+1]),final_score_yuan=float(e['score'][i,3*j+2]),
                        selected_index=d['selected_index']))
    table=pd.DataFrame(rows).set_index('policy')
    for baseline in REFS:
        for field,label in zip(FIELDS+['inventory_adjusted_cost_yuan'],['ordinary','emergency','total','inventory_adjusted']):
            table[f'{label}_saving_vs_{baseline}_yuan']=table.loc[baseline,field]-table[field]
    table.to_csv(out/'comparison_all.csv')
    day=pd.concat(daily,ignore_index=True);day.to_csv(out/'daily.csv',index=False)
    month=pd.concat(monthly,ignore_index=True);month.to_csv(out/'monthly.csv',index=False)
    pd.concat(hourly,ignore_index=True).to_csv(out/'hourly.csv',index=False)
    pd.DataFrame(opts).to_csv(out/'optimizer_summary.csv',index=False)
    paired=[];counts=[];boot=[];rng=np.random.default_rng(cfg['bootstrap_seed'])
    for name in names[len(REFS):]:
        for baseline in REFS:
            a=day.loc[day.policy==baseline].set_index('date');b=day.loc[day.policy==name].set_index('date')
            diff=a[FIELDS]-b[FIELDS]; z=diff.reset_index();z['policy']=name;z['baseline']=baseline;paired.append(z)
            d=diff.total_cost_yuan;em=diff.emergency_cost_yuan
            counts.append(dict(policy=name,baseline=baseline,total_winning_days=int((d>1e-5).sum()),
                total_losing_days=int((d< -1e-5).sum()),emergency_worse_days=int((em< -1e-5).sum()),
                positive_total_months=int((d.groupby(d.index.str[:7]).sum()>1e-5).sum()),
                emergency_worse_months=int((em.groupby(em.index.str[:7]).sum()< -1e-5).sum())))
            if baseline!='X_strong_morning85':continue
            for block in cfg['bootstrap_blocks']:
                x=diff.to_numpy();n=len(x);starts=rng.integers(0,n,(cfg['bootstrap_replicates'],math.ceil(n/block)))
                ix=((starts[:,:,None]+np.arange(block))%n).reshape(len(starts),-1)[:,:n]
                samples=x[ix].sum(axis=1);low,high=np.quantile(samples,[.025,.975],axis=0)
                for j,field in enumerate(FIELDS):
                    boot.append(dict(policy=name,baseline=baseline,block_days=block,component=field,saving_yuan=float(x[:,j].sum()),
                        ci95_low_yuan=float(low[j]),ci95_high_yuan=float(high[j]),seed=cfg['bootstrap_seed'],replicates=len(starts),
                        scope='Fixed observed paths; descriptive dependence-aware resampling, not post-selection or future guarantee.'))
    pd.concat(paired,ignore_index=True).to_csv(out/'paired_daily.csv',index=False)
    pd.DataFrame(counts).to_csv(out/'win_loss_counts.csv',index=False);pd.DataFrame(boot).to_csv(out/'block_bootstrap.csv',index=False)
    feasible=table.loc[table.passes_emergency_cap];best=feasible.total_cost_yuan.idxmin()
    save_json(out/'acceptance.json',dict(primary='D56',primary_passed=bool(table.loc['D56','passes_improvement']),
        best_observed_policy=best,best_total_yuan=float(table.loc[best,'total_cost_yuan']),
        best_emergency_yuan=float(table.loc[best,'emergency_cost_yuan']),emergency_cap_yuan=cfg['emergency_cap_yuan'],
        new_passes=table.loc[(table.stage=='direct')&table.passes_improvement].index.tolist(),
        oracle_lower_bound_yuan=12227565.30317241,
        best_gap_to_prescient_bound_yuan=float(table.loc[best,'total_cost_yuan']-12227565.30317241),
        scope='Historical selection from first-stage policies and references; with --all, includes two outcome-informed solver-budget refinements. Year already observed.'))
    print(table[FIELDS+['passes_emergency_cap','passes_improvement']].to_string())


if __name__=='__main__':main()
