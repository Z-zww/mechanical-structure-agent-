"""Deterministic Markdown/HTML engineering design dossier generator."""

from __future__ import annotations

import html
import json
import sys
from typing import Any


DOSSIER_VERSION = "cantilever-design-dossier-v3"
MAX_TEXT_LENGTH = 200_000
DEFAULT_PROJECT_NAME = "悬臂支架确定性工程设计验证"
STANDARD_REFERENCE = (
    "EN 1993-1-5:2006+A2:2019，Eurocode 3: Design of steel structures — "
    "Part 1-5: Plated structural elements"
)
MOJIBAKE_MARKERS = ("�", "锟", "Ã", "Â", "æ", "ç", "è", "å", "�")

# These are deterministic display mappings only.  The raw structured values are
# still accepted and used for validation; mappings keep the human-facing report
# in Chinese without adding another model to the execution chain.
DISPLAY_STATUS = {
    "feasible": "约束满足",
    "constraint_failed": "约束未满足",
    "robust_feasible": "公差工况全部满足",
    "robustness_failed": "公差工况存在失败",
    "no_feasible_candidate": "没有满足约束的候选方案",
    "no_valid_geometry": "没有合法几何候选",
    "generated": "报告已生成",
    "completed": "分析已完成",
    "All constraints passed": "当前已提供约束通过",
}
DISPLAY_MATERIAL = {
    "steel_s235": "S235钢（工程参考参数）",
    "aluminum_6061_t6": "6061-T6铝（工程参考参数）",
    "steel_s355": "S355结构钢（工程参考参数）",
    "stainless_steel_304": "304不锈钢（工程参考参数）",
    "aluminum_7075_t6": "7075-T6铝合金（工程参考参数）",
    "titanium_ti6al4v": "Ti-6Al-4V钛合金（工程参考参数）",
}
DISPLAY_STAGE = {
    "initial_calculation": "初始方案计算",
    "calculation_failed": "初始方案未满足约束",
    "replanned": "Agnes重新规划",
    "candidate_search": "候选方案搜索",
    "final_calculation": "最终方案计算",
    "sensitivity_analysis": "敏感性分析",
    "tolerance_verification": "制造公差验证",
    "dossier_generation": "工程报告生成",
}


class InputError(ValueError):
    """Raised when dossier input is incomplete or malformed."""


def _replace_surrogates(value: str) -> str:
    """Replace lone UTF-16 surrogate code units before crossing a UTF-8 boundary."""
    return "".join("\ufffd" if 0xD800 <= ord(char) <= 0xDFFF else char for char in value)


def _text(payload: dict[str, Any], key: str, *, required: bool = False, default: str = "") -> str:
    value = payload.get(key, default)
    if not isinstance(value, str):
        raise InputError(f"{key}必须是字符串")
    if required and not value.strip():
        raise InputError(f"{key}不能为空")
    if len(value) > MAX_TEXT_LENGTH:
        raise InputError(f"{key}长度超过限制")
    return _replace_surrogates(value)


def _project_name(payload: dict[str, Any]) -> tuple[str, bool]:
    value = _text(payload, "project_name", required=True)
    if any(marker in value for marker in MOJIBAKE_MARKERS):
        return DEFAULT_PROJECT_NAME, True
    return value, False


def _json_value(payload: dict[str, Any], key: str, *, required: bool = False) -> Any:
    raw = _text(payload, key, required=required)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"{key}不是合法JSON: {exc.msg}") from exc
    return value


def _structured_value(
    payload: dict[str, Any],
    structured_key: str,
    legacy_key: str,
    *,
    required: bool = False,
) -> Any:
    """Read a native AGH object/array, with a legacy JSON-string fallback."""
    if structured_key in payload:
        value = payload[structured_key]
        if value is None and required:
            raise InputError(f"{structured_key}不能为空")
        return value
    return _json_value(payload, legacy_key, required=required)


def _structured_object(
    payload: dict[str, Any],
    structured_key: str,
    legacy_key: str,
    *,
    required: bool = False,
) -> dict[str, Any] | None:
    value = _structured_value(payload, structured_key, legacy_key, required=required)
    if value is not None and not isinstance(value, dict):
        raise InputError(f"{structured_key}必须是JSON对象")
    return value


