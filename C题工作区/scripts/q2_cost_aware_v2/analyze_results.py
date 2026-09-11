"""Report all preregistered paths, selection behavior and dependent-day uncertainty."""
import json
import math
from policy import WORK, ROOT, np, pd, save_json, simulate


def read(path): return pd.read_csv(path, float_precision='round_trip', dtype={'selected_terminal':str})


def main():
    config=json.loads((WORK/'configs/q2_cost_aware_v2/experiments.json').read_text())
    extension=json.loads((WORK/'configs/q2_cost_aware_v2/extension.json').read_text())
    names=['B0','B1','P','P_terminal']+[c['policy'] for c in config['runs']+extension['runs']]
    summaries=[];frames={};daily={};months=[];hours=[];selection=[];score_diagnostics=[]
    for name in names:
        folder=ROOT/('references' if name in names[:4] else 'runs')/name
        f=read(folder/'ledger.csv'); frames[name]=f
        s=json.loads((folder/'summary.json').read_text());price=f.price_yuan_per_kwh
        s.update(policy=name,emergency_fee_share=s['emergency_cost_yuan']/s['total_cost_yuan'],
                 unused_grid_cost_yuan=float((price*f.unused_grid_kwh).sum()),
                 emergency_premium_yuan=float((4*price*f.emergency_kwh).sum()),
                 emergency_intervals=int((f.emergency_kwh>1e-6).sum()),
                 emergency_days=int(f.loc[f.emergency_kwh>1e-6,'date'].nunique()),
                 emergency_share_of_load=float(f.emergency_kwh.sum()/f.load_actual_kwh.sum()),
                 days_starting_full=int((f.loc[f.slot_id==1,'energy_start_actual_kwh']>=10800-1e-6).sum()),
                 mean_initial_soc_kwh=float(f.loc[f.slot_id==1,'energy_start_actual_kwh'].mean()))
        summaries.append(s)
        daily[name]=f.groupby('date').total_cost_yuan.sum()
        columns=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh','unused_grid_kwh']
        for target,key in [(months,'month'),(hours,'hour')]:
            grouped=f.assign(**{key:f.date.str[:7] if key=='month' else (f.slot_id-1)//6}).groupby(key)[columns].sum().reset_index()
            grouped['policy']=name;target.append(grouped)
        if name not in names[:4]:
            decisions=json.loads((folder/'decisions.json').read_text())['days'];e=np.load(folder/'decision_evidence.npz')
            for i,d in enumerate(decisions):
                k=d['selected_index'];selected=d['candidates'][k];n=d['scenario_count'];real=f.loc[f.date==d['date']]
                selection.append({'policy':name,'date':d['date'],'tau':selected['tau'],'terminal':str(selected['terminal']),
                                  'initial_soc_kwh':d['initial_energy_kwh'],'scenario_count':n,'selected_index':k})
                expected=float(e['emergency_fee'][i,k,:n].mean());actual=float(real.emergency_cost_yuan.sum())
                score_diagnostics.append({'policy':name,'date':d['date'],'expected_emergency_yuan':expected,
                                          'actual_emergency_yuan':actual,'emergency_prediction_error_yuan':actual-expected,
                                          'selected_proxy_score_yuan':float(e['score'][i,k]),
                                          'actual_cost_yuan':float(real.total_cost_yuan.sum())})
    summary=pd.DataFrame(summaries).set_index('policy')
    for b in names[:4]+['P_floor']:
        summary['saving_vs_'+b+'_yuan']=summary.loc[b,'total_cost_yuan']-summary.total_cost_yuan
        summary['saving_vs_'+b+'_percent']=100*summary['saving_vs_'+b+'_yuan']/summary.loc[b,'total_cost_yuan']
        summary['inventory_adjusted_saving_vs_'+b+'_yuan']=summary.loc[b,'inventory_adjusted_cost_yuan']-summary.inventory_adjusted_cost_yuan
    bound=json.loads((ROOT/'lower_bound/status.json').read_text())['dual_bound_yuan']
    summary['gap_to_relaxed_bound_yuan']=summary.total_cost_yuan-bound
    summary.to_csv(ROOT/'comparison_all.csv')
    pair=pd.DataFrame(daily)
    for target in ['S_joint','P_B1_floor']:
        for b in names[:4]+['P_floor']: pair[target+'_saving_vs_'+b]=pair[b]-pair[target]
    pair.to_csv(ROOT/'daily_costs_and_differences.csv')
    monthly=pair.groupby(pair.index.str[:7]).sum();monthly.index.name='month'
    monthly.to_csv(ROOT/'monthly_costs_and_differences.csv')
    pd.concat(months,ignore_index=True).to_csv(ROOT/'monthly.csv',index=False)
    pd.concat(hours,ignore_index=True).to_csv(ROOT/'hourly.csv',index=False)
    selections=pd.DataFrame(selection);selections.to_csv(ROOT/'daily_selections.csv',index=False)
    selections.groupby(['policy','tau','terminal']).size().rename('days').reset_index().to_csv(ROOT/'selection_counts.csv',index=False)
    pd.DataFrame(score_diagnostics).to_csv(ROOT/'scenario_score_diagnostics.csv',index=False)
    counts=[];bootstrap=[];rng=np.random.default_rng(config['bootstrap_seed'])
    for target in ['S_joint','P_B1_floor']:
        for b in names[:4]+['P_floor']:
            x=(pair[b]-pair[target]).to_numpy();n=len(x)
            counts.append({'policy':target,'baseline':b,'wins':int((x>1e-5).sum()),'losses':int((x< -1e-5).sum()),'ties':int((abs(x)<=1e-5).sum()),
                           'positive_months':int((monthly[b]-monthly[target]>1e-5).sum()),
                           'worst_day_saving_yuan':float(x.min()),'best_day_saving_yuan':float(x.max())})
            for block in config['bootstrap_blocks']:
                starts=rng.integers(0,n,size=(config['bootstrap_replicates'],math.ceil(n/block)))
                ix=((starts[:,:,None]+np.arange(block))%n).reshape(len(starts),-1)[:,:n]
                lo,hi=np.quantile(x[ix].sum(axis=1),[.025,.975])
                bootstrap.append({'policy':target,'baseline':b,'block_days':block,'point_saving_yuan':float(x.sum()),
                                  'ci95_low_yuan':float(lo),'ci95_high_yuan':float(hi),'replicates':len(starts),
                                  'seed':config['bootstrap_seed'],'scope':'single-year dependent-day descriptive interval, not external validation'})
    pd.DataFrame(counts).to_csv(ROOT/'win_loss_counts.csv',index=False)
    pd.DataFrame(bootstrap).to_csv(ROOT/'block_bootstrap.csv',index=False)
    c=summary.total_cost_yuan
    save_json(ROOT/'ablation.json',{'P':c.P,'S_tau':c.S_tau,'S_terminal':c.S_terminal,'S_joint':c.S_joint,
        'tau_selection_saving':c.P-c.S_tau,'terminal_selection_saving':c.P-c.S_terminal,
        'joint_saving':c.P-c.S_joint,'tau_increment_on_terminal':c.S_terminal-c.S_joint,
        'terminal_increment_on_tau':c.S_tau-c.S_joint,
        'interaction_extra_saving':c.S_tau+c.S_terminal-c.P-c.S_joint,
        'scope':'Independent continuous paths include endogenous state feedback; not isolated same-SOC daily causal contributions.'})
    for name in ['P','P_terminal','S_joint','P_B1_floor']:
        r=frames[name].loc[frames[name].date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
        folder=ROOT/'representative'/name;folder.mkdir(parents=True,exist_ok=True)
        r.to_csv(folder/'four_days_ledger.csv',index=False)
        r.loc[r.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_plan_kwh','planned_cost_yuan']].to_csv(folder/'table1_intervals.csv',index=False)
        r.groupby('date')[['grid_plan_kwh','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']].sum().to_csv(folder/'table1_daily.csv')
        r.groupby('date').agg(initial_energy_kwh=('energy_start_actual_kwh','first'),final_energy_kwh=('energy_end_actual_kwh','last')).to_csv(folder/'terminal.csv')
        r.assign(block_start_hour=((r.slot_id-1)//24)*4).groupby(['date','block_start_hour'])[['charge_actual_kwh','discharge_actual_kwh']].sum().to_csv(folder/'table2_charge_discharge.csv')
        r.loc[r.emergency_kwh>1e-6,['date','interval_start','interval_end','emergency_kwh','emergency_cost_yuan']].to_csv(folder/'table3_emergency.csv',index=False)
    stress(frames)
    print(summary[['total_cost_yuan','emergency_cost_yuan','unused_grid_cost_yuan','saving_vs_P_yuan','saving_vs_P_terminal_yuan']].to_string(),flush=True)


def stress(frames):
    archive=read(ROOT/'forecasts/linear_harmonic.csv');rows=[];traces=[]
    price=pd.read_csv(ROOT/'inputs/fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    for day in pd.date_range('2025-02-01','2025-12-01',freq='MS'):
        ds=str(day.date());hist=archive.loc[(archive.date>=str((day-pd.Timedelta(days=56)).date()))&(archive.date<ds)]
        order=hist.groupby('date').net_residual_kwh.sum().sort_values(kind='stable')
        forecast=archive.loc[archive.date==ds]
        for tau in [.9,.95]:
            source=order.index[math.ceil(tau*len(order))-1]
            net=(forecast.load_forecast_kwh-forecast.pv_forecast_kwh).to_numpy()+hist.loc[hist.date==source,'net_residual_kwh'].to_numpy()
            for name in ['B1','P','P_terminal','S_joint','P_B1_floor']:
                f=frames[name].loc[frames[name].date==ds];initial=float(f.energy_start_actual_kwh.iloc[0])
                q=f.grid_plan_kwh.to_numpy()[None,:]
                simulated=simulate(q,net[None,:],price,initial,0.,traces=True)
                rows.append({'date':ds,'policy':name,'stress_quantile':tau,'source_date':source,
                             'source_available_time':str(pd.Timestamp(source)+pd.Timedelta(days=1)),
                             'initial_energy_kwh':initial,'emergency_cost_yuan':float(simulated['emergency_fee'][0,0]),
                             'total_cost_yuan':float(simulated['score'][0]),'final_energy_kwh':float(simulated['end_energy'][0,0])})
                for t in range(144):
                    traces.append({'date':ds,'policy':name,'stress_quantile':tau,'source_date':source,'slot_id':t+1,
                                   'grid_plan_kwh':float(q[0,t]),'scenario_net_kwh':float(net[t]),'price_yuan_per_kwh':float(price[t]),
                                   **{key:float(value[0,0,t]) for key,value in simulated['trace'].items()}})
    folder=ROOT/'stress';folder.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(folder/'summary.csv',index=False);pd.DataFrame(traces).to_csv(folder/'ledger.csv',index=False)
    save_json(folder/'scope.json',{'scenarios':22,'paths':110,'rows':len(traces),
        'scope':'Historical tail diagnostics with each policy own actual-path state and frozen plan; overlaps scoring scenarios, not independent validation or fair same-initial annual ranking.',
        'construction':'Common point net forecast plus whole historical net-error day, signed net demand, no physical-source clipping or alteration.'})


if __name__=='__main__': main()
