"""Analytic dispatch check and deliberately corrupted saved-plan checks."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'scripts'))


class Q1Tests(unittest.TestCase):
    def module(self, name):
        self.assertIsNotNone(importlib.util.find_spec(name), f'{name} is not implemented')
        return importlib.import_module(name)

    def fixture(self):
        cfg = json.loads((WORK / 'configs/model_baseline.json').read_text())
        source = pd.DataFrame({'slot_id': range(1,145), 'start_minute': range(0,1440,10),
                               'end_minute': range(10,1441,10), 'price_yuan_per_kwh': 1.,
                               'load_kwh': 100., 'pv_forecast_kwh': 0.})
        plan = source.copy()
        for key, value in {'grid_kwh':100., 'charge_kwh':0., 'discharge_kwh':0.,
                           'curtailment_kwh':0., 'energy_start_kwh':6000.,
                           'energy_end_kwh':6000., 'charge_mode':0., 'cost_yuan':100.}.items():
            plan[key] = value
        summary = {'cost_yuan':14400., 'grid_kwh':14400., 'charge_kwh':0.,
                   'discharge_kwh':0., 'curtailment_kwh':0.}
        return source, plan, summary, cfg

    def test_valid_plan(self):
        self.assertTrue(self.module('validate_q1_solution').validate_frames(*self.fixture())['passed'])

    def test_power_limit_is_energy_per_interval(self):
        source, plan, summary, cfg = self.fixture()
        plan.loc[0, 'charge_kwh'] = 834.
        r = self.module('validate_q1_solution').validate_frames(source, plan, summary, cfg)
        self.assertFalse(r['checks']['charge_power'])

    def test_state_recursion_corruption(self):
        source, plan, summary, cfg = self.fixture()
        plan.loc[10, 'energy_end_kwh'] += 2.
        r = self.module('validate_q1_solution').validate_frames(source, plan, summary, cfg)
        self.assertFalse(r['checks']['state_recursion'])

    def test_wrong_summary_is_rejected(self):
        source, plan, summary, cfg = self.fixture()
        summary['cost_yuan'] -= 100.
        r = self.module('validate_q1_solution').validate_frames(source, plan, summary, cfg)
        self.assertFalse(r['checks']['summary_cost_yuan'])

    def test_shifted_time_keys_are_rejected(self):
        source, plan, summary, cfg = self.fixture()
        plan['start_minute'] += 10
        r = self.module('validate_q1_solution').validate_frames(source, plan, summary, cfg)
        self.assertFalse(r['checks']['time_keys'])

    def test_nonfinite_value_is_rejected(self):
        source, plan, summary, cfg = self.fixture()
        plan.loc[0, 'grid_kwh'] = np.nan
        self.assertFalse(self.module('validate_q1_solution').validate_frames(source, plan, summary, cfg)['passed'])

    def test_analytic_two_interval_arbitrage(self):
        cfg = self.fixture()[3]
        cfg['battery'].update(eta_charge=1., eta_discharge=1., initial_energy_kwh=1200.)
        data = pd.DataFrame({'price_yuan_per_kwh':[1.,3.], 'load_kwh':[0.,100.], 'pv_forecast_kwh':[0.,0.]})
        x, status = self.module('solve_q1').solve_model(data, cfg)
        self.assertEqual(status['status'], 'Optimal')
        self.assertAlmostEqual(status['objective_yuan'], 100., places=6)
        np.testing.assert_allclose(x['grid_kwh'], [100.,0.], atol=1e-6)
        np.testing.assert_allclose(x['charge_kwh'], [100.,0.], atol=1e-6)
        np.testing.assert_allclose(x['discharge_kwh'], [0.,100.], atol=1e-6)

    def test_lp_evidence_has_no_nonfinite_mip_statistics(self):
        cfg = self.fixture()[3]
        data = pd.DataFrame({'price_yuan_per_kwh':[1.,3.], 'load_kwh':[0.,100.], 'pv_forecast_kwh':[0.,0.]})
        _, status = self.module('solve_q1').solve_model(data, cfg, relaxed=True)
        json.dumps(status, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
