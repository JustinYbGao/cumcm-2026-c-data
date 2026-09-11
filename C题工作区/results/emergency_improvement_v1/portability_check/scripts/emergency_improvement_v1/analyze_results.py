"""Complete declared comparisons, dependent-day uncertainty and historical joint-error stress."""
import hashlib
import json
import math
import numpy as np
import pandas as pd
from policy import ROOT, WORK, execute, write_json

REPORT = WORK/'reports/emergency_improvement_v1'
MAIN = ['B0','B1','P','E','PE']


def csv(path):
    return pd.read_csv(path,float_precision='round_trip')


def diagnostic(f,tau):
    net=f.load_actual_kwh-f.pv_actual_kwh
    point=f.load_forecast_kwh-f.pv_forecast_kwh
    qnet=f.plan_load_kwh-f.plan_pv_kwh
    error=net-qnet
    f=f.copy()
    f['coverage']=(error<=0).astype(float)
    f['quantile_loss_kwh']=np.maximum(tau*error,(tau-1)*error)
    pe=net-point
    f['point_pinball_same_tau_kwh']=np.maximum(tau*pe,(tau-1)*pe)
    f['point_net_mae_kwh']=pe.abs()
    f['risk_net_absolute_error_kwh']=error.abs()
    f['net_underforecast_kwh']=np.maximum(error,0)
    return f


