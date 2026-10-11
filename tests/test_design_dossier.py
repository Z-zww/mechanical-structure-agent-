import json
import unittest

from tools.design_dossier import InputError, generate
from tools.hollow_cantilever_calculator import calculate as calculate_hollow


class DesignDossierTests(unittest.TestCase):
    def setUp(self):
        calculation = {
            "ok": True,
            "status": "feasible",
            "input": {
                "load_n": 1000,
                "length_mm": 500,
                "width_mm": 25,
                "height_mm": 40,
                "material_id": "steel_s235",
            },
            "metrics": {
                "max_stress_mpa": 75,
                "max_deflection_mm": 1.5625,
                "mass_kg": 3.925,
                "safety_factor": 3.1333,
            },
            "failed_constraints": [],
        }
        tolerance = {"status": "robust_feasible", "cases_evaluated": 16, "passed_cases": 16}
        self.payload = {
            "project_name": "悬臂支架设计验证",
            "task_summary": "在安全系数、挠度和质量约束下验证矩形截面方案。",
            "final_status": "robust_feasible",
            "calculation_result_json": json.dumps(calculation),
            "tolerance_result_json": json.dumps(tolerance),
            "replanning_trace_json": json.dumps([{"stage": "replanned", "width_mm": 25, "height_mm": 40}]),
        }

        self.public_reference = {
            "source": "SCI / Steel for Life Interactive Blue Book",
            "source_file": "validation/sources/steel_for_life_hfrhs_table_2026-10-11.html",
            "not_experimental": True,
            "cases": [{
                "source_record": "SCI-HFRHS-50x30x3.2",
                "tabulated_properties": {
                    "area_mm2": 460,
                    "major_inertia_mm4": 142000,
                    "major_modulus_mm3": 5680,
                    "mass_kg_per_m": 3.61,
                },
                "derived_response": {
                    "max_stress_mpa": 35.2113,
                    "max_deflection_mm": 0.375587,
                    "mass_kg": 1.444,
                },
            }],
            "limitations": ["公开表未提供圆角半径"],
        }

    def test_generates_markdown_from_structured_results(self):
        result = generate(self.payload)
        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["format"], "markdown")
        self.assertTrue(result["content"].startswith("# 悬臂支架设计验证"))
        self.assertIn("75", result["content"])
        self.assertIn("16", result["content"])
        self.assertIn("不代表真实实验", result["content"])
        self.assertIn("规范依据", result["content"])
        self.assertIn("EN 1993-1-5:2006+A2:2019", result["content"])
        self.assertIn("状态定义", result["content"])
        self.assertEqual(result["dossier_version"], "cantilever-design-dossier-v3")

    def test_includes_optional_public_reference_in_both_formats(self):
        payload = {**self.payload, "public_reference_result": self.public_reference}
        for output_format in ("markdown", "html"):
            with self.subTest(output_format=output_format):
                result = generate({**payload, "format": output_format})
                self.assertIn("公开工程参考对比", result["content"])
                self.assertIn("SCI-HFRHS-50x30x3.2", result["content"])
                self.assertIn("不代表真实实验验证", result["content"])
                self.assertIn("public_reference_result", result["source_checks"])
                self.assertTrue(result["source_checks"]["public_reference_result"])

    def test_legacy_payload_without_public_reference_remains_compatible(self):
        result = generate(self.payload)
        self.assertNotIn("公开工程参考对比", result["content"])
        self.assertFalse(result["source_checks"]["public_reference_result"])

    def test_accepts_native_structured_results_without_json_string_wrapping(self):
        native_payload = {
            **self.payload,
            "calculation_result": json.loads(self.payload["calculation_result_json"]),
            "tolerance_result": json.loads(self.payload["tolerance_result_json"]),
            "replanning_trace": json.loads(self.payload["replanning_trace_json"]),
        }
        for legacy_key in (
            "calculation_result_json",
            "tolerance_result_json",
            "replanning_trace_json",
        ):
            native_payload.pop(legacy_key)
        result = generate(native_payload)
        self.assertEqual(result["status"], "generated")
        self.assertIn("75", result["content"])
        self.assertIn("16", result["content"])

    def test_native_calculation_result_is_required_to_be_an_object(self):
        with self.assertRaises(InputError):
            generate({
                **self.payload,
                "calculation_result": [1, 2, 3],
                "calculation_result_json": None,
            })

    def test_generates_html_with_escaped_content(self):
        result = generate({**self.payload, "format": "html", "project_name": "A < B"})
        self.assertEqual(result["format"], "html")
        self.assertIn("&lt;", result["content"])
        self.assertIn('<meta charset="UTF-8">', result["content"])
        self.assertIn("<table>", result["content"])
        self.assertNotIn("<pre>", result["content"])
        self.assertIn("在安全系数", result["content"])

    def test_localizes_english_summary_status_and_material(self):
        calculation = json.loads(self.payload["calculation_result_json"])
        calculation["input"]["material_id"] = "titanium_ti6al4v"
        payload = {
            **self.payload,
            "task_summary": "Deterministic engineering design verification.",
            "final_status": "All constraints passed",
            "calculation_result_json": json.dumps(calculation),
        }
        html_result = generate({**payload, "format": "html"})["content"]
        markdown_result = generate(payload)["content"]
        for content in (html_result, markdown_result):
            self.assertIn("当前已提供约束通过", content)
            self.assertIn("Ti-6Al-4V钛合金（工程参考参数）", content)
            self.assertIn("对矩形实心截面悬臂支架进行确定性工程校核", content)
        self.assertNotIn("Deterministic engineering design verification", html_result)

    def test_is_repeatable(self):
        self.assertEqual(generate(self.payload), generate(self.payload))

    def test_rejects_invalid_format(self):
        with self.assertRaises(InputError):
            generate({**self.payload, "format": "pdf"})

    def test_rejects_invalid_calculation_json(self):
        with self.assertRaises(InputError):
            generate({**self.payload, "calculation_result_json": "not-json"})

    def test_rejects_missing_metric(self):
        calculation = json.loads(self.payload["calculation_result_json"])
        del calculation["metrics"]["safety_factor"]
        with self.assertRaises(InputError):
            generate({**self.payload, "calculation_result_json": json.dumps(calculation)})

    def test_replaces_lone_surrogate_in_report_text(self):
        result = generate({**self.payload, "evidence_note": "异常字符：\udcac"})
        self.assertNotIn("\udcac", result["content"])
        self.assertIn("\ufffd", result["content"])

    def test_falls_back_for_mojibake_project_name(self):
        result = generate({**self.payload, "project_name": "����֧��ȷ���Թ�����֤"})
        self.assertIn("# 悬臂支架确定性工程设计验证", result["content"])
        self.assertIn("疑似存在编码异常", result["content"])

    def test_generates_hollow_report_with_geometry_and_stability(self):
        calculation = calculate_hollow({
            "load_n": 1000,
            "length_mm": 500,
            "outer_width_mm": 40,
            "outer_height_mm": 60,
            "wall_thickness_mm": 4,
            "outer_corner_radius_mm": 8,
            "material_id": "steel_s235",
            "max_deflection_mm": 2,
            "min_safety_factor": 2.3,
            "max_mass_kg": 20,
            "min_local_buckling_factor": 1,
        })
        tolerance = {
            "status": "robust_feasible",
            "cases_evaluated": 64,
            "passed_cases": 64,
            "invalid_geometry_cases": 0,
        }
        payload = {
            **self.payload,
            "project_name": "圆角空心悬臂支架验证",
            "calculation_result_json": json.dumps(calculation),
            "tolerance_result_json": json.dumps(tolerance),
            "final_status": "robust_feasible",
        }
        for output_format in ("markdown", "html"):
            with self.subTest(output_format=output_format):
                content = generate({**payload, "format": output_format})["content"]
                self.assertIn("外圆角", content)
                self.assertIn("壁厚", content)
                self.assertIn("局部屈曲", content)
                self.assertIn("腹板", content)
                self.assertIn("不得外推为实际允许应力", content)
                self.assertIn("规范依据", content)
                self.assertIn("64", content)
                self.assertNotIn("矩形实心梁公式范围", content)


if __name__ == "__main__":
    unittest.main()
