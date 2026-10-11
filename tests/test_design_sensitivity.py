import math
import unittest

from tools.design_sensitivity import InputError, analyze


class DesignSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "load_n": 1000,
            "length_mm": 300,
            "width_mm": 50,
            "height_mm": 20,
            "material_id": "steel_s235",
            "perturbation_percent": 5,
        }

    def test_returns_expected_physical_elasticities(self):
        result = analyze(self.payload)
        self.assertEqual(result["status"], "completed")
        sensitivity = result["relative_sensitivity"]
        self.assertTrue(math.isclose(sensitivity["height_mm"]["max_deflection_mm"], -3, rel_tol=0.02))
        self.assertTrue(math.isclose(sensitivity["width_mm"]["mass_kg"], 1, rel_tol=0.02))
        self.assertTrue(math.isclose(sensitivity["load_n"]["max_stress_mpa"], 1, rel_tol=0.02))
        self.assertEqual(result["dominant_parameters"]["max_deflection_mm"][0], "height_mm")

    def test_same_input_is_repeatable(self):
        self.assertEqual(analyze(self.payload), analyze(self.payload))

    def test_rejects_excessive_perturbation(self):
        with self.assertRaises(InputError):
            analyze({**self.payload, "perturbation_percent": 21})


if __name__ == "__main__":
    unittest.main()
