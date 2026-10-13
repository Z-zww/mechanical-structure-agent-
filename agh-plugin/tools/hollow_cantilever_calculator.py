"""Deterministic rounded hollow rectangular cantilever calculator.

The section has a constant wall thickness and rounded corners. Bending is
about the horizontal centroidal axis, so ``outer_height_mm`` is the bending
height. Local buckling is an elastic plate screening calculation, not a full
material-specific code verification.
Material parameters are reused from the solid-section calculator and are
engineering reference values, not experimental measurements.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

try:
    from tools.cantilever_calculator import InputError, MATERIALS
except ModuleNotFoundError:  # Direct execution by the AGH Python subprocess.
    from cantilever_calculator import InputError, MATERIALS


FORMULA_VERSION = "cantilever-rounded-hollow-rectangular-end-load-v2"
STABILITY_VERSION = "elastic-plate-local-buckling-screening-v1"
FLANGE_BUCKLING_COEFFICIENT = 4.0
WEB_BUCKLING_COEFFICIENT = 23.9


class GeometryError(InputError):
    """Raised when a positive input cannot form a hollow rectangle."""


def _positive_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{key}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{key}必须是有限正数")
    return value


def _finite_metrics(metrics: dict[str, float]) -> None:
    if not all(math.isfinite(value) for value in metrics.values()):
        raise ArithmeticError("计算结果包含非有限数值")


def _rounded_rectangle_properties(
    width_mm: float, height_mm: float, radius_mm: float
) -> tuple[float, float]:
    """Return area and centroidal I_x of a rounded rectangle in mm units."""
    area_mm2 = width_mm * height_mm - (4.0 - math.pi) * radius_mm**2
    corner_y_mm = height_mm / 2.0 - radius_mm
    square_corner_i_mm4 = radius_mm * (
        (corner_y_mm + radius_mm) ** 3 - corner_y_mm**3
    ) / 3.0
    quarter_circle_i_mm4 = (
        math.pi * radius_mm**2 * corner_y_mm**2 / 4.0
        + 2.0 * corner_y_mm * radius_mm**3 / 3.0
        + math.pi * radius_mm**4 / 16.0
    )
    inertia_mm4 = (
        width_mm * height_mm**3 / 12.0
        - 4.0 * (square_corner_i_mm4 - quarter_circle_i_mm4)
    )
    return area_mm2, inertia_mm4


def _elastic_plate_critical_stress_mpa(
    youngs_modulus_mpa: float,
    poisson_ratio: float,
    thickness_mm: float,
    flat_width_mm: float,
    buckling_coefficient: float,
) -> float:
    return (
        buckling_coefficient
        * math.pi**2
        * youngs_modulus_mpa
        / (12.0 * (1.0 - poisson_ratio**2))
        * (thickness_mm / flat_width_mm) ** 2
    )


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate hollow-section metrics and optional constraint checks."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")

    load_n = _positive_number(payload, "load_n")
    length_mm = _positive_number(payload, "length_mm")
    outer_width_mm = _positive_number(payload, "outer_width_mm")
    outer_height_mm = _positive_number(payload, "outer_height_mm")
    wall_thickness_mm = _positive_number(payload, "wall_thickness_mm")
    outer_corner_radius_mm = _positive_number(payload, "outer_corner_radius_mm")
    material_id = payload.get("material_id")
    if not isinstance(material_id, str) or material_id not in MATERIALS:
        raise InputError("material_id必须是已支持的材料ID")

    inner_width_mm = outer_width_mm - 2.0 * wall_thickness_mm
    inner_height_mm = outer_height_mm - 2.0 * wall_thickness_mm
    if inner_width_mm <= 0 or inner_height_mm <= 0:
        raise GeometryError("外部尺寸必须严格大于两倍壁厚，内腔尺寸必须为正数")
    if outer_corner_radius_mm <= wall_thickness_mm:
        raise GeometryError("实际圆角模型要求外圆角半径严格大于壁厚")
    if outer_corner_radius_mm >= min(outer_width_mm, outer_height_mm) / 2.0:
        raise GeometryError("外圆角半径必须小于外宽和外高较小值的一半")
    inner_corner_radius_mm = outer_corner_radius_mm - wall_thickness_mm
    flange_flat_width_mm = outer_width_mm - 2.0 * outer_corner_radius_mm
    web_flat_height_mm = outer_height_mm - 2.0 * outer_corner_radius_mm
    if flange_flat_width_mm <= 0 or web_flat_height_mm <= 0:
        raise GeometryError("圆角之间的翼缘和腹板平直段必须为正数")

    material = MATERIALS[material_id]
    youngs_modulus_mpa = float(material["youngs_modulus_gpa"]) * 1000.0
    yield_strength_mpa = float(material["yield_strength_mpa"])
    density_kg_m3 = float(material["density_kg_m3"])
    poisson_ratio = float(material["poisson_ratio"])

    outer_area_mm2, outer_inertia_mm4 = _rounded_rectangle_properties(
        outer_width_mm, outer_height_mm, outer_corner_radius_mm
    )
    inner_area_mm2, inner_inertia_mm4 = _rounded_rectangle_properties(
        inner_width_mm, inner_height_mm, inner_corner_radius_mm
    )
    area_mm2 = outer_area_mm2 - inner_area_mm2
    inertia_mm4 = outer_inertia_mm4 - inner_inertia_mm4
    section_modulus_mm3 = inertia_mm4 / (outer_height_mm / 2.0)
    moment_nmm = load_n * length_mm
    stress_mpa = moment_nmm / section_modulus_mm3
    deflection_mm = load_n * length_mm**3 / (3.0 * youngs_modulus_mpa * inertia_mm4)
    volume_m3 = area_mm2 * length_mm * 1.0e-9
    mass_kg = density_kg_m3 * volume_m3
    safety_factor = yield_strength_mpa / stress_mpa
    flange_critical_stress_mpa = _elastic_plate_critical_stress_mpa(
        youngs_modulus_mpa,
        poisson_ratio,
        wall_thickness_mm,
        flange_flat_width_mm,
        FLANGE_BUCKLING_COEFFICIENT,
    )
    web_critical_stress_mpa = _elastic_plate_critical_stress_mpa(
        youngs_modulus_mpa,
        poisson_ratio,
        wall_thickness_mm,
        web_flat_height_mm,
        WEB_BUCKLING_COEFFICIENT,
    )
    flange_buckling_factor = flange_critical_stress_mpa / stress_mpa
    web_buckling_factor = web_critical_stress_mpa / stress_mpa
    local_buckling_factor = min(flange_buckling_factor, web_buckling_factor)
    metrics = {
        "max_stress_mpa": stress_mpa,
        "max_deflection_mm": deflection_mm,
        "mass_kg": mass_kg,
        "safety_factor": safety_factor,
        "fixed_end_moment_nm": moment_nmm / 1000.0,
        "cross_section_area_mm2": area_mm2,
        "second_moment_mm4": inertia_mm4,
        "section_modulus_mm3": section_modulus_mm3,
        "local_buckling_factor": local_buckling_factor,
    }
    _finite_metrics(metrics)

    constraints: dict[str, dict[str, Any]] = {}
    if "max_deflection_mm" in payload:
        limit = _positive_number(payload, "max_deflection_mm")
        constraints["deflection"] = {
            "actual": deflection_mm,
            "limit": limit,
            "passed": deflection_mm <= limit,
        }
    if "min_safety_factor" in payload:
        limit = _positive_number(payload, "min_safety_factor")
        constraints["safety_factor"] = {
            "actual": safety_factor,
            "limit": limit,
            "passed": safety_factor >= limit,
        }
    if "max_mass_kg" in payload:
        limit = _positive_number(payload, "max_mass_kg")
        constraints["mass"] = {
            "actual": mass_kg,
            "limit": limit,
            "passed": mass_kg <= limit,
        }
    local_buckling_limit = (
        _positive_number(payload, "min_local_buckling_factor")
        if "min_local_buckling_factor" in payload
        else 1.0
    )
    constraints["local_buckling"] = {
        "actual": local_buckling_factor,
        "limit": local_buckling_limit,
        "passed": local_buckling_factor >= local_buckling_limit,
    }

    failed = [name for name, result in constraints.items() if not result["passed"]]
    return {
        "ok": True,
        "status": "feasible" if not failed else "constraint_failed",
        "formula_version": FORMULA_VERSION,
        "section_type": "hollow_rectangular",
        "units": {
            "stress": "MPa",
            "deflection": "mm",
            "mass": "kg",
            "safety_factor": "1",
            "area": "mm^2",
            "inertia": "mm^4",
            "section_modulus": "mm^3",
        },
        "input": {
            "load_n": load_n,
            "length_mm": length_mm,
            "outer_width_mm": outer_width_mm,
            "outer_height_mm": outer_height_mm,
            "wall_thickness_mm": wall_thickness_mm,
            "outer_corner_radius_mm": outer_corner_radius_mm,
            "material_id": material_id,
            "min_local_buckling_factor": local_buckling_limit,
        },
        "geometry": {
            "inner_width_mm": inner_width_mm,
            "inner_height_mm": inner_height_mm,
            "outer_corner_radius_mm": outer_corner_radius_mm,
            "inner_corner_radius_mm": inner_corner_radius_mm,
            "flange_flat_width_mm": flange_flat_width_mm,
            "web_flat_height_mm": web_flat_height_mm,
            "cross_section_area_mm2": area_mm2,
            "second_moment_mm4": inertia_mm4,
            "section_modulus_mm3": section_modulus_mm3,
        },
        "material": {"id": material_id, **material},
        "metrics": metrics,
        "stability_screening": {
            "status": "passed" if local_buckling_factor >= local_buckling_limit else "failed",
            "method_version": STABILITY_VERSION,
            "screening_only": True,
            "required_factor": local_buckling_limit,
            "governing_component": (
                "flange" if flange_buckling_factor <= web_buckling_factor else "web"
            ),
            "flange": {
                "stress_distribution": "uniform_compression",
                "buckling_coefficient": FLANGE_BUCKLING_COEFFICIENT,
                "flat_width_mm": flange_flat_width_mm,
                "width_thickness_ratio": flange_flat_width_mm / wall_thickness_mm,
                "critical_stress_mpa": flange_critical_stress_mpa,
                "buckling_factor": flange_buckling_factor,
                "passed": flange_buckling_factor >= local_buckling_limit,
            },
            "web": {
                "stress_distribution": "pure_bending_gradient",
                "buckling_coefficient": WEB_BUCKLING_COEFFICIENT,
                "flat_height_mm": web_flat_height_mm,
                "height_thickness_ratio": web_flat_height_mm / wall_thickness_mm,
                "critical_stress_mpa": web_critical_stress_mpa,
                "buckling_factor": web_buckling_factor,
                "passed": web_buckling_factor >= local_buckling_limit,
            },
            "reference_basis": [
                "经典弹性薄板屈曲方程",
                "EN 1993-1-5:2006+A2:2019内板单向应力板屈曲系数：均匀受压k=4.0，纯弯曲应力梯度k=23.9",
            ],
        },
        "constraints": constraints,
        "failed_constraints": failed,
        "limitations": [
            "采用小挠度、线弹性、Euler-Bernoulli梁和端部集中载荷假设",
            "局部屈曲结果是基于长板、简支纵边和理想弹性材料的工程筛查，不等同于材料专用规范验算",
            "未计入初始缺陷、残余应力、圆角板件耦合、屈曲后强度、整体屈曲、疲劳、连接和焊缝失效",
        ],
    }


def main() -> int:
    try:
        result = calculate(json.load(sys.stdin))
    except (json.JSONDecodeError, InputError) as exc:
        error_code = "INVALID_GEOMETRY" if isinstance(exc, GeometryError) else "INVALID_INPUT"
        result = {"ok": False, "error_code": error_code, "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive process boundary
        result = {"ok": False, "error_code": "CALCULATION_ERROR", "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
