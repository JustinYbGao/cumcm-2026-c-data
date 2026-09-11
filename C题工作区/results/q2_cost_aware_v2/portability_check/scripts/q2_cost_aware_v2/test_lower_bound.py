import unittest
import numpy as np
from lower_bound import solve_relaxation


class BoundTests(unittest.TestCase):
    def test_loss_aware_two_interval_arbitrage(self):
        result = solve_relaxation(np.array([0., 1.]), np.array([1., 10.]), 1200.)
        self.assertAlmostEqual(result.fun, 1/.81, places=7)
        self.assertAlmostEqual(result.x[-1], 1200., places=7)

    def test_free_initial_inventory_is_accounted(self):
        result = solve_relaxation(np.array([10.]), np.array([2.]), 1210.)
        self.assertAlmostEqual(result.fun, 2., places=7)


if __name__ == '__main__': unittest.main(verbosity=2)
