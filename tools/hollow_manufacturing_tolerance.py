"""Deterministic corner-case robustness check for rounded hollow sections."""

from __future__ import annotations

import itertools
import json
import math
import sys
from typing import Any

try:
    from tools.cantilever_calculator import InputError
    from tools.hollow_cantilever_calculator import GeometryError, calculate
except ModuleNotFoundError:  # Direct execution by the AGH Python subprocess.
    from cantilever_calculator import InputError
    from hollow_cantilever_calculator import GeometryError, calculate


TOLERANCE_VERSION = "rounded-hollow-cantilever-corner-tolerance-v1"
MIN_EFFECTIVE_DIMENSION_MM = 0.01
SEVERITY_CAP = 1.0e12


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{name}必须是有限正数")
    return value


def _nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是有限非负数")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise InputError(f"{name}必须是有限非负数")
    return value


def _bounds(nominal: float, tolerance: float, name: str) -> tuple[float, float]:
    lower = nominal - tolerance
    if lower < MIN_EFFECTIVE_DIMENSION_MM:
        raise InputError(
            f"{name}公差过大，公差下限必须不小于{MIN_EFFECTIVE_DIMENSION_MM}mm"
        )
    return lower, nominal + tolerance


def _unique(values: tuple[float, float]) -> tuple[float, ...]:
    return tuple(dict.fromkeys(values))


def _severity(result: dict[str, Any]) -> float:
    ratios: list[float] = []
    for name, constraint in result.get("constraints", {}).items():
        actual = float(constraint["actual"])
        limit = float(constraint["limit"])
        if not math.isfinite(actual) or not math.isfinite(limit) or limit <= 0:
            ratios.append(SEVERITY_CAP)
            continue
        if name in {"safety_factor", "local_buckling"}:
            ratio = SEVERITY_CAP if actual <= 0 else limit / actual
        else:
            ratio = actual / limit
        ratios.append(min(SEVERITY_CAP, ratio) if math.isfinite(ratio) else SEVERITY_CAP)
    return max(ratios, default=0.0)


def verify(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate all six-parameter tolerance corners."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")
    base = {
        key: _positive(payload.get(key), key)
        for key in (
            "load_n",
            "length_mm",
            "outer_width_mm",
            "outer_height_mm",
            "wall_thickness_mm",
            "outer_corner_radius_mm",
        )
    }
    material_id = payload.get("material_id")
    if not isinstance(material_id, str):
        raise InputError("material_id必须是字符串")

    tolerance_names = {
        "length_tolerance_mm": "length_mm",
        "outer_width_tolerance_mm": "outer_width_mm",
        "outer_height_tolerance_mm": "outer_height_mm",
        "wall_thickness_tolerance_mm": "wall_thickness_mm",
        "outer_corner_radius_tolerance_mm": "outer_corner_radius_mm",
    }
    tolerances = {
        tolerance_name: _nonnegative(payload.get(tolerance_name, 0), tolerance_name)
        for tolerance_name in tolerance_names
    }
    load_tolerance_percent = _nonnegative(
        payload.get("load_tolerance_percent", 0), "load_tolerance_percent"
    )
    if load_tolerance_percent > 20:
        raise InputError("load_tolerance_percent不能超过20")
    constraints = {
        key: payload[key]
        for key in (
            "max_deflection_mm",
            "min_safety_factor",
            "max_mass_kg",
            "min_local_buckling_factor",
        )
        if key in payload
    }
    if not constraints:
        raise InputError("至少需要提供一个约束限值")

    dimensions = {
        "load_n": _unique(
            (
                base["load_n"] * (1 - load_tolerance_percent / 100),
                base["load_n"] * (1 + load_tolerance_percent / 100),
            )
        ),
    }
    for tolerance_name, parameter_name in tolerance_names.items():
        dimensions[parameter_name] = _unique(
            _bounds(base[parameter_name], tolerances[tolerance_name], parameter_name)
        )

    cases: list[dict[str, Any]] = []
    failed_constraint_counts: dict[str, int] = {}
    valid_cases = 0
    invalid_geometry_cases = 0
    for values in itertools.product(
        dimensions["load_n"],
        dimensions["length_mm"],
        dimensions["outer_width_mm"],
        dimensions["outer_height_mm"],
        dimensions["wall_thickness_mm"],
        dimensions["outer_corner_radius_mm"],
    ):
        case_input = dict(zip(dimensions, values))
        try:
            result = calculate({**case_input, "material_id": material_id, **constraints})
        except GeometryError as exc:
            invalid_geometry_cases += 1
            cases.append({
                **case_input,
                "status": "invalid_geometry",
                "reason": str(exc),
                "failed_constraints": ["geometry"],
                "severity": SEVERITY_CAP,
            })
            continue

        valid_cases += 1
        for name in result["failed_constraints"]:
            failed_constraint_counts[name] = failed_constraint_counts.get(name, 0) + 1
        cases.append({
            **case_input,
            "status": result["status"],
            "geometry": result["geometry"],
            "metrics": result["metrics"],
            "stability_screening": result["stability_screening"],
            "constraints": result["constraints"],
            "failed_constraints": result["failed_constraints"],
            "severity": _severity(result),
        })

    passed_cases = [case for case in cases if case["status"] == "feasible"]
    failed_cases = [case for case in cases if case["status"] != "feasible"]
    valid_case_results = [case for case in cases if case["status"] != "invalid_geometry"]
    worst_valid_case = max(valid_case_results, key=lambda case: case["severity"], default=None)
    worst_invalid_case = max(
        (case for case in cases if case["status"] == "invalid_geometry"),
        key=lambda case: case["severity"],
        default=None,
    )
    return {
        "ok": True,
        "status": "robust_feasible" if not failed_cases else "robustness_failed",
        "tolerance_version": TOLERANCE_VERSION,
        "input": {
            **base,
            "material_id": material_id,
            **tolerances,
            "load_tolerance_percent": load_tolerance_percent,
            **constraints,
        },
        "cases_evaluated": len(cases),
        "valid_cases": valid_cases,
        "invalid_geometry_cases": invalid_geometry_cases,
        "passed_cases": len(passed_cases),
        "failed_cases": len(failed_cases),
        "failed_constraint_counts": failed_constraint_counts,
        "worst_case": worst_valid_case,
        "worst_invalid_geometry_case": worst_invalid_case,
        "corner_cases": cases,
        "failed_case_summaries": [
            {
                **{
                    key: case[key]
                    for key in (
                        "load_n",
                        "length_mm",
                        "outer_width_mm",
                        "outer_height_mm",
                        "wall_thickness_mm",
                        "outer_corner_radius_mm",
                    )
                },
                "status": case["status"],
                "failed_constraints": case["failed_constraints"],
                "reason": case.get("reason"),
                "severity": case["severity"],
            }
            for case in failed_cases
        ],
    }


def main() -> int:
    try:
        result = verify(json.load(sys.stdin))
    except (json.JSONDecodeError, InputError, ValueError) as exc:
        result = {"ok": False, "error_code": "INVALID_INPUT", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive process boundary
        result = {"ok": False, "error_code": "ROBUSTNESS_ERROR", "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
