import unittest

from tools.design_search import InputError, search


class DesignSearchTests(unittest.TestCase):
    def test_finds_and_ranks_feasible_candidates(self):
        result = search(
            {
                "load_n": 1000,
                "length_mm": 300,
                "material_id": "steel_s235",
                "width_options_mm": [20, 50],
                "height_options_mm": [20, 80],
                "max_deflection_mm": 2,
                "min_safety_factor": 2,
                "max_mass_kg": 10,
            }
        )
        self.assertEqual(result["status"], "feasible")
        self.assertEqual(result["candidates_evaluated"], 4)
        self.assertEqual(result["best_candidate"]["width_mm"], 50)
        self.assertEqual(result["best_candidate"]["height_mm"], 20)

    def test_reports_no_feasible_candidate(self):
        result = search(
            {
                "load_n": 1000,
                "length_mm": 300,
                "material_id": "steel_s235",
                "width_options_mm": [10],
                "height_options_mm": [10],
                "max_deflection_mm": 0.001,
            }
        )
        self.assertEqual(result["status"], "no_feasible_candidate")
        self.assertIsNone(result["best_candidate"])
        self.assertEqual(result["failed_constraint_counts"]["deflection"], 1)

    def test_rejects_too_many_combinations(self):
        with self.assertRaises(InputError):
            search(
                {
                    "load_n": 1000,
                    "length_mm": 300,
                    "material_id": "steel_s235",
                    "width_options_mm": list(range(1, 51)),
                    "height_options_mm": list(range(1, 51)),
                }
            )


if __name__ == "__main__":
    unittest.main()
