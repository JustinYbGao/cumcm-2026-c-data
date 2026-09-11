"""Post-result descriptive evidence for the simple and cheapest terminal policies.

Does not change the preregistered comparison or select/refit any annual policy.
"""
import math
from policy import ROOT, np, pd, save_json


def main():
    out=ROOT/'followup_diagnostics';out.mkdir(exist_ok=True)
    costs=pd.read_csv(ROOT/'daily_costs_and_differences.csv',index_col='date',float_precision='round_trip')
    monthly=costs.groupby(costs.index.str[:7]).sum()
    rng=np.random.default_rng(20260912);stats=[];boots=[]
    for target in ['P_floor','S_terminal']:
        for baseline in ['B0','B1','P','P_terminal','P_floor']:
            if target==baseline:continue
            x=(costs[baseline]-costs[target]).to_numpy();n=len(x)
            stats.append({'policy':target,'baseline':baseline,'saving_yuan':float(x.sum()),
                          'winning_days':int((x>1e-5).sum()),'losing_days':int((x< -1e-5).sum()),
                          'tied_days':int((abs(x)<=1e-5).sum()),
                          'positive_months':int((monthly[baseline]-monthly[target]>1e-5).sum()),
                          'worst_day_saving_yuan':float(x.min()),'best_day_saving_yuan':float(x.max())})
            for block in [7,14]:
                starts=rng.integers(0,n,size=(2000,math.ceil(n/block)))
                ix=((starts[:,:,None]+np.arange(block))%n).reshape(2000,-1)[:,:n]
                lo,hi=np.quantile(x[ix].sum(axis=1),[.025,.975])
                boots.append({'policy':target,'baseline':baseline,'block_days':block,'saving_yuan':float(x.sum()),
                              'ci95_low_yuan':float(lo),'ci95_high_yuan':float(hi),'seed':20260912,'replicates':2000})
        f=pd.read_csv(ROOT/'runs'/target/'ledger.csv',float_precision='round_trip')
        r=f.loc[f.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
        folder=out/'representative'/target;folder.mkdir(parents=True,exist_ok=True)
        r.to_csv(folder/'four_days_ledger.csv',index=False)
        r.loc[r.slot_id.isin([61,73,85,97,109,121]),['date','interval_start','interval_end','grid_plan_kwh','planned_cost_yuan']].to_csv(folder/'table1_intervals.csv',index=False)
        r.groupby('date')[['grid_plan_kwh','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']].sum().to_csv(folder/'table1_daily.csv')
        r.groupby('date').agg(initial_energy_kwh=('energy_start_actual_kwh','first'),final_energy_kwh=('energy_end_actual_kwh','last')).to_csv(folder/'terminal.csv')
        r.assign(block_start_hour=((r.slot_id-1)//24)*4).groupby(['date','block_start_hour'])[['charge_actual_kwh','discharge_actual_kwh']].sum().to_csv(folder/'table2_charge_discharge.csv')
        r.loc[r.emergency_kwh>1e-6,['date','interval_start','interval_end','emergency_kwh','emergency_cost_yuan']].to_csv(folder/'table3_emergency.csv',index=False)
    pd.DataFrame(stats).to_csv(out/'win_loss.csv',index=False)
    pd.DataFrame(boots).to_csv(out/'block_bootstrap.csv',index=False)
    save_json(out/'scope.json',{'status':'Post-result descriptive analysis; no policy redefinition or parameter selection',
                              'bootstrap':'Circular moving blocks of observed paired daily costs; same single year, conditional on fitted paths; not external validation or guaranteed coverage.'})


if __name__=='__main__':main()
