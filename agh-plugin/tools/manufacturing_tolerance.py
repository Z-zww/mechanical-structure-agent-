"""Deterministic corner-case robustness check for manufacturing tolerances."""

from __future__ import annotations

import itertools
import json
import math
import sys
from typing import Any

try:
    from tools.cantilever_calculator import InputError, calculate
except ModuleNotFoundError:  # Direct execution by the AGH Python subprocess.
    from cantilever_calculator import InputError, calculate


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


def _severity(result: dict[str, Any]) -> float:
    ratios: list[float] = []
    for name, constraint in result["constraints"].items():
        actual = float(constraint["actual"])
        limit = float(constraint["limit"])
        if not math.isfinite(actual) or not math.isfinite(limit) or limit <= 0:
            ratios.append(SEVERITY_CAP)
            continue
        if name == "safety_factor":
            ratio = SEVERITY_CAP if actual <= 0 else limit / actual
        else:
            ratio = actual / limit
        ratios.append(min(SEVERITY_CAP, ratio) if math.isfinite(ratio) else SEVERITY_CAP)
    return max(ratios, default=0.0)


def _bounds(nominal: float, tolerance: float, name: str) -> tuple[float, float]:
    lower = nominal - tolerance
    if lower < MIN_EFFECTIVE_DIMENSION_MM:
        raise InputError(
            f"{name}公差过大，公差下限必须不小于{MIN_EFFECTIVE_DIMENSION_MM}mm"
        )
    return lower, nominal + tolerance


def _unique(values: tuple[float, float]) -> tuple[float, ...]:
    """Return unique bounds while preserving lower/upper order."""
    return tuple(dict.fromkeys(values))


def verify(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate all width/height/load tolerance corners."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")
    base = {key: _positive(payload.get(key), key) for key in ("load_n", "length_mm", "width_mm", "height_mm")}
    material_id = payload.get("material_id")
    if not isinstance(material_id, str):
        raise InputError("material_id必须是字符串")
    width_tolerance_mm = _nonnegative(payload.get("width_tolerance_mm", 0), "width_tolerance_mm")
    height_tolerance_mm = _nonnegative(payload.get("height_tolerance_mm", 0), "height_tolerance_mm")
    length_tolerance_mm = _nonnegative(payload.get("length_tolerance_mm", 0), "length_tolerance_mm")
    load_tolerance_percent = _nonnegative(payload.get("load_tolerance_percent", 0), "load_tolerance_percent")
    if load_tolerance_percent > 20:
        raise InputError("load_tolerance_percent不能超过20")
    constraints = {
        key: payload[key]
        for key in ("max_deflection_mm", "min_safety_factor", "max_mass_kg")
        if key in payload
    }
    if not constraints:
        raise InputError("至少需要提供一个约束限值")

    load_fraction = load_tolerance_percent / 100.0
    load_bounds = _unique(
        (base["load_n"] * (1 - load_fraction), base["load_n"] * (1 + load_fraction))
    )
    length_bounds = _unique(_bounds(base["length_mm"], length_tolerance_mm, "length_mm"))
    width_bounds = _unique(_bounds(base["width_mm"], width_tolerance_mm, "width_mm"))
    height_bounds = _unique(_bounds(base["height_mm"], height_tolerance_mm, "height_mm"))
    dimensions = {
        "load_n": load_bounds,
        "length_mm": length_bounds,
        "width_mm": width_bounds,
        "height_mm": height_bounds,
    }
    cases: list[dict[str, Any]] = []
    for load_n, length_mm, width_mm, height_mm in itertools.product(
        dimensions["load_n"], dimensions["length_mm"], dimensions["width_mm"], dimensions["height_mm"]
    ):
        result = calculate(
            {
                **base,
                "load_n": load_n,
                "length_mm": length_mm,
                "width_mm": width_mm,
                "height_mm": height_mm,
                "material_id": material_id,
                **constraints,
            }
        )
        case = {
            "load_n": load_n,
            "length_mm": length_mm,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "status": result["status"],
            "metrics": result["metrics"],
            "constraints": result["constraints"],
            "failed_constraints": result["failed_constraints"],
            "severity": _severity(result),
        }
        cases.append(case)

    worst = max(cases, key=lambda case: case["severity"])
    failed = [case for case in cases if case["status"] != "feasible"]
    return {
        "ok": True,
        "status": "robust_feasible" if not failed else "robustness_failed",
        "tolerance_version": "cantilever-corner-tolerance-v2",
        "input": {
            **base,
            "material_id": material_id,
            "length_tolerance_mm": length_tolerance_mm,
            "width_tolerance_mm": width_tolerance_mm,
            "height_tolerance_mm": height_tolerance_mm,
            "load_tolerance_percent": load_tolerance_percent,
            **constraints,
        },
        "cases_evaluated": len(cases),
        "passed_cases": len(cases) - len(failed),
        "failed_cases": len(failed),
        "worst_case": worst,
        "corner_cases": cases,
        "failed_case_summaries": [
            {
                "load_n": case["load_n"],
                "length_mm": case["length_mm"],
                "width_mm": case["width_mm"],
                "height_mm": case["height_mm"],
                "failed_constraints": case["failed_constraints"],
                "severity": case["severity"],
            }
            for case in failed
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
