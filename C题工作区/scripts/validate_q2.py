"""Independent saved-file audit: Q2 physics, billing, forecasts, chronology and required tables."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[1]
OUT=WORK/'results/q2'


def read(path): return pd.read_csv(path,float_precision='round_trip')


def main():
    cfg=json.loads((OUT/'config_snapshot.json').read_text())
    phys=json.loads((OUT/'physical_snapshot.json').read_text())['battery']
    selection=json.loads((OUT/'selection.json').read_text())
    source=read(WORK/'data/processed/actual_10min.csv')
    fixed=read(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy()
    source=source.set_index('interval_start')
    all_load=source.load_actual_kwh.to_numpy().reshape(365,144)
    all_pv=source.pv_actual_kwh.to_numpy().reshape(365,144)
    ec,ed=phys['eta_charge'],phys['eta_discharge']
    reports={}
    totals={}
    def harmonics(k):
        columns=[np.ones(144)]
        for j in range(1,k+1):
            angle=2*np.pi*j*np.arange(144)/144
            columns.extend([np.sin(angle),np.cos(angle)])
        return np.column_stack(columns)
    checked_refits=set()
    for name in ['warmup']+['calibration/'+k for k in cfg['candidates']]+['selected','seasonal','no_storage']:
        path=OUT/name
        f=read(path/'ledger.csv')
        f['interval_start']=pd.to_datetime(f.interval_start)
        f['interval_end']=pd.to_datetime(f.interval_end)
        checks={}
        residuals={}
        def test(key,condition): checks[key]=bool(condition)
        def near(key,a,b,tol=1e-6):
            aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
            if aa.shape!=bb.shape and aa.size!=1 and bb.size!=1:
                test(key,False)
                return
            r=float(np.max(np.abs(aa-bb)))
            residuals[key]=r
            test(key,np.isfinite(r) and r<=tol)
        def bound(key,value):
            r=float(max(0.,np.asarray(value).max()))
            residuals[key]=r
            test(key,np.isfinite(r) and r<=1e-6)
        begin='2025-01-01' if name=='warmup' else cfg['calibration_start'] if name.startswith('calibration') else cfg['evaluation_start']
        end='2025-01-31' if name=='warmup' or name.startswith('calibration') else cfg['evaluation_end']
        expected=pd.date_range(begin,pd.Timestamp(end)+pd.Timedelta(days=1),freq='10min',inclusive='left')
        test('complete_grid',f.interval_start.tolist()==expected.tolist() and f.interval_end.tolist()==(expected+pd.Timedelta(minutes=10)).tolist())
        test('date_slot_keys',f.date.tolist()==expected.strftime('%Y-%m-%d').tolist() and f.slot_id.tolist()==list(np.tile(np.arange(1,145),len(expected)//144)))
        actual=source.loc[f.interval_start.dt.strftime('%Y-%m-%dT%H:%M:%S')]
        for field in ['load_actual_kwh','pv_actual_kwh']: near('source_'+field,f[field],actual[field])
        price=np.tile(fixed,f.date.nunique())
        near('fixed_price',f.price_yuan_per_kwh,price)
        test('issue_times',pd.to_datetime(f.issue_time).tolist()==f.interval_start.dt.normalize().tolist())
        g,c,d,e,w=[f[k].to_numpy() for k in ['grid_plan_kwh','charge_actual_kwh','discharge_actual_kwh','emergency_kwh','surplus_kwh']]
        es,ee=f.energy_start_actual_kwh.to_numpy(),f.energy_end_actual_kwh.to_numpy()
        l,pv=f.load_actual_kwh.to_numpy(),f.pv_actual_kwh.to_numpy()
        numeric=f.select_dtypes(include='number').drop(columns=['load_forecast_kwh','pv_forecast_kwh'])
        test('finite_outputs',np.isfinite(numeric.to_numpy()).all())
        near('actual_balance',g+e+pv+d,l+c+w)
        near('actual_state_recursion',ee,es+ec*c-d/ed)
        near('actual_state_continuity',es[1:],ee[:-1])
        bound('capacity_upper',np.r_[es,ee]-10800)
        bound('capacity_lower',1200-np.r_[es,ee])
        bound('nonnegative',-np.r_[g,c,d,e,w])
        bound('charge_power',c-5000/6)
        bound('discharge_power',d-5000/6)
        near('actual_mutex',np.minimum(c,d),0.)
        net=g+pv-l
        desired_charge=np.minimum.reduce([np.maximum(net,0),np.full(len(f),5000/6),np.maximum((10800-es)/ec,0)])
        desired_discharge=np.minimum.reduce([np.maximum(-net,0),np.full(len(f),5000/6),np.maximum((es-1200)*ed,0)])
        if name=='no_storage': desired_charge[:]=0; desired_discharge[:]=0
        near('executor_charge',c,desired_charge)
        near('executor_discharge',d,desired_discharge)
        near('executor_emergency',e,np.maximum(-net-desired_discharge,0))
        near('surplus_split',f.unused_grid_kwh+f.pv_curtailment_kwh,w)
        near('grid_disposal_priority',f.unused_grid_kwh,np.minimum(g,w))
        bound('pv_disposal_upper',f.pv_curtailment_kwh-pv)
        bound('disposal_nonnegative',-f[['unused_grid_kwh','pv_curtailment_kwh']].to_numpy())
        near('planned_fee_full_commitment',f.planned_cost_yuan,price*g)
        near('emergency_fee_fivefold',f.emergency_cost_yuan,5*price*e)
        near('total_fee',f.total_cost_yuan,price*(g+5*e))
        mask=f.load_forecast_kwh.notna().to_numpy()
        test('missing_forecast_only_coldstart',bool(mask.all()) if name!='warmup' else (not mask[:144].any() and mask[144:].all()))
        pc,pd_,pe0,pe1,pw,z=[f[k].to_numpy() for k in ['charge_plan_kwh','discharge_plan_kwh','energy_start_plan_kwh','energy_end_plan_kwh','pv_curtailment_plan_kwh','charge_mode_plan']]
        near('plan_balance',g[mask]+f.pv_forecast_kwh.to_numpy()[mask]+pd_[mask],f.load_forecast_kwh.to_numpy()[mask]+pc[mask]+pw[mask])
        near('plan_state',pe1,pe0+ec*pc-pd_/ed)
        daily_first=np.arange(0,len(f),144)
        near('plan_initial_actual',pe0[daily_first],es[daily_first])
        near('plan_daily_cycle',pe1[daily_first+143],pe0[daily_first])
        not_first=np.arange(len(f))%144!=0
        near('plan_within_day_continuity',pe0[not_first],pe1[np.flatnonzero(not_first)-1])
        bound('plan_capacity_upper',np.r_[pe0,pe1]-10800)
        bound('plan_capacity_lower',1200-np.r_[pe0,pe1])
        near('plan_integer',z,np.rint(z),1e-7)
        bound('plan_modes_and_nonnegative',np.r_[pc-5000/6*z,pd_-5000/6*(1-z),-pc,-pd_,-pw,-z,z-1])
        bound('plan_curtailment',pw[mask]-f.pv_forecast_kwh.to_numpy()[mask])
        # Reconstruct every forecast from only stored parameters and historical lags.
        models=json.loads((path/'models_and_solvers.json').read_text())
        test('metadata_dates',[r['date'] for r in models]==f.date.drop_duplicates().tolist())
        for i,record in enumerate(models):
            day=pd.Timestamp(record['date'])
            n=(day-pd.Timestamp('2025-01-01')).days
            forecast=record['forecast']
            part=f.iloc[i*144:(i+1)*144]
            if n==0:
                near('coldstart_commitment',part.grid_plan_kwh,0.)
                continue
            test('history_cutoff_'+record['date'],pd.Timestamp(forecast['history_end'])==day)
            load=all_load[n-7 if n>=7 else n-1]
            predict_pv=all_pv[n-1]
            if 'load_coefficients' in forecast:
                x=np.column_stack([harmonics(cfg['load_harmonics']),all_load[n-1]/1000,all_load[n-7]/1000,
                                   np.tile([float(day.weekday()==k) for k in range(1,7)],(144,1))])
                load=np.maximum(x@np.array(forecast['load_coefficients']),0.)
                test('load_training_cutoff_'+record['date'],pd.Timestamp(forecast['load_training_last'])<day)
            if 'pv_coefficients' in forecast:
                predict_pv=np.maximum(harmonics(cfg['pv_harmonics'])@np.array(forecast['pv_coefficients'])+
                                      forecast['pv_phi']**np.arange(1,145)*forecast['pv_last_residual'],0.)
                test('pv_training_cutoff_'+record['date'],pd.Timestamp(forecast['pv_training_last'])<day)
            near('load_forecast_'+record['date'],part.load_forecast_kwh,load)
            near('pv_forecast_'+record['date'],part.pv_forecast_kwh,predict_pv)
            # Refit a fixed audit set independently; no same-day targets enter fitting.
            audit_key=(forecast['method'],record['date'])
            if record['date'] in ['2025-01-15','2025-02-01','2025-03-20','2025-06-21','2025-09-23','2025-12-21'] and audit_key not in checked_refits:
                if 'load_coefficients' in forecast:
                    xs=[]
                    first=max(7,n-cfg['load_training_days'])
                    for j in range(first,n):
                        weekday=(pd.Timestamp('2025-01-01')+pd.Timedelta(days=j)).weekday()
                        xs.append(np.column_stack([harmonics(cfg['load_harmonics']),all_load[j-1]/1000,all_load[j-7]/1000,
                                  np.tile([float(weekday==k) for k in range(1,7)],(144,1))]))
                    beta=np.linalg.lstsq(np.vstack(xs),all_load[first:n].ravel(),rcond=None)[0]
                    near('load_refit_'+record['date'],forecast['load_coefficients'],beta)
                if 'pv_coefficients' in forecast:
                    window=min(n,cfg['pv_training_days'])
                    x=np.tile(harmonics(cfg['pv_harmonics']),(window,1))
                    y=all_pv[n-window:n].ravel()
                    beta=np.linalg.lstsq(x,y,rcond=None)[0]
                    r=y-x@beta
                    denominator=r[:-1]@r[:-1]
                    phi=np.clip(r[:-1]@r[1:]/denominator if denominator>1e-12 else 0.,-cfg['ar1_bound'],cfg['ar1_bound'])
                    near('pv_refit_'+record['date'],forecast['pv_coefficients'],beta)
                    near('pv_ar1_refit_'+record['date'],forecast['pv_phi'],phi)
                checked_refits.add(audit_key)
            solver=record['solver']
            if solver['status']=='Optimal':
                near('solver_objective_'+record['date'],solver['objective_yuan'],part.planned_cost_yuan.sum())
                test('solver_gap_'+record['date'],solver['mip_gap']<=1e-9 and solver['objective_yuan']-solver['lower_bound_yuan']<=1e-5)
            else: test('allowed_analytic_status_'+record['date'],name=='no_storage')
        summary=json.loads((path/'summary.json').read_text())
        totals[name]=summary
        sums=['grid_plan_kwh','emergency_kwh','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan',
              'surplus_kwh','unused_grid_kwh','pv_curtailment_kwh']
        for field in sums: near('summary_'+field,summary[field],f[field].sum(),1e-5)
        near('summary_start_end',[summary['initial_energy_kwh'],summary['final_energy_kwh']],[es[0],ee[-1]])
        daily=read(path/'daily.csv')
        test('daily_keys',daily.date.tolist()==f.date.drop_duplicates().tolist())
        for field in sums+['charge_actual_kwh','discharge_actual_kwh']:
            near('daily_'+field,daily[field],f.groupby('date')[field].sum(),1e-5)
        near('daily_first_state',daily.energy_start_actual_kwh,es[daily_first])
        near('daily_last_state',daily.energy_end_actual_kwh,ee[daily_first+143])
        for variable in ['load','pv']:
            error=f[variable+'_forecast_kwh']-f[variable+'_actual_kwh']
            near('summary_'+variable+'_mae',summary[variable+'_mae_kwh'],error.abs().mean())
            near('summary_'+variable+'_rmse',summary[variable+'_rmse_kwh'],np.sqrt((error**2).mean()))
        if name in ['selected','seasonal','no_storage']:
            near('common_initial_state',es[0],selection['common_evaluation_initial_energy_kwh'])
            representative=f.loc[f.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
            t1=read(path/'table1_representative.csv')
            wanted=representative.loc[representative.slot_id.isin([61,73,85,97,109,121])]
            test('table1_time',pd.to_datetime(t1.interval_start).tolist()==wanted.interval_start.tolist())
            near('table1_value',t1.grid_plan_kwh,wanted.grid_plan_kwh)
            t2=read(path/'table2_representative.csv')
            expected_blocks=[]
            for date in representative.date.unique():
                for start in range(0,1440,240):
                    block=representative.loc[(representative.date==date)&((representative.slot_id-1)*10>=start)&((representative.slot_id-1)*10<start+240)]
                    expected_blocks.append([block.charge_actual_kwh.sum(),block.discharge_actual_kwh.sum()])
            test('table2_keys',t2.date.tolist()==list(np.repeat(representative.date.unique(),6)) and t2.block_start_minute.tolist()==list(range(0,1440,240))*4)
            near('table2_values',t2[['charge_actual_kwh','discharge_actual_kwh']],expected_blocks)
            for file,data in [('emergency_intervals.csv',f),('table3_representative.csv',representative)]:
                exported=read(path/file)
                wanted=data.loc[data.emergency_kwh>1e-6]
                test(file+'_time',pd.to_datetime(exported.interval_start).tolist()==wanted.interval_start.tolist())
                near(file+'_quantity',exported.emergency_kwh,wanted.emergency_kwh)
        reports[name]={'passed':all(checks.values()),'checks':checks,'max_residuals':residuals}
        print(name,'PASS' if reports[name]['passed'] else 'FAIL',len(checks),'checks',flush=True)
        for key,val in checks.items():
            if not val: print('FAIL',key,residuals.get(key),flush=True)
    cross={}
    initial=totals['warmup']['final_energy_kwh']
    cross['warmup_to_february']=abs(initial-selection['common_evaluation_initial_energy_kwh'])<1e-6
    calibration=read(OUT/'calibration/comparison.csv')
    scores=[]
    value=fixed.mean()*ed
    for _,row in calibration.iterrows():
        total=totals['calibration/'+row.candidate]
        score=total['total_cost_yuan']-value*(total['final_energy_kwh']-total['initial_energy_kwh'])
        scores.append(score)
        cross['calibration_score_'+row.candidate]=bool(abs(score-row.inventory_adjusted_score_yuan)<1e-5)
    cross['selection_frozen_before_evaluation']=selection['selected']==calibration.iloc[np.argmin(scores)].candidate and pd.Timestamp(selection['frozen_at'])<=pd.Timestamp(cfg['evaluation_start'])
    comparison=read(OUT/'comparison.csv')
    for _,row in comparison.iterrows():
        total=totals[row.policy]
        cross['comparison_'+row.policy]=all(abs(row[k]-total[k])<1e-5 for k in ['total_cost_yuan','grid_plan_kwh','emergency_kwh','initial_energy_kwh','final_energy_kwh'])
        expected=total['total_cost_yuan']-value*(total['final_energy_kwh']-initial)
        cross['inventory_'+row.policy]=abs(row.inventory_adjusted_cost_yuan-expected)<1e-5
    hashes=json.loads((OUT/'input_code_hashes.json').read_text())
    cross['input_code_unchanged']=all(hashlib.sha256((WORK/name).read_bytes()).hexdigest()==h for name,h in hashes.items())
    output={'passed':all(r['passed'] for r in reports.values()) and all(cross.values()),
            'runs':reports,'cross_checks':{k:bool(v) for k,v in cross.items()},
            'refit_audit_count':len(checked_refits),'independence':'no import of run_q2 or solver; saved-file physics/accounting plus forecast reconstruction and selected independent refits'}
    (OUT/'validation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print('OVERALL',output['passed'],'checks',sum(len(r['checks']) for r in reports.values())+len(cross),flush=True)
    sys.exit(0 if output['passed'] else 1)


if __name__=='__main__': main()
