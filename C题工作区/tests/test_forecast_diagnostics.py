"""Synthetic energy fixtures only; not competition results."""
import importlib.util
from pathlib import Path
import sys
import unittest
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))


class ForecastDiagnostics(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('diagnose_forecasts'), 'diagnostics not implemented')
        import diagnose_forecasts
        self.m = diagnose_forecasts

    def fixture(self):
        issue = pd.Timestamp('2025-12-31 23:00')
        hourly = pd.DataFrame({'issue_time':[issue,issue], 'target_time':[issue+pd.Timedelta(hours=1),issue+pd.Timedelta(hours=2)],'horizon_h':[1,2],'pv_forecast_kw':[60.,60.]})
        starts = pd.date_range(issue,periods=12,freq='10min')
        derived = pd.DataFrame({'issue_time':[issue]*12,'interval_start':starts,'interval_end':starts+pd.Timedelta(minutes=10),'pv_forecast_kwh':[10.]*12})
        actual = pd.DataFrame({'interval_start':starts[:6],'interval_end':starts[:6]+pd.Timedelta(minutes=10),'pv_actual_kwh':[5.]*6})
        return hourly,derived,actual

    def test_energy_units_year_end_missing_actual(self):
        frame = self.m.evaluate_pv(*self.fixture())
        self.assertEqual(len(frame),2)
        self.assertEqual(frame.forecast_hour_kwh.iloc[0],60.)
        self.assertEqual(frame.actual_hour_kwh.iloc[0],30.)
        self.assertEqual(frame.error_kwh.iloc[0],30.)
        self.assertEqual(frame.target_business_date.iloc[0],'2025-12-31')
        self.assertTrue(pd.isna(frame.actual_hour_kwh.iloc[1]))
        self.assertTrue(pd.isna(frame.error_kwh.iloc[1]))
        self.assertEqual(frame.comparison_status.iloc[1],'missing_actual')

    def test_partial_forecast_not_summed_as_full_hour(self):
        h,d,a = self.fixture()
        frame = self.m.evaluate_pv(h,d.iloc[1:],a)
        self.assertEqual(frame.forecast_interval_count.iloc[0],5)
        self.assertTrue(pd.isna(frame.forecast_hour_kwh.iloc[0]))
        self.assertTrue(pd.isna(frame.error_kwh.iloc[0]))
        self.assertEqual(frame.comparison_status.iloc[0],'missing_forecast')

    def test_error_unavailable_until_entire_hour_complete(self):
        frame = self.m.evaluate_pv(*self.fixture())
        self.assertEqual(len(self.m.errors_at(frame,'2025-12-31T23:59:59')),0)
        self.assertEqual(len(self.m.errors_at(frame,'2026-01-01T00:00:00')),1)
        self.assertEqual(len(self.m.errors_at(frame,'2026-01-02T00:00:00')),1)

    def test_real_zero_is_comparable_and_duplicates_are_rejected(self):
        h,d,a = self.fixture()
        a['pv_actual_kwh'] = 0.
        frame = self.m.evaluate_pv(h,d,a)
        self.assertEqual(frame.actual_hour_kwh.iloc[0],0.)
        self.assertEqual(frame.error_kwh.iloc[0],60.)
        self.assertEqual(frame.comparison_status.iloc[0],'comparable')
        with self.assertRaises(ValueError):
            self.m.evaluate_pv(h,d,pd.concat([a,a.iloc[:1]]))

    def test_common_sample_requires_four_distinct_versions_and_groups(self):
        target = pd.Timestamp('2025-02-01')
        good = pd.DataFrame({'target_time':[target]*4,'issue_hour':[0,6,12,18],
                             'lead_block':[4,3,2,1],'horizon_h':[24,18,12,6],'error_kwh':[4.,3.,2.,1.],
                             'comparison_status':['comparable']*4,'actual_positive_pv':[True]*4})
        absent = good.iloc[:3].copy()
        absent['target_time'] = target+pd.Timedelta(hours=1)
        repeated_hour = good.copy()
        repeated_hour['target_time'] = target+pd.Timedelta(hours=2)
        repeated_hour['issue_hour'] = [0,0,12,18]
        repeated_lead = good.copy()
        repeated_lead['target_time'] = target+pd.Timedelta(hours=3)
        repeated_lead['lead_block'] = [1,1,3,4]
        summary,common = self.m.summarize(pd.concat([good,absent,repeated_hour,repeated_lead],ignore_index=True))
        self.assertEqual(len(common),4)
        self.assertEqual(set(common.target_time),{target})
        self.assertTrue(summary.loc[summary.scope=='same_target_four_versions','target_hour_count'].eq(1).all())


if __name__=='__main__':
    unittest.main()
