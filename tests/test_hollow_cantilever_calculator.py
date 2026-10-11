import math
import unittest

from tools.hollow_cantilever_calculator import GeometryError, InputError, calculate


class HollowCantileverCalculatorTests(unittest.TestCase):
    def base(self):
        return {
            "load_n": 1000,
            "length_mm": 500,
            "outer_width_mm": 40,
            "outer_height_mm": 60,
            "wall_thickness_mm": 4,
            "outer_corner_radius_mm": 8,
            "material_id": "steel_s235",
            "max_deflection_mm": 2.0,
            "min_safety_factor": 2.3,
            "max_mass_kg": 20.0,
        }

    def test_known_geometry_and_units(self):
        result = calculate(self.base())
        self.assertEqual(result["status"], "feasible")
        self.assertEqual(result["geometry"]["inner_width_mm"], 32.0)
        self.assertEqual(result["geometry"]["inner_height_mm"], 52.0)
        expected_area = (
            40 * 60 - (4 - math.pi) * 8**2
            - (32 * 52 - (4 - math.pi) * 4**2)
        )
        self.assertTrue(math.isclose(result["geometry"]["cross_section_area_mm2"], expected_area))
        self.assertTrue(math.isclose(result["metrics"]["fixed_end_moment_nm"], 500.0))
        self.assertEqual(result["formula_version"], "cantilever-rounded-hollow-rectangular-end-load-v2")
        self.assertIn("local_buckling", result["constraints"])
        self.assertIn(result["stability_screening"]["governing_component"], {"flange", "web"})

    def test_wall_thickness_changes_stiffness_and_mass(self):
        thin = calculate({**self.base(), "wall_thickness_mm": 2})
        thick = calculate({**self.base(), "wall_thickness_mm": 6})
        self.assertLess(thick["metrics"]["max_deflection_mm"], thin["metrics"]["max_deflection_mm"])
        self.assertGreater(thick["metrics"]["mass_kg"], thin["metrics"]["mass_kg"])

    def test_boundary_equal_to_half_dimension_is_rejected(self):
        with self.assertRaises(GeometryError):
            calculate({**self.base(), "wall_thickness_mm": 20})

    def test_boundary_exceeding_half_dimension_is_rejected(self):
        with self.assertRaises(GeometryError):
            calculate({**self.base(), "wall_thickness_mm": 20.001})

    def test_near_boundary_with_positive_inner_height_is_valid(self):
        result = calculate({
            **self.base(),
            "outer_width_mm": 100,
            "outer_height_mm": 100,
            "wall_thickness_mm": 19.999,
            "outer_corner_radius_mm": 25,
        })
        self.assertGreater(result["geometry"]["inner_height_mm"], 0)
        self.assertTrue(math.isfinite(result["metrics"]["max_stress_mpa"]))

    def test_invalid_corner_radius_is_rejected(self):
        for radius in (4, 20, 21):
            with self.subTest(radius=radius):
                with self.assertRaises(GeometryError):
                    calculate({**self.base(), "outer_corner_radius_mm": radius})

    def test_nonfinite_and_boolean_values_are_rejected(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value):
                with self.assertRaises(InputError):
                    calculate({**self.base(), "load_n": value})

    def test_nonpositive_and_unknown_material_are_rejected(self):
        for key in ("load_n", "length_mm", "outer_width_mm", "outer_height_mm", "wall_thickness_mm"):
            with self.subTest(key=key):
                with self.assertRaises(InputError):
                    calculate({**self.base(), key: 0})
        with self.assertRaises(InputError):
            calculate({**self.base(), "material_id": "unknown"})

    def test_constraint_failure_is_structured(self):
        result = calculate({**self.base(), "min_safety_factor": 1.0e6})
        self.assertEqual(result["status"], "constraint_failed")
        self.assertIn("safety_factor", result["failed_constraints"])

    def test_web_is_checked_and_can_govern(self):
        result = calculate({
            **self.base(),
            "load_n": 40000,
            "outer_width_mm": 40,
            "outer_height_mm": 400,
            "wall_thickness_mm": 2,
            "outer_corner_radius_mm": 4,
            "min_local_buckling_factor": 1.0,
        })
        screening = result["stability_screening"]
        self.assertEqual(screening["governing_component"], "web")
        self.assertTrue(screening["flange"]["passed"])
        self.assertFalse(screening["web"]["passed"])
        self.assertIn("local_buckling", result["failed_constraints"])

    def test_flange_can_govern(self):
        result = calculate({
            **self.base(),
            "load_n": 10000,
            "outer_width_mm": 400,
            "outer_height_mm": 40,
            "wall_thickness_mm": 2,
            "outer_corner_radius_mm": 4,
            "min_local_buckling_factor": 1.0,
        })
        self.assertEqual(result["stability_screening"]["governing_component"], "flange")

    def test_requested_buckling_factor_controls_constraint(self):
        baseline = calculate(self.base())
        factor = baseline["metrics"]["local_buckling_factor"]
        failed = calculate({**self.base(), "min_local_buckling_factor": factor * 1.01})
        self.assertIn("local_buckling", failed["failed_constraints"])

    def test_all_supported_materials_are_calculable(self):
        for material_id in (
            "steel_s235", "aluminum_6061_t6", "steel_s355",
            "stainless_steel_304", "aluminum_7075_t6", "titanium_ti6al4v",
        ):
            with self.subTest(material_id=material_id):
                self.assertTrue(calculate({**self.base(), "material_id": material_id})["ok"])
                self.assertIn("poisson_ratio", calculate({**self.base(), "material_id": material_id})["material"])


if __name__ == "__main__":
    unittest.main()
