import argparse
import json
import time

from policy import (WORK, ROOT, INPUTS, PLAN_COLUMNS, np, pd, decision, execute_interval, save_json)

SUMS = ['grid_plan_kwh', 'planned_cost_yuan', 'emergency_kwh', 'emergency_cost_yuan', 'total_cost_yuan',
        'charge_actual_kwh', 'discharge_actual_kwh', 'surplus_kwh', 'unused_grid_kwh', 'pv_curtailment_kwh']


def run_one(cfg, stage='runs', actual=None, archive=None):
    folder = ROOT / stage / cfg['policy']
    folder.mkdir(parents=True, exist_ok=False)
    save_json(folder / 'config.json', cfg)
    actual = pd.read_csv(INPUTS / 'actual_10min.csv', float_precision='round_trip') if actual is None else actual
    archive = pd.read_csv(ROOT / ('forecasts/'+cfg.get('forecast_model','linear_harmonic')+'.csv'), float_precision='round_trip') if archive is None else archive
    price = pd.read_csv(INPUTS / 'fixed_price.csv', float_precision='round_trip').price_yuan_per_kwh.to_numpy()
    frames, metadata, arrays = [], [], []
    energy = cfg['initial_energy_kwh']; wall = time.perf_counter()
    for i, day in enumerate(pd.date_range(cfg['start'], cfg['end'])):
        ds = str(day.date())
        f = archive.loc[archive.date == ds]
        load_hat, pv_hat = f.load_forecast_kwh.to_numpy(), f.pv_forecast_kwh.to_numpy()
        d = decision(archive, day, load_hat, pv_hat, price, energy, cfg)
        k = d['selected']; chosen = d['candidates'][k]; plan = d['plans'][k]
        current = actual.loc[actual.date == ds].copy().reset_index(drop=True)
        current['issue_time'] = str(day); current['forecast_history_end'] = str(day)
        current['dispatch_time'] = current.interval_end; current['decision_input_cutoff'] = current.interval_end
        current['price_yuan_per_kwh'] = price
        current['load_forecast_kwh'] = load_hat; current['pv_forecast_kwh'] = pv_hat
        current['risk_delta_kwh'] = d['risk_delta'][k]
        current['plan_load_kwh'] = np.maximum(load_hat + d['risk_delta'][k], 0.)
        current['plan_pv_kwh'] = pv_hat + np.maximum(-load_hat - d['risk_delta'][k], 0.)
        current['selected_index'] = k; current['selected_tau'] = chosen['tau']
        current['selected_terminal'] = str(chosen['terminal'])
        current['selected_terminal_energy_kwh'] = chosen['terminal_energy_kwh']
        for j, column in enumerate(PLAN_COLUMNS): current[column] = plan[:, j]
        initial = energy; events = []
        for t in range(144):
            event = execute_interval(float(plan[t, 0]), float(current.load_actual_kwh.iloc[t]),
                                     float(current.pv_actual_kwh.iloc[t]), energy, .9, .9)
            energy = event['energy_end_actual_kwh']; events.append(event)
        for column in events[0]: current[column] = [row[column] for row in events]
        current['planned_cost_yuan'] = price * current.grid_plan_kwh
        current['emergency_cost_yuan'] = 5 * price * current.emergency_kwh
        current['total_cost_yuan'] = current.planned_cost_yuan + current.emergency_cost_yuan
        frames.append(current)
        metadata.append({'date': ds, 'initial_energy_kwh': initial, 'scenario_source_dates': d['source_dates'],
                         'scenario_count': len(d['source_dates']), 'selected_index': k, 'candidates': d['candidates']})
        arrays.append(d)
        if i % 30 == 0: print(cfg['policy'], ds, 'cumulative_cost', sum(f.total_cost_yuan.sum() for f in frames), flush=True)
    frame = pd.concat(frames, ignore_index=True)
    frame.to_csv(folder / 'ledger.csv', index=False)
    frame[['date','slot_id','issue_time','forecast_history_end','load_forecast_kwh','pv_forecast_kwh',
           'risk_delta_kwh','plan_load_kwh','plan_pv_kwh','selected_index','selected_tau','selected_terminal',
           'selected_terminal_energy_kwh'] + PLAN_COLUMNS].to_csv(folder / 'plans.csv', index=False)
    daily = frame.groupby('date')[SUMS].sum()
    daily['energy_start_actual_kwh'] = frame.groupby('date').energy_start_actual_kwh.first()
    daily['energy_end_actual_kwh'] = frame.groupby('date').energy_end_actual_kwh.last()
    daily['selected_tau'] = frame.groupby('date').selected_tau.first()
    daily['selected_terminal'] = frame.groupby('date').selected_terminal.first()
    daily.to_csv(folder / 'daily.csv')
    max_s = max(len(a['source_dates']) for a in arrays)
    padded = lambda value, shape: np.pad(value, [(0, n - m) for m, n in zip(value.shape, shape)], constant_values=np.nan)
    np.savez_compressed(folder / 'decision_evidence.npz',
        plans=np.stack([a['plans'] for a in arrays]), risk_delta=np.stack([a['risk_delta'] for a in arrays]),
        scenario_net=np.stack([padded(a['scenarios'], (max_s,144)) for a in arrays]),
        emergency_fee=np.stack([padded(a['emergency_fee'], (len(a['plans']),max_s)) for a in arrays]),
        end_energy=np.stack([padded(a['end_energy'], (len(a['plans']),max_s)) for a in arrays]),
        score=np.stack([a['score'] for a in arrays]), ordinary=np.stack([a['ordinary'] for a in arrays]),
        selected_index=np.asarray([a['selected'] for a in arrays]))
    save_json(folder / 'decisions.json', {'plan_columns': PLAN_COLUMNS, 'days': metadata})
    statuses = [c['solver'] for day in metadata for c in day['candidates']]
    summary = {column: float(frame[column].sum()) for column in SUMS}
    summary.update(policy=cfg['policy'], days=len(metadata), intervals=len(frame),
        initial_energy_kwh=cfg['initial_energy_kwh'], final_energy_kwh=float(energy),
        inventory_adjusted_cost_yuan=summary['total_cost_yuan'] - float(price.mean()*.9)*(energy-cfg['initial_energy_kwh']),
        solver_count=len(statuses), solver_runtime_seconds=sum(s['runtime_seconds'] for s in statuses),
        solver_max_runtime_seconds=max(s['runtime_seconds'] for s in statuses),
        solver_max_mip_gap=max(s['mip_gap'] for s in statuses), solver_failures=0, solver_fallbacks=0,
        wall_seconds=time.perf_counter()-wall)
    save_json(folder / 'summary.json', summary)
    print('DONE', stage, cfg['policy'], summary['total_cost_yuan'], summary['emergency_cost_yuan'], flush=True)
    return frame


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['january','runs'])
    parser.add_argument('--policies', nargs='+')
    parser.add_argument('--extension', action='store_true')
    args = parser.parse_args()
    configs = json.loads((WORK / 'configs/q2_cost_aware_v2' / ('extension.json' if args.extension else 'experiments.json')).read_text())['runs']
    allowed = ['S_tau','S_terminal','S_joint','P_floor'] if args.stage == 'january' and not args.extension else [c['policy'] for c in configs]
    if args.policies:
        assert set(args.policies) <= set(allowed)
        allowed = args.policies
    for cfg in configs:
        if cfg['policy'] not in allowed: continue
        if args.stage == 'january': cfg = dict(cfg, start='2025-01-15', end='2025-01-18', initial_energy_kwh=6000.)
        run_one(cfg, args.stage)
