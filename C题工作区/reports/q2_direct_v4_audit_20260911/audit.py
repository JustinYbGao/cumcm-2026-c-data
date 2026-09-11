"""Fresh audit: no imports from production code or the supplied verifier."""
import hashlib
import json
import math
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = OUT.parents[1]
ROOT = WORK/'results/q2_direct_v4'
REPORT = WORK/'reports/q2_direct_v4'
INITIAL = 7268.4231640740745
CHECKS = []


def csv(path):
    return pd.read_csv(path, float_precision='round_trip')


def close(label, a, b, tol=1e-6):
    a, b = np.asarray(a), np.asarray(b)
    assert a.shape == b.shape, (label, a.shape, b.shape)
    err = float(np.abs(a-b).max(initial=0))
    assert np.isfinite(err) and err <= tol, (label, err, tol)
    CHECKS.append((label, err, tol))


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def replay(q, demand, initial):
    state = float(initial)
    out = []
    for buy, need in zip(q, demand):
        start = state
        excess = buy-need
        c = min(max(excess, 0), 5000/6, max((10800-state)/.9, 0))
        d = min(max(-excess, 0), 5000/6, max((state-1200)*.9, 0))
        emergency = max(-excess, 0)-d
        spill = max(excess, 0)-c
        state += .9*c-d/.9
        out.append((start, state, c, d, emergency, spill))
    return np.array(out)


def forecasts(source):
    """Rebuild the specified B0 release sequence from completed source prefixes."""
    load = source.load_actual_kwh.to_numpy().reshape(365, 144)
    pv = source.pv_actual_kwh.to_numpy().reshape(365, 144)
    dates = pd.date_range('2025-01-01', periods=365)
    angle = 2*np.pi*np.arange(144)/144
    basis = lambda k: np.array([np.ones(144)]+[fun(j*angle) for j in range(1,k+1) for fun in (np.sin,np.cos)]).T
    f2, f3 = basis(2), basis(3)
    def features(i):
        dow = np.ones((144,1)) @ np.array([[float(dates[i].weekday()==k) for k in range(1,7)]])
        return np.column_stack((f2,load[i-1]/1000,load[i-7]/1000,dow))
    predictions = []
    for day in range(1,365):
        lh = load[day-7 if day>=7 else day-1].copy()
        ph = pv[day-1].copy()
        if day>=14:
            first = max(7,day-28)
            x = np.concatenate([features(k) for k in range(first,day)])
            coef = np.linalg.lstsq(x,load[first:day].ravel(),rcond=None)[0]
            lh = np.maximum(features(day)@coef,0)
        if day>=2:
            first = max(0,day-7)
            x = np.tile(f3,(day-first,1)); y = pv[first:day].ravel()
            coef = np.linalg.lstsq(x,y,rcond=None)[0]; res=y-x@coef
            den = res[:-1]@res[:-1]
            phi = np.clip(res[:-1]@res[1:]/den if den>1e-12 else 0,-.99,.99)
            ph = np.maximum(f3@coef+res[-1]*phi**np.arange(1,145),0)
        predictions.append(np.column_stack((lh,ph)))
    return np.array(predictions)


def scenario_costs(q, net, price, initial, kappa, mu):
    # Batched explicit transition with energy capacities, no imported kernel.
    state = np.full((6,len(net)),initial); fee=np.zeros_like(state)
    for t in range(144):
        demand = net[:,t][None,:]-q[:,t][:,None]
        c = np.minimum(np.clip(-demand,0,5000/6),np.maximum((10800-state)/.9,0))
        d = np.minimum(np.clip(demand,0,5000/6),np.maximum((state-1200)*.9,0))
        fee += 5*price[t]*(np.maximum(demand,0)-d)
        state = state+.9*c-d/.9
    normal=q@price
    score=normal+(kappa/5*fee-mu*(state-initial)).mean(axis=1)
    return normal,fee,state,score