def _json_object(payload: dict[str, Any], key: str, *, required: bool = False) -> dict[str, Any] | None:
    value = _json_value(payload, key, required=required)
    if value is not None and not isinstance(value, dict):
        raise InputError(f"{key}必须编码JSON对象")
    return value


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return _replace_surrogates(f"{value:.6g}")
    if isinstance(value, (dict, list)):
        return _replace_surrogates(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return _replace_surrogates(str(value))


def _display_status(value: Any) -> str:
    text = _fmt(value)
    return DISPLAY_STATUS.get(text, text)


def _display_material(value: Any) -> str:
    text = _fmt(value)
    return DISPLAY_MATERIAL.get(text, text)


def _has_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _localized_task_summary(task_summary: str, calc: dict[str, Any]) -> str:
    """Keep Chinese caller text; otherwise derive a Chinese summary from inputs."""
    if _has_chinese(task_summary):
        return task_summary
    if calc.get("section_type") == "hollow_rectangular":
        return (
            "对实际圆角空心矩形截面悬臂支架进行确定性工程校核，"
            f"材料为{_display_material(_input(calc, 'material_id'))}，"
            f"长度{_input(calc, 'length_mm')} mm、外宽{_input(calc, 'outer_width_mm')} mm、"
            f"外高{_input(calc, 'outer_height_mm')} mm、壁厚{_input(calc, 'wall_thickness_mm')} mm、"
            f"外圆角半径{_input(calc, 'outer_corner_radius_mm')} mm，端部载荷{_input(calc, 'load_n')} N；"
            "报告覆盖应力、挠度、质量、屈服安全系数、局部屈曲筛查和约束判定。"
        )
    return (
        "对矩形实心截面悬臂支架进行确定性工程校核，"
        f"材料为{_display_material(_input(calc, 'material_id'))}，"
        f"长度{_input(calc, 'length_mm')} mm、宽度{_input(calc, 'width_mm')} mm、"
        f"高度{_input(calc, 'height_mm')} mm，端部载荷{_input(calc, 'load_n')} N；"
        "报告覆盖应力、挠度、质量、安全系数和约束判定。"
    )


def _localized_trace(trace: Any) -> Any:
    """Translate known trace labels while preserving all other evidence fields."""
    if isinstance(trace, list):
        return [_localized_trace(item) for item in trace]
    if isinstance(trace, dict):
        return {
            key: (
                DISPLAY_STAGE.get(value, value)
                if key in {"stage", "event", "step"} and isinstance(value, str)
                else _localized_trace(value)
            )
            for key, value in trace.items()
        }
    return trace


def _metric(result: dict[str, Any], key: str) -> str:
    metrics = result.get("metrics")
    if not isinstance(metrics, dict) or key not in metrics:
        raise InputError(f"calculation_result_json缺少指标: {key}")
    return _fmt(metrics[key])


def _input(result: dict[str, Any], key: str) -> str:
    values = result.get("input")
    if not isinstance(values, dict) or key not in values:
        return "未提供"
    return _fmt(values[key])


def _validate_calculation(result: dict[str, Any]) -> None:
    if not isinstance(result.get("status"), str):
        raise InputError("calculation_result_json缺少status")
    for key in ("max_stress_mpa", "max_deflection_mm", "mass_kg", "safety_factor"):
        _metric(result, key)
    if result.get("section_type") == "hollow_rectangular":
        for key in (
            "outer_width_mm",
            "outer_height_mm",
            "wall_thickness_mm",
            "outer_corner_radius_mm",
        ):
            if _input(result, key) == "未提供":
                raise InputError(f"空心计算结果缺少输入字段: {key}")
        for key in (
            "inner_width_mm",
            "inner_height_mm",
            "inner_corner_radius_mm",
            "cross_section_area_mm2",
            "second_moment_mm4",
            "section_modulus_mm3",
        ):
            geometry = result.get("geometry")
            if not isinstance(geometry, dict) or key not in geometry:
                raise InputError(f"空心计算结果缺少几何字段: {key}")
        _metric(result, "local_buckling_factor")
        if not isinstance(result.get("stability_screening"), dict):
            raise InputError("空心计算结果缺少stability_screening")


def _is_hollow(calc: dict[str, Any]) -> bool:
    return calc.get("section_type") == "hollow_rectangular"


def _geometry_rows(calc: dict[str, Any]) -> list[tuple[str, str]]:
    if _is_hollow(calc):
        geometry = calc["geometry"]
        return [
            ("截面类型", "实际圆角空心矩形截面"),
            ("载荷", f"{_input(calc, 'load_n')} N"),
            ("长度", f"{_input(calc, 'length_mm')} mm"),
            ("外宽", f"{_input(calc, 'outer_width_mm')} mm"),
            ("外高", f"{_input(calc, 'outer_height_mm')} mm"),
            ("壁厚", f"{_input(calc, 'wall_thickness_mm')} mm"),
            ("外圆角半径", f"{_input(calc, 'outer_corner_radius_mm')} mm"),
            ("内宽", f"{_fmt(geometry['inner_width_mm'])} mm"),
            ("内高", f"{_fmt(geometry['inner_height_mm'])} mm"),
            ("内圆角半径", f"{_fmt(geometry['inner_corner_radius_mm'])} mm"),
            ("材料", _display_material(_input(calc, "material_id"))),
        ]
    return [
        ("截面类型", "矩形实心截面"),
        ("载荷", f"{_input(calc, 'load_n')} N"),
        ("长度", f"{_input(calc, 'length_mm')} mm"),
        ("宽度", f"{_input(calc, 'width_mm')} mm"),
        ("高度", f"{_input(calc, 'height_mm')} mm"),
        ("材料", _display_material(_input(calc, "material_id"))),
    ]


def _metric_rows(calc: dict[str, Any]) -> list[tuple[str, str]]:
    rows = [
        ("最大应力", f"{_metric(calc, 'max_stress_mpa')} MPa"),
        ("最大挠度", f"{_metric(calc, 'max_deflection_mm')} mm"),
        ("质量", f"{_metric(calc, 'mass_kg')} kg"),
        ("屈服安全系数", _metric(calc, "safety_factor")),
    ]
    if _is_hollow(calc):
        rows.append(("局部屈曲安全系数", _metric(calc, "local_buckling_factor")))
    else:
        rows.insert(3, ("安全系数", rows.pop()[1]))
    return rows


def _stability_summary(calc: dict[str, Any]) -> list[str]:
    if not _is_hollow(calc):
        return []
    screening = calc["stability_screening"]
    flange = screening.get("flange", {})
    web = screening.get("web", {})
    return [
        "## 4. 局部屈曲筛查",
        "",
        f"- 筛查状态：`{_display_status(screening.get('status'))}`",
        f"- 方法版本：`{_fmt(screening.get('method_version', '未提供'))}`",
        f"- 控制板件：`{_fmt(screening.get('governing_component', '未提供'))}`",
        f"- 翼缘屈曲安全系数：`{_fmt(flange.get('buckling_factor', '未提供'))}`，屈曲系数 `k={_fmt(flange.get('buckling_coefficient', '未提供'))}`",
        f"- 腹板屈曲安全系数：`{_fmt(web.get('buckling_factor', '未提供'))}`，屈曲系数 `k={_fmt(web.get('buckling_coefficient', '未提供'))}`",
        "- 说明：该结果是经典弹性薄板局部屈曲工程筛查，不等同于材料专用规范的完整验算。",
        "",
    ]


def _limitations(calc: dict[str, Any]) -> list[str]:
    if _is_hollow(calc):
        return [
            "局部屈曲结果是工程筛查，不代表完整规范验算或真实实验结果。",
            "弹性临界应力若高于材料屈服强度，不得外推为实际允许应力或实际承载能力；屈服安全系数与局部屈曲筛查系数是不同指标。",
            "未覆盖初始缺陷、残余应力、圆角板件耦合、屈曲后强度、整体屈曲、疲劳、连接和焊缝失效。",
        ]
    return ["屈曲、疲劳、连接失效和大变形不在当前矩形实心梁公式范围内。"]


def _public_reference_markdown(reference: dict[str, Any], heading: int) -> list[str]:
    """Render caller-supplied public reference data without treating it as experiment data."""
    source = _fmt(reference.get("source", "未提供"))
    source_file = _fmt(reference.get("source_file", "未提供"))
    cases = reference.get("cases")
    if not isinstance(cases, list):
        cases = []
    lines = [
        f"## {heading}. 公开工程参考对比",
        "",
        f"- 来源：{source}",
        f"- 来源文件：`{source_file}`",
        "- 本节仅表示公开工程参考数据对照，不代表真实实验验证。",
    ]
    if reference.get("not_experimental") is not True:
        lines.append("- 警示：调用方未明确标记 `not_experimental=true`，请在提交前核对证据性质。")
    if cases:
        lines.extend([
            "",
            "| 公开规格 | 面积 (mm²) | 主轴惯性矩 (mm⁴) | 主轴截面模量 (mm³) | 单位质量 (kg/m) | 计算应力 (MPa) | 计算挠度 (mm) | 梁质量 (kg) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for case in cases:
            if not isinstance(case, dict):
                continue
            props = case.get("tabulated_properties") or {}
            response = case.get("derived_response") or {}
            input_data = case.get("input") or {}
            label = case.get("source_record", "未命名规格")
            lines.append(
                "| " + " | ".join([
                    _fmt(label),
                    _fmt(props.get("area_mm2", "未提供")),
                    _fmt(props.get("major_inertia_mm4", "未提供")),
                    _fmt(props.get("major_modulus_mm3", "未提供")),
                    _fmt(props.get("mass_kg_per_m", "未提供")),
                    _fmt(response.get("max_stress_mpa", "未提供")),
                    _fmt(response.get("max_deflection_mm", "未提供")),
                    _fmt(response.get("mass_kg", "未提供")),
                ]) + " |"
            )
            if input_data.get("material_reference"):
                lines.append(f"  - 工况/材料：{_fmt(input_data['material_reference'])}")
    else:
        lines.append("- 对照案例：未提供。")
    limitations = reference.get("limitations")
    if isinstance(limitations, list) and limitations:
        lines.extend(["", "- 来源限制："])
        lines.extend(f"  - {_fmt(item)}" for item in limitations)
    lines.append("")
    return lines


def _public_reference_html(reference: dict[str, Any], heading: int) -> str:
    """Render public reference evidence as escaped standalone HTML."""
    def cell(value: Any) -> str:
        return html.escape(_fmt(value))

    cases = reference.get("cases")
    if not isinstance(cases, list):
        cases = []
    rows = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        props = case.get("tabulated_properties") or {}
        response = case.get("derived_response") or {}
        rows.append("<tr>" + "".join(
            f"<td>{cell(value)}</td>" for value in (
                case.get("source_record", "未命名规格"),
                props.get("area_mm2", "未提供"),
                props.get("major_inertia_mm4", "未提供"),
                props.get("major_modulus_mm3", "未提供"),
                props.get("mass_kg_per_m", "未提供"),
                response.get("max_stress_mpa", "未提供"),
                response.get("max_deflection_mm", "未提供"),
                response.get("mass_kg", "未提供"),
            )
        ) + "</tr>")
    limitations = reference.get("limitations")
    limitation_html = "".join(
        f"<li>{cell(item)}</li>" for item in limitations
    ) if isinstance(limitations, list) else ""
    warning = "" if reference.get("not_experimental") is True else (
        "<li><strong>警示：</strong>调用方未明确标记 not_experimental=true，请在提交前核对证据性质。</li>"
    )
    table = (
        "<table><thead><tr>"
        "<th>公开规格</th><th>面积 (mm²)</th><th>主轴惯性矩 (mm⁴)</th>"
        "<th>主轴截面模量 (mm³)</th><th>单位质量 (kg/m)</th>"
        "<th>计算应力 (MPa)</th><th>计算挠度 (mm)</th><th>梁质量 (kg)</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        if rows else "<p>对照案例：未提供。</p>"
    )
    return f"""
  <h2>{heading}. 公开工程参考对比</h2>
  <p>来源：<code>{cell(reference.get('source', '未提供'))}</code></p>
  <p>来源文件：<code>{cell(reference.get('source_file', '未提供'))}</code></p>
  <p>本节仅表示公开工程参考数据对照，不代表真实实验验证。</p>
  {table}
  <ul>{warning}{limitation_html}</ul>"""


def _markdown(payload: dict[str, Any], results: dict[str, Any]) -> str:
    project_name, project_name_fallback = _project_name(payload)
    task_summary = _text(payload, "task_summary", required=True)
    final_status = _text(payload, "final_status", required=True)
    note = _text(payload, "evidence_note") or "本报告由团队开发的确定性模板生成，数值仅来自工具结构化返回。"
    calc = results["calculation"]
    search = results["search"]
    sensitivity = results["sensitivity"]
    tolerance = results["tolerance"]
    trace = results["trace"]
    public_reference = results["public_reference"]
    failed = calc.get("failed_constraints", [])
    stability_lines = _stability_summary(calc)
    geometry_rows = _geometry_rows(calc)
    metric_rows = _metric_rows(calc)
    tolerance_invalid = tolerance.get("invalid_geometry_cases") if tolerance else None
    public_heading = 9 if public_reference else 0
    data_heading = public_heading + 1 if public_heading else 9
    lines = [
        f"# {project_name}",
        "",
        f"- 报告版本：`{DOSSIER_VERSION}`",
        f"- 最终状态：`{_display_status(final_status)}`",
        "- 状态定义：本报告的组合状态表示最终计算状态为 `feasible` 且制造公差验证状态为 `robust_feasible`。",
        "- 生成方式：团队开发的确定性模板工具",
        "",
        "## 1. 设计任务",
        "",
        _localized_task_summary(task_summary, calc),
        "",
        *( [f"> 说明：输入的项目名称疑似存在编码异常，已使用规范名称“{DEFAULT_PROJECT_NAME}”。"] if project_name_fallback else [] ),
        "",
        "## 2. 最终方案输入",
        "",
        "| 参数 | 值 |",
        "|---|---:|",
        *[f"| {label} | {value} |" for label, value in geometry_rows],
        "",
        "## 3. 计算结果",
        "",
        "| 指标 | 值 |",
        "|---|---:|",
        *[f"| {label} | {value} |" for label, value in metric_rows],
        "",
        *stability_lines,
        "## 5. 约束与公差验证",
        "",
        f"- 计算失败约束：`{_fmt(failed)}`",
        f"- 候选搜索结果：`{_display_status(search.get('status')) if search else '未提供'}`",
        f"- 敏感性分析结果：`{_display_status(sensitivity.get('status')) if sensitivity else '未提供'}`",
        f"- 公差验证结果：`{_display_status(tolerance.get('status')) if tolerance else '未提供'}`",
        f"- 公差工况数：`{_fmt(tolerance.get('cases_evaluated') if tolerance else '未提供')}`",
        f"- 公差通过数：`{_fmt(tolerance.get('passed_cases') if tolerance else '未提供')}`",
        f"- 公差非法几何数：`{_fmt(tolerance_invalid if tolerance_invalid is not None else '未提供')}`",
        "",
        "## 6. 失败与重规划轨迹",
        "",
        _fmt(_localized_trace(trace)) if trace else "未提供重规划轨迹。",
        "",
        "## 7. 证据和限制",
        "",
        note,
        "",
        "- 本报告不代表真实实验或实物测试结果。",
        "- 公开材料参数只能作为工程参考数据。",
        *[f"- {item}" for item in _limitations(calc)],
        "",
        "## 8. 规范依据",
        "",
        f"- {STANDARD_REFERENCE}",
        "- 本项目仅借用内部板件弹性屈曲系数与应力分布边界进行工程筛查，不声称完成 EN 1993-1-5 的完整材料设计验算。",
        "",
        *(_public_reference_markdown(public_reference, public_heading) if public_reference else []),
        f"## {data_heading}. 数据来源字段",
        "",
        "- 计算结果、候选搜索、敏感性分析、公差验证和重规划轨迹由调用方以 JSON 结构传入。",
        "- 工具不调用任何大模型，不根据自然语言自行补全缺失工程数据。",
    ]
    return "\n".join(lines) + "\n"


def _html_report(payload: dict[str, Any], results: dict[str, Any]) -> str:
    """Render a standalone UTF-8 HTML report without a Markdown/GBK ambiguity."""
    raw_project_name, project_name_fallback = _project_name(payload)
    project_name = html.escape(raw_project_name)
    raw_task_summary = _text(payload, "task_summary", required=True)
    final_status = html.escape(_display_status(_text(payload, "final_status", required=True)))
    note = html.escape(
        _text(payload, "evidence_note")
        or "本报告由团队开发的确定性模板生成，数值仅来自工具结构化返回。"
    )
    calc = results["calculation"]
    search = results["search"]
    sensitivity = results["sensitivity"]
    tolerance = results["tolerance"]
    trace = results["trace"]
    public_reference = results["public_reference"]
    failed = calc.get("failed_constraints", [])
    task_summary = html.escape(_localized_task_summary(raw_task_summary, calc))
    geometry_rows = _geometry_rows(calc)
    metric_rows_data = _metric_rows(calc)
    stability = calc.get("stability_screening") if _is_hollow(calc) else None
    tolerance_invalid = tolerance.get("invalid_geometry_cases") if tolerance else None
    public_heading = 9 if public_reference else 0
    data_heading = public_heading + 1 if public_heading else 9

    def cell(value: Any) -> str:
        return html.escape(_fmt(value))

    rows = "".join(
        f"<tr><th>{cell(label)}</th><td>{cell(value)}</td></tr>"
        for label, value in geometry_rows
    )
    metric_rows = "".join(
        f"<tr><th>{label}</th><td>{value}</td></tr>"
        for label, value in ((cell(label), cell(value)) for label, value in metric_rows_data)
    )
    stability_html = ""
    if stability is not None:
        flange = stability.get("flange", {})
        web = stability.get("web", {})
        stability_html = f"""
  <h2>4. 局部屈曲筛查</h2>
  <ul>
    <li>筛查状态：<code>{cell(_display_status(stability.get('status')))}</code></li>
    <li>方法版本：<code>{cell(stability.get('method_version', '未提供'))}</code></li>
    <li>控制板件：<code>{cell(stability.get('governing_component', '未提供'))}</code></li>
    <li>翼缘屈曲安全系数：<code>{cell(flange.get('buckling_factor', '未提供'))}</code>，k={cell(flange.get('buckling_coefficient', '未提供'))}</li>
    <li>腹板屈曲安全系数：<code>{cell(web.get('buckling_factor', '未提供'))}</code>，k={cell(web.get('buckling_coefficient', '未提供'))}</li>
    <li>该结果是弹性局部屈曲工程筛查，不等同于材料专用规范的完整验算。</li>
  </ul>"""
    optional = "".join(
        f"<li>{label}：<code>{cell(value)}</code></li>"
        for label, value in (
            ("计算失败约束", _fmt(failed)),
            ("候选搜索结果", _display_status(search.get("status")) if search else "未提供"),
            ("敏感性分析结果", _display_status(sensitivity.get("status")) if sensitivity else "未提供"),
            ("公差验证结果", _display_status(tolerance.get("status")) if tolerance else "未提供"),
            ("公差工况数", _fmt(tolerance.get("cases_evaluated") if tolerance else "未提供")),
            ("公差通过数", _fmt(tolerance.get("passed_cases") if tolerance else "未提供")),
            ("公差非法几何数", _fmt(tolerance_invalid if tolerance_invalid is not None else "未提供")),
        )
    )
    trace_html = f"<code>{cell(_fmt(_localized_trace(trace)))}</code>" if trace else "<p>未提供重规划轨迹。</p>"
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{project_name}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.6; margin: 2rem auto; max-width: 900px; padding: 0 1rem; color: #1f2937; }}
    h1 {{ border-bottom: 2px solid #2563eb; padding-bottom: .4rem; }}
    table {{ border-collapse: collapse; margin: .75rem 0 1.5rem; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: .5rem .75rem; text-align: left; }}
    th {{ background: #f3f4f6; width: 35%; }}
    code {{ white-space: pre-wrap; word-break: break-word; }}
    .status {{ font-weight: 600; }}
  </style>
</head>
<body>
  <h1>{project_name}</h1>
  <p>报告版本：<code>{DOSSIER_VERSION}</code></p>
  <p>最终状态：<span class="status"><code>{final_status}</code></span></p>
  <p>状态定义：本报告的组合状态表示最终计算状态为 <code>feasible</code> 且制造公差验证状态为 <code>robust_feasible</code>。</p>
  <p>生成方式：团队开发的确定性模板工具</p>
  {f'<p><strong>说明：</strong>输入的项目名称疑似存在编码异常，已使用规范名称“{html.escape(DEFAULT_PROJECT_NAME)}”。</p>' if project_name_fallback else ''}
  <h2>1. 设计任务</h2>
  <p>{task_summary}</p>
  <h2>2. 最终方案输入</h2>
  <table><tbody>{rows}</tbody></table>
  <h2>3. 计算结果</h2>
  <table><tbody>{metric_rows}</tbody></table>
  {stability_html}
  <h2>5. 约束与公差验证</h2>
  <ul>{optional}</ul>
  <h2>6. 失败与重规划轨迹</h2>
  {trace_html}
  <h2>7. 证据和限制</h2>
  <p>{note}</p>
  <ul>
    <li>本报告不代表真实实验或实物测试结果。</li>
    <li>公开材料参数只能作为工程参考数据。</li>
    {''.join(f'<li>{html.escape(item)}</li>' for item in _limitations(calc))}
  </ul>
  <h2>8. 规范依据</h2>
  <ul>
    <li>{html.escape(STANDARD_REFERENCE)}</li>
    <li>本项目仅借用内部板件弹性屈曲系数与应力分布边界进行工程筛查，不声称完成 EN 1993-1-5 的完整材料设计验算。</li>
  </ul>
  {_public_reference_html(public_reference, public_heading) if public_reference else ''}
  <h2>{data_heading}. 数据来源字段</h2>
  <ul>
    <li>计算结果、候选搜索、敏感性分析、公差验证和重规划轨迹由调用方以 JSON 结构传入。</li>
    <li>工具不调用任何大模型，不根据自然语言自行补全缺失工程数据。</li>
  </ul>
</body>
</html>
'''


def generate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InputError("输入必须是JSON对象")
    output_format = _text(payload, "format", default="markdown").lower()
    if output_format not in {"markdown", "html"}:
        raise InputError("format必须是markdown或html")
    calculation = _structured_object(payload, "calculation_result", "calculation_result_json", required=True)
    _validate_calculation(calculation)
    results = {
        "calculation": calculation,
        "search": _structured_object(payload, "search_result", "search_result_json"),
        "sensitivity": _structured_object(payload, "sensitivity_result", "sensitivity_result_json"),
        "tolerance": _structured_object(payload, "tolerance_result", "tolerance_result_json"),
        "trace": _structured_value(payload, "replanning_trace", "replanning_trace_json"),
        "public_reference": _structured_object(
            payload, "public_reference_result", "public_reference_result_json"
        ),
    }
    markdown = _markdown(payload, results)
    content = markdown if output_format == "markdown" else _html_report(payload, results)
    return {
        "ok": True,
        "status": "generated",
        "dossier_version": DOSSIER_VERSION,
        "format": output_format,
        "content": content,
        "sections": [
            "设计任务",
            "最终方案输入",
            "计算结果",
            *( ["局部屈曲筛查"] if _is_hollow(calculation) else [] ),
            "约束与公差验证",
            "失败与重规划轨迹",
            "证据和限制",
            "规范依据",
            *( ["公开工程参考对比"] if results["public_reference"] is not None else [] ),
            "数据来源字段",
        ],
        "source_checks": {
            "calculation_result": True,
            "search_result": results["search"] is not None,
            "sensitivity_result": results["sensitivity"] is not None,
            "tolerance_result": results["tolerance"] is not None,
            "replanning_trace": results["trace"] is not None,
            "public_reference_result": results["public_reference"] is not None,
        },
    }


def main() -> int:
    # The AGH Node boundary consumes UTF-8 JSON bytes even on Windows locales using GBK.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    except (AttributeError, TypeError):
        pass
    try:
        result = generate(json.load(sys.stdin))
    except (json.JSONDecodeError, InputError, ValueError) as exc:
        result = {"ok": False, "error_code": "INVALID_INPUT", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive process boundary
        result = {"ok": False, "error_code": "DOSSIER_ERROR", "message": str(exc)}
    # ASCII JSON escapes keep lone surrogates and non-ASCII report text safe on every host locale.
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
