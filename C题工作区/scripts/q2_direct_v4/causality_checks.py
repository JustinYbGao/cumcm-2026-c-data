"""Perturb future raw inputs, rebuild historical releases, and rerun complete policy decisions."""
import hashlib
import argparse
import json
from policy import WORK, ROOT, INPUTS, np, pd, forecast_day, save_json
from run_experiments import run_one


def rebuild(actual, kind='linear_harmonic'):
    config = json.loads((INPUTS / 'q2_baseline.json').read_text())
    rows = []
    for day in pd.date_range('2025-01-02','2025-01-26'):
        history = actual.loc[pd.to_datetime(actual.interval_end) <= day]
        load, pv, meta = forecast_day(history, day, kind, config)
        f = actual.loc[actual.date == str(day.date())].copy()
        f['issue_time'] = str(day); f['history_end'] = meta['history_end']
        f['load_forecast_kwh'] = load; f['pv_forecast_kwh'] = pv
        f['net_residual_kwh'] = f.load_actual_kwh - f.pv_actual_kwh - load + pv
        f['residual_available_time'] = str(day + pd.Timedelta(days=1))
        rows.append(f)
    return pd.concat(rows,ignore_index=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refinement',action='store_true');args=parser.parse_args()
    path_prefix=''
    folder = ROOT / 'causality_inputs'; folder.mkdir(exist_ok=True)
    original = pd.read_csv(INPUTS / 'actual_10min.csv',float_precision='round_trip')
    mutated = original.copy(); cutoff = pd.Timestamp('2025-01-25T12:00:00')
    future = pd.to_datetime(mutated.interval_start) >= cutoff
    mutated.loc[future,'load_actual_kwh'] += 800.
    mutated.loc[future,'pv_actual_kwh'] *= .5
    for kind in ['load','pv']: mutated[kind+'_actual_kw'] = mutated[kind+'_actual_kwh'] * 6
    kind='linear_harmonic'
    archive_a, archive_b = rebuild(original,kind), rebuild(mutated,kind)
    for name, data in [('future_mutated_actual.csv',mutated),('original_forecasts.csv',archive_a),('future_mutated_forecasts.csv',archive_b)]:
        path=folder/name; content=data.to_csv(index=False)
        if path.exists(): assert path.read_text()==content, 'Resume source differs: '+name
        else: path.write_text(content)
    checks = []
    for cfg in json.loads((WORK/'configs/q2_direct_v4'/('refinement.json' if args.refinement else 'experiments.json')).read_text())['runs']:
        test = dict(cfg,start='2025-01-24',end='2025-01-26',initial_energy_kwh=6000.)
        trajectories=[]
        for stage, data, archive in [('causality_original',original,archive_a),('causality_mutated',mutated,archive_b)]:
            path=ROOT/(path_prefix+stage)/cfg['policy']/'ledger.csv'
            trajectories.append(pd.read_csv(path,float_precision='round_trip',dtype={'selected_terminal':str}) if path.exists()
                                else run_one(test,path_prefix+stage,data,archive))
        a,b=trajectories
        earlier = pd.to_datetime(a.interval_start) < cutoff
        columns = a.select_dtypes(include='number').columns
        prefix = float(abs(a.loc[earlier,columns].to_numpy()-b.loc[earlier,columns].to_numpy()).max())
        pa=pd.read_csv(ROOT/(path_prefix+'causality_original')/cfg['policy']/'plans.csv',float_precision='round_trip',dtype={'selected_terminal':str})
        pb=pd.read_csv(ROOT/(path_prefix+'causality_mutated')/cfg['policy']/'plans.csv',float_precision='round_trip',dtype={'selected_terminal':str})
        keys=pa.select_dtypes(include='number').columns
        frozen=pa.date<='2025-01-25'
        planned=float(abs(pa.loc[frozen,keys].to_numpy()-pb.loc[frozen,keys].to_numpy()).max())
        later=pa.date=='2025-01-26'
        response=float(abs(pa.loc[later,['grid_plan_kwh','load_forecast_kwh','pv_forecast_kwh']].to_numpy()
                           -pb.loc[later,['grid_plan_kwh','load_forecast_kwh','pv_forecast_kwh']].to_numpy()).max())
        ea=np.load(ROOT/(path_prefix+'causality_original')/cfg['policy']/'decision_evidence.npz')
        eb=np.load(ROOT/(path_prefix+'causality_mutated')/cfg['policy']/'decision_evidence.npz')
        evidence=all(np.array_equal(ea[key][:2],eb[key][:2],equal_nan=True) for key in ea.files)
        checks.append({'policy':cfg['policy'],'prefix_rows':int(earlier.sum()),'prefix_difference_kwh':prefix,
                       'frozen_plan_difference_kwh':planned,'earlier_candidate_evidence_identical':evidence,
                       'next_day_response_kwh':response,'passed':prefix<=1e-6 and planned<=1e-6 and evidence and response>1e-4})
        print(checks[-1],flush=True)
    result={'passed':all(c['passed'] for c in checks),'mutation_cutoff':str(cutoff),
            'mutation':'Source copy: interval_start >= cutoff has load +800kWh, PV times .5; corresponding kW updated.',
            'scope':'Full source/forecast/decision/execution recomputation; not a formal all-input proof.',
            'checks':checks}
    save_json(WORK/'reports/q2_direct_v4'/('refinement_causality_validation.json' if args.refinement else 'causality_validation.json'),result)
    assert result['passed']
