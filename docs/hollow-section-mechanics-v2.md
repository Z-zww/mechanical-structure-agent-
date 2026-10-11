# 圆角空心矩形截面力学与局部屈曲筛查 v2

## 1. 适用范围

本模型用于圆角、等壁厚空心矩形悬臂支架的确定性工程筛查。载荷为自由端集中力，弯曲方向与截面外高一致。计算结果用于比赛演示、方案比较和失败后重规划，不等同于有限元分析、实体试验、安全认证或任何一种材料设计规范的完整验算。

## 2. 几何输入与边界

| 参数 | 含义 | 必须满足 |
|---|---|---|
| `outer_width_mm` | 外宽 `B` | `B > 2t` |
| `outer_height_mm` | 外高 `H` | `H > 2t` |
| `wall_thickness_mm` | 等壁厚 `t` | `t > 0` |
| `outer_corner_radius_mm` | 外圆角半径 `r_o` | `t < r_o < min(B,H)/2` |

内宽、内高和内圆角半径为：

```text
B_i = B - 2t
H_i = H - 2t
r_i = r_o - t
```

翼缘与腹板用于局部屈曲筛查的平直段分别为：

```text
c_f = B - 2r_o
c_w = H - 2r_o
```

所有输入必须为有限正数，且两个平直段必须严格为正。

## 3. 圆角截面性质

圆角矩形的面积为：

```text
A_r(B,H,r) = B H - (4-pi) r^2
```

关于水平形心轴的惯性矩通过“外接矩形减四个角部方形与四分之一圆之差”精确计算。空心截面的面积和惯性矩为外轮廓减内轮廓：

```text
A = A_r(B,H,r_o) - A_r(B_i,H_i,r_i)
I_x = I_r(B,H,r_o) - I_r(B_i,H_i,r_i)
W_x = I_x / (H/2)
```

该处理考虑名义圆角几何，但不考虑制造造成的圆角不均匀、壁厚减薄或焊缝几何。

## 4. 静力计算

```text
M = P L
sigma = M / W_x
delta = P L^3 / (3 E I_x)
mass = rho A L
yield_safety_factor = f_y / sigma
```

采用小挠度、线弹性 Euler-Bernoulli 梁假设。

## 5. 弹性局部屈曲筛查

单个平板的经典弹性临界屈曲应力为：

```text
sigma_cr = k_sigma * pi^2 * E / [12(1-nu^2)] * (t/c)^2
```

其中 `c` 为平直板宽，`nu` 为泊松比。筛查分别计算：

| 板件 | 应力分布理想化 | `k_sigma` |
|---|---|---:|
| 受压翼缘平直段 | 均匀受压，内部板件 | 4.0 |
| 腹板平直段 | 纯弯曲线性应力梯度，内部板件 | 23.9 |

两个系数与 EN 1993-1-5 表 4.1 的内部受压板应力分布边界相对应，也可由经典弹性薄板屈曲理论得到。本项目只借用其板件边界与应力分布对应的屈曲系数，不声称对六种材料完成了 Eurocode 材料设计验算。

局部屈曲安全系数定义为：

```text
gamma_flange = sigma_cr,flange / sigma
gamma_web = sigma_cr,web / sigma
gamma_local = min(gamma_flange, gamma_web)
```

默认要求 `gamma_local >= 1.0`。调用方可通过 `min_local_buckling_factor` 提高阈值。翼缘和腹板必须分别计算并返回，不能只检查其中一个。

## 6. 六种材料的统一处理

六种材料均启用同一套弹性板筛查。屈曲系数由板件边界和应力分布决定；材料差异通过各自的弹性模量 `E` 和泊松比 `nu` 进入临界应力。屈服强度继续用于独立的屈服安全系数。

这些材料属性是团队维护的工程参考数据，不代表材料批次证明或真实试验数据。对于最终工程设计，仍需按对应材料、制造方式和应用领域的正式规范复核。

