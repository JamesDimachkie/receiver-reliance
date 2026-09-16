"""Checks of arithmetic/support failures, not evidence for sampling assumptions."""
from fractions import Fraction as F
import unittest

from .estimation import confidence_certificate, contrast, lattice_count, upper_root


class EstimationChecks(unittest.TestCase):
    def test_exact_resolution_and_preceding_lattice_failure(self):
        for classes in (1, 2, 17, 47, 58):
            for target, support in ((F(1, 2), F(26, 3)), (F(1, 8), F(1))):
                n = lattice_count(classes, target, support)
                self.assertLessEqual(6 * support / n, target * target)
                previous = n - 6 * classes
                if previous:
                    self.assertGreater(6 * support / previous, target * target)
        self.assertEqual(lattice_count(47, F(1, 2), F(26, 3)), 282)
        self.assertEqual(lattice_count(2, F(1, 8), F(1)), 384)

    def test_roots_are_outward_and_minimal(self):
        for n in range(65):
            for d in (1, 3, 7, 19):
                value = F(n, d)
                root = upper_root(value, 1000)
                self.assertGreaterEqual(root * root, value)
                if root:
                    self.assertLess((root - F(1, 1000)) ** 2, value)

    def test_sign_swap_and_prospective_support(self):
        rows = [{"weight": F(1, 2), "lower": 0, "upper": 1,
                 "treatment": [0] * 100, "comparator": [1] * 100},
                {"weight": F(1, 2), "lower": 0, "upper": 3,
                 "treatment": [1] * 100, "comparator": [3] * 100}]
        result = contrast(rows)
        self.assertEqual(result["estimate"], F(-3, 2))
        self.assertEqual(result["S"], F(1, 20))
        reverse = contrast([{**r, "treatment": r["comparator"], "comparator": r["treatment"]} for r in rows])
        self.assertEqual(reverse["lower"], -result["upper"])
        self.assertEqual(reverse["upper"], -result["lower"])
        rows[0]["treatment"] = [2]
        with self.assertRaises(ValueError):
            contrast(rows)

    def test_missing_or_fractional_design_errors_do_not_become_zero(self):
        valid = {"weight": 1, "lower": 0, "upper": 1, "treatment": [0], "comparator": [1]}
        for invalid in ({**valid, "treatment": []}, {**valid, "treatment": [None]},
                        {**valid, "treatment": [True]}, {**valid, "treatment": [0.5]},
                        {**valid, "treatment": {0: None}}, {**valid, "treatment": {0: "not an endpoint"}},
                        {**valid, "comparator": {1: None}}, {**valid, "treatment": (0,)},
                        {**valid, "weight": F(1, 2)}):
            with self.assertRaises(ValueError):
                contrast([invalid])

    def test_joint_tail_certificate(self):
        cert = confidence_certificate()
        self.assertGreater(cert["exp_6_strict_lower"], 256)
        self.assertEqual(1 - 12 * cert["directional_tail_strict_upper"], cert["simultaneous_coverage_lower"])


if __name__ == "__main__":
    unittest.main()
