"""Price information and settlement boundary tests, written before Q4 implementation."""
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


class Q4Tests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('run_q4'),'Q4 implementation missing')
        return importlib.import_module('run_q4')

    def data(self):
        t=pd.date_range('2025-01-01',periods=35*144,freq='10min')
        return pd.DataFrame({'interval_start':t,'interval_end':t+pd.Timedelta(minutes=10),
            'actual_price_yuan_per_kwh':1+.2*np.sin(2*np.pi*np.arange(len(t))/144)})

    def config(self):return json.loads((WORK/'configs/q4_baseline.json').read_text())

    def test_forecast_rejects_future_actual(self):
        with self.assertRaisesRegex(ValueError,'future'):
            self.module().forecast_price(self.data(),pd.Timestamp('2025-02-01'),self.config())

    def test_constant_price_forecast(self):
        data=self.data();data['actual_price_yuan_per_kwh']=.8
        issue=pd.Timestamp('2025-02-01T06:00');history=data.loc[data.interval_end<=issue]
        forecast,meta=self.module().forecast_price(history,issue,self.config())
        np.testing.assert_allclose(forecast,.8,atol=1e-10)
        self.assertEqual(len(forecast),108)
        self.assertLessEqual(pd.Timestamp(meta['training_last_end']),issue)

    def test_intraday_completed_interval_is_included(self):
        data=self.data();issue=pd.Timestamp('2025-02-01T06:00')
        history=data.loc[data.interval_end<=issue].copy()
        before,_=self.module().forecast_price(history,issue,self.config())
        history.loc[history.index[-1],'actual_price_yuan_per_kwh']+=10
        after,meta=self.module().forecast_price(history,issue,self.config())
        self.assertFalse(np.allclose(before,after))
        self.assertEqual(pd.Timestamp(meta['training_last_end']),issue)

    def test_past_only_forecast_has_exact_horizon(self):
        data=self.data();issue=pd.Timestamp('2025-02-01T18:00')
        predicted,meta=self.module().forecast_price(data.loc[data.interval_end<=issue],issue,self.config())
        self.assertEqual(len(predicted),36)
        self.assertTrue(np.isfinite(predicted).all() and (predicted>0).all())
        self.assertEqual(meta['feature_count'],13)

    def test_actual_settlement_uses_actual_not_forecast_price(self):
        frame=pd.DataFrame({'grid_original_kwh':[100.,100.],'grid_effective_kwh':[120.,80.],
            'emergency_kwh':[10.,0.],'price_actual_yuan_per_kwh':[2.,3.],
            'price_forecast_yuan_per_kwh':[.1,.1]})
        billed=self.module().bill(frame,'A')
        np.testing.assert_allclose(billed.total_cost_yuan,[360.,270.])


if __name__=='__main__':unittest.main()
