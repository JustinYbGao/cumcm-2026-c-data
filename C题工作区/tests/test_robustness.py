"""Causal PV-correction and frozen robustness-design tests."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd


WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "scripts"))


class RobustnessTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(
            importlib.util.find_spec("run_robustness"),
            "robustness runner missing",
        )
        return importlib.import_module("run_robustness")

    def config(self):
        return json.loads((WORK / "configs/robustness.json").read_text())

    def test_frozen_config_has_all_ten_policies(self):
        policies = self.config()["policies"]
        self.assertEqual(
            list(policies),
            [
                "fixed_raw", "fixed_w28", "fixed_w14", "fixed_w56",
                "efficiency_raw", "efficiency_w28", "soft_raw", "soft_w28",
                "variable_raw", "variable_w28",
            ],
        )

    def test_correction_switches_on_at_april_first_only_for_window_policies(self):
        module = self.module()
        cfg = self.config()
        march = pd.Timestamp("2025-03-31 18:00")
        april = pd.Timestamp("2025-04-01 00:00")
        self.assertFalse(module.correction_active(cfg["policies"]["fixed_w28"], march, cfg))
        self.assertTrue(module.correction_active(cfg["policies"]["fixed_w28"], april, cfg))
        self.assertFalse(module.correction_active(cfg["policies"]["fixed_raw"], april, cfg))

    def test_bias_uses_same_issue_hour_positive_pv_inside_completed_window(self):
        module = self.module()
        issue = pd.Timestamp("2025-04-01 12:00")
        history = pd.DataFrame(
            [
                # The only eligible row.
                ("2025-03-31 12:00", "2025-03-31 12:00", "2025-03-31 12:10", 3.0, 2.0),
                # At the left boundary and therefore eligible.
                ("2025-03-18 12:00", "2025-03-18 00:00", "2025-03-18 00:10", 2.0, 4.0),
                # Expired by ten minutes.
                ("2025-03-17 12:00", "2025-03-17 23:50", "2025-03-18 00:00", 2.0, 100.0),
                # Wrong publication hour.
                ("2025-03-31 06:00", "2025-03-31 12:00", "2025-03-31 12:10", 2.0, 100.0),
                # Daylight filter: zero raw PV must not enter the fit.
                ("2025-03-31 12:00", "2025-03-31 00:00", "2025-03-31 00:10", 0.0, 100.0),
                # Target is not completed before the issue-day midnight cutoff.
                ("2025-04-01 12:00", "2025-04-01 12:00", "2025-04-01 12:10", 2.0, 100.0),
            ],
            columns=["issue_time", "interval_start", "interval_end", "pv_forecast_kwh", "residual_kwh"],
        )
        corrected, meta = module.correct_pv(history, issue, 14, np.array([0.0, 1.0, 5.0]))
        np.testing.assert_allclose(corrected, [0.0, 4.0, 8.0])
        self.assertEqual(meta["training_rows"], 2)
        self.assertEqual(meta["positive_training_rows"], 2)
        self.assertEqual(meta["training_cutoff"], "2025-04-01 00:00:00")
        self.assertEqual(meta["window_start"], "2025-03-18 00:00:00")
        self.assertEqual(meta["latest_target_end"], "2025-03-31 12:10:00")
        self.assertAlmostEqual(meta["bias_kwh"], 3.0)

    def test_daylight_application_leaves_nonpositive_raw_pv_at_zero(self):
        module = self.module()
        history = pd.DataFrame(
            [("2025-03-31 00:00", "2025-03-31 08:00", "2025-03-31 08:10", 2.0, -5.0)],
            columns=["issue_time", "interval_start", "interval_end", "pv_forecast_kwh", "residual_kwh"],
        )
        corrected, meta = module.correct_pv(
            history, pd.Timestamp("2025-04-01 00:00"), 28, np.array([0.0, 2.0, 10.0])
        )
        np.testing.assert_allclose(corrected, [0.0, 0.0, 5.0])
        self.assertEqual(meta["active_positive_intervals"], 2)
        self.assertEqual(meta["clipped_intervals"], 1)


if __name__ == "__main__":
    unittest.main()
