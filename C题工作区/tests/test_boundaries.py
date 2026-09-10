"""Small synthetic fixtures; these numbers are tests, never competition results."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from datetime import time
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('prepare_data'), 'processing module not implemented')
        import prepare_data
        self.m = prepare_data

    def test_time_and_year_end(self):
        for raw, minutes in [(time(0, 10), 10), ('7:0', 420), ('0:00+1', 1440), ('24:00', 1440)]:
            self.assertEqual(self.m.minute_of_day(raw), minutes)
        end = pd.Timestamp('2025-12-31') + pd.Timedelta(minutes=self.m.minute_of_day('0:00+1'))
        self.assertEqual(end, pd.Timestamp('2026-01-01'))
        self.assertEqual((end - pd.Timedelta(minutes=10)).date().isoformat(), '2025-12-31')

    def test_linear_energy_and_missing_initial_endpoint(self):
        issue = pd.Timestamp('2025-01-01')
        hourly = pd.DataFrame({'issue_time': [issue]*24, 'horizon_h': range(1,25),
                               'target_time': [issue+pd.Timedelta(hours=h) for h in range(1,25)],
                               'pv_forecast_kw': np.arange(1,25)*60.0})
        result = self.m.convert_forecasts(hourly)
        self.assertEqual(len(result), 138)
        self.assertEqual(result.interval_start.min(), issue + pd.Timedelta(hours=1))
        self.assertAlmostEqual(result.pv_forecast_kwh.iloc[0], 65/6)
        # Second release uses previous release's h=6 value at its issue time.
        later = hourly.copy()
        later.issue_time += pd.Timedelta(hours=6)
        later.target_time += pd.Timedelta(hours=6)
        combined = self.m.convert_forecasts(pd.concat([hourly, later], ignore_index=True))
        second = combined.loc[combined.issue_time == issue+pd.Timedelta(hours=6)]
        self.assertEqual(len(second), 144)
        self.assertAlmostEqual(second.pv_forecast_kwh.iloc[:6].sum(), (360+60)/2)
        self.assertEqual(second.endpoint_issue_time.iloc[0], issue)
        self.assertTrue(combined.duplicated('interval_start').any())
        self.assertFalse(combined.duplicated(['issue_time', 'interval_start']).any())

    def test_causal_slicing_boundaries(self):
        t = pd.Timestamp('2025-02-01')
        actual = pd.DataFrame({'interval_end': [t-pd.Timedelta(minutes=10), t, t+pd.Timedelta(minutes=10)]})
        self.assertEqual(len(self.m.history_at(actual, t)), 2)
        self.assertEqual(len(self.m.history_at(actual, t-pd.Timedelta(seconds=1))), 1)
        forecast = pd.DataFrame({'issue_time': [t,t+pd.Timedelta(hours=6)],
                                 'target_time': [t+pd.Timedelta(hours=7)]*2})
        self.assertEqual(len(self.m.forecasts_at(forecast, t)), 1)
        self.assertEqual(len(self.m.forecasts_at(forecast, t+pd.Timedelta(hours=6))), 2)
        with self.assertRaises(ValueError):
            self.m.history_at(actual, '2025-02-01T00:00:00Z')

    def test_source_blank_dates_expand_without_index_alignment(self):
        with patch.object(self.m,'write'), patch.object(pd.DataFrame,'to_csv'):
            result = self.m.prepare_hourly()
        self.assertEqual(len(result),35040)
        self.assertEqual(int(result.date_was_filled.sum()),1095*24)
        self.assertEqual(result.issue_time.iloc[24],pd.Timestamp('2025-01-01 06:00'))


if __name__ == '__main__':
    unittest.main()