## 7. 判定与状态

| 约束 | 通过条件 |
|---|---|
| 挠度 | `actual <= max_deflection_mm` |
| 质量 | `actual <= max_mass_kg` |
| 屈服安全系数 | `actual >= min_safety_factor` |
| 局部屈曲安全系数 | `actual >= min_local_buckling_factor` |

局部屈曲默认进入结构化约束，但同时返回 `screening_only=true`。任何报告都必须称其为“弹性局部屈曲筛查”，不得表述为“已证明不会屈曲”或“已通过完整规范验算”。

## 8. 未覆盖事项

- 初始几何缺陷和残余应力；
- 圆角与平直板件之间的耦合屈曲；
- 材料塑性、非线性与屈曲后强度；
- 短板效应、局部载荷引起的承压或剪切屈曲；
- 整体弯扭屈曲；
- 疲劳、连接、螺栓和焊缝失效；
- 制造公差下圆角与壁厚的联合波动。

## 9. 依据

- EN 1993-1-5:2006+A2:2019, Eurocode 3: Design of steel structures, Part 1-5: Plated structural elements，内部受压板的板屈曲系数表。该版本信息依据 BSI 公共标准条目核对；正式提交时仍应以团队实际采用的标准文本和赛事要求为准。
- 经典弹性薄板屈曲理论中的长板临界应力方程。

项目当前统一引用版本为 EN 1993-1-5:2006+A2:2019；若团队最终采用其他国家标准转化文本或更新代际版本，提交前必须同步替换版本号和适用范围说明。

## 10. 候选搜索接口

`tools/hollow_design_search.py` 对以下四个候选轴做笛卡尔积枚举：

```text
outer_width_options_mm
outer_height_options_mm
wall_thickness_options_mm
outer_corner_radius_options_mm
```

每个轴最多 100 个去重后的有限正数，组合总数不得超过 1000。非法圆角或内腔几何会被跳过并计入 `invalid_geometry_count`，不会伪装成计算失败；如果所有组合均非法，状态为 `no_valid_geometry`。如果存在有效几何但没有满足约束的方案，状态为 `no_feasible_candidate`。

可行候选排序为：先最小质量，再最小挠度，再最大化较小的屈服/局部屈曲安全裕度。该排序是确定性工具内的公开规则，Agnes 仍负责根据任务目标决定是否接受候选或调整搜索范围。

## 11. 敏感性分析接口

`tools/hollow_design_sensitivity.py` 使用中心差分计算以下参数的局部相对灵敏度：

```text
load_n
length_mm
outer_width_mm
outer_height_mm
wall_thickness_mm
outer_corner_radius_mm
```

输出指标包括最大应力、最大挠度、质量、屈服安全系数和局部屈曲安全系数。默认扰动为 `±5%`，上限为 `20%`。如果任一扰动端点使圆角或壁厚组合进入非法几何域，工具返回输入错误并要求 Agnes 调整扰动幅度或基准方案，不生成不完整敏感度结果。

## 12. 制造公差验证接口

`tools/hollow_manufacturing_tolerance.py` 对以下六个轴枚举边界组合：

```text
载荷
长度
外宽
外高
壁厚
外圆角半径
```

每个轴采用名义值的上下边界，零公差会自动去重。默认最大组合数为 `2^6=64`，工具将几何非法、静力约束失败和局部屈曲约束失败分别记录：

- `invalid_geometry_cases`：外形、内腔或圆角关系非法；
- `failed_constraint_counts`：有效几何上的挠度、质量、屈服安全系数或局部屈曲安全系数失败；
- `worst_case`：有效几何中严重度最高的工况；
- `worst_invalid_geometry_case`：非法几何边界示例。

只有全部角点均为合法几何且满足所有约束时，状态才为 `robust_feasible`；否则为 `robustness_failed`，由 Agnes 根据失败类型重规划。
