"""Deterministic candidate search built on the cantilever calculator."""

from __future__ import annotations

import json
import math
import sys
from typing import Any

try:
    from tools.cantilever_calculator import InputError, calculate
except ModuleNotFoundError:  # Direct execution by the AGH Python subprocess.
    from cantilever_calculator import InputError, calculate


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{name}必须是有限正数")
    return value


def _positive_options(payload: dict[str, Any], name: str) -> list[float]:
    values = payload.get(name)
    if not isinstance(values, list) or not values or len(values) > 100:
        raise InputError(f"{name}必须是1到100个数值组成的数组")
    result = [_positive_number(value, f"{name}[{index}]") for index, value in enumerate(values)]
    return sorted(set(result))


def search(payload: dict[str, Any]) -> dict[str, Any]:
    """Enumerate width/height combinations and rank feasible designs by mass."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")

    load_n = _positive_number(payload.get("load_n"), "load_n")
    length_mm = _positive_number(payload.get("length_mm"), "length_mm")
    material_id = payload.get("material_id")
    if not isinstance(material_id, str):
        raise InputError("material_id必须是字符串")
    width_options_mm = _positive_options(payload, "width_options_mm")
    height_options_mm = _positive_options(payload, "height_options_mm")
    max_candidates = int(_positive_number(payload.get("max_candidates", 1000), "max_candidates"))
    if max_candidates > 1000:
        raise InputError("max_candidates不能超过1000")
    if len(width_options_mm) * len(height_options_mm) > max_candidates:
        raise InputError("候选组合数量超过max_candidates")

    constraints = {
        key: payload[key]
        for key in ("max_deflection_mm", "min_safety_factor", "max_mass_kg")
        if key in payload
    }
    base = {
        "load_n": load_n,
        "length_mm": length_mm,
        "material_id": material_id,
        **constraints,
    }
    feasible: list[dict[str, Any]] = []
    failed_counts: dict[str, int] = {}
    evaluated = 0
    for width_mm in width_options_mm:
        for height_mm in height_options_mm:
            evaluated += 1
            result = calculate({**base, "width_mm": width_mm, "height_mm": height_mm})
            candidate = {
                "width_mm": width_mm,
                "height_mm": height_mm,
                "status": result["status"],
                "metrics": result["metrics"],
                "failed_constraints": result["failed_constraints"],
            }
            if result["status"] == "feasible":
                feasible.append(candidate)
            for name in result["failed_constraints"]:
                failed_counts[name] = failed_counts.get(name, 0) + 1

    feasible.sort(
        key=lambda item: (
            item["metrics"]["mass_kg"],
            item["metrics"]["max_deflection_mm"],
            item["width_mm"] * item["height_mm"],
        )
    )
    return {
        "ok": True,
        "status": "feasible" if feasible else "no_feasible_candidate",
        "search_version": "cantilever-grid-search-v1",
        "objective": "先最小质量，再最小挠度",
        "input": {
            "load_n": load_n,
            "length_mm": length_mm,
            "material_id": material_id,
            "width_options_mm": width_options_mm,
            "height_options_mm": height_options_mm,
            **constraints,
        },
        "candidates_evaluated": evaluated,
        "feasible_count": len(feasible),
        "failed_constraint_counts": failed_counts,
        "best_candidate": feasible[0] if feasible else None,
        "feasible_candidates": feasible[:20],
    }


def main() -> int:
    try:
        result = search(json.load(sys.stdin))
    except (json.JSONDecodeError, InputError, ValueError) as exc:
        result = {"ok": False, "error_code": "INVALID_INPUT", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive process boundary
        result = {"ok": False, "error_code": "SEARCH_ERROR", "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
