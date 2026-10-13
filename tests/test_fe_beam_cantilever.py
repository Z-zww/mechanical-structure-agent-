import math
import unittest

from tools.fe_beam_cantilever import (
    FORMULA_VERSION,
    InputError,
    SolverError,
    calculate,
)


SOLID_PAYLOAD = {
    "load_n": 1000,
    "length_mm": 500,
    "youngs_modulus_gpa": 200,
    "width_mm": 40,
    "height_mm": 70,
    "n_elements": 20,
    "yield_strength_mpa": 235,
    "max_deflection_mm": 2.0,
    "min_safety_factor": 2.3,
}

CUSTOM_INERTIA_PAYLOAD = {
    "load_n": 1000,
    "length_mm": 500,
    "youngs_modulus_gpa": 200,
    "inertia_mm4": 280845.3,
    "neutral_axis_mm": 35,
    "yield_strength_mpa": 235,
    "min_safety_factor": 2.3,
}


class BeamElementFeaReviewTests(unittest.TestCase):
    def test_formula_version(self):
        self.assertEqual(
            FORMULA_VERSION,
            "cantilever-euler-bernoulli-beam-elements-end-load-v2",
        )

    def test_solid_section_is_feasible_and_matches_analytical(self):
        result = calculate(SOLID_PAYLOAD)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "feasible")
        self.assertEqual(result["failed_constraints"], [])
        for metric, entry in result["comparison"].items():
            self.assertTrue(
                math.isclose(entry["fea"], entry["analytical"], rel_tol=1e-9),
                msg=f"{metric} 未与解析解一致",
            )

    def test_custom_inertia_section_is_feasible(self):
        result = calculate(CUSTOM_INERTIA_PAYLOAD)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "feasible")
        for entry in result["comparison"].values():
            self.assertTrue(
                math.isclose(entry["fea"], entry["analytical"], rel_tol=1e-9)
            )

    def test_mesh_consistency_across_element_counts(self):
        result = calculate(CUSTOM_INERTIA_PAYLOAD)
        deflections = [m["tip_deflection_mm"] for m in result["mesh_consistency"]]
        self.assertEqual(
            [m["n_elements"] for m in result["mesh_consistency"]],
            [1, 2, 5, 20],
        )
        for value in deflections[1:]:
            self.assertTrue(math.isclose(value, deflections[0], rel_tol=1e-9))

    def test_constraint_failure_is_structured(self):
        payload = {
            "load_n": 5000,
            "length_mm": 500,
            "youngs_modulus_gpa": 200,
            "inertia_mm4": 280845.3,
            "neutral_axis_mm": 35,
            "yield_strength_mpa": 235,
            "min_safety_factor": 2.3,
        }
        result = calculate(payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "constraint_failed")
        self.assertIn("safety_factor", result["failed_constraints"])

    def test_default_safety_limit_is_one_when_limit_omitted(self):
        # 未提供 min_safety_factor 时，默认要求 SF>=1.0；该工况会进入屈服。
        payload = {
            "load_n": 20000,
            "length_mm": 500,
            "youngs_modulus_gpa": 200,
            "inertia_mm4": 280845.3,
            "neutral_axis_mm": 35,
            "yield_strength_mpa": 235,
        }
        result = calculate(payload)
        self.assertEqual(result["status"], "constraint_failed")
        self.assertIn("safety_factor", result["failed_constraints"])
        self.assertEqual(result["constraints"]["safety_factor"]["limit"], 1.0)

    def test_missing_section_is_rejected(self):
        with self.assertRaises(InputError):
            calculate({
                "load_n": 1000,
                "length_mm": 500,
                "youngs_modulus_gpa": 200,
            })

    def test_conflicting_section_modes_are_rejected(self):
        payload = dict(SOLID_PAYLOAD)
        payload["inertia_mm4"] = 280845.3
        payload["neutral_axis_mm"] = 35
        with self.assertRaises(InputError):
            calculate(payload)

    def test_boolean_load_is_rejected(self):
        payload = dict(SOLID_PAYLOAD)
        payload["load_n"] = True
        with self.assertRaises(InputError):
            calculate(payload)

    def test_nan_load_is_rejected(self):
        payload = dict(SOLID_PAYLOAD)
        payload["load_n"] = float("nan")
        with self.assertRaises(InputError):
            calculate(payload)

    def test_boolean_element_count_is_rejected(self):
        payload = dict(SOLID_PAYLOAD)
        payload["n_elements"] = True
        with self.assertRaises(InputError):
            calculate(payload)

    def test_element_count_out_of_range_is_rejected(self):
        payload = dict(SOLID_PAYLOAD)
        payload["n_elements"] = 150
        with self.assertRaises(InputError):
            calculate(payload)

    def test_non_object_payload_is_rejected(self):
        with self.assertRaises(InputError):
            calculate([1, 2, 3])

    def test_solver_error_class_exists(self):
        self.assertTrue(issubclass(SolverError, RuntimeError))


if __name__ == "__main__":
    unittest.main()
