"""Regenerate the checked-in Chinese HTML demo from deterministic tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.design_dossier import generate
from tools.hollow_cantilever_calculator import calculate
from tools.hollow_design_search import search
from tools.hollow_design_sensitivity import analyze
from tools.hollow_manufacturing_tolerance import verify


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    constraints = {
        "max_deflection_mm": 2.0,
        "min_safety_factor": 2.3,
        "max_mass_kg": 20.0,
        "min_local_buckling_factor": 1.0,
    }
    base = {
        "load_n": 1000.0,
        "length_mm": 500.0,
        "material_id": "steel_s235",
        **constraints,
    }

    initial_input = {
        **base,
        "outer_width_mm": 40.0,
        "outer_height_mm": 50.0,
        "wall_thickness_mm": 2.0,
        "outer_corner_radius_mm": 5.0,
    }
    initial_result = calculate(initial_input)
    if initial_result["status"] != "constraint_failed":
        raise RuntimeError("演示初始方案预期应因安全系数约束失败")

    search_result = search({
        **base,
        "outer_width_options_mm": [40, 60, 80],
        "outer_height_options_mm": [50, 80, 100],
        "wall_thickness_options_mm": [2, 4],
        "outer_corner_radius_options_mm": [5, 10],
        "max_candidates": 100,
    })
    if search_result["status"] != "feasible" or not search_result["best_candidate"]:
        raise RuntimeError("演示搜索没有返回可行候选方案")

    best = search_result["best_candidate"]
    final_input = {
        **base,
        "outer_width_mm": best["outer_width_mm"],
        "outer_height_mm": best["outer_height_mm"],
        "wall_thickness_mm": best["wall_thickness_mm"],
        "outer_corner_radius_mm": best["outer_corner_radius_mm"],
    }
    calculation_result = calculate(final_input)
    sensitivity_result = analyze({**final_input, "perturbation_percent": 5.0})
    tolerance_result = verify({
        **final_input,
        "length_tolerance_mm": 2.0,
        "outer_width_tolerance_mm": 0.5,
        "outer_height_tolerance_mm": 0.5,
        "wall_thickness_tolerance_mm": 0.1,
        "outer_corner_radius_tolerance_mm": 0.5,
        "load_tolerance_percent": 10.0,
    })
    if calculation_result["status"] != "feasible":
        raise RuntimeError("搜索最优候选在独立单点复算时未通过约束")
    if tolerance_result["status"] != "robust_feasible":
        raise RuntimeError("最终演示候选未通过64个公差角点")

    reference_data = json.loads(
        (PROJECT_ROOT / "validation/results/steel_for_life_hfrhs_reference_comparison.json")
        .read_text(encoding="utf-8")
    )
    public_reference = {
        "source": reference_data["source"],
        "source_file": (
            "https://www.steelforlifebluebook.co.uk/hfrhs/ec3-ukna/"
            "section-properties-dimensions-properties"
        ),
        "not_experimental": reference_data["not_experimental"],
        "cases": reference_data["cases"],
        "limitations": reference_data["limitations"],
    }
    trace = [
        {
            "step": 1,
            "stage": "initial_calculation",
            "result_status": initial_result["status"],
            "failed_constraints": initial_result["failed_constraints"],
            "metrics": initial_result["metrics"],
            "decision": "初始方案安全系数低于2.3；保持材料、载荷和长度，转入候选搜索。",
        },
        {
            "step": 2,
            "stage": "candidate_search",
            "search_version": search_result["search_version"],
            "combinations_considered": search_result["combinations_considered"],
            "candidates_evaluated": search_result["candidates_evaluated"],
            "invalid_geometry_count": search_result["invalid_geometry_count"],
            "feasible_count": search_result["feasible_count"],
            "objective": search_result["objective"],
        },
        {
            "step": 3,
            "stage": "final_calculation",
            "result_status": calculation_result["status"],
            "failed_constraints": calculation_result["failed_constraints"],
            "selected_dimensions": {key: final_input[key] for key in (
                "outer_width_mm", "outer_height_mm", "wall_thickness_mm",
                "outer_corner_radius_mm",
            )},
        },
        {
            "step": 4,
            "stage": "sensitivity_analysis",
            "status": sensitivity_result["status"],
            "perturbation_percent": sensitivity_result["perturbation_percent"],
            "dominant_parameters": sensitivity_result["dominant_parameters"],
        },
        {
            "step": 5,
            "stage": "tolerance_verification",
            "status": tolerance_result["status"],
            "cases_evaluated": tolerance_result["cases_evaluated"],
            "passed_cases": tolerance_result["passed_cases"],
            "invalid_geometry_cases": tolerance_result["invalid_geometry_cases"],
        },
    ]
    payload = {
        "project_name": "圆角空心悬臂支架确定性设计验证",
        "task_summary": "以给定载荷、材料和制造约束完成方案搜索、复算与边界验证。",
        "final_status": "completed_feasible_robust",
        "format": "html",
        "evidence_note": (
            "报告数值由随项目提供的确定性计算、搜索、敏感性和公差工具生成。"
            "公开型材数据仅作工程参考对比，不代表真实实验或实物测试。"
        ),
        "calculation_result": calculation_result,
        "search_result": search_result,
        "sensitivity_result": sensitivity_result,
        "tolerance_result": tolerance_result,
        "replanning_trace": trace,
        "public_reference_result": public_reference,
    }
    dossier = generate(payload)
    if not dossier["content"].startswith("<!doctype html>"):
        raise RuntimeError("报告生成器没有返回独立HTML文档")
    if "constraint-chart" not in dossier["content"]:
        raise RuntimeError("报告缺少来自工具约束的裕度可视化")
    if "class=\"trace-list\"" not in dossier["content"]:
        raise RuntimeError("报告缺少逐步呈现的重规划轨迹")

    dossier["content"] = "\n".join(
        line.rstrip() for line in dossier["content"].splitlines()
    ) + "\n"

    (PROJECT_ROOT / "report.html").write_text(dossier["content"], encoding="utf-8")
    _write_json(PROJECT_ROOT / "cases/generated_dossier_v3.json", dossier)
    print(json.dumps({
        "report": "report.html",
        "format": dossier["format"],
        "status": calculation_result["status"],
        "selected_dimensions": trace[2]["selected_dimensions"],
        "search_feasible_count": search_result["feasible_count"],
        "tolerance": {
            "status": tolerance_result["status"],
            "cases": tolerance_result["cases_evaluated"],
            "passed": tolerance_result["passed_cases"],
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