def main():
    configs=json.loads((WORK/'configs/emergency_improvement_v1/experiments.json').read_text())
    summaries=[];monthly=[];hourly=[];coverage=[];slots=[];dailies={};frames={}
    for cfg in configs['runs']:
        name=cfg['policy'];folder=ROOT/'runs'/name
        f=csv(folder/'ledger.csv'); frames[name]=f
        s=json.loads((folder/'summary.json').read_text())
        s.update(group=cfg['group'],conditional=cfg['conditional'],tau=cfg['tau'],residual_days=cfg['residual_days'],
                 eta_charge=cfg['eta_charge'],power_basis=cfg['power_basis'],terminal_target=cfg['terminal_target'])
        emerg=f.emergency_kwh>1e-6
        s['evening_emergency_fee_share']=float(f.loc[emerg & (f.slot_id>=109),'emergency_cost_yuan'].sum()/max(1e-20,s['emergency_cost_yuan']))
        s['floor_emergency_fee_share']=float(f.loc[emerg & (f.energy_end_actual_kwh<=1200+1e-6),'emergency_cost_yuan'].sum()/max(1e-20,s['emergency_cost_yuan']))
        s['risk_sample_min']=int(f.risk_sample_count.min());s['risk_sample_max']=int(f.risk_sample_count.max())
        s['risk_cold_start_days']=int(f.groupby('date').risk_cold_start.first().sum())
        summaries.append(s)
        daily=csv(folder/'daily.csv').set_index('date');dailies[name]=daily
        m=f.assign(month=f.date.str[:7]).groupby('month')[['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh','surplus_kwh','unused_grid_kwh']].sum().reset_index()
        m['policy']=name;monthly.append(m)
        h=f.assign(hour=(f.slot_id-1)//6).groupby('hour')[['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh']].sum().reset_index();h['policy']=name;hourly.append(h)
        if cfg['group'] in ['main','risk_sensitivity']:
            z=diagnostic(f,cfg['tau']);z['month']=z.date.str[:7];z['hour']=(z.slot_id-1)//6
            for group in ['month','hour']:
                out=z.groupby(group)[['coverage','quantile_loss_kwh','point_pinball_same_tau_kwh','point_net_mae_kwh','risk_net_absolute_error_kwh','net_underforecast_kwh']].mean().reset_index()
                out['policy']=name;out['grouping']=group;out['tau']=cfg['tau'];out['n_intervals']=z.groupby(group).size().to_numpy();coverage.append(out)
            out=z.groupby('slot_id')[['coverage','quantile_loss_kwh','point_pinball_same_tau_kwh','point_net_mae_kwh']].mean().reset_index();out['policy']=name;out['tau']=cfg['tau'];out['lead_minutes']=out.slot_id*10;slots.append(out)
    summary=pd.DataFrame(summaries).set_index('policy')
    for b in ['B0','B1']:
        references=[b+'_'+group if group in ['terminal','efficiency','power'] else b for group in summary.group]
        summary[f'reference_{b}_policy']=references
        costs=summary.loc[references,'total_cost_yuan'].to_numpy()
        adjusted=summary.loc[references,'inventory_adjusted_cost_yuan'].to_numpy()
        summary[f'saving_vs_{b}_yuan']=costs-summary.total_cost_yuan
        summary[f'saving_vs_{b}_percent']=100*summary[f'saving_vs_{b}_yuan']/costs
        summary[f'inventory_adjusted_saving_vs_{b}_yuan']=adjusted-summary.inventory_adjusted_cost_yuan
    summary.to_csv(ROOT/'comparison_all.csv')
    pd.concat(monthly,ignore_index=True).to_csv(ROOT/'monthly.csv',index=False)
    pd.concat(hourly,ignore_index=True).to_csv(ROOT/'hourly.csv',index=False)
    pd.concat(coverage,ignore_index=True).to_csv(ROOT/'forecast_coverage.csv',index=False)
    pd.concat(slots,ignore_index=True).to_csv(ROOT/'forecast_lead_time.csv',index=False)
    pair=pd.DataFrame({name:d.total_cost_yuan for name,d in dailies.items()})
    for b in ['B0','B1']:pair[f'P_saving_vs_{b}']=pair[b]-pair.P
    pair.to_csv(ROOT/'daily_costs_and_differences.csv')
    pmonth=pair.groupby(pair.index.str[:7]).sum();pmonth.index.name='month';pmonth.to_csv(ROOT/'monthly_costs_and_differences.csv')
    # Apples-to-apples comparisons within the changed physical/terminal assumptions.
    paired=[]
    for setting in ['base','terminal','efficiency','power']:
        suf='' if setting=='base' else '_'+setting
        for baseline in ['B0','B1']:
            b=summary.loc[baseline+suf];p=summary.loc['P'+suf]
            paired.append({'setting':setting,'baseline':baseline,'baseline_cost_yuan':b.total_cost_yuan,
                           'P_cost_yuan':p.total_cost_yuan,'P_saving_yuan':b.total_cost_yuan-p.total_cost_yuan,
                           'P_inventory_adjusted_saving_yuan':b.inventory_adjusted_cost_yuan-p.inventory_adjusted_cost_yuan,
                           'baseline_final_soc_kwh':b.final_energy_kwh,'P_final_soc_kwh':p.final_energy_kwh})
    pd.DataFrame(paired).to_csv(ROOT/'paired_assumption_sensitivity.csv',index=False)
    bootstrap=[]
    rng=np.random.default_rng(configs['bootstrap']['seed'])
    for b in ['B0','B1']:
        x=(pair[b]-pair.P).to_numpy();n=len(x)
        for block in configs['bootstrap']['block_days']:
            starts=rng.integers(0,n,size=(configs['bootstrap']['replicates'],math.ceil(n/block)))
            ix=(starts[:,:,None]+np.arange(block))%n;ix=ix.reshape(len(starts),-1)[:,:n]
            totals=x[ix].sum(axis=1)
            lo,hi=np.quantile(totals,[.025,.975])
            bootstrap.append({'baseline':b,'block_days':block,'point_saving_yuan':x.sum(),'ci95_low_yuan':lo,'ci95_high_yuan':hi,
                              'replicates':len(starts),'seed':configs['bootstrap']['seed'],'scope':'conditional historical circular moving-block bootstrap; no independent-year guarantee'})
    pd.DataFrame(bootstrap).to_csv(ROOT/'block_bootstrap.csv',index=False)
    c=summary.total_cost_yuan
    write_json(ROOT/'ablation.json',{'B0_yuan':c.B0,'P_yuan':c.P,'E_conditional_yuan':c.E,'PE_conditional_yuan':c.PE,
                                   'P_saving_vs_B0':c.B0-c.P,'E_saving_vs_B0':c.B0-c.E,
                                   'PE_saving_vs_B0':c.B0-c.PE,'P_increment_on_E':c.E-c.PE,
                                   'E_increment_on_P':c.P-c.PE,
                                   'interaction_extra_saving':(c.B0-c.PE)-(c.B0-c.P)-(c.B0-c.E)})
    stress(configs,frames)
    dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    for name in MAIN:
        f=frames[name];folder=ROOT/'representative'/name;folder.mkdir(parents=True,exist_ok=True)
        r=f.loc[f.date.isin(dates)]
        r.to_csv(folder/'four_days_ledger.csv',index=False)
        r.loc[r.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_plan_kwh','planned_cost_yuan']].to_csv(folder/'table1_intervals.csv',index=False)
        dailies[name].loc[dates].to_csv(folder/'table1_daily_and_terminal.csv')
        r.assign(block_start_hour=((r.slot_id-1)//24)*4).groupby(['date','block_start_hour'])[['charge_actual_kwh','discharge_actual_kwh']].sum().to_csv(folder/'table2_charge_discharge.csv')
        r.loc[r.emergency_kwh>1e-6,['date','interval_start','interval_end','emergency_kwh','emergency_cost_yuan']].to_csv(folder/'table3_emergency_intervals.csv',index=False)
    print(summary[['total_cost_yuan','emergency_cost_yuan','saving_vs_B0_yuan','saving_vs_B1_yuan']].to_string(),flush=True)


def stress(configs,frames):
    # A common joint load/PV error day is used for all three policies.
    archive=csv(ROOT/'forecasts/linear_harmonic.csv')
    archive['load_error']=archive.load_actual_kwh-archive.load_forecast_kwh
    archive['pv_error']=archive.pv_actual_kwh-archive.pv_forecast_kwh
    folder=ROOT/'stress';folder.mkdir(exist_ok=True)
    output=[];details=[]
    for day in pd.date_range('2025-02-01','2025-12-01',freq='MS'):
        hist=archive.loc[(archive.date>=str((day-pd.Timedelta(days=56)).date())) & (archive.date<str(day.date()))]
        scores=hist.groupby('date').net_residual_kwh.sum().sort_values(kind='stable')
        target=archive.loc[archive.date==str(day.date())]
        for tau in [.9,.95]:
            source_day=scores.index[math.ceil(tau*len(scores))-1]
            src=hist.loc[hist.date==source_day]
            raw_load=target.load_forecast_kwh.to_numpy()+src.load_error.to_numpy()
            raw_pv=target.pv_forecast_kwh.to_numpy()+src.pv_error.to_numpy()
            sl=np.maximum(raw_load,0);sp=np.maximum(raw_pv,0)
            for name in ['B0','B1','P']:
                f=frames[name].loc[frames[name].date==str(day.date())]
                cfg=next(c for c in configs['runs'] if c['policy']==name)
                energy=float(f.energy_start_actual_kwh.iloc[0]);initial=energy;cost=emer=0.
                for t,(_,r) in enumerate(f.iterrows()):
                    e=execute(max(0.,r.grid_plan_kwh),sl[t],sp[t],energy,cfg['eta_charge'],cfg['eta_discharge'])
                    energy=e['energy_end_actual_kwh'];ec=5*r.price_yuan_per_kwh*e['emergency_kwh'];tc=r.planned_cost_yuan+ec
                    cost+=tc;emer+=ec
                    details.append({'target_date':str(day.date()),'policy':name,'stress_quantile':tau,'source_date':source_day,
                                    'source_available_time':str(pd.Timestamp(source_day)+pd.Timedelta(days=1)),'issue_time':str(day),
                                    'slot_id':int(r.slot_id),'grid_plan_kwh':r.grid_plan_kwh,'load_actual_kwh':sl[t],'pv_actual_kwh':sp[t],
                                    'raw_load_before_clipping_kwh':raw_load[t],'raw_pv_before_clipping_kwh':raw_pv[t],
                                    'price_yuan_per_kwh':r.price_yuan_per_kwh,'total_cost_yuan':tc,'emergency_cost_yuan':ec,**e})
                output.append({'target_date':str(day.date()),'policy':name,'stress_quantile':tau,'source_date':source_day,'history_days':len(scores),
                               'source_cumulative_signed_underforecast_kwh':float(scores.loc[source_day]),'total_cost_yuan':cost,
                               'emergency_cost_yuan':emer,'initial_energy_kwh':initial,'final_energy_kwh':energy,
                               'load_clipping_kwh':float(np.maximum(-raw_load,0).sum()),'pv_clipping_kwh':float(np.maximum(-raw_pv,0).sum())})
    pd.DataFrame(output).to_csv(folder/'summary.csv',index=False)
    pd.DataFrame(details).to_csv(folder/'ledger.csv',index=False)
    write_json(folder/'scope.json',{'policy_comparison':'Conditional per-policy states from actual path; not same-initial-state annual policy ranking',
                                   'scenario':'Common B0 forecast plus one historical load/PV error trajectory; nonnegative clipping is logged',
                                   'scenario_count':22,'paths':66,'rows':len(details),'oracle_used':False})


if __name__=='__main__':main()
