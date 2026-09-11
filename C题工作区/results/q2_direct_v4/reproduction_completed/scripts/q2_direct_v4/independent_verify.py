"""Independent v4 audits; imports no production forecast, dispatch, score or gradient."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[2]
ROOT = WORK / 'results/q2_direct_v4'
REPORT = WORK / 'reports/q2_direct_v4'
ETOL = 1e-6
CTOL = 1e-5


class Audit:
    def __init__(self):
        self.rows = []

    def check(self, name, value, **extra):
        value = np.asarray(value, dtype=bool)
        self.rows.append(dict(check=name, passed=bool(value.all()),
                              comparisons=int(value.size), failures=int((~value).sum()), **extra))

    def close(self, name, observed, expected, tol=ETOL):
        left, right = np.asarray(observed), np.asarray(expected)
        if left.shape != right.shape:
            self.check(name, False, observed_shape=list(left.shape), expected_shape=list(right.shape))
            return
        delta = np.abs(left-right)
        self.check(name, np.isfinite(delta) & (delta <= tol),
                   max_abs_error=float(delta.max(initial=0)), tolerance=tol)

    @property
    def passed(self):
        return all(row['passed'] for row in self.rows)


def csv(path):
    return pd.read_csv(path, float_precision='round_trip')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def npz(path):
    # Materialize once; repeated NpzFile indexing repeatedly decompresses full annual arrays.
    with np.load(path) as data:
        return {name: data[name] for name in data.files}


def replay(q, net, initial):
    """Scalar physical reconstruction from the original strict-priority equations."""
    columns = {k: [] for k in ('charge', 'discharge', 'emergency', 'surplus', 'start', 'end')}
    energy = float(initial)
    for buy, demand in zip(np.asarray(q), np.asarray(net)):
        charge = discharge = emergency = surplus = 0.
        start = energy
        if buy >= demand:
            charge = min(buy-demand, 5000/6, max(0., (10800-energy)/.9))
            surplus = buy-demand-charge
        else:
            discharge = min(demand-buy, 5000/6, max(0., .9*(energy-1200)))
            emergency = demand-buy-discharge
        energy += .9*charge-discharge/.9
        for key, value in zip(columns, (charge, discharge, emergency, surplus, start, energy)):
            columns[key].append(value)
    return {key: np.asarray(value) for key, value in columns.items()}


def forward_score_gradient(q, scenarios, price, initial, mu, kappa=5.):
    """Independent forward sensitivities, deliberately different from reverse AD.

    A branch derivative is returned at ties; only non-tied points possess the
    ordinary gradient checked by centered finite differences.
    """
    q, scenarios, price = map(np.asarray, (q, scenarios, price))
    count, horizon = scenarios.shape
    states = np.full(count, initial, dtype=float)
    sensitivities = np.zeros((count, horizon))
    emergency = np.zeros(count)
    emergency_gradient = np.zeros((count, horizon))
    min_margin = float('inf')
    for t in range(horizon):
        basis = np.zeros(horizon); basis[t] = 1.
        delta = q[t]-scenarios[:, t]
        min_margin = min(min_margin, float(abs(delta).min()))
        for s in range(count):
            if delta[s] >= 0:
                caps = np.array((delta[s], 5000/6, max(0., (10800-states[s])/.9)))
                branch = int(np.argmin(caps))
                min_margin = min(min_margin, float(np.sort(caps)[1]-caps[branch]))
                dc = basis if branch == 0 else (-sensitivities[s]/.9 if branch == 2 else np.zeros(horizon))
                states[s] += .9*caps[branch]
                sensitivities[s] += .9*dc
            else:
                caps = np.array((-delta[s], 5000/6, max(0., .9*(states[s]-1200))))
                branch = int(np.argmin(caps))
                min_margin = min(min_margin, float(np.sort(caps)[1]-caps[branch]))
                dd = -basis if branch == 0 else (.9*sensitivities[s] if branch == 2 else np.zeros(horizon))
                emergency[s] += kappa*price[t]*(-delta[s]-caps[branch])
                emergency_gradient[s] += kappa*price[t]*(-basis-dd)
                states[s] -= caps[branch]/.9
                sensitivities[s] -= dd/.9
    score = float(q@price+np.mean(emergency-mu*(states-initial)))
    gradient = price+np.mean(emergency_gradient-mu*sensitivities, axis=0)
    return score, gradient, min_margin


def scenario_metrics(q, scenarios, price, initial, mu, kappa=5.):
    """Cash-price scenario recourse from scalar replay, independent of gradients."""
    emergency, terminal = [], []
    for path in scenarios:
        out = replay(q, path, initial)
        emergency.append(float(5*price@out['emergency']))
        terminal.append(float(out['end'][-1]))
    emergency, terminal = np.asarray(emergency), np.asarray(terminal)
    ordinary = float(price@q)
    return dict(ordinary=ordinary, emergency_fee=emergency, end_energy=terminal,
                score=float(ordinary+np.mean(kappa/5*emergency-mu*(terminal-initial))))


def all_scenario_metrics(q, scenarios, price, initial, mu, kappa):
    """Equation reconstruction for the full candidate-by-scenario table."""
    count, samples = len(q), len(scenarios)
    state = np.full((count, samples), initial)
    fee = np.zeros((count, samples))
    for t in range(144):
        excess = q[:, t, None]-scenarios[None, :, t]
        charge = np.minimum(np.maximum(excess, 0.), np.minimum(5000/6, np.maximum((10800-state)/.9, 0.)))
        discharge = np.minimum(np.maximum(-excess, 0.), np.minimum(5000/6, np.maximum((state-1200)*.9, 0.)))
        deficit = np.maximum(-excess, 0.)-discharge
        fee += 5*price[t]*deficit
        state = state+.9*charge-discharge/.9
    ordinary = q@price
    return dict(ordinary=ordinary, emergency_fee=fee, end_energy=state,
                score=ordinary+np.mean(kappa/5*fee-mu*(state-initial), axis=1))


def rebuild_forecasts(source):
    """Re-estimate each historical issue from its completed-day prefix only."""
    dates = pd.to_datetime(source.date.unique())
    loads = source.load_actual_kwh.to_numpy().reshape(len(dates), 144)
    pv = source.pv_actual_kwh.to_numpy().reshape(len(dates), 144)
    angle = 2*np.pi*np.arange(144)/144
    bases = {h: np.column_stack([np.ones(144)]+[f(k*angle) for k in range(1, h+1) for f in (np.sin, np.cos)]) for h in (2, 3)}
    forecast = []
    for day in range(1, len(dates)):
        lp = loads[day-7 if day >= 7 else day-1].copy()
        pp = pv[day-1].copy()
        if day >= 14:
            first = max(7, day-28)
            def design(k):
                weekdays = np.broadcast_to(np.array([dates[k].weekday() == j for j in range(1, 7)], dtype=float), (144, 6))
                return np.column_stack((bases[2], loads[k-1]/1000, loads[k-7]/1000, weekdays))
            matrix = np.vstack([design(k) for k in range(first, day)])
            coefficients = np.linalg.lstsq(matrix, loads[first:day].ravel(), rcond=None)[0]
            lp = np.maximum(design(day)@coefficients, 0.)
        if day >= 2:
            matrix = np.tile(bases[3], (min(day, 7), 1))
            values = pv[max(0, day-7):day].ravel()
            coefficients = np.linalg.lstsq(matrix, values, rcond=None)[0]
            residual = values-matrix@coefficients
            denom = float(residual[:-1]@residual[:-1])
            phi = np.clip(float(residual[:-1]@residual[1:])/denom if denom > 1e-12 else 0., -.99, .99)
            pp = np.maximum(bases[3]@coefficients+residual[-1]*phi**np.arange(1, 145), 0.)
        forecast.append(np.column_stack((lp, pp)))
    return np.concatenate(forecast)


def audit_forecast(a, source, archive, tag):
    source = source.loc[source.date <= archive.date.iloc[-1]].reset_index(drop=True)
    truth = source.loc[source.date >= archive.date.iloc[0]].reset_index(drop=True)
    a.check(tag+'.keys', np.array_equal(archive[['date', 'slot_id']], truth[['date', 'slot_id']]))
    a.check(tag+'.dates_unique', ~archive[['date', 'slot_id']].duplicated())
    a.close(tag+'.load_source', archive.load_actual_kwh.to_numpy(), truth.load_actual_kwh.to_numpy())
    a.close(tag+'.pv_source', archive.pv_actual_kwh.to_numpy(), truth.pv_actual_kwh.to_numpy())
    forecasts = rebuild_forecasts(source)
    a.close(tag+'.load_forecast', archive.load_forecast_kwh.to_numpy(), forecasts[:, 0])
    a.close(tag+'.pv_forecast', archive.pv_forecast_kwh.to_numpy(), forecasts[:, 1])
    residual = truth.load_actual_kwh.to_numpy()-truth.pv_actual_kwh.to_numpy()-forecasts[:, 0]+forecasts[:, 1]
    a.close(tag+'.net_residual', archive.net_residual_kwh.to_numpy(), residual)
    issue = pd.to_datetime(archive.issue_time)
    day = pd.to_datetime(archive.date)
    a.check(tag+'.midnight_issue', issue == day)
    a.check(tag+'.history_cutoff', pd.to_datetime(archive.history_end) <= day)
    a.check(tag+'.residual_release', pd.to_datetime(archive.residual_available_time) == day+pd.Timedelta(days=1))


def sources_audit():
    a = Audit()
    source = csv(ROOT/'inputs/actual_10min.csv')
    a.check('source.coverage', len(source) == 365*144)
    a.check('source.ordered_keys', np.array_equal(source[['date', 'slot_id']], source.sort_values(['date', 'slot_id'])[['date', 'slot_id']]))
    a.check('source.unique_keys', ~source[['date', 'slot_id']].duplicated())
    a.check('source.complete_days', source.groupby('date').slot_id.apply(list).apply(lambda values: values == list(range(1, 145))))
    a.check('source.nonnegative', np.isfinite(source[['load_actual_kwh', 'pv_actual_kwh']]) & (source[['load_actual_kwh', 'pv_actual_kwh']] >= 0.))
    a.close('source.load_power_to_energy', source.load_actual_kwh, source.load_actual_kw/6)
    a.close('source.pv_power_to_energy', source.pv_actual_kwh, source.pv_actual_kw/6)
    a.check('source.ten_minutes', pd.to_datetime(source.interval_end)-pd.to_datetime(source.interval_start) == pd.Timedelta(minutes=10))
    a.check('source.availability', pd.to_datetime(source.available_time) == pd.to_datetime(source.interval_end))
    originals = {'actual_10min.csv': WORK/'data/processed/actual_10min.csv',
                 'fixed_price.csv': WORK/'data/processed/fixed_price.csv',
                 'model_baseline.json': WORK/'configs/model_baseline.json',
                 'q2_baseline.json': WORK/'configs/q2_baseline.json',
                 'problem_text.txt': WORK/'data/interim/problem_text.txt'}
    for name, original in originals.items():
        a.check('snapshot.'+name, original.exists() and digest(ROOT/'inputs'/name) == digest(original))
    audit_forecast(a, source, csv(ROOT/'forecasts/linear_harmonic.csv'), 'forecast')
    return a, dict(source_rows=len(source), forecast_days=364)


def ledger_audit(a, folder, source, initial, tag):
    frame = csv(folder/'ledger.csv')
    plans = csv(folder/'plans.csv')
    truth = source.loc[source.date.between(frame.date.iloc[0], frame.date.iloc[-1])].reset_index(drop=True)
    keys = ['date', 'slot_id']
    a.check(tag+'.source_keys', np.array_equal(frame[keys], truth[keys]))
    a.check(tag+'.plan_keys', np.array_equal(frame[keys], plans[keys]))
    a.check(tag+'.unique_keys', ~frame[keys].duplicated())
    for field in ('load_actual_kwh', 'pv_actual_kwh'):
        a.close(tag+'.source_'+field, frame[field].to_numpy(), truth[field].to_numpy())
    q = frame.grid_plan_kwh.to_numpy()
    price = truth.fixed_price_yuan_per_kwh.to_numpy()
    net = (truth.load_actual_kwh-truth.pv_actual_kwh).to_numpy()
    a.close(tag+'.fixed_contract', q, plans.grid_plan_kwh.to_numpy())
    a.close(tag+'.fixed_prices', frame.price_yuan_per_kwh.to_numpy(), price)
    a.check(tag+'.nonnegative_contract', np.isfinite(q) & (q >= -ETOL))
    a.check(tag+'.midnight_issue', pd.to_datetime(frame.issue_time) == pd.to_datetime(frame.date))
    if 'forecast_history_end' in frame:
        a.check(tag+'.information_cutoff', pd.to_datetime(frame.forecast_history_end) <= pd.to_datetime(frame.date))
    out = replay(q, net, initial)
    mapping = dict(charge='charge_actual_kwh', discharge='discharge_actual_kwh', emergency='emergency_kwh',
                   surplus='surplus_kwh', start='energy_start_actual_kwh', end='energy_end_actual_kwh')
    for key, column in mapping.items():
        a.close(tag+'.greedy_'+key, frame[column].to_numpy(), out[key])
    a.check(tag+'.soc_range', (frame.energy_end_actual_kwh >= 1200-ETOL) & (frame.energy_end_actual_kwh <= 10800+ETOL))
    a.check(tag+'.charge_power', (frame.charge_actual_kwh >= -ETOL) & (frame.charge_actual_kwh <= 5000/6+ETOL))
    a.check(tag+'.discharge_power', (frame.discharge_actual_kwh >= -ETOL) & (frame.discharge_actual_kwh <= 5000/6+ETOL))
    a.check(tag+'.mutual_exclusion', (frame.charge_actual_kwh <= ETOL) | (frame.discharge_actual_kwh <= ETOL))
    a.close(tag+'.balance', q+frame.pv_actual_kwh+frame.discharge_actual_kwh+frame.emergency_kwh,
            frame.load_actual_kwh+frame.charge_actual_kwh+frame.surplus_kwh)
    a.close(tag+'.soc_recurrence', frame.energy_end_actual_kwh-frame.energy_start_actual_kwh,
            .9*frame.charge_actual_kwh-frame.discharge_actual_kwh/.9)
    a.close(tag+'.cross_interval', frame.energy_start_actual_kwh.to_numpy(), np.r_[initial, frame.energy_end_actual_kwh.to_numpy()[:-1]])
    unused = np.minimum(q, out['surplus'])
    a.close(tag+'.unused_grid', frame.unused_grid_kwh.to_numpy(), unused)
    a.close(tag+'.pv_curtailment', frame.pv_curtailment_kwh.to_numpy(), out['surplus']-unused)
    ordinary, emergency = price*q, 5*price*out['emergency']
    for column, values in (('planned_cost_yuan', ordinary), ('emergency_cost_yuan', emergency), ('total_cost_yuan', ordinary+emergency)):
        a.close(tag+'.'+column, frame[column].to_numpy(), values, CTOL)
    daily = csv(folder/'daily.csv')
    sums = ['grid_plan_kwh', 'planned_cost_yuan', 'emergency_kwh', 'emergency_cost_yuan', 'total_cost_yuan',
            'charge_actual_kwh', 'discharge_actual_kwh', 'surplus_kwh', 'unused_grid_kwh', 'pv_curtailment_kwh']
    rebuilt = pd.DataFrame(dict(date=frame.date, grid_plan_kwh=q, planned_cost_yuan=ordinary,
                                emergency_kwh=out['emergency'], emergency_cost_yuan=emergency,
                                total_cost_yuan=ordinary+emergency, charge_actual_kwh=out['charge'],
                                discharge_actual_kwh=out['discharge'], surplus_kwh=out['surplus'],
                                unused_grid_kwh=unused, pv_curtailment_kwh=out['surplus']-unused))
    expected = rebuilt.groupby('date', sort=True)[sums].sum()
    a.check(tag+'.daily_dates', daily.date.tolist() == expected.index.tolist())
    for field in sums:
        a.close(tag+'.daily_'+field, daily[field].to_numpy(), expected[field].to_numpy(), CTOL if field.endswith('yuan') else ETOL)
    metrics = {field: float(rebuilt[field].sum()) for field in sums}
    for field, value in metrics.items():
        a.close(tag+'.independent_annual_'+field, float(frame[field].sum()), value, CTOL if field.endswith('yuan') else ETOL)
    metrics.update(initial_energy_kwh=initial, final_energy_kwh=float(out['end'][-1]),
                   inventory_adjusted_cost_yuan=float((ordinary+emergency).sum()-.6895775*(out['end'][-1]-initial)),
                   days=int(frame.date.nunique()), intervals=len(frame))
    summary = json.loads((folder/'summary.json').read_text())
    for field, value in metrics.items():
        if field in summary:
            a.close(tag+'.summary_'+field, summary[field], value, CTOL if field.endswith('yuan') else ETOL)
    metrics['emergency_cap_passed'] = metrics['emergency_cost_yuan'] <= 1000000.
    return metrics


def references_audit():
    a = Audit(); source = csv(ROOT/'inputs/actual_10min.csv')
    metrics = {}
    for name in ('B0', 'B1', 'P_floor', 'X_strong_morning85'):
        metrics[name] = ledger_audit(a, ROOT/'references'/name, source, 7268.4231640740745, name)
    a.close('reference.best_total', metrics['X_strong_morning85']['total_cost_yuan'], 13994282.258970976, CTOL)
    a.close('reference.best_emergency', metrics['X_strong_morning85']['emergency_cost_yuan'], 644292.1650026435, CTOL)
    return a, metrics


def candidate_audit(a, folder, archive, tag):
    config = json.loads((folder/'config.json').read_text())
    metadata = json.loads((folder/'decisions.json').read_text())
    ev = npz(folder/'decision_evidence.npz')
    initializer = ev['initializer_plan'] if 'initializer_plan' in ev else npz(folder/'initializer_certificate.npz')['initializer_plan']
    plans = csv(folder/'plans.csv'); ledger = csv(folder/'ledger.csv')
    price = csv(ROOT/'inputs/fixed_price.csv').price_yuan_per_kwh.to_numpy()
    labels = ['profile_start', 'profile_incumbent', 'profile_final', 'point_start', 'point_incumbent', 'point_final']
    a.check(tag+'.labels', metadata['candidate_labels'] == labels)
    dates = pd.date_range(config['start'], config['end']).strftime('%Y-%m-%d').tolist()
    a.check(tag+'.decision_dates', [d['date'] for d in metadata['days']] == dates)
    a.check(tag+'.q_dimensions', ev['q'].shape == (len(dates), 6, 144))
    a.check(tag+'.q_nonnegative_finite', np.isfinite(ev['q']) & (ev['q'] >= -ETOL))
    a.check(tag+'.risk_dimensions', ev['risk_delta'].shape == (len(dates), 144))
    a.check(tag+'.initializer_dimensions', initializer.shape == (len(dates), 144, 7))
    successes = nfev = 0
    for i, day in enumerate(metadata['days']):
        date = day['date']; prefix = tag+'.'+date
        p = plans.loc[plans.date == date].reset_index(drop=True)
        live = ledger.loc[ledger.date == date].reset_index(drop=True)
        issued = archive.loc[archive.date == date].reset_index(drop=True)
        for field in ('load_forecast_kwh', 'pv_forecast_kwh'):
            a.close(prefix+'.issued_'+field, p[field].to_numpy(), issued[field].to_numpy())
        start = float(live.energy_start_actual_kwh.iloc[0])
        a.close(prefix+'.decision_initial', day['initial_energy_kwh'], start)
        hist = archive.loc[(pd.to_datetime(archive.date) >= pd.Timestamp(date)-pd.Timedelta(days=config['scenario_window']))
                           & (archive.date < date)].sort_values(['date', 'slot_id'])
        source_dates = sorted(hist.date.unique().tolist()); ns = len(source_dates)
        a.check(prefix+'.scenario_dates', day['scenario_source_dates'] == source_dates)
        a.check(prefix+'.scenario_count', day['scenario_count'] == ns and ns >= 7)
        a.check(prefix+'.scenario_availability', pd.to_datetime(hist.residual_available_time) <= pd.Timestamp(date))
        forecast_net = issued.load_forecast_kwh.to_numpy()-issued.pv_forecast_kwh.to_numpy()
        scenarios = hist.net_residual_kwh.to_numpy().reshape(ns, 144)+forecast_net
        a.close(prefix+'.scenario_net', ev['scenario_net'][i, :ns], scenarios)
        for key in ('scenario_net', 'emergency_fee', 'end_energy'):
            tail = ev[key][i, ns:] if key == 'scenario_net' else ev[key][i, :, ns:]
            a.check(prefix+'.padding_'+key, np.isnan(tail))
        risk = archive.loc[(pd.to_datetime(archive.date) >= pd.Timestamp(date)-pd.Timedelta(days=28)) & (archive.date < date)]
        values = risk.net_residual_kwh.to_numpy().reshape(-1, 24, 6).transpose(1, 0, 2).reshape(24, -1)
        taus = [.85 if 9 <= h < 11 else .65 if 11 <= h < 18 else .95 if 18 <= h < 22 else .8 for h in range(24)]
        delta = np.repeat([np.quantile(values[h], taus[h], method='linear') for h in range(24)], 6)
        a.close(prefix+'.risk_delta_evidence', ev['risk_delta'][i], delta)
        a.close(prefix+'.risk_delta_plan', p.risk_delta_kwh.to_numpy(), delta)
        q = ev['q'][i]
        a.close(prefix+'.point_initializer', q[3], np.maximum(forecast_net, 0.))
        a.close(prefix+'.profile_initializer_cost', float(q[0]@price), day['milp_initializer']['objective_yuan'], CTOL)
        grid, ch, dis, s0, s1, spill, mode = initializer[i].T
        a.close(prefix+'.initializer_q', grid, q[0])
        a.close(prefix+'.initializer_balance', grid+dis-ch-spill, forecast_net+delta)
        a.close(prefix+'.initializer_recurrence', s1-s0, .9*ch-dis/.9)
        a.close(prefix+'.initializer_continuity', s0, np.r_[start, s1[:-1]])
        a.close(prefix+'.initializer_terminal', s1[-1], 1200.)
        a.check(prefix+'.initializer_nonnegative', np.array([grid, ch, dis, spill]) >= -ETOL)
        a.check(prefix+'.initializer_soc_bounds', (np.r_[s0, s1] >= 1200-ETOL) & (np.r_[s0, s1] <= 10800+ETOL))
        a.check(prefix+'.initializer_charge_power', ch <= mode*(5000/6)+ETOL)
        a.check(prefix+'.initializer_discharge_power', dis <= (1-mode)*(5000/6)+ETOL)
        a.check(prefix+'.initializer_modes', (abs(mode-np.round(mode)) <= ETOL) & (mode >= -ETOL) & (mode <= 1+ETOL))
        adjusted_pv = issued.pv_forecast_kwh.to_numpy()+np.maximum(-issued.load_forecast_kwh.to_numpy()-delta, 0.)
        a.check(prefix+'.initializer_pv_spill_bound', spill <= adjusted_pv+ETOL)
        profile_replay = replay(q[0], forecast_net+delta, start)
        a.close(prefix+'.profile_initializer_no_shortage', profile_replay['emergency'], np.zeros(144))
        a.check(prefix+'.initializer_milp_status', day['milp_initializer']['status'] == 'Optimal')
        metrics = all_scenario_metrics(q, scenarios, price, start, config['mu'], config['kappa'])
        for key in ('ordinary', 'score', 'emergency_fee', 'end_energy'):
            observed = ev[key][i, :, :ns] if key in ('emergency_fee', 'end_energy') else ev[key][i]
            a.close(prefix+'.candidate_'+key, observed, metrics[key], ETOL if key == 'end_energy' else CTOL)
        chosen = int(np.flatnonzero(metrics['score'] <= metrics['score'].min()+1e-8)[0])
        a.check(prefix+'.chosen', chosen == day['selected_index'] == ev['selected_index'][i])
        a.check(prefix+'.chosen_label', (p.selected_candidate == labels[chosen]).all())
        a.close(prefix+'.chosen_q', p.grid_plan_kwh.to_numpy(), q[chosen])
        nominal = replay(q[chosen], forecast_net, start)
        for key, column in dict(charge='charge_kwh', discharge='discharge_kwh', emergency='emergency_kwh',
                                surplus='surplus_kwh', start='energy_start_kwh', end='energy_end_kwh').items():
            a.close(prefix+'.nominal_'+key, live['forecast_'+column].to_numpy(), nominal[key])
        a.check(prefix+'.optimizer_count', len(day['optimizer']) == 2)
        for j, opt in enumerate(day['optimizer']):
            trace = np.asarray(opt['evaluation_score_yuan'])
            offset = 3*j
            a.check(prefix+f'.opt{j}.trace_length', len(trace) == opt['nfev'] == opt['njev'])
            a.check(prefix+f'.opt{j}.trace_finite', np.isfinite(trace))
            a.close(prefix+f'.opt{j}.start_score', trace[0], metrics['score'][offset], CTOL)
            a.close(prefix+f'.opt{j}.incumbent_trace', trace.min(), opt['incumbent_score_yuan'], CTOL)
            a.close(prefix+f'.opt{j}.incumbent_candidate', metrics['score'][offset+1], trace.min(), CTOL)
            a.check(prefix+f'.opt{j}.incumbent_dominates_endpoints', metrics['score'][offset+1] <= min(metrics['score'][offset], metrics['score'][offset+2])+CTOL)
            a.check(prefix+f'.opt{j}.termination_recorded', isinstance(opt['success'], bool) and isinstance(opt['status'], int) and bool(opt['message']))
            successes += int(opt['success']); nfev += opt['nfev']
    summary = json.loads((folder/'summary.json').read_text())
    a.check(tag+'.summary_optimizer_count', summary['optimizer_count'] == 2*len(dates))
    a.check(tag+'.summary_optimizer_successes', summary['optimizer_success_count'] == successes)
    a.check(tag+'.summary_optimizer_nfev', summary['optimizer_nfev'] == nfev)
    times = [opt['wall_seconds'] for day in metadata['days'] for opt in day['optimizer'] if 'wall_seconds' in opt]
    if times:
        a.check(tag+'.optimizer_times_complete', len(times) == 2*len(dates))
        a.check(tag+'.optimizer_times_valid', np.isfinite(times) & (np.asarray(times) >= 0.))
        a.close(tag+'.optimizer_total_time', summary['optimizer_total_wall_seconds'], sum(times), 1e-9)
        a.close(tag+'.optimizer_max_time', summary['optimizer_max_wall_seconds'], max(times), 1e-9)
        mtimes = [day['milp_initializer']['runtime_seconds'] for day in metadata['days']]
        a.close(tag+'.milp_total_time', summary['milp_total_runtime_seconds'], sum(mtimes), 1e-9)
        a.close(tag+'.milp_max_time', summary['milp_max_runtime_seconds'], max(mtimes), 1e-9)
    return dict(days=len(dates), candidates=6*len(dates), optimizer_count=2*len(dates), optimizer_successes=successes,
                optimizer_nfev=nfev, profile_full_milp_path_verified=True)


def runs_audit(stage, config_name='experiments.json'):
    a = Audit(); source = csv(ROOT/'inputs/actual_10min.csv'); archive = csv(ROOT/'forecasts/linear_harmonic.csv')
    metrics = {}
    configs = json.loads((WORK/'configs/q2_direct_v4'/config_name).read_text())['runs']
    for config in configs:
        name = config['policy']; folder = ROOT/stage/name
        expected = dict(config)
        if stage == 'january':
            expected.update(start='2025-01-15', end='2025-01-18', initial_energy_kwh=6000.)
        a.check(name+'.frozen_config', json.loads((folder/'config.json').read_text()) == expected)
        metrics[name] = ledger_audit(a, folder, source, expected['initial_energy_kwh'], name)
        metrics[name].update(candidate_audit(a, folder, archive, name))
    return a, metrics


def gradient_audit():
    a = Audit(); z = np.load(ROOT/'gradient_fixtures.npz')
    q, net, price = (z[k] for k in ('q', 'scenarios', 'price'))
    initial, kappa, mu = (float(z[k]) for k in ('initial', 'kappa', 'mu'))
    score, gradient, margin = forward_score_gradient(q, net, price, initial, mu, kappa)
    a.close('gradient.independent_score', z['score'], score, CTOL)
    a.close('gradient.forward_vs_reverse', z['gradient'], gradient, 1e-9)
    delta = 1e-4; numeric = []
    a.check('gradient.non_kink_margin', margin > delta*4)
    for t in range(len(q)):
        plus, minus = q.copy(), q.copy(); plus[t] += delta; minus[t] -= delta
        numeric.append((scenario_metrics(plus, net, price, initial, mu, kappa)['score']
                        -scenario_metrics(minus, net, price, initial, mu, kappa)['score'])/(2*delta))
    a.close('gradient.finite_difference', gradient, np.asarray(numeric), 5e-6)
    return a, dict(minimum_branch_margin_kwh=margin, finite_difference_step_kwh=delta,
                   maximum_finite_difference_error=float(abs(gradient-numeric).max()))


def causality_audit(config_name='experiments.json'):
    a = Audit(); inputs = ROOT/'causality_inputs'
    original = csv(ROOT/'inputs/actual_10min.csv')
    mutated = csv(inputs/'future_mutated_actual.csv')
    expected = original.copy()
    cutoff = pd.Timestamp('2025-01-25T12:00:00')
    later = pd.to_datetime(expected.interval_start) >= cutoff
    expected.loc[later, 'load_actual_kwh'] += 800.
    expected.loc[later, 'pv_actual_kwh'] *= .5
    for kind in ('load', 'pv'):
        expected[kind+'_actual_kw'] = 6*expected[kind+'_actual_kwh']
    a.check('mutation.keys', np.array_equal(mutated[['date', 'slot_id']], expected[['date', 'slot_id']]))
    for field in expected.select_dtypes(include='number'):
        a.close('mutation.'+field, mutated[field].to_numpy(), expected[field].to_numpy())
    archives = [csv(inputs/name) for name in ('original_forecasts.csv', 'future_mutated_forecasts.csv')]
    for label, source, archive in zip(('original', 'mutated'), (original, mutated), archives):
        audit_forecast(a, source, archive, label+'.forecast')
    metrics = {}
    for config in json.loads((WORK/'configs/q2_direct_v4'/config_name).read_text())['runs']:
        name = config['policy']; folders = [ROOT/stage/name for stage in ('causality_original', 'causality_mutated')]
        for label, folder, source, archive in zip(('original', 'mutated'), folders, (original, mutated), archives):
            test_config = dict(config, start='2025-01-24', end='2025-01-26', initial_energy_kwh=6000.)
            a.check(name+'.'+label+'.config', json.loads((folder/'config.json').read_text()) == test_config)
            ledger_audit(a, folder, source, 6000., name+'.'+label)
            candidate_audit(a, folder, archive, name+'.'+label)
        left, right = [csv(folder/'ledger.csv') for folder in folders]
        prefix = pd.to_datetime(left.interval_start) < cutoff
        a.check(name+'.prefix_rows', int(prefix.sum()) == 216)
        numeric = left.select_dtypes(include='number').columns
        a.close(name+'.physical_prefix', left.loc[prefix, numeric].to_numpy(), right.loc[prefix, numeric].to_numpy())
        plan_left, plan_right = [csv(folder/'plans.csv') for folder in folders]
        frozen = plan_left.date <= '2025-01-25'
        a.close(name+'.frozen_plan', plan_left.loc[frozen, 'grid_plan_kwh'].to_numpy(), plan_right.loc[frozen, 'grid_plan_kwh'].to_numpy())
        decision_left, decision_right = [npz(folder/'decision_evidence.npz') for folder in folders]
        a.check(name+'.candidate_evidence_keys', list(decision_left) == list(decision_right))
        for field in decision_left:
            a.check(name+'.frozen_candidate_'+field, np.array_equal(decision_left[field][:2], decision_right[field][:2], equal_nan=True))
        future_day = plan_left.date == '2025-01-26'
        response_columns = ['grid_plan_kwh', 'load_forecast_kwh', 'pv_forecast_kwh']
        change = abs(plan_left.loc[future_day, response_columns].to_numpy()-plan_right.loc[future_day, response_columns].to_numpy())
        a.check(name+'.next_day_positive_response', change.max() > 1e-4)
        # Verify the first two days' numerical optimizer evidence too; elapsed times may differ.
        meta_left, meta_right = [json.loads((folder/'decisions.json').read_text()) for folder in folders]
        for i in range(2):
            for j in range(2):
                ml = meta_left['days'][i]['optimizer'][j]; mr = meta_right['days'][i]['optimizer'][j]
                for field in ('success', 'status', 'nit', 'nfev', 'njev', 'evaluation_score_yuan', 'incumbent_score_yuan'):
                    a.check(name+f'.frozen_optimizer_{i}_{j}_'+field, ml[field] == mr[field])
        metrics[name] = dict(prefix_rows=216, maximum_prefix_error=float(abs(left.loc[prefix, numeric].to_numpy()-right.loc[prefix, numeric].to_numpy()).max()),
                             next_day_response_kwh=float(change.max()), frozen_q_and_candidate_evidence=True)
    return a, metrics


def analysis_audit(all_runs=False):
    a = Audit()
    config = json.loads((WORK/'configs/q2_direct_v4/experiments.json').read_text())
    output = ROOT/'analysis_all' if all_runs else ROOT
    if all_runs:
        config['runs'] += json.loads((WORK/'configs/q2_direct_v4/refinement.json').read_text())['runs']
    refs = ['B0', 'B1', 'P_floor', 'X_strong_morning85']
    direct = [r['policy'] for r in config['runs']]; names = refs+direct
    fields = ['planned_cost_yuan', 'emergency_cost_yuan', 'total_cost_yuan']
    aggregates = fields+['emergency_kwh', 'grid_plan_kwh', 'unused_grid_kwh']
    table = csv(output/'comparison_all.csv').set_index('policy')
    a.check('comparison.policies', table.index.tolist() == names)
    daily = {}; frames = {}; expected = {}
    for name in names:
        folder = ROOT/('references' if name in refs else 'runs')/name
        frame = csv(folder/'ledger.csv'); frames[name] = frame
        daily[name] = frame.groupby('date')[aggregates].sum()
        total = float(frame.total_cost_yuan.sum()); emergency = float(frame.emergency_cost_yuan.sum())
        final = float(frame.energy_end_actual_kwh.iloc[-1])
        expected[name] = {key: float(frame[key].sum()) for key in aggregates}
        expected[name].update(final_energy_kwh=final,
            inventory_adjusted_cost_yuan=total-.6895775*(final-7268.4231640740745),
            unused_grid_cost_yuan=float((frame.price_yuan_per_kwh*frame.unused_grid_kwh).sum()),
            emergency_share_load=float(frame.emergency_kwh.sum()/frame.load_actual_kwh.sum()),
            emergency_at_soc_floor_share=float(frame.loc[frame.energy_end_actual_kwh <= 1200+ETOL, 'emergency_cost_yuan'].sum()/emergency),
            emergency_days=int(frame.loc[frame.emergency_kwh > ETOL, 'date'].nunique()),
            emergency_intervals=int((frame.emergency_kwh > ETOL).sum()))
        for field, value in expected[name].items():
            a.close(name+'.comparison_'+field, table.loc[name, field], value, CTOL if field.endswith('yuan') else ETOL)
        a.check(name+'.cap', bool(table.loc[name, 'passes_emergency_cap']) == (emergency <= 1000000.))
        a.check(name+'.improvement', bool(table.loc[name, 'passes_improvement']) == (emergency <= 1000000. and total < config['reference_total_yuan']-CTOL))
    for name in names:
        for baseline in refs:
            for field, label in zip(fields+['inventory_adjusted_cost_yuan'], ['ordinary', 'emergency', 'total', 'inventory_adjusted']):
                a.close(name+'.saving_'+label+'_vs_'+baseline, table.loc[name, f'{label}_saving_vs_{baseline}_yuan'],
                        expected[baseline][field]-expected[name][field], CTOL)
    for frequency, key in [('daily', 'date'), ('monthly', 'month'), ('hourly', 'hour')]:
        published = csv(output/(frequency+'.csv'))
        a.check(frequency+'.policy_coverage', set(published.policy) == set(names))
        for name in names:
            f = frames[name]
            group = f.date if key == 'date' else f.date.str[:7] if key == 'month' else (f.slot_id-1)//6
            truth = f.assign(**{key: group}).groupby(key)[aggregates].sum()
            got = published.loc[published.policy == name].set_index(key)
            a.check(name+'.'+frequency+'_keys', got.index.tolist() == truth.index.tolist())
            a.close(name+'.'+frequency+'_values', got[aggregates].to_numpy(), truth.to_numpy(), CTOL)
    paired = csv(output/'paired_daily.csv'); counts = csv(output/'win_loss_counts.csv'); boot = csv(output/'block_bootstrap.csv')
    rng = np.random.default_rng(config['bootstrap_seed'])
    for name in direct:
        for baseline in refs:
            diff = daily[baseline][fields]-daily[name][fields]
            got = paired.loc[(paired.policy == name) & (paired.baseline == baseline)].set_index('date')
            a.check(name+'.pair_dates_'+baseline, got.index.tolist() == diff.index.tolist())
            a.close(name+'.pair_values_'+baseline, got[fields].to_numpy(), diff.to_numpy(), CTOL)
            row = counts.loc[(counts.policy == name) & (counts.baseline == baseline)]
            a.check(name+'.counts_unique_'+baseline, len(row) == 1)
            d, e = diff.total_cost_yuan, diff.emergency_cost_yuan
            expected_counts = dict(total_winning_days=int((d > CTOL).sum()), total_losing_days=int((d < -CTOL).sum()),
                emergency_worse_days=int((e < -CTOL).sum()), positive_total_months=int((d.groupby(d.index.str[:7]).sum() > CTOL).sum()),
                emergency_worse_months=int((e.groupby(e.index.str[:7]).sum() < -CTOL).sum()))
            for field, value in expected_counts.items():
                a.check(name+'.'+baseline+'.'+field, int(row.iloc[0][field]) == value)
            if baseline != 'X_strong_morning85':
                continue
            for block in config['bootstrap_blocks']:
                x = diff.to_numpy(); n = len(x); replicates = config['bootstrap_replicates']
                starts = rng.integers(n, size=(replicates, (n+block-1)//block))
                indices = (starts[..., None]+np.arange(block)) % n
                values = x[indices.reshape(replicates, -1)[:, :n]].sum(axis=1)
                low, high = np.quantile(values, [.025, .975], axis=0)
                for j, field in enumerate(fields):
                    row = boot.loc[(boot.policy == name) & (boot.baseline == baseline) & (boot.block_days == block) & (boot.component == field)]
                    a.check(name+f'.bootstrap_{block}_{field}_unique', len(row) == 1)
                    for column, value in dict(saving_yuan=float(x[:, j].sum()), ci95_low_yuan=float(low[j]), ci95_high_yuan=float(high[j])).items():
                        a.close(name+f'.bootstrap_{block}_{field}_'+column, row.iloc[0][column], value, CTOL)
                    a.check(name+f'.bootstrap_{block}_{field}_settings', int(row.iloc[0]['seed']) == config['bootstrap_seed'] and int(row.iloc[0]['replicates']) == replicates)
    optimizer = csv(output/'optimizer_summary.csv'); opt_rows = 0
    for name in direct:
        folder = ROOT/'runs'/name; metadata = json.loads((folder/'decisions.json').read_text())['days']
        ev = npz(folder/'decision_evidence.npz')
        for i, day in enumerate(metadata):
            for j, record in enumerate(day['optimizer']):
                row = optimizer.loc[(optimizer.policy == name) & (optimizer.date == day['date']) & (optimizer.start == j)]
                a.check(name+f'.optimizer_{i}_{j}_unique', len(row) == 1); opt_rows += 1
                for field in ('success', 'status', 'nit', 'nfev', 'message'):
                    a.check(name+f'.optimizer_{i}_{j}_'+field, row.iloc[0][field] == record[field])
                for field, offset in [('initial_score_yuan', 0), ('incumbent_score_yuan', 1), ('final_score_yuan', 2)]:
                    a.close(name+f'.optimizer_{i}_{j}_'+field, row.iloc[0][field], ev['score'][i, 3*j+offset], CTOL)
    a.check('optimizer.total_rows', len(optimizer) == opt_rows)
    acceptance = json.loads((output/'acceptance.json').read_text())
    feasible = [name for name in names if expected[name]['emergency_cost_yuan'] <= 1000000.]
    best = min(feasible, key=lambda name: expected[name]['total_cost_yuan'])
    a.check('acceptance.best', acceptance['best_observed_policy'] == best)
    a.close('acceptance.total', acceptance['best_total_yuan'], expected[best]['total_cost_yuan'], CTOL)
    a.close('acceptance.emergency', acceptance['best_emergency_yuan'], expected[best]['emergency_cost_yuan'], CTOL)
    a.close('acceptance.gap', acceptance['best_gap_to_prescient_bound_yuan'], expected[best]['total_cost_yuan']-12227565.30317241, CTOL)
    new_passes = [name for name in direct if expected[name]['emergency_cost_yuan'] <= 1000000. and expected[name]['total_cost_yuan'] < config['reference_total_yuan']-CTOL]
    a.check('acceptance.new_passes', acceptance['new_passes'] == new_passes)
    a.check('acceptance.primary', acceptance['primary'] == 'D56' and acceptance['primary_passed'] == ('D56' in new_passes))
    return a, dict(policies=len(names), optimizer_rows=opt_rows, best_observed=best, new_passes=new_passes)


def oracle_audit():
    """Reconstruct all LP equations and dual signs without importing its matrix builder."""
    a = Audit()
    folder = ROOT/'oracle_source'
    z = np.load(folder/'certificate.npz')
    source = csv(ROOT/'inputs/actual_10min.csv')
    source = source.loc[source.date.between('2025-02-01', '2025-12-31')]
    price = np.tile(csv(ROOT/'inputs/fixed_price.csv').price_yuan_per_kwh.to_numpy(), 334)
    net = (source.load_actual_kwh-source.pv_actual_kwh).to_numpy()
    n = len(net)
    a.check('source.coverage', n == 334*144)
    a.close('source.net', z['net'], net)
    a.close('source.price', z['price'], price)
    initial = float(z['initial'])
    a.close('source.initial', initial, 7268.4231640740745)
    grid, charge, discharge, spill, end = z['primal'].reshape(5, n)
    y = z['equality_dual'].reshape(2, n)
    lower = z['lower_dual'].reshape(5, n)
    upper = z['upper_dual'].reshape(5, n)
    start = np.r_[initial, end[:-1]]
    a.close('lp.balance', grid-charge+discharge-spill, net)
    a.close('lp.recurrence', end-start, .9*charge-discharge/.9)
    a.check('lp.nonnegative', np.array((grid, charge, discharge, spill)) >= -ETOL)
    a.check('lp.power', np.array((charge, discharge)) <= 5000/6+ETOL)
    a.check('lp.soc', (end >= 1200-ETOL) & (end <= 10800+ETOL))
    # A^T y for independent balance and storage equations.
    aty = np.array((y[0], -y[0]-.9*y[1], y[0]+y[1]/.9,
                    -y[0], y[1]-np.r_[y[1, 1:], 0.]))
    objective = np.zeros((5, n)); objective[0] = price
    a.close('dual.stationarity', objective-aty-lower-upper, np.zeros((5, n)), 1e-9)
    a.check('dual.lower_sign', lower >= -1e-9)
    a.check('dual.upper_sign', upper <= 1e-9)
    a.close('dual.unbounded_upper_zero', upper[[0, 3]], np.zeros((2, n)), 1e-9)
    dual = float(net@y[0]+initial*y[1, 0]+1200*lower[4].sum()
                 +(5000/6)*(upper[1].sum()+upper[2].sum())+10800*upper[4].sum())
    primal = float(price@grid)
    a.close('dual.gap', primal, dual, CTOL)
    a.close('lp.recorded_cost', primal, json.loads((folder/'status.json').read_text())['primal_cost_yuan'], CTOL)
    actual = replay(grid, net, initial)
    a.close('greedy.balance', grid+actual['discharge']+actual['emergency']-actual['charge']-actual['surplus'], net)
    a.check('greedy.power', np.array((actual['charge'], actual['discharge'])) <= 5000/6+ETOL)
    a.check('greedy.soc', (actual['end'] >= 1200-ETOL) & (actual['end'] <= 10800+ETOL))
    a.close('greedy.emergency_zero', actual['emergency'], np.zeros(n))
    emergency = float(5*price@actual['emergency'])
    a.close('greedy.upper_equals_lower', primal+emergency, dual, CTOL)
    metrics = dict(dual_bound_yuan=dual, lp_primal_yuan=primal,
                   strict_greedy_total_yuan=primal+emergency,
                   strict_greedy_emergency_yuan=emergency,
                   max_greedy_emergency_kwh=float(actual['emergency'].max()),
                   greedy_final_kwh=float(actual['end'][-1]),
                   lp_final_kwh=float(end[-1]),
                   max_greedy_vs_lp_soc_difference_kwh=float(abs(actual['end']-end).max()),
                   certificate_sha256=digest(folder/'certificate.npz'))
    return a, metrics


def write_report(scope, audit, metrics):
    REPORT.mkdir(parents=True, exist_ok=True)
    result = dict(created_utc=datetime.now(timezone.utc).isoformat(), scope=scope,
                  passed=audit.passed,
                  independence='Standard library, NumPy and pandas only; no production predictor, planner, dispatch, score or gradient imports.',
                  tolerances=dict(physical_kwh=ETOL, cost_yuan=CTOL), checks=audit.rows, metrics=metrics)
    (REPORT/f'independent_{scope}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(scope=scope, passed=audit.passed, checks=len(audit.rows), metrics=metrics), ensure_ascii=False, indent=2))
    if not audit.passed:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    functions = dict(oracle=oracle_audit, sources=sources_audit, references=references_audit,
                     january=lambda: runs_audit('january'), annual=lambda: runs_audit('runs'), gradient=gradient_audit,
                     causality=causality_audit, analysis=analysis_audit,
                     refinement_january=lambda: runs_audit('january', 'refinement.json'),
                     refinement_annual=lambda: runs_audit('runs', 'refinement.json'),
                     refinement_causality=lambda: causality_audit('refinement.json'),
                     analysis_all=lambda: analysis_audit(True))
    parser.add_argument('--scope', choices=list(functions), default='oracle')
    args = parser.parse_args()
    write_report(args.scope, *functions[args.scope]())
