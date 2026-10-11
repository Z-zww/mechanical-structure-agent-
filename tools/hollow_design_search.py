"""Deterministic grid search for rounded hollow rectangular cantilevers."""

from __future__ import annotations

import itertools
import json
import math
import sys
from typing import Any

try:
    from tools.cantilever_calculator import InputError, MATERIALS
    from tools.hollow_cantilever_calculator import GeometryError, calculate
except ModuleNotFoundError:  # Direct execution by the AGH Python subprocess.
    from cantilever_calculator import InputError, MATERIALS
    from hollow_cantilever_calculator import GeometryError, calculate


SEARCH_VERSION = "rounded-hollow-cantilever-grid-search-v1"
MAX_OPTIONS_PER_AXIS = 100
MAX_CANDIDATES = 1000


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{name}必须是有限正数")
    return value


def _positive_options(payload: dict[str, Any], name: str) -> list[float]:
    values = payload.get(name)
    if not isinstance(values, list) or not values or len(values) > MAX_OPTIONS_PER_AXIS:
        raise InputError(f"{name}必须是1到{MAX_OPTIONS_PER_AXIS}个数值组成的数组")
    normalized = [
        _positive_number(value, f"{name}[{index}]")
        for index, value in enumerate(values)
    ]
    return sorted(set(normalized))


def search(payload: dict[str, Any]) -> dict[str, Any]:
    """Enumerate valid four-axis designs and rank feasible candidates."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")

    load_n = _positive_number(payload.get("load_n"), "load_n")
    length_mm = _positive_number(payload.get("length_mm"), "length_mm")
    material_id = payload.get("material_id")
    if not isinstance(material_id, str) or material_id not in MATERIALS:
        raise InputError("material_id必须是已支持的材料ID")

    axes = {
        "outer_width_options_mm": _positive_options(payload, "outer_width_options_mm"),
        "outer_height_options_mm": _positive_options(payload, "outer_height_options_mm"),
        "wall_thickness_options_mm": _positive_options(payload, "wall_thickness_options_mm"),
        "outer_corner_radius_options_mm": _positive_options(
            payload, "outer_corner_radius_options_mm"
        ),
    }
    raw_max_candidates = _positive_number(
        payload.get("max_candidates", MAX_CANDIDATES), "max_candidates"
    )
    if not raw_max_candidates.is_integer():
        raise InputError("max_candidates必须是正整数")
    max_candidates = int(raw_max_candidates)
    if max_candidates > MAX_CANDIDATES:
        raise InputError(f"max_candidates不能超过{MAX_CANDIDATES}")

    combinations_considered = math.prod(len(values) for values in axes.values())
    if combinations_considered > max_candidates:
        raise InputError("候选组合数量超过max_candidates")

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
    base = {
        "load_n": load_n,
        "length_mm": length_mm,
        "material_id": material_id,
        **constraints,
    }

    feasible: list[dict[str, Any]] = []
    failed_constraint_counts: dict[str, int] = {}
    invalid_geometry_count = 0
    invalid_geometry_summaries: list[dict[str, Any]] = []
    evaluated = 0

    combinations = itertools.product(
        axes["outer_width_options_mm"],
        axes["outer_height_options_mm"],
        axes["wall_thickness_options_mm"],
        axes["outer_corner_radius_options_mm"],
    )
    for outer_width_mm, outer_height_mm, wall_thickness_mm, outer_corner_radius_mm in combinations:
        dimensions = {
            "outer_width_mm": outer_width_mm,
            "outer_height_mm": outer_height_mm,
            "wall_thickness_mm": wall_thickness_mm,
            "outer_corner_radius_mm": outer_corner_radius_mm,
        }
        try:
            result = calculate({**base, **dimensions})
        except GeometryError as exc:
            invalid_geometry_count += 1
            if len(invalid_geometry_summaries) < 20:
                invalid_geometry_summaries.append({**dimensions, "reason": str(exc)})
            continue

        evaluated += 1
        candidate = {
            **dimensions,
            "status": result["status"],
            "geometry": result["geometry"],
            "metrics": result["metrics"],
            "stability_screening": result["stability_screening"],
            "constraints": result["constraints"],
            "failed_constraints": result["failed_constraints"],
        }
        if result["status"] == "feasible":
            feasible.append(candidate)
        for name in result["failed_constraints"]:
            failed_constraint_counts[name] = failed_constraint_counts.get(name, 0) + 1

    feasible.sort(
        key=lambda item: (
            item["metrics"]["mass_kg"],
            item["metrics"]["max_deflection_mm"],
            -min(
                item["metrics"]["safety_factor"],
                item["metrics"]["local_buckling_factor"],
            ),
            item["outer_width_mm"] * item["outer_height_mm"],
            item["wall_thickness_mm"],
            item["outer_corner_radius_mm"],
        )
    )
    if evaluated == 0:
        status = "no_valid_geometry"
    elif feasible:
        status = "feasible"
    else:
        status = "no_feasible_candidate"

    return {
        "ok": True,
        "status": status,
        "search_version": SEARCH_VERSION,
        "objective": "先最小质量，再最小挠度，再最大化较小安全裕度",
        "input": {
            "load_n": load_n,
            "length_mm": length_mm,
            "material_id": material_id,
            **axes,
            "max_candidates": max_candidates,
            **constraints,
        },
        "combinations_considered": combinations_considered,
        "candidates_evaluated": evaluated,
        "invalid_geometry_count": invalid_geometry_count,
        "feasible_count": len(feasible),
        "failed_constraint_counts": failed_constraint_counts,
        "best_candidate": feasible[0] if feasible else None,
        "feasible_candidates": feasible[:20],
        "invalid_geometry_summaries": invalid_geometry_summaries,
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
