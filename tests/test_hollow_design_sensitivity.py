import math
import unittest

from tools.hollow_design_sensitivity import InputError, analyze


class HollowDesignSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "load_n": 1000,
            "length_mm": 500,
            "outer_width_mm": 40,
            "outer_height_mm": 60,
            "wall_thickness_mm": 4,
            "outer_corner_radius_mm": 8,
            "material_id": "steel_s235",
            "perturbation_percent": 5,
            "min_local_buckling_factor": 1,
        }

    def test_returns_all_hollow_parameters_and_metrics(self):
        result = analyze(self.payload)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["section_type"], "hollow_rectangular_rounded")
        self.assertEqual(len(result["relative_sensitivity"]), 6)
        self.assertEqual(len(result["relative_sensitivity"]["wall_thickness_mm"]), 5)
        self.assertIn("local_buckling_factor", result["dominant_parameters"])

    def test_expected_physical_directions(self):
        sensitivity = analyze(self.payload)["relative_sensitivity"]
        self.assertGreater(sensitivity["load_n"]["max_stress_mpa"], 0.9)
        self.assertGreater(sensitivity["load_n"]["max_deflection_mm"], 0.9)
        self.assertGreater(sensitivity["wall_thickness_mm"]["mass_kg"], 0)
        self.assertLess(sensitivity["wall_thickness_mm"]["max_deflection_mm"], 0)
        self.assertGreater(sensitivity["wall_thickness_mm"]["local_buckling_factor"], 0)

    def test_length_and_load_are_reproducible(self):
        first = analyze(self.payload)
        second = analyze(self.payload)
        self.assertEqual(first, second)
        self.assertTrue(math.isfinite(first["baseline"]["local_buckling_factor"]))

    def test_invalid_perturbation_domain_is_rejected(self):
        with self.assertRaises(InputError):
            analyze({**self.payload, "wall_thickness_mm": 7, "outer_corner_radius_mm": 7.1})

    def test_rejects_excessive_perturbation(self):
        with self.assertRaises(InputError):
            analyze({**self.payload, "perturbation_percent": 21})

    def test_all_supported_materials_are_supported(self):
        for material_id in (
            "steel_s235", "aluminum_6061_t6", "steel_s355",
            "stainless_steel_304", "aluminum_7075_t6", "titanium_ti6al4v",
        ):
            with self.subTest(material_id=material_id):
                result = analyze({**self.payload, "material_id": material_id})
                self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
