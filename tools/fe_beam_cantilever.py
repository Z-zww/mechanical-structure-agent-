#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Euler-Bernoulli beam finite element reviewer for cantilever beams.

定位
----
对单点计算 / 搜索工具冻结后的设计方案，做一次独立的梁单元（FEA）数值复核，
并与解析解逐项对照，输出可审计的误差与网格一致性证据。

- 仅依赖 Python 标准库；确定性、可复现；纯数值求解，100% 幂等。
- 属于一维梁单元数值复核，不是三维通用 FEA 软件，也不是物理实验。

输入（stdin，单个 JSON 对象）
----------------------------
必填：load_n、length_mm、youngs_modulus_gpa；
截面二选一（oneOf）：
  (a) 实心矩形：width_mm + height_mm
  (b) 显式截面属性：inertia_mm4 + neutral_axis_mm（空心截面由上游算出 I、中性轴后透传）
可选：n_elements(1..100，默认20)、yield_strength_mpa、max_deflection_mm、min_safety_factor。

约束判定约定
------------
- 提供 max_deflection_mm 时校核自由端挠度；
- 提供 yield_strength_mpa 时校核安全系数；若未提供 min_safety_factor，
  则默认限值为 1.0（即至少不允许进入屈服）。

错误码
------
- INVALID_INPUT：必填缺失、截面二选一冲突/缺失、非正数或类型错误（含布尔、NaN、Inf）；
- SINGULAR_MATRIX：刚度矩阵奇异或病态、主元过小；
- CALCULATION_ERROR：内部出现非有限数值等其它错误。
"""
from __future__ import annotations

import json
import math
import sys
from typing import Any

FORMULA_VERSION = "cantilever-euler-bernoulli-beam-elements-end-load-v2"


class InputError(ValueError):
    """Raised when structured input is invalid or boundary conditions fail."""


class SolverError(RuntimeError):
    """Raised when stiffness matrix is singular or ill-conditioned."""


def _positive_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{key}必须是有限正数")
    val_float = float(value)
    if not math.isfinite(val_float) or val_float <= 0:
        raise InputError(f"{key}必须是有限正数")
    return val_float


def solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(vector)
    a = [row[:] for row in matrix]
    b = vector[:]
    for col in range(n):
        pivot = col
        best = abs(a[col][col])
        for r in range(col + 1, n):
            if abs(a[r][col]) > best:
                best = abs(a[r][col])
                pivot = r
        if best < 1e-15:
            raise SolverError("刚度矩阵奇异或病态，无法完成高斯消元求解")
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
            b[col], b[pivot] = b[pivot], b[col]
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            if factor != 0.0:
                for c in range(col, n):
                    a[r][c] -= factor * a[col][c]
                b[r] -= factor * b[col]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        remainder = b[i]
        for j in range(i + 1, n):
            remainder -= a[i][j] * x[j]
        x[i] = remainder / a[i][i]
    return x


def element_stiffness(e_modulus: float, inertia: float, length: float) -> list[list[float]]:
    """Euler-Bernoulli 4x4 beam element stiffness matrix."""
    k = e_modulus * inertia / (length ** 3)
    l = length
    return [
        [12.0 * k, 6.0 * l * k, -12.0 * k, 6.0 * l * k],
        [6.0 * l * k, 4.0 * l * l * k, -6.0 * l * k, 2.0 * l * l * k],
        [-12.0 * k, -6.0 * l * k, 12.0 * k, -6.0 * l * k],
        [6.0 * l * k, 2.0 * l * l * k, -6.0 * l * k, 4.0 * l * l * k],
    ]


def resolve_section(data: dict[str, Any]) -> tuple[float | None, float, float]:
    """Parse section properties: returns (area_mm2, inertia_mm4, neutral_axis_mm)."""
    has_inertia = "inertia_mm4" in data
    has_dim = "width_mm" in data or "height_mm" in data
    if has_inertia and has_dim:
        raise InputError("截面参数冲突：不能同时提供 (width_mm, height_mm) 和 inertia_mm4")
    if has_inertia:
        inertia = _positive_number(data, "inertia_mm4")
        neutral = _positive_number(data, "neutral_axis_mm")
        # area_mm2 为可选的直接调用/测试入口；对外 schema 未暴露该字段。
        area = _positive_number(data, "area_mm2") if "area_mm2" in data else None
        return area, inertia, neutral
    if "width_mm" in data and "height_mm" in data:
        width = _positive_number(data, "width_mm")
        height = _positive_number(data, "height_mm")
        area = width * height
        inertia = width * (height ** 3) / 12.0
        neutral = height / 2.0
        return area, inertia, neutral
    raise InputError("必须提供实心截面尺寸 (width_mm, height_mm) 或显式截面属性 (inertia_mm4, neutral_axis_mm)")


def run_fea(load: float, length: float, e_modulus: float, inertia: float, n_elements: int) -> dict[str, Any]:
    if n_elements < 1 or n_elements > 100:
        raise InputError("n_elements 必须在 1 到 100 之间")
    element_length = length / n_elements
    ndof = 2 * (n_elements + 1)
    k_global = [[0.0 for _ in range(ndof)] for _ in range(ndof)]
    k_el = element_stiffness(e_modulus, inertia, element_length)
    for e in range(n_elements):
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        for i in range(4):
            for j in range(4):
                k_global[dofs[i]][dofs[j]] += k_el[i][j]
    # Boundary conditions: Node 0 clamped (w0=0, theta0=0)
    free = list(range(2, ndof))
    k_reduced = [[k_global[i][j] for j in free] for i in free]
    # Load vector: Tip load at Node n, w-direction (downward positive)
    f_reduced = [0.0] * len(free)
    tip_w_dof = 2 * n_elements
    f_reduced[free.index(tip_w_dof)] = load
    u_reduced = solve_linear_system(k_reduced, f_reduced)
    u = [0.0] * ndof
    for idx, dof in enumerate(free):
        u[dof] = u_reduced[idx]
    node_deflections = [u[2 * i] for i in range(n_elements + 1)]
    node_rotations = [u[2 * i + 1] for i in range(n_elements + 1)]
    # Element internal forces recovery
    element_end_moments = []
    for e in range(n_elements):
        d = [u[2 * e], u[2 * e + 1], u[2 * e + 2], u[2 * e + 3]]
        forces = [sum(k_el[i][j] * d[j] for j in range(4)) for i in range(4)]
        element_end_moments.append([forces[1], forces[3]])
    tip_deflection = node_deflections[-1]
    fixed_end_moment = abs(element_end_moments[0][0])
    return {
        "n_elements": n_elements,
        "tip_deflection_mm": tip_deflection,
        "fixed_end_moment_nmm": fixed_end_moment,
        "node_deflections_mm": node_deflections,
        "node_rotations_rad": node_rotations,
        "element_end_moments_nmm": element_end_moments,
    }


def analytical_solution(load: float, length: float, e_modulus: float, inertia: float, neutral: float) -> dict[str, float]:
    moment = load * length
    stress = moment * neutral / inertia
    deflection = load * (length ** 3) / (3.0 * e_modulus * inertia)
    return {
        "fixed_end_moment_nmm": moment,
        "fixed_end_stress_mpa": stress,
        "tip_deflection_mm": deflection,
    }


def relative_error(approx: float, exact: float) -> float | None:
    if exact == 0.0:
        return 0.0 if approx == 0.0 else None
    return abs(approx - exact) / abs(exact)


def _element_count(payload: dict[str, Any]) -> int:
    n_elem_val = payload.get("n_elements", 20)
    if isinstance(n_elem_val, bool) or not isinstance(n_elem_val, int) or n_elem_val < 1:
        raise InputError("n_elements必须是大于等于1的正整数")
    return int(n_elem_val)


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")
    load = _positive_number(payload, "load_n")
    length = _positive_number(payload, "length_mm")
    e_gpa = _positive_number(payload, "youngs_modulus_gpa")
    e_modulus = e_gpa * 1000.0  # GPa -> MPa (N/mm^2)
    area, inertia, neutral = resolve_section(payload)
    n_elements = _element_count(payload)

    fea = run_fea(load, length, e_modulus, inertia, n_elements)
    ana = analytical_solution(load, length, e_modulus, inertia, neutral)
    fea_stress = fea["fixed_end_moment_nmm"] * neutral / inertia

    comparison = {
        "tip_deflection_mm": {
            "fea": fea["tip_deflection_mm"],
            "analytical": ana["tip_deflection_mm"],
            "relative_error": relative_error(fea["tip_deflection_mm"], ana["tip_deflection_mm"]),
        },
        "fixed_end_moment_nmm": {
            "fea": fea["fixed_end_moment_nmm"],
            "analytical": ana["fixed_end_moment_nmm"],
            "relative_error": relative_error(fea["fixed_end_moment_nmm"], ana["fixed_end_moment_nmm"]),
        },
        "fixed_end_stress_mpa": {
            "fea": fea_stress,
            "analytical": ana["fixed_end_stress_mpa"],
            "relative_error": relative_error(fea_stress, ana["fixed_end_stress_mpa"]),
        },
    }

    # Mesh consistency verification (beam elements are exact for this load case).
    mesh_consistency = []
    for n in (1, 2, 5, 20):
        r = run_fea(load, length, e_modulus, inertia, n)
        mesh_consistency.append({
            "n_elements": n,
            "tip_deflection_mm": r["tip_deflection_mm"],
            "fixed_end_moment_nmm": r["fixed_end_moment_nmm"],
        })

    # Constraints verification
    constraints: dict[str, dict[str, Any]] = {}
    if "max_deflection_mm" in payload:
        limit = _positive_number(payload, "max_deflection_mm")
        constraints["deflection"] = {
            "actual": fea["tip_deflection_mm"],
            "limit": limit,
            "passed": fea["tip_deflection_mm"] <= limit,
        }
    if "yield_strength_mpa" in payload:
        yield_strength = _positive_number(payload, "yield_strength_mpa")
        safety_factor = yield_strength / fea_stress
        sf_limit = _positive_number(payload, "min_safety_factor") if "min_safety_factor" in payload else 1.0
        constraints["safety_factor"] = {
            "actual": safety_factor,
            "limit": sf_limit,
            "passed": safety_factor >= sf_limit,
        }

    failed_constraints = [name for name, c in constraints.items() if not c["passed"]]
    return {
        "ok": True,
        "status": "feasible" if not failed_constraints else "constraint_failed",
        "validation_type": "beam_element_fea_review",
        "formula_version": FORMULA_VERSION,
        "not_experimental": True,
        "input": {
            "load_n": load,
            "length_mm": length,
            "youngs_modulus_gpa": e_gpa,
            "inertia_mm4": inertia,
            "neutral_axis_mm": neutral,
            "area_mm2": area,
            "n_elements": n_elements,
        },
        "fea_result": {
            "tip_deflection_mm": fea["tip_deflection_mm"],
            "fixed_end_moment_nmm": fea["fixed_end_moment_nmm"],
            "fixed_end_stress_mpa": fea_stress,
            "node_deflections_mm": fea["node_deflections_mm"],
        },
        "analytical_result": ana,
        "comparison": comparison,
        "mesh_consistency": mesh_consistency,
        "constraints": constraints,
        "failed_constraints": failed_constraints,
        "limitations": [
            "采用 Euler-Bernoulli 梁单元、线弹性、小挠度假设，仅适用于端部集中载荷工况",
            "本工具属于一维梁单元离散数值复核，不等同于三维连续体通用 FEA 仿真，亦不代表物理实物试验",
            "未计入剪切变形 (Timoshenko 效应)、几何非线性、局部屈曲与接头焊缝失效",
        ],
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = calculate(payload)
    except (json.JSONDecodeError, InputError) as exc:
        result = {"ok": False, "error_code": "INVALID_INPUT", "message": str(exc)}
    except SolverError as exc:
        result = {"ok": False, "error_code": "SINGULAR_MATRIX", "message": str(exc)}
    except Exception as exc:
        result = {"ok": False, "error_code": "CALCULATION_ERROR", "message": str(exc)}
    # ASCII-escaped JSON is immune to Windows console code-page corruption when AGH reads stdout.
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
