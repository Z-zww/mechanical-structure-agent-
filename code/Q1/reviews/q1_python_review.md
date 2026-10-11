# Q1 Python 代码审查

> **状态**：通过但有适用范围警告  
> **审查器**：python-code-reviewer  
> **日期**：2026-10-10  
> **审查脚本**：`tools/hollow_cantilever_calculator.py`、`tools/cantilever_calculator.py`、`agh-plugin/index.mjs`、`tests/test_hollow_cantilever_calculator.py`

## 明确通过项

1. `tools/hollow_cantilever_calculator.py:49` 使用圆角矩形复合截面公式计算面积和水平形心轴惯性矩，空心截面按外轮廓减内轮廓处理，而非继续使用尖角矩形近似。
2. `tools/hollow_cantilever_calculator.py:99` 至 `tools/hollow_cantilever_calculator.py:115` 明确校验内腔正尺寸、外圆角大于壁厚、外圆角小于半个最小外尺寸以及圆角间平直段为正。
3. `tools/hollow_cantilever_calculator.py:136` 至 `tools/hollow_cantilever_calculator.py:152` 分别计算翼缘和腹板的弹性临界屈曲应力，并由两者中较小的屈曲安全系数控制，未重复候选代码只检查翼缘的错误。
4. `tools/hollow_cantilever_calculator.py:188` 至 `tools/hollow_cantilever_calculator.py:197` 的局部屈曲约束方向为 `actual >= limit`，符合“屈曲安全系数不得低于要求值”的物理含义。
5. `tools/cantilever_calculator.py:18` 至 `tools/cantilever_calculator.py:53` 为六种材料提供有限正值的弹性模量、屈服强度、密度和泊松比；测试 `tests/test_hollow_cantilever_calculator.py:121` 验证六种材料均可执行稳定性筛查。
6. `tests/test_hollow_cantilever_calculator.py:87` 构造了翼缘通过而腹板失败的故障注入用例，能够防止腹板漏判回归；`tests/test_hollow_cantilever_calculator.py:103` 验证翼缘也可成为控制板件。
7. `tests/test_hollow_cantilever_calculator.py:62` 验证圆角等于壁厚、达到或超过半个最小外尺寸时被拒绝；其余测试覆盖零值、负值、布尔值、NaN、无穷大和未知材料。
8. `agh-plugin/index.mjs:33` 至 `agh-plugin/index.mjs:49` 的 AGH schema 与 Python 必填字段一致，包含外圆角半径和可选局部屈曲安全系数。
9. 执行项目虚拟环境中的 `python -B -m unittest discover -s tests -v`，65 项测试全部通过；插件注册、空心演示和故障注入测试分别为 1、4、7 项且全部通过；`node --check agh-plugin/index.mjs` 通过。

## 失败项与修复项

| 序号 | 位置 | 问题 | 处理 | 状态 |
|---|---|---|---|---|
| 1 | 用户提供的候选 v2 代码 | 计算腹板宽厚比但只判定翼缘 | 改为翼缘和腹板分别计算临界应力与安全系数 | 已修复 |
| 2 | 用户提供的候选 v2 代码 | `1.28*sqrt(E/fy)` 缺少边界条件与普适性说明 | 改为经典弹性板屈曲方程，并显式返回 `k_sigma`、应力分布和依据 | 已修复 |
| 3 | 原空心截面 v1 | 使用尖角矩形截面性质 | 改为外、内圆角矩形复合截面 | 已修复 |
| 4 | 共享材料库 | 缺少泊松比 | 为六种工程参考材料增加泊松比 | 已修复 |
| 5 | 首轮腹板失败测试 | 10 kN 下腹板屈曲安全系数仍为 2.99，测试预期与物理结果不符 | 将故障注入载荷改为确实能触发腹板失效的 40 kN | 已修复 |

## 约束方向复核

| 位置 | 方向 | 左侧 | 右侧 | 物理含义 |
|---|---|---|---|---|
| `tools/hollow_cantilever_calculator.py:172` | `<=` | 实际挠度 | 最大允许挠度 | 挠度上限 |
| `tools/hollow_cantilever_calculator.py:179` | `>=` | 屈服安全系数 | 最小安全系数 | 强度安全下限 |
| `tools/hollow_cantilever_calculator.py:186` | `<=` | 实际质量 | 最大允许质量 | 质量上限 |
| `tools/hollow_cantilever_calculator.py:196` | `>=` | 局部屈曲安全系数 | 最小局部屈曲安全系数 | 稳定性筛查下限 |

## 剩余风险

- 该模型是长板、理想弹性、简支纵边假设下的局部屈曲筛查，不是六种材料各自设计规范的完整验算。
- 当前未考虑初始缺陷、残余应力、圆角板件耦合、短板效应、屈曲后强度和制造导致的角部增厚或减薄。
- `k_sigma=4.0` 和 `23.9` 对应内部板件的均匀受压与纯弯曲应力梯度理想化；载荷形式改变时必须重新确定应力分布和屈曲系数。
- 本轮代码尚未在 AGH 后台重新同步，不能声称空心截面 v2 已完成 AGH 现场调用。

## 运行方式

```powershell
python -m unittest discover -s tests -v
node --test agh-plugin/test-failure-injection.mjs
node --check agh-plugin/index.mjs
```

工具从标准输入读取 JSON，并向标准输出返回 ASCII 转义的结构化 JSON。

## 预期输出

- 单点计算返回 `formula_version=cantilever-rounded-hollow-rectangular-end-load-v2`。
- 返回圆角截面面积、惯性矩、截面模量、静力指标和材料信息。
- `stability_screening` 分别包含翼缘、腹板及控制板件。
- 非法圆角或内腔返回 `INVALID_GEOMETRY`。
- 静力或局部屈曲约束失败返回 `constraint_failed` 及明确的 `failed_constraints`。

## 建议下一步

在保持当前单点工具接口不变的前提下，开发空心截面候选搜索工具，并将外宽、外高、壁厚和圆角半径作为明确候选变量。随后扩展空心截面公差验证，不应直接复用只支持实心宽高参数的旧工具。