def main():
    source=csv(WORK/'data/processed/actual_10min.csv')
    fixed=csv(WORK/'data/processed/fixed_price.csv').price_yuan_per_kwh.to_numpy()
    assert len(source)==52560
    for filename, original in [('actual_10min.csv',WORK/'data/processed/actual_10min.csv'),
                               ('fixed_price.csv',WORK/'data/processed/fixed_price.csv'),
                               ('original_run_q2.py',WORK/'scripts/run_q2.py'),
                               ('original_solve_q1.py',WORK/'scripts/solve_q1.py')]:
        assert digest(ROOT/'inputs'/filename)==digest(original),filename
    pred=forecasts(source)
    archive=csv(ROOT/'forecasts/linear_harmonic.csv')
    close('all_364_forecast_releases',archive[['load_forecast_kwh','pv_forecast_kwh']].to_numpy(),pred.reshape(-1,2))
    dates=pd.date_range('2025-01-02',periods=364)
    assert archive.date.tolist()==np.repeat(dates.strftime('%Y-%m-%d'),144).tolist()
    assert (pd.to_datetime(archive.issue_time)==pd.to_datetime(archive.date)).all()
    assert (pd.to_datetime(archive.history_end)<=pd.to_datetime(archive.date)).all()
    assert (pd.to_datetime(archive.residual_available_time)==pd.to_datetime(archive.date)+pd.Timedelta(days=1)).all()
    residual=(source.load_actual_kwh-source.pv_actual_kwh).to_numpy().reshape(365,144)[1:]-pred[:,:,0]+pred[:,:,1]
    close('all_residuals',archive.net_residual_kwh.to_numpy(),residual.ravel())
    actual=source.loc[source.date>='2025-02-01'].reset_index(drop=True)
    price=np.tile(fixed,334); net=(actual.load_actual_kwh-actual.pv_actual_kwh).to_numpy()
    table=csv(ROOT/'analysis_all/comparison_all.csv').set_index('policy')
    config=json.loads((WORK/'configs/q2_direct_v4/experiments.json').read_text())
    runs=config['runs']+json.loads((WORK/'configs/q2_direct_v4/refinement.json').read_text())['runs']
    refs=['B0','B1','P_floor','X_strong_morning85']; names=refs+[r['policy'] for r in runs]
    assert list(table.index)==names
    totals={}; daily={}; evidence_summary={}
    for name in names:
        folder=ROOT/('references' if name in refs else 'runs')/name
        frame=csv(folder/'ledger.csv'); plans=csv(folder/'plans.csv')
        assert frame[['date','slot_id']].equals(actual[['date','slot_id']])
        close(name+'.source',frame[['load_actual_kwh','pv_actual_kwh']].to_numpy(),actual[['load_actual_kwh','pv_actual_kwh']].to_numpy())
        close(name+'.prices',frame.price_yuan_per_kwh.to_numpy(),price)
        q=frame.grid_plan_kwh.to_numpy(); assert np.isfinite(q).all() and (q>=-1e-6).all()
        close(name+'.frozen_plans',q,plans.grid_plan_kwh.to_numpy())
        assert (pd.to_datetime(frame.issue_time)==pd.to_datetime(frame.date)).all()
        state=replay(q,net,INITIAL)
        fields=['energy_start_actual_kwh','energy_end_actual_kwh','charge_actual_kwh','discharge_actual_kwh','emergency_kwh','surplus_kwh']
        close(name+'.strict_greedy_full_path',state,frame[fields].to_numpy())
        assert state[:,:2].min()>=1200-1e-6 and state[:,:2].max()<=10800+1e-6
        assert state[:,2:4].min()>=-1e-6 and state[:,2:4].max()<=5000/6+1e-6
        assert np.minimum(state[:,2],state[:,3]).max()<=1e-6
        close(name+'.balance',q+state[:,3]+state[:,4]-state[:,2]-state[:,5],net)
        billed=np.column_stack((price*q,5*price*state[:,4],price*q+5*price*state[:,4]))
        costfields=['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']
        close(name+'.bills',billed,frame[costfields].to_numpy())
        total=np.array([math.fsum(billed[:,i]) for i in range(3)])
        close(name+'.reported_totals',total,table.loc[name,costfields].to_numpy(dtype=float),1e-5)
        daily[name]=billed.reshape(334,144,3).sum(axis=1)
        totals[name]=dict(zip(costfields,map(float,total)),final_energy_kwh=float(state[-1,1]),
                          emergency_cap_passed=bool(total[1]<=1000000))
        if name in refs:continue
        cfg=next(r for r in runs if r['policy']==name)
        assert json.loads((folder/'config.json').read_text())==cfg
        with np.load(folder/'decision_evidence.npz') as z: ev={k:z[k] for k in z.files}
        meta=json.loads((folder/'decisions.json').read_text())['days']
        forecast_net=pred[30:,:,0]-pred[30:,:,1]
        counts=[]
        for i,md in enumerate(meta):
            day=pd.Timestamp(md['date']); hi=int((day-dates[0]).days); lo=max(0,hi-cfg['scenario_window'])
            expected_dates=dates[lo:hi].strftime('%Y-%m-%d').tolist(); count=hi-lo;counts.append(count)
            assert count>=7 and md['scenario_source_dates']==expected_dates
            start=state[i*144,0];close(name+'.candidate_initial',md['initial_energy_kwh'],start)
            scenarios=residual[lo:hi]+forecast_net[i]
            close(name+'.scenarios',ev['scenario_net'][i,:count],scenarios)
            assert np.isnan(ev['scenario_net'][i,count:]).all()
            candidates=ev['q'][i];assert np.isfinite(candidates).all() and candidates.min()>=-1e-6
            close(name+'.point_initializer',candidates[3],np.maximum(forecast_net[i],0))
            pool=residual[max(0,hi-28):hi].reshape(-1,24,6).transpose(1,0,2).reshape(24,-1)
            delta=np.concatenate([np.repeat(np.quantile(pool[h],.85 if 9<=h<11 else .65 if 11<=h<18 else .95 if 18<=h<22 else .8),6) for h in range(24)])
            close(name+'.risk_delta',ev['risk_delta'][i],delta)
            g,c,d,s0,s1,w,z=ev['initializer_plan'][i].T
            close(name+'.milp_q',candidates[0],np.maximum(g,0))
            close(name+'.milp_balance',g+d-c-w,forecast_net[i]+delta)
            close(name+'.milp_state',s1-s0,.9*c-d/.9)
            close(name+'.milp_continuity',s0,np.r_[start,s1[:-1]])
            close(name+'.milp_terminal',s1[-1],1200.)
            assert min(g.min(),c.min(),d.min(),w.min())>=-1e-6
            assert np.r_[s0,s1].min()>=1200-1e-6 and np.r_[s0,s1].max()<=10800+1e-6
            assert (c<=z*5000/6+1e-6).all() and (d<=(1-z)*5000/6+1e-6).all()
            close(name+'.milp_integrality',z,np.round(z))
            normal,fee,end,score=scenario_costs(candidates,scenarios,fixed,start,cfg['kappa'],cfg['mu'])
            for key,obs in [('ordinary',normal),('score',score),('emergency_fee',fee),('end_energy',end)]:
                saved=ev[key][i,:,:count] if key in ['emergency_fee','end_energy'] else ev[key][i]
                close(name+'.'+key,saved,obs,1e-6 if key=='end_energy' else 1e-5)
            selected=int(np.flatnonzero(score<=score.min()+1e-8)[0])
            assert selected==md['selected_index']==ev['selected_index'][i]
            close(name+'.selected_q',candidates[selected],q.reshape(334,144)[i])
            for j,opt in enumerate(md['optimizer']):
                trace=np.array(opt['evaluation_score_yuan']); assert len(trace)==opt['nfev']==opt['njev']
                close(name+'.incumbent_trace',trace.min(),score[3*j+1],1e-5)
                close(name+'.initial_trace',trace[0],score[3*j],1e-5)
        evidence_summary[name]={'candidate_days':334,'candidate_vectors':2004,'minimum_scenarios':min(counts),
            'maximum_scenarios':max(counts),'full_window_days':sum(c==cfg['scenario_window'] for c in counts),
            'optimizer_successes':sum(o['success'] for m in meta for o in m['optimizer'])}
        print('AUDITED',name,flush=True)
    pd.DataFrame(totals).T.to_csv(OUT/'costs_recomputed.csv')
    # Recreate the stated paired descriptive bootstrap with its frozen RNG stream.
    rng=np.random.default_rng(config['bootstrap_seed']); boot=csv(ROOT/'analysis_all/block_bootstrap.csv')
    counts=csv(ROOT/'analysis_all/win_loss_counts.csv');stats={}
    for cfg in runs:
        name=cfg['policy'];diff=daily['X_strong_morning85']-daily[name]
        monthly=pd.DataFrame(diff,index=pd.date_range('2025-02-01',periods=334).strftime('%Y-%m'),columns=['normal','emergency','total']).groupby(level=0).sum()
        observed=[int((diff[:,2]>1e-5).sum()),int((diff[:,2]<-1e-5).sum()),int((diff[:,1]<-1e-5).sum()),int((monthly.total>1e-5).sum()),int((monthly.emergency<-1e-5).sum())]
        row=counts[(counts.policy==name)&(counts.baseline=='X_strong_morning85')].iloc[0]
        close(name+'.win_loss',observed,row[['total_winning_days','total_losing_days','emergency_worse_days','positive_total_months','emergency_worse_months']].to_numpy(dtype=float),0)
        intervals={}
        for block in config['bootstrap_blocks']:
            starts=rng.integers(0,334,(2000,math.ceil(334/block)))
            indices=((starts[:,:,None]+np.arange(block))%334).reshape(2000,-1)[:,:334]
            ci=np.quantile(diff[indices].sum(axis=1),[.025,.975],axis=0)
            for j,key in enumerate(['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']):
                row=boot[(boot.policy==name)&(boot.block_days==block)&(boot.component==key)].iloc[0]
                close(name+'.bootstrap',ci[:,j],row[['ci95_low_yuan','ci95_high_yuan']].to_numpy(dtype=float),1e-5)
            intervals[block]=ci[:,2].tolist()
        stats[name]={'day_month_counts':observed,'total_savings_intervals':intervals}
    # Oracle: independently assemble sparse linear equalities and verify a primal/dual pair.
    from scipy.sparse import diags,bmat,eye
    n=len(net); I=eye(n,format='csr');zero=I*0; shift=diags([-np.ones(n-1)],[ -1],shape=(n,n),format='csr')
    A=bmat([[I,-I,I,-I,zero],[zero,-.9*I,I/.9,zero,I+shift]],format='csr')
    with np.load(ROOT/'oracle_source/certificate.npz') as z: cert={k:z[k] for k in z.files}
    rhs=np.r_[net,INITIAL,np.zeros(n-1)];cost=np.r_[price,np.zeros(4*n)]
    lower_bound=np.r_[np.zeros(4*n),np.full(n,1200.)]
    upper_bound=np.r_[np.full(n,np.inf),np.full(2*n,5000/6),np.full(n,np.inf),np.full(n,10800.)]
    x=cert['primal'];y=cert['equality_dual'];ld=cert['lower_dual'];ud=cert['upper_dual']
    close('oracle.source_net',cert['net'],net);close('oracle.source_price',cert['price'],price);close('oracle.initial',cert['initial'],INITIAL)
    close('oracle.primal',A@x,rhs)
    assert (x>=lower_bound-1e-6).all() and (x<=upper_bound+1e-6).all()
    close('oracle.stationarity',A.T@y+ld+ud,cost,1e-9)
    assert ld.min()>=-1e-9 and ud.max()<=1e-9
    finite=np.isfinite(upper_bound);close('oracle.unbounded_dual',ud[~finite],np.zeros((~finite).sum()),1e-9)
    dual=float(rhs@y+lower_bound@ld+upper_bound[finite]@ud[finite]);primal=float(cost@x)
    close('oracle.duality',dual,primal,1e-5)
    oracle_state=replay(x[:n],net,INITIAL);greedy_bill=float(price@x[:n]+5*price@oracle_state[:,4])
    close('oracle.greedy_attainment',greedy_bill,dual,1e-5)
    oracle={'primal':primal,'dual':dual,'greedy_total':greedy_bill,'greedy_emergency_fee':float(5*price@oracle_state[:,4]),
            'maximum_soc_difference':float(np.abs(oracle_state[:,1]-x[4*n:]).max())}
    # Verify ZIP independently, rather than trusting the prior packaging PASS.
    manifest=csv(REPORT/'package_manifest.csv');archive_path=REPORT/'q2_direct_v4_review.zip'
    archive_sha=digest(archive_path);assert archive_sha=='e52e54d7f80063429d8dcf566a80796b48c790a19bbed53d5eeff19b71c49745'
    with zipfile.ZipFile(archive_path) as z:
        assert len(z.namelist())==len(set(z.namelist()))==450
        assert z.testzip() is None
        for row in manifest.itertuples():
            assert digest(WORK/row.path)==row.sha256
            assert hashlib.sha256(z.read(row.path)).hexdigest()==row.sha256
    result={'passed':True,'ledger_rows':len(names)*48096,'forecast_releases':364,'candidate_vectors':len(runs)*334*6,
            'numeric_checks':len(CHECKS),'evidence':evidence_summary,'paired_statistics':stats,'oracle':oracle,
            'zip_sha256':archive_sha,'manifest_files':len(manifest),'zip_entries':450}
    (OUT/'audit_results.json').write_text(json.dumps(result,indent=2)+'\n')
    pd.DataFrame(CHECKS,columns=['check','max_error','tolerance']).to_csv(OUT/'numeric_checks.csv',index=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ['evidence','paired_statistics']},indent=2),flush=True)


if __name__=='__main__':main()
