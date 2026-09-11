"""Hand-computable risk and physical boundary specifications."""
import importlib.util
import unittest
import numpy as np
import pandas as pd


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('policy'), 'risk policy implementation is missing')
        import policy
        self.p = policy

    def test_joint_residual_quantile_and_future_exclusion(self):
        rows = []
        for d in range(2, 12):
            for s in range(1, 145):
                rows.append({'date': f'2025-01-{d:02}', 'slot_id': s,
                             'net_residual_kwh': float(d),
                             'residual_available_time': str(pd.Timestamp(f'2025-01-{d:02}')+pd.Timedelta(days=1))})
        a = pd.DataFrame(rows)
        delta, meta = self.p.risk_adjustment(a, pd.Timestamp('2025-01-10'), 28, 0.8)
        self.assertAlmostEqual(delta[0], 8.0)  # 8 prior days × 6 slots, 80th quantile.
        a.loc[a.date >= '2025-01-10', 'net_residual_kwh'] = 1e9
        np.testing.assert_array_equal(delta, self.p.risk_adjustment(a, pd.Timestamp('2025-01-10'), 28, 0.8)[0])
        self.assertEqual(meta['risk_sample_count'], 48)

    def test_insufficient_history_falls_back_to_zero(self):
        a = pd.DataFrame(columns=['date','slot_id','net_residual_kwh','residual_available_time'])
        delta, meta = self.p.risk_adjustment(a, pd.Timestamp('2025-01-02'), 28, 0.8)
        np.testing.assert_array_equal(delta, np.zeros(144))
        self.assertTrue(meta['risk_cold_start'])

    def test_storage_floor_and_power_limit(self):
        f = self.p.execute
        e = f(0, 100, 0, 1200, .9, .9)
        self.assertEqual(e['emergency_kwh'], 100)
        self.assertEqual(e['energy_end_actual_kwh'], 1200)
        e = f(0, 2000, 0, 10800, .9, .9)
        self.assertAlmostEqual(e['discharge_actual_kwh'], 5000/6)
        self.assertAlmostEqual(e['emergency_kwh'], 2000-5000/6)

    def test_charge_ceiling_and_paid_disposal(self):
        e = self.p.execute(100, 0, 10, 10800, .9, .9)
        self.assertEqual(e['charge_actual_kwh'], 0)
        self.assertEqual(e['unused_grid_kwh'], 100)
        self.assertEqual(e['pv_curtailment_kwh'], 10)
        self.assertEqual(e['emergency_kwh'], 0)

    def test_conditional_reserve_cannot_charge_from_emergency(self):
        e = self.p.execute(0, 100, 0, 2200, .9, .9, reserve=1000)
        self.assertEqual(e['emergency_kwh'], 100)
        self.assertEqual(e['charge_actual_kwh'], 0)
        self.assertEqual(e['energy_end_actual_kwh'], 2200)

    def test_reserve_uses_only_strictly_future_higher_price_predictions(self):
        r = self.p.reserve_schedule(np.array([1., 2., 1.]), np.array([100., 200., 300.]), np.zeros(3), .9)
        np.testing.assert_allclose(r, [200/.9, 0, 0])

    def test_internal_power_side_conversion(self):
        e = self.p.execute(2000, 0, 0, 1200, .9, .9, power_basis='battery_internal')
        self.assertAlmostEqual(e['charge_actual_kwh']*.9, 5000/6)
        e = self.p.execute(0, 2000, 0, 10800, .9, .9, power_basis='battery_internal')
        self.assertAlmostEqual(e['discharge_actual_kwh']/.9, 5000/6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
