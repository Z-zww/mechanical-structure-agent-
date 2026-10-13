"""Deterministic local sensitivity analysis for rounded hollow sections."""

from __future__ import annotations

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


SENSITIVITY_VERSION = "rounded-hollow-cantilever-local-sensitivity-v1"
METRICS = (
    "max_stress_mpa",
    "max_deflection_mm",
    "mass_kg",
    "safety_factor",
    "local_buckling_factor",
)
PARAMETERS = (
    "load_n",
    "length_mm",
    "outer_width_mm",
    "outer_height_mm",
    "wall_thickness_mm",
    "outer_corner_radius_mm",
)


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{name}必须是有限正数")
    return value


def _relative_effect(plus: float, minus: float, baseline: float, fraction: float) -> float:
    if not math.isfinite(baseline) or baseline == 0:
        raise InputError("基准指标不能为零或非有限数")
    value = ((plus - minus) / baseline) / (2.0 * fraction)
    if not math.isfinite(value):
        raise InputError("敏感度结果必须是有限数")
    return value


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """Return central-difference elasticities for the hollow-section model."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")
    base = {
        key: _positive_number(payload.get(key), key)
        for key in PARAMETERS
    }
    material_id = payload.get("material_id")
    if not isinstance(material_id, str):
        raise InputError("material_id必须是字符串")
    perturbation_percent = _positive_number(
        payload.get("perturbation_percent", 5), "perturbation_percent"
    )
    if perturbation_percent > 20:
        raise InputError("perturbation_percent不能超过20")
    fraction = perturbation_percent / 100.0
    extra = {
        key: payload[key]
        for key in ("min_local_buckling_factor", "max_deflection_mm", "min_safety_factor", "max_mass_kg")
        if key in payload
    }
    baseline_input = {**base, "material_id": material_id, **extra}
    try:
        baseline = calculate(baseline_input)
    except GeometryError as exc:
        raise InputError(f"基准几何非法，无法进行敏感性分析：{exc}") from exc

    relative_sensitivity: dict[str, dict[str, float]] = {}
    perturbation_results: dict[str, dict[str, dict[str, float]]] = {}
    for parameter in PARAMETERS:
        minus_input = {
            **baseline_input,
            parameter: base[parameter] * (1.0 - fraction),
        }
        plus_input = {
            **baseline_input,
            parameter: base[parameter] * (1.0 + fraction),
        }
        try:
            minus_result = calculate(minus_input)
            plus_result = calculate(plus_input)
        except GeometryError as exc:
            raise InputError(
                f"参数{parameter}的±{perturbation_percent}%扰动导致非法几何，无法计算中心差分：{exc}"
            ) from exc
        minus_metrics = minus_result["metrics"]
        plus_metrics = plus_result["metrics"]
        relative_sensitivity[parameter] = {
            metric: _relative_effect(
                float(plus_metrics[metric]),
                float(minus_metrics[metric]),
                float(baseline["metrics"][metric]),
                fraction,
            )
            for metric in METRICS
        }
        perturbation_results[parameter] = {
            "minus": {metric: float(minus_metrics[metric]) for metric in METRICS},
            "plus": {metric: float(plus_metrics[metric]) for metric in METRICS},
        }

    dominant_parameters = {
        metric: sorted(
            PARAMETERS,
            key=lambda parameter: abs(relative_sensitivity[parameter][metric]),
            reverse=True,
        )
        for metric in METRICS
    }
    return {
        "ok": True,
        "status": "completed",
        "sensitivity_version": SENSITIVITY_VERSION,
        "section_type": "hollow_rectangular_rounded",
        "perturbation_percent": perturbation_percent,
        "input": {**base, "material_id": material_id, **extra},
        "baseline": baseline["metrics"],
        "relative_sensitivity": relative_sensitivity,
        "dominant_parameters": dominant_parameters,
        "perturbation_results": perturbation_results,
        "limitations": [
            "采用局部中心差分，结果只反映当前基准点附近的相对敏感度",
            "圆角、壁厚和外形变化必须保持在合法几何域内",
        ],
    }


def main() -> int:
    try:
        result = analyze(json.load(sys.stdin))
    except (json.JSONDecodeError, InputError, ValueError) as exc:
        result = {"ok": False, "error_code": "INVALID_INPUT", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive process boundary
        result = {"ok": False, "error_code": "SENSITIVITY_ERROR", "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
