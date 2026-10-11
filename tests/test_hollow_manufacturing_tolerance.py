import unittest

from tools.hollow_manufacturing_tolerance import InputError, verify


class HollowManufacturingToleranceTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "load_n": 1000,
            "length_mm": 500,
            "outer_width_mm": 40,
            "outer_height_mm": 60,
            "wall_thickness_mm": 4,
            "outer_corner_radius_mm": 8,
            "material_id": "steel_s235",
            "length_tolerance_mm": 2,
            "outer_width_tolerance_mm": 0.5,
            "outer_height_tolerance_mm": 0.5,
            "wall_thickness_tolerance_mm": 0.5,
            "outer_corner_radius_tolerance_mm": 0.5,
            "load_tolerance_percent": 10,
            "max_deflection_mm": 2,
            "min_safety_factor": 2.3,
            "max_mass_kg": 20,
            "min_local_buckling_factor": 1,
        }

    def test_all_six_axes_are_enumerated(self):
        result = verify(self.payload)
        self.assertEqual(result["cases_evaluated"], 64)
        self.assertEqual(result["valid_cases"] + result["invalid_geometry_cases"], 64)
        self.assertIn(result["status"], {"robust_feasible", "robustness_failed"})

    def test_robust_feasible_design(self):
        result = verify({**self.payload, "wall_thickness_mm": 6, "outer_corner_radius_mm": 10})
        self.assertEqual(result["status"], "robust_feasible")
        self.assertEqual(result["passed_cases"], 64)
        self.assertEqual(result["failed_cases"], 0)

    def test_invalid_geometry_is_separated_from_constraint_failure(self):
        result = verify({
            **self.payload,
            "wall_thickness_mm": 5,
            "outer_corner_radius_mm": 5.1,
            "outer_corner_radius_tolerance_mm": 1,
        })
        self.assertGreater(result["invalid_geometry_cases"], 0)
        self.assertEqual(result["worst_invalid_geometry_case"]["status"], "invalid_geometry")
        self.assertEqual(result["worst_invalid_geometry_case"]["failed_constraints"], ["geometry"])

    def test_constraint_failure_reports_local_buckling(self):
        result = verify({**self.payload, "min_local_buckling_factor": 1.0e9})
        self.assertEqual(result["status"], "robustness_failed")
        self.assertGreater(result["failed_constraint_counts"]["local_buckling"], 0)
        self.assertIn("local_buckling", result["worst_case"]["failed_constraints"])

    def test_zero_tolerances_deduplicate_to_one_case(self):
        result = verify({
            **self.payload,
            "length_tolerance_mm": 0,
            "outer_width_tolerance_mm": 0,
            "outer_height_tolerance_mm": 0,
            "wall_thickness_tolerance_mm": 0,
            "outer_corner_radius_tolerance_mm": 0,
            "load_tolerance_percent": 0,
        })
        self.assertEqual(result["cases_evaluated"], 1)

    def test_rejects_tolerance_lower_bound_and_missing_constraint(self):
        with self.assertRaises(InputError):
            verify({**self.payload, "wall_thickness_tolerance_mm": 4})
        without_constraints = {
            key: value
            for key, value in self.payload.items()
            if key not in {"max_deflection_mm", "min_safety_factor", "max_mass_kg", "min_local_buckling_factor"}
        }
        with self.assertRaises(InputError):
            verify(without_constraints)


if __name__ == "__main__":
    unittest.main()
