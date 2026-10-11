import unittest

from tools.hollow_design_search import InputError, search


class HollowDesignSearchTests(unittest.TestCase):
    def base(self):
        return {
            "load_n": 1000,
            "length_mm": 500,
            "material_id": "steel_s235",
            "outer_width_options_mm": [30, 40],
            "outer_height_options_mm": [50, 60],
            "wall_thickness_options_mm": [2, 4],
            "outer_corner_radius_options_mm": [6, 8],
            "max_deflection_mm": 2,
            "min_safety_factor": 2.3,
            "max_mass_kg": 20,
            "min_local_buckling_factor": 1,
        }

    def test_finds_and_ranks_feasible_candidates(self):
        result = search(self.base())
        self.assertEqual(result["status"], "feasible")
        self.assertEqual(result["combinations_considered"], 16)
        self.assertGreater(result["candidates_evaluated"], 0)
        self.assertGreater(result["feasible_count"], 0)
        masses = [item["metrics"]["mass_kg"] for item in result["feasible_candidates"]]
        self.assertEqual(masses, sorted(masses))
        self.assertEqual(result["best_candidate"], result["feasible_candidates"][0])

    def test_invalid_geometry_is_skipped_and_counted(self):
        result = search({
            **self.base(),
            "outer_width_options_mm": [20],
            "outer_height_options_mm": [20, 60],
            "wall_thickness_options_mm": [4],
            "outer_corner_radius_options_mm": [4, 8],
        })
        self.assertGreater(result["invalid_geometry_count"], 0)
        self.assertGreater(result["candidates_evaluated"], 0)
        self.assertEqual(
            result["combinations_considered"],
            result["invalid_geometry_count"] + result["candidates_evaluated"],
        )
        self.assertTrue(result["invalid_geometry_summaries"])

    def test_reports_no_valid_geometry_separately(self):
        result = search({
            **self.base(),
            "outer_width_options_mm": [20],
            "outer_height_options_mm": [20],
            "wall_thickness_options_mm": [10],
            "outer_corner_radius_options_mm": [10],
        })
        self.assertEqual(result["status"], "no_valid_geometry")
        self.assertEqual(result["candidates_evaluated"], 0)
        self.assertIsNone(result["best_candidate"])

    def test_reports_no_feasible_candidate_with_failure_counts(self):
        result = search({**self.base(), "max_deflection_mm": 1.0e-6})
        self.assertEqual(result["status"], "no_feasible_candidate")
        self.assertEqual(result["feasible_count"], 0)
        self.assertGreater(result["failed_constraint_counts"]["deflection"], 0)

    def test_deduplicates_options_before_counting(self):
        result = search({
            **self.base(),
            "outer_width_options_mm": [40, 40],
            "outer_height_options_mm": [60, 60],
            "wall_thickness_options_mm": [4, 4],
            "outer_corner_radius_options_mm": [8, 8],
        })
        self.assertEqual(result["combinations_considered"], 1)

    def test_rejects_fractional_or_excessive_candidate_limit(self):
        for max_candidates in (1.5, 1001):
            with self.subTest(max_candidates=max_candidates):
                with self.assertRaises(InputError):
                    search({**self.base(), "max_candidates": max_candidates})

    def test_rejects_too_many_combinations(self):
        with self.assertRaises(InputError):
            search({
                **self.base(),
                "outer_width_options_mm": list(range(20, 31)),
                "outer_height_options_mm": list(range(40, 51)),
                "wall_thickness_options_mm": list(range(1, 11)),
                "outer_corner_radius_options_mm": [4],
            })

    def test_rejects_unknown_material_before_geometry_enumeration(self):
        with self.assertRaises(InputError):
            search({**self.base(), "material_id": "unknown"})

    def test_is_repeatable(self):
        self.assertEqual(search(self.base()), search(self.base()))


if __name__ == "__main__":
    unittest.main()
