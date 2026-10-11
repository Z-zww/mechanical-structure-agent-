"""Deterministic cantilever calculator for the AGH mechanical-agent project."""

from __future__ import annotations

import json
import math
import sys
from typing import Any


FORMULA_VERSION = "cantilever-rectangular-end-load-v1"
MATERIALS: dict[str, dict[str, float | str]] = {
    "steel_s235": {
        "name": "S235钢（演示参数）",
        "youngs_modulus_gpa": 200.0,
        "yield_strength_mpa": 235.0,
        "density_kg_m3": 7850.0,
        "poisson_ratio": 0.30,
    },
    "aluminum_6061_t6": {
        "name": "6061-T6铝合金（演示参数）",
        "youngs_modulus_gpa": 68.9,
        "yield_strength_mpa": 276.0,
        "density_kg_m3": 2700.0,
        "poisson_ratio": 0.33,
    },
    "steel_s355": {
        "name": "S355结构钢（工程参考参数）",
        "youngs_modulus_gpa": 210.0,
        "yield_strength_mpa": 355.0,
        "density_kg_m3": 7850.0,
        "poisson_ratio": 0.30,
    },
    "stainless_steel_304": {
        "name": "304不锈钢（工程参考参数）",
        "youngs_modulus_gpa": 193.0,
        "yield_strength_mpa": 215.0,
        "density_kg_m3": 8000.0,
        "poisson_ratio": 0.29,
    },
    "aluminum_7075_t6": {
        "name": "7075-T6铝合金（工程参考参数）",
        "youngs_modulus_gpa": 71.7,
        "yield_strength_mpa": 503.0,
        "density_kg_m3": 2810.0,
        "poisson_ratio": 0.33,
    },
    "titanium_ti6al4v": {
        "name": "Ti-6Al-4V钛合金（工程参考参数）",
        "youngs_modulus_gpa": 114.0,
        "yield_strength_mpa": 880.0,
        "density_kg_m3": 4430.0,
        "poisson_ratio": 0.34,
    },
}


class InputError(ValueError):
    """Raised when the structured tool input is invalid."""


def _positive_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{key}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{key}必须是有限正数")
    return value


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate metrics and constraints from one normalized design payload."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")

    load_n = _positive_number(payload, "load_n")
    length_mm = _positive_number(payload, "length_mm")
    width_mm = _positive_number(payload, "width_mm")
    height_mm = _positive_number(payload, "height_mm")
    material_id = payload.get("material_id")
    if not isinstance(material_id, str) or material_id not in MATERIALS:
        raise InputError("material_id必须是已支持的材料ID")

    material = MATERIALS[material_id]
    E = float(material["youngs_modulus_gpa"]) * 1e9
    yield_strength = float(material["yield_strength_mpa"])
    density = float(material["density_kg_m3"])
    length = length_mm / 1000.0
    width = width_mm / 1000.0
    height = height_mm / 1000.0
    force = load_n

    inertia_m4 = width * height**3 / 12.0
    section_modulus_m3 = width * height**2 / 6.0
    moment_nm = force * length
    stress_mpa = (moment_nm / section_modulus_m3) / 1e6
    deflection_mm = (force * length**3 / (3.0 * E * inertia_m4)) * 1000.0
    volume_m3 = width * height * length
    mass_kg = density * volume_m3
    safety_factor = yield_strength / stress_mpa

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

    failed = [name for name, result in constraints.items() if not result["passed"]]
    return {
        "ok": True,
        "status": "feasible" if not failed else "constraint_failed",
        "formula_version": FORMULA_VERSION,
        "units": {"stress": "MPa", "deflection": "mm", "mass": "kg", "safety_factor": "1"},
        "input": {
            "load_n": load_n,
            "length_mm": length_mm,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "material_id": material_id,
        },
        "material": {"id": material_id, **material},
        "metrics": {
            "max_stress_mpa": stress_mpa,
            "max_deflection_mm": deflection_mm,
            "mass_kg": mass_kg,
            "safety_factor": safety_factor,
            "fixed_end_moment_nm": moment_nm,
        },
        "constraints": constraints,
        "failed_constraints": failed,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = calculate(payload)
    except (json.JSONDecodeError, InputError) as exc:
        result = {"ok": False, "error_code": "INVALID_INPUT", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive boundary for AGH wrapper
        result = {"ok": False, "error_code": "CALCULATION_ERROR", "message": str(exc)}
    # ASCII-escaped JSON avoids console code-page corruption when AGH reads stdout on Windows.
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
