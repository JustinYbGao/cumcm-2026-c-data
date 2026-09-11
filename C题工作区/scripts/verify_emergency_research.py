"""Independent standard-library verification of the descriptive research outputs."""
import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'reports/emergency_research_v1'


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    provenance = json.loads((OUT/'analysis_validation.json').read_text())
    for name, digest in provenance['protected_hashes'].items():
        assert hashlib.sha256((WORK/name).read_bytes()).hexdigest() == digest, name
    assert hashlib.sha256((WORK/'scripts/research_emergency_costs.py').read_bytes()).hexdigest() == provenance['script_sha256']
    summary = {r['policy']: r for r in rows(OUT/'policy_comparison.csv')}
    paths = dict(q2_selected='q2/selected', q2_seasonal='q2/seasonal',
                 q2_no_storage='q2/no_storage', q3_no_update='q3/no_update',
                 q3_corrected='robustness/fixed_w28', q42='q4/q42_ols',
                 q43_corrected='robustness/variable_w28')
    prices = {int(r['slot_id']): float(r['price_yuan_per_kwh']) for r in rows(WORK/'data/processed/fixed_price.csv')}
    actual = {(r['date'], int(r['slot_id'])): r for r in rows(WORK/'data/processed/actual_10min.csv')}
    expected = [((date(2025, 2, 1)+timedelta(days=d)).isoformat(), s) for d in range(334) for s in range(1, 145)]
    result = {}
    for policy, path in paths.items():
        ledger = rows(WORK/'results'/path/'ledger.csv')
        assert [(r['date'], int(r['slot_id'])) for r in ledger] == expected
        totals = dict(emergency_kwh=0., emergency_cost_yuan=0., contract_cost_yuan=0., total_cost_yuan=0.)
        floor_fee = evening_fee = 0.
        previous = None
        max_residual = 0.
        for r in ledger:
            key = (r['date'], int(r['slot_id']))
            src = actual[key]
            p = float(src['actual_price_yuan_per_kwh']) if policy.startswith('q4') else prices[key[1]]
            q0 = float(r.get('grid_plan_kwh', r.get('grid_original_kwh')))
            q = float(r.get('grid_plan_kwh', r.get('grid_effective_kwh')))
            e, c, d, w = [float(r[k]) for k in ('emergency_kwh', 'charge_actual_kwh', 'discharge_actual_kwh', 'surplus_kwh')]
            start, end = float(r['energy_start_actual_kwh']), float(r['energy_end_actual_kwh'])
            assert min(q0, q, e, c, d, w) >= -1e-6
            assert max(c, d) <= 5000/6+1e-6
            assert min(c, d) <= 1e-6
            assert 1200-1e-6 <= start <= 10800+1e-6 and 1200-1e-6 <= end <= 10800+1e-6
            if previous is not None:
                assert abs(start-previous) < 1e-6
            previous = end
            residuals = [abs(q+float(src['pv_actual_kwh'])+d+e-float(src['load_actual_kwh'])-c-w),
                         abs(end-start-.9*c+d/.9)]
            fee = 5*p*e
            contract = p*q0+1.5*p*max(q-q0, 0)-.5*p*max(q0-q, 0)
            residuals += [abs(fee-float(r['emergency_cost_yuan'])), abs(contract+fee-float(r['total_cost_yuan']))]
            max_residual = max(max_residual, *residuals)
            assert max_residual < 1e-6
            for k, v in zip(totals, (e, fee, contract, contract+fee)):
                totals[k] += v
            if e > 1e-7 and end <= 1200+1e-6:
                floor_fee += fee
            if key[1] >= 109:
                evening_fee += fee
        discrepancies = {k: abs(v-float(summary[policy][k])) for k, v in totals.items()}
        assert max(discrepancies.values()) < 1e-5, discrepancies
        result[policy] = dict(rows=len(ledger), max_interval_residual=max_residual,
                              max_summary_difference=max(discrepancies.values()),
                              floor_fee_share=floor_fee/totals['emergency_cost_yuan'],
                              evening_fee_share=evening_fee/totals['emergency_cost_yuan'])
    diagnostics = json.loads((OUT/'q2_diagnostics.json').read_text())
    assert abs(result['q2_selected']['evening_fee_share']-diagnostics['emergency_cost_18_23h_share']) < 1e-12
    payload = dict(passed=True, verified_ledger_rows=sum(r['rows'] for r in result.values()),
                   protected_files_unchanged=len(provenance['protected_hashes']),
                   verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   checks=result,
                   scope='Independent arithmetic, physical bounds and continuity checks; not proof of policy optimality or forecast causality.')
    (OUT/'independent_validation.json').write_text(json.dumps(payload, indent=2)+'\n')
    print(json.dumps({k: v for k, v in payload.items() if k != 'checks'}))


if __name__ == '__main__':
    main()
