import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_robustness import Audit, settlement_a


class AuditBoundaries(unittest.TestCase):
    def test_nonfinite_residual_does_not_pass(self):
        audit = Audit()
        audit.close('nan', [np.nan], [0.])
        self.assertFalse(audit.checks['nan'])

    def test_shape_mismatch_cannot_broadcast_to_success(self):
        audit = Audit()
        audit.close('shape', np.ones((2, 1)), np.ones(2))
        self.assertFalse(audit.checks['shape'])

    def test_settlement_uses_final_volume_and_actual_price(self):
        np.testing.assert_allclose(settlement_a(np.array([100.,100.,100.]),
            np.array([80.,100.,120.]), np.array([2.,2.,2.])), [180.,200.,260.])

    def test_table_preserves_declared_missing_values_and_booleans(self):
        frame = pd.DataFrame({'window': [np.nan, 28.], 'active': [False, True]})
        audit = Audit()
        audit.frame('table', frame, frame.copy())
        self.assertTrue(all(audit.checks.values()))


if __name__ == '__main__':
    unittest.main()
