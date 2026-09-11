from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "scripts"))

import analyze_robustness as analysis


class BootstrapTests(unittest.TestCase):
    def test_moving_blocks_stay_within_month_and_are_reproducible(self):
        dates = pd.date_range("2025-04-01", "2025-05-31")
        first = analysis.monthly_block_indices(dates, 7, 20, 20260910, "moving_block")
        second = analysis.monthly_block_indices(dates, 7, 20, 20260910, "moving_block")
        np.testing.assert_array_equal(first, second)
        months = dates.to_period("M").to_numpy()
        for row in first:
            np.testing.assert_array_equal(months[row], months)
            for start in (0, 7, 14, 21):
                np.testing.assert_array_equal(np.diff(row[start:start + 7]), np.ones(6))

    def test_circular_control_wraps_only_within_month(self):
        dates = pd.date_range("2025-04-01", "2025-04-30")
        rows = analysis.monthly_block_indices(dates, 7, 50, 20260910, "circular_block")
        self.assertTrue(any(np.any(np.diff(row[:7]) < 0) for row in rows))
        self.assertTrue(np.all((rows >= 0) & (rows < 30)))


class PairSummaryTests(unittest.TestCase):
    def test_pair_summary_uses_own_inventory_endpoints_and_daily_signs(self):
        dates = pd.to_datetime(["2025-04-01", "2025-04-02", "2025-04-03"])
        raw = pd.DataFrame({
            "date": dates, "total_cost_yuan": [10.0, 20.0, 30.0],
            "contract_cost_yuan": [8.0, 17.0, 24.0], "emergency_cost_yuan": [2.0, 3.0, 6.0],
            "emergency_kwh": [1.0, 1.0, 2.0], "energy_start_actual_kwh": [5.0, 6.0, 7.0],
            "energy_end_actual_kwh": [6.0, 7.0, 9.0],
        })
        corrected = raw.copy()
        corrected["total_cost_yuan"] = [8.0, 21.0, 30.0]
        corrected["contract_cost_yuan"] = [7.0, 18.0, 24.0]
        corrected["emergency_cost_yuan"] = [1.0, 3.0, 6.0]
        corrected["energy_start_actual_kwh"] = [4.0, 5.0, 6.0]
        corrected["energy_end_actual_kwh"] = [5.0, 6.0, 6.0]
        daily, monthly, summary = analysis.analyze_pair(
            raw, corrected, "example", "Example comparison", inventory_value=2.0,
            scope="april_december",
        )
        np.testing.assert_allclose(daily.cash_gain_yuan, [2.0, -1.0, 0.0])
        self.assertEqual((summary.winning_days, summary.losing_days, summary.tie_days), (1, 1, 1))
        self.assertAlmostEqual(summary.cash_gain_yuan, 1.0)
        # Raw adjustment: 60 - 2*(9-5); corrected: 59 - 2*(6-4).
        self.assertAlmostEqual(summary.inventory_adjusted_gain_yuan, -3.0)
        self.assertAlmostEqual(monthly.cash_gain_yuan.iloc[0], 1.0)


if __name__ == "__main__":
    unittest.main()
