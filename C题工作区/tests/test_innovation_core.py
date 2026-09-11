import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "scripts"))

import innovation_core as core
from run_q3 import solve_horizon


def physical():
    cfg = json.loads((WORK / "configs/model_baseline.json").read_text())
    cfg["battery"].update(
        min_energy_kwh=0.0,
        max_energy_kwh=10.0,
        max_charge_kw=30.0,
        max_discharge_kw=30.0,
    )
    return cfg


class SolverTests(unittest.TestCase):
    def test_zero_reserve_matches_q3_hard_terminal(self):
        load = np.array([2.0, 4.0, 1.0])
        pv = np.array([0.0, 1.0, 0.0])
        price = np.array([1.0, 2.0, 1.0])
        expected, expected_status = solve_horizon(
            load, pv, price, 5.0, 5.0, physical(), relaxed=True
        )
        actual, status = core.solve(
            load, pv, price, 5.0, 5.0, physical(),
            reserve={"index": 1, "amount_kwh": 0.0, "penalty_yuan_per_kwh": 1.0},
            relaxed=True,
        )
        for key in expected:
            np.testing.assert_allclose(actual[key], expected[key], atol=1e-7)
        self.assertAlmostEqual(status["objective_yuan"], expected_status["objective_yuan"], places=7)
        self.assertAlmostEqual(status["reserve_shortfall_kwh"], 0.0, places=7)

    def test_unreachable_reserve_uses_shortfall_instead_of_becoming_infeasible(self):
        plan, status = core.solve(
            [0.0], [0.0], [1.0], 0.0, 0.0, physical(),
            reserve={"index": 1, "amount_kwh": 20.0, "penalty_yuan_per_kwh": 2.0},
            relaxed=True,
        )
        self.assertEqual(status["status"], "Optimal")
        self.assertAlmostEqual(status["reserve_shortfall_kwh"], 20.0, places=7)
        self.assertAlmostEqual(status["reserve_proxy_yuan"], 40.0, places=7)
        self.assertAlmostEqual(plan["energy_end_kwh"][-1], 0.0, places=7)

    def test_frozen_grid_shortage_is_feasible_without_emergency_charging(self):
        plan, status = core.solve(
            [5.0], [0.0], [1.0], 0.0, 0.0, physical(),
            fixed_grid=[0.0], soft_terminal=True, terminal_penalty=0.9,
        )
        self.assertAlmostEqual(plan["grid_kwh"][0], 0.0, places=7)
        self.assertAlmostEqual(plan["emergency_plan_kwh"][0], 5.0, places=7)
        self.assertAlmostEqual(plan["charge_kwh"][0], 0.0, places=7)
        self.assertAlmostEqual(status["emergency_plan_kwh"], 5.0, places=7)

    def test_free_update_cannot_cost_more_than_holding_same_plan(self):
        args = ([5.0], [0.0], [1.0], 0.0, 0.0, physical())
        _, hold = core.solve(
            *args, original=[0.0], fixed_grid=[0.0],
            soft_terminal=True, terminal_penalty=0.9,
        )
        _, update = core.solve(
            *args, original=[0.0], soft_terminal=True, terminal_penalty=0.9,
        )
        self.assertLessEqual(update["objective_yuan"], hold["objective_yuan"] + 1e-7)
        for status in (hold, update):
            self.assertAlmostEqual(
                status["objective_yuan"],
                status["contract_cost_yuan"] + status["emergency_cost_yuan"]
                + status["reserve_proxy_yuan"] + status["terminal_proxy_yuan"],
                places=7,
            )

    def test_soft_terminal_requires_explicit_penalty(self):
        with self.assertRaises(ValueError):
            core.solve([0.0], [0.0], [1.0], 0.0, 0.0, physical(), soft_terminal=True)


class StatisticalKernelTests(unittest.TestCase):
    def test_quantile_lp_fits_analytical_intercept_and_clips_prediction(self):
        pred, meta = core.quantile_fit_predict(
            np.ones((5, 1)), np.array([1.0, 2.0, 3.0, 100.0, 101.0]), np.array([1.0]), alpha=0.75
        )
        self.assertAlmostEqual(pred, 100.0, places=7)
        self.assertEqual(meta["source"], "pinball_lp")
        self.assertEqual(meta["rank"], 1)
        self.assertGreaterEqual(meta["objective"], 0.0)
        negative, _ = core.quantile_fit_predict(np.ones((3, 1)), [-4.0, -3.0, -2.0], [1.0], 0.75)
        self.assertEqual(negative, 0.0)

    def test_rank_deficiency_falls_back_to_empirical_quantile(self):
        pred, meta = core.quantile_fit_predict(
            np.ones((4, 2)), [1.0, 2.0, 3.0, 4.0], [1.0, 1.0], 0.75
        )
        self.assertEqual(meta["source"], "empirical_quantile")
        self.assertEqual(meta["rank"], 1)
        self.assertGreaterEqual(pred, 0.0)

    def test_risk_prefix_allows_deficit_cancellation(self):
        self.assertAlmostEqual(core.risk_prefix([-2.0, 5.0, -4.0]), 3.0)
        self.assertEqual(core.risk_prefix([-2.0, -1.0]), 0.0)

    def test_gate_excludes_future_wrong_hour_and_expired_records(self):
        issue = pd.Timestamp("2025-04-01 12:00")
        records = [
            {"id": "valid", "available_time": "2025-03-31 00:00", "issue_time": "2025-03-30 12:00", "issue_hour": 12, "zeta_yuan": 4.0},
            {"id": "future", "available_time": "2025-04-01 12:01", "issue_time": "2025-03-31 12:00", "issue_hour": 12, "zeta_yuan": 999.0},
            {"id": "wrong-hour", "available_time": "2025-03-31 00:00", "issue_time": "2025-03-31 06:00", "issue_hour": 6, "zeta_yuan": 999.0},
            {"id": "old", "available_time": "2025-01-01 00:00", "issue_time": "2025-01-01 12:00", "issue_hour": 12, "zeta_yuan": 999.0},
        ]
        tau, meta = core.gate_threshold(records, issue, 12, 0.75, min_samples=1)
        self.assertAlmostEqual(tau, 4.0)
        self.assertEqual(meta["n"], 1)
        self.assertEqual(meta["record_ids"], ["valid"])
        self.assertEqual(meta["latest_available_time"], "2025-03-31 00:00:00")
        self.assertTrue(meta["active"])


if __name__ == "__main__":
    unittest.main()
