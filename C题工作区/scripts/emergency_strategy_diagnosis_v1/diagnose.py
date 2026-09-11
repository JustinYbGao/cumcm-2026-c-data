"""Read-only accounting and state diagnostics of the frozen Q2 improvement results."""
import hashlib
import json
from pathlib import Path

import pandas as pd

WORK = Path(__file__).resolve().parents[2]
SOURCE = WORK / 'results/emergency_improvement_v1'
OUT = WORK / 'reports/emergency_strategy_diagnosis_v1'
OUT.mkdir(parents=True, exist_ok=True)
records, hashes = {}, {}
for name in ['B0', 'B1', 'P', 'P_tau07', 'P_tau09', 'P_terminal']:
    path = SOURCE / 'runs' / name / 'ledger.csv'
    hashes[str(path.relative_to(WORK))] = hashlib.sha256(path.read_bytes()).hexdigest()
    d = pd.read_csv(path, float_precision='round_trip')
    price = d.price_yuan_per_kwh
    total = d.total_cost_yuan.sum()
    unused_fee = (price * d.unused_grid_kwh).sum()
    premium = (4 * price * d.emergency_kwh).sum()
    retained_normal_fee = (price * (d.grid_plan_kwh - d.unused_grid_kwh + d.emergency_kwh)).sum()
    assert abs(total - unused_fee - premium - retained_normal_fee) < 1e-5
    initial = d.loc[d.slot_id == 1, 'energy_start_actual_kwh']
    daily = d.groupby('date')[['unused_grid_kwh', 'emergency_kwh']].sum()
    records[name] = {
        'total_cost_yuan': float(total), 'ordinary_cost_yuan': float(d.planned_cost_yuan.sum()),
        'emergency_cost_yuan': float(d.emergency_cost_yuan.sum()),
        'emergency_fee_share': float(d.emergency_cost_yuan.sum() / total),
        'unused_grid_cost_yuan': float(unused_fee), 'emergency_premium_4p_yuan': float(premium),
        'retained_grid_at_normal_price_yuan': float(retained_normal_fee),
        'mean_daily_initial_energy_kwh': float(initial.mean()),
        'days_starting_full': int((initial >= 10800 - 1e-6).sum()),
        'days_with_both_unused_and_emergency': int(((daily.unused_grid_kwh > 1e-6) & (daily.emergency_kwh > 1e-6)).sum()),
        'load_kwh': float(d.load_actual_kwh.sum()), 'pv_kwh': float(d.pv_actual_kwh.sum()),
        'cost_per_load_kwh': float(total / d.load_actual_kwh.sum()),
    }
    if name == 'P':
        # From energy conservation, q+e >= L-V-eta_d*(E0-Emin), dropping nonnegative loss and surplus.
        lower_energy = max(0., d.load_actual_kwh.sum() - d.pv_actual_kwh.sum()
                           - .9 * (d.energy_start_actual_kwh.iloc[0] - 1200))
        records[name]['loose_energy_only_cost_lower_bound_yuan'] = float(price.min() * lower_energy)
        records[name]['lower_bound_scope'] = 'Energy-only relaxation using minimum normal price; not an achievable dispatch or estimate of causal optimal cost.'
payload = {'passed': True, 'records': records, 'source_sha256': hashes,
           'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'method': 'Exact bookkeeping: J = retained grid at normal prices + unused contracted energy fees + 4p emergency premium. Components are not independently avoidable savings.',
           'scope': 'Read existing frozen paths only; no new annual optimization, Q3/Q4 computation, or edits to the delivered v1 package.'}
(OUT / 'diagnosis.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'passed': True, 'P': records['P'], 'terminal_matched_saving_yuan': records['P']['total_cost_yuan'] - records['P_terminal']['total_cost_yuan']}, ensure_ascii=False, indent=2))
