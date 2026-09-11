import unittest
import numpy as np
import pandas as pd
from policy import simulate, choose_index, scenario_bank, decision, ROOT, INPUTS


class PolicyTests(unittest.TestCase):
    def test_candidate_plan_roundtrip(self):
        archive = pd.read_csv(ROOT / 'forecasts/linear_harmonic.csv', float_precision='round_trip')
        f = archive.loc[archive.date == '2025-01-15']
        price = pd.read_csv(INPUTS / 'fixed_price.csv').price_yuan_per_kwh.to_numpy()
        result = decision(archive, '2025-01-15', f.load_forecast_kwh.to_numpy(), f.pv_forecast_kwh.to_numpy(),
                          price, 6000., {'risk_window':28, 'scenario_window':28, 'taus':[.8], 'terminals':[6000.], 'mu':.38232})
        self.assertEqual(result['plans'].shape, (1, 144, 7))
        self.assertAlmostEqual(result['plans'][0, -1, 4], 6000.)

    def test_shared_plan_tradeoff_uses_total_cost(self):
        q = np.array([[0., 0.], [10., 0.]])
        n = np.array([[5., 5.], [5., 10.]])
        result = simulate(q, n, np.ones(2), 1200., 0.)
        np.testing.assert_allclose(result['score'], [62.5, 27.25], atol=1e-9)
        self.assertEqual(choose_index(result['score']), 1)

    def test_inventory_is_only_a_scoring_credit(self):
        result = simulate(np.array([[10.]]), np.array([[0.]]), np.ones(1), 1200., .4)
        self.assertAlmostEqual(result['ordinary'][0], 10.)
        self.assertAlmostEqual(result['end_energy'][0, 0], 1209.)
        self.assertAlmostEqual(result['score'][0], 6.4)

    def test_floor_power_ceiling_and_surplus(self):
        result = simulate(np.array([[2000., 0., 0.]]), np.array([[0., 1000., 1000.]]), np.ones(3), 10700., 0., traces=True)
        self.assertAlmostEqual(result['trace']['charge'][0, 0, 0], 100 / .9)
        self.assertAlmostEqual(result['trace']['surplus'][0, 0, 0], 2000 - 100 / .9)
        self.assertAlmostEqual(result['trace']['discharge'][0, 0, 1], 5000 / 6)
        self.assertAlmostEqual(result['trace']['emergency'][0, 0, 1], 1000 - 5000 / 6)

    def test_negative_net_means_surplus(self):
        result = simulate(np.array([[0.]]), np.array([[-100.]]), np.ones(1), 1200., 0.)
        self.assertAlmostEqual(result['end_energy'][0, 0], 1290.)
        self.assertAlmostEqual(result['emergency_fee'][0, 0], 0.)

    def test_scenario_future_cannot_change_prefix(self):
        q = np.array([[0., 0., 0.]])
        a = simulate(q, np.array([[10., 20., 30.]]), np.ones(3), 6000., 0., traces=True)
        b = simulate(q, np.array([[10., 20., 3000.]]), np.ones(3), 6000., 0., traces=True)
        for field in a['trace']:
            np.testing.assert_array_equal(a['trace'][field][..., :2], b['trace'][field][..., :2])

    def test_tie_uses_predeclared_order(self):
        self.assertEqual(choose_index(np.array([10. + 5e-9, 10., 11.])), 0)
        self.assertEqual(choose_index(np.array([10. + 5e-7, 10., 11.])), 1)

    def test_scenario_cutoff_and_order(self):
        rows = []
        for day in pd.date_range('2025-01-01', '2025-01-10'):
            for slot in range(1, 145):
                rows.append({'date':str(day.date()),'slot_id':slot,'residual_available_time':str(day+pd.Timedelta(days=1)), 'net_residual_kwh':day.day+slot/1000})
        a = pd.DataFrame(rows)
        net, dates = scenario_bank(a, '2025-01-10', 7, np.zeros(144))
        self.assertEqual(dates, [str(d.date()) for d in pd.date_range('2025-01-03','2025-01-09')])
        self.assertAlmostEqual(net[0,0],3.001)
        self.assertAlmostEqual(net[-1,-1],9.144)


if __name__ == '__main__':
    unittest.main(verbosity=2)
