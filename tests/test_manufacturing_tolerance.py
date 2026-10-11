import unittest

from tools.manufacturing_tolerance import InputError, verify


class ManufacturingToleranceTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "load_n": 1000,
            "length_mm": 300,
            "width_mm": 50,
            "height_mm": 80,
            "material_id": "steel_s235",
            "width_tolerance_mm": 1,
            "height_tolerance_mm": 1,
            "load_tolerance_percent": 5,
            "max_deflection_mm": 2,
            "min_safety_factor": 2,
            "max_mass_kg": 10,
        }

    def test_all_corners_pass_for_robust_design(self):
        result = verify(self.payload)
        self.assertEqual(result["status"], "robust_feasible")
        self.assertEqual(result["cases_evaluated"], 8)
        self.assertEqual(result["passed_cases"], 8)

    def test_reports_worst_case_failure(self):
        result = verify({**self.payload, "height_mm": 20, "height_tolerance_mm": 1, "min_safety_factor": 2.3})
        self.assertEqual(result["status"], "robustness_failed")
        self.assertGreater(result["failed_cases"], 0)
        self.assertIn("safety_factor", result["worst_case"]["failed_constraints"])

    def test_zero_tolerance_matches_nominal_case_count(self):
        result = verify(
            {
                **self.payload,
                "width_tolerance_mm": 0,
                "height_tolerance_mm": 0,
                "load_tolerance_percent": 0,
            }
        )
        self.assertEqual(result["status"], "robust_feasible")
        self.assertEqual(result["cases_evaluated"], 1)
        metrics = {tuple(sorted(case["metrics"].items())) for case in result["corner_cases"]}
        self.assertEqual(len(metrics), 1)

    def test_length_tolerance_is_included_in_boundary_cases(self):
        result = verify({**self.payload, "length_tolerance_mm": 10})
        self.assertEqual(result["cases_evaluated"], 16)
        lengths = {case["length_mm"] for case in result["corner_cases"]}
        self.assertEqual(lengths, {290.0, 310.0})

    def test_rejects_effective_dimension_near_zero(self):
        with self.assertRaises(InputError):
            verify({**self.payload, "width_tolerance_mm": 49.995})

    def test_severity_remains_finite_for_non_finite_metrics(self):
        result = verify({**self.payload, "max_deflection_mm": 1e-300})
        self.assertTrue(all(case["severity"] <= 1e12 for case in result["corner_cases"]))

    def test_rejects_tolerance_larger_than_dimension(self):
        with self.assertRaises(InputError):
            verify({**self.payload, "height_tolerance_mm": 80})


if __name__ == "__main__":
    unittest.main()
