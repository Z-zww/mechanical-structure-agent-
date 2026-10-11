"""Deterministic local sensitivity analysis for the cantilever model."""

from __future__ import annotations

import json
import math
import sys
from typing import Any

try:
    from tools.cantilever_calculator import InputError, calculate
except ModuleNotFoundError:  # Direct execution by the AGH Python subprocess.
    from cantilever_calculator import InputError, calculate


METRICS = ("max_stress_mpa", "max_deflection_mm", "mass_kg", "safety_factor")
PARAMETERS = ("load_n", "length_mm", "width_mm", "height_mm")


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name}必须是有限正数")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{name}必须是有限正数")
    return value


def _relative_effect(plus: float, minus: float, baseline: float, fraction: float) -> float:
    if baseline == 0:
        raise InputError("基准指标不能为零")
    return ((plus - minus) / baseline) / (2.0 * fraction)


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """Return central-difference elasticities for the deterministic model."""
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")
    base = {
        key: _positive_number(payload.get(key), key)
        for key in ("load_n", "length_mm", "width_mm", "height_mm")
    }
    material_id = payload.get("material_id")
    if not isinstance(material_id, str):
        raise InputError("material_id必须是字符串")
    perturbation_percent = _positive_number(payload.get("perturbation_percent", 5), "perturbation_percent")
    if perturbation_percent > 20:
        raise InputError("perturbation_percent不能超过20")
    fraction = perturbation_percent / 100.0
    baseline = calculate({**base, "material_id": material_id})

    relative_sensitivity: dict[str, dict[str, float]] = {}
    perturbation_results: dict[str, dict[str, dict[str, float]]] = {}
    for parameter in PARAMETERS:
        minus_input = {**base, "material_id": material_id, parameter: base[parameter] * (1 - fraction)}
        plus_input = {**base, "material_id": material_id, parameter: base[parameter] * (1 + fraction)}
        minus_result = calculate(minus_input)
        plus_result = calculate(plus_input)
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
        "sensitivity_version": "cantilever-local-sensitivity-v1",
        "perturbation_percent": perturbation_percent,
        "input": {**base, "material_id": material_id},
        "baseline": baseline["metrics"],
        "relative_sensitivity": relative_sensitivity,
        "dominant_parameters": dominant_parameters,
        "perturbation_results": perturbation_results,
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
