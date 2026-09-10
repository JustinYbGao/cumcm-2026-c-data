import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK/'scripts'))


class Q3Tests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('run_q3'),'Q3 implementation missing')
        return importlib.import_module('run_q3')

    def config(self):return json.loads((WORK/'configs/model_baseline.json').read_text())

    def test_billing_examples(self):
        m=self.module()
        for rule,want in [('A',[100,130,90]),('B',[100,130,110])]:
            np.testing.assert_allclose(m.contract_fee(np.array([100.]*3),np.array([100.,120.,80.]),np.ones(3),rule),want)

    def test_final_settlement_ignores_superseded_versions(self):
        m=self.module()
        original=np.array([100.]);final=np.array([100.]);p=np.ones(1)
        # Intermediate 120 kWh followed by cancellation back to 100 is not two bills.
        self.assertEqual(float(m.contract_fee(original,final,p,'A')[0]),100.)

    def test_one_interval_decrease_A_and_no_decrease_B(self):
        m=self.module()
        for rule,q,cost in [('A',80.,90.),('B',100.,100.)]:
            plan,status=m.solve_horizon(np.array([80.]),np.zeros(1),np.ones(1),6000.,6000.,
                self.config(),original=np.array([100.]),rule=rule)
            self.assertAlmostEqual(plan['grid_kwh'][0],q)
            self.assertAlmostEqual(status['objective_yuan'],cost)

    def test_increase_cost_and_no_emergency_charging_channel(self):
        plan,status=self.module().solve_horizon(np.array([120.]),np.zeros(1),np.ones(1),6000.,6000.,
            self.config(),original=np.array([100.]),rule='B')
        self.assertAlmostEqual(plan['grid_kwh'][0],120.)
        self.assertAlmostEqual(status['objective_yuan'],130.)
        self.assertAlmostEqual(plan['charge_kwh'][0],0.)

    def test_frozen_original_excess_can_be_disposed(self):
        plan,_=self.module().solve_horizon(np.zeros(1),np.array([50.]),np.ones(1),10800.,10800.,
            self.config(),original=np.array([100.]),rule='B')
        self.assertAlmostEqual(plan['grid_kwh'][0],100.)
        self.assertAlmostEqual(plan['surplus_kwh'][0],150.)

    def test_pv_selector_never_uses_future_issue(self):
        m=self.module();now=pd.Timestamp('2025-02-01T06:00');end=now+pd.Timedelta(minutes=20)
        f=pd.DataFrame({'issue_time':[now,now,now+pd.Timedelta(hours=6)],
            'interval_start':[now,now+pd.Timedelta(minutes=10),now],
            'interval_end':[now+pd.Timedelta(minutes=10),end,now+pd.Timedelta(minutes=10)],
            'pv_forecast_kwh':[1.,2.,9999.]})
        np.testing.assert_array_equal(m.select_forecast(f,now,end).pv_forecast_kwh,[1.,2.])
        with self.assertRaisesRegex(ValueError,'coverage'):
            m.select_forecast(f.iloc[1:],now,end)

    def test_q1_objective_reproduced_by_horizon_solver(self):
        m=self.module();f=pd.read_csv(WORK/'results/q1/baseline/schedule.csv')
        _,status=m.solve_horizon(f.load_kwh.to_numpy(),f.pv_forecast_kwh.to_numpy(),
            f.price_yuan_per_kwh.to_numpy(),6000.,6000.,self.config())
        self.assertAlmostEqual(status['objective_yuan'],35126.948589289634,places=5)


if __name__=='__main__':unittest.main()
