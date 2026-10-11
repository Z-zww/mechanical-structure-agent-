import math
import unittest

from tools.cantilever_calculator import InputError, MATERIALS, calculate


class CantileverCalculatorTests(unittest.TestCase):
    def test_expanded_material_library_is_calculable(self):
        expected = {
            "steel_s235", "aluminum_6061_t6", "steel_s355",
            "stainless_steel_304", "aluminum_7075_t6", "titanium_ti6al4v",
        }
        self.assertEqual(set(MATERIALS), expected)
        for material_id in expected:
            with self.subTest(material_id=material_id):
                result = calculate({
                    "load_n": 500,
                    "length_mm": 300,
                    "width_mm": 40,
                    "height_mm": 60,
                    "material_id": material_id,
                })
                self.assertTrue(result["ok"])
                self.assertEqual(result["input"]["material_id"], material_id)
                self.assertGreater(result["metrics"]["safety_factor"], 0)

    def test_known_steel_case_matches_formula(self):
        result = calculate(
            {
                "load_n": 1000,
                "length_mm": 300,
                "width_mm": 50,
                "height_mm": 80,
                "material_id": "steel_s235",
                "max_deflection_mm": 2.0,
                "min_safety_factor": 2.0,
                "max_mass_kg": 10.0,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "feasible")
        self.assertTrue(math.isclose(result["metrics"]["max_stress_mpa"], 5.625, rel_tol=1e-12))
        self.assertTrue(math.isclose(result["metrics"]["max_deflection_mm"], 0.02109375, rel_tol=1e-12))
        self.assertEqual(result["failed_constraints"], [])

    def test_constraint_failure_is_structured(self):
        result = calculate(
            {
                "load_n": 1000,
                "length_mm": 300,
                "width_mm": 20,
                "height_mm": 20,
                "material_id": "steel_s235",
                "max_deflection_mm": 0.01,
            }
        )
        self.assertEqual(result["status"], "constraint_failed")
        self.assertIn("deflection", result["failed_constraints"])

    def test_invalid_input_is_rejected(self):
        payloads = [
            {},
            {"load_n": -1, "length_mm": 300, "width_mm": 50, "height_mm": 80, "material_id": "steel_s235"},
            {"load_n": 1, "length_mm": 300, "width_mm": 50, "height_mm": 80, "material_id": "unknown"},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(InputError):
                    calculate(payload)


if __name__ == "__main__":
    unittest.main()
