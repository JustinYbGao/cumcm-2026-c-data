import importlib
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK/'scripts'))


class Q2Tests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('run_q2'),'Q2 implementation missing')
        return importlib.import_module('run_q2')

    def test_power_limit_and_emergency_do_not_charge(self):
        r=self.module().execute_interval(0.,1000.,0.,6000.,.9,.9,True)
        self.assertAlmostEqual(r['discharge_actual_kwh'],5000/6)
        self.assertAlmostEqual(r['emergency_kwh'],1000-5000/6)
        self.assertEqual(r['charge_actual_kwh'],0.)

    def test_unused_grid_is_paid_and_not_all_called_pv(self):
        r=self.module().execute_interval(1000.,100.,50.,10800.,.9,.9,True)
        self.assertEqual(r['surplus_kwh'],950.)
        self.assertEqual(r['unused_grid_kwh'],950.)
        self.assertEqual(r['pv_curtailment_kwh'],0.)

    def test_state_floor_and_no_storage(self):
        r=self.module().execute_interval(0.,100.,0.,1200.,.9,.9,True)
        self.assertEqual(r['emergency_kwh'],100.)
        self.assertEqual(r['energy_end_actual_kwh'],1200.)
        r=self.module().execute_interval(0.,100.,0.,6000.,.9,.9,False)
        self.assertEqual(r['energy_end_actual_kwh'],6000.)
        self.assertEqual(r['emergency_kwh'],100.)

    def test_future_history_is_rejected(self):
        h=pd.DataFrame({'interval_end':['2025-02-01T00:10:00']})
        with self.assertRaisesRegex(ValueError,'future'):
            self.module().forecast_day(h,pd.Timestamp('2025-02-01'),'seasonal',{})

    def test_seasonal_only_uses_past_days(self):
        m=self.module()
        end=pd.date_range('2025-01-01T00:10',periods=7*144,freq='10min')
        h=pd.DataFrame({'interval_end':end,'date':np.repeat(pd.date_range('2025-01-01',periods=7).strftime('%Y-%m-%d'),144),
                        'load_actual_kwh':np.repeat(np.arange(7)+100.,144),'pv_actual_kwh':np.repeat(np.arange(7)+10.,144)})
        load,pv,_=m.forecast_day(h,pd.Timestamp('2025-01-08'),'seasonal',{})
        np.testing.assert_array_equal(load,np.full(144,100.))
        np.testing.assert_array_equal(pv,np.full(144,16.))


if __name__=='__main__': unittest.main()
