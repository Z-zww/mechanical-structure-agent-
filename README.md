# 机械结构设计智能体

这是团队参加2026年江苏省AI+科学与工程创新实践黑客松的项目工作区。

## 已确定方向

- 组别：本科生组
- 参考方向：工程设计与数字世界，重点为数字孪生与仿真到现实
- 演示对象：悬臂支架
- 运行时底座约束：必须使用AGH作为智能体运行与执行底座
- 运行/演示阶段模型：固定使用赛事指定的 Agnes 模型；不得接入其他大模型
- 调度底座：Agnes Harness（AGH）
- 工程工具：由参赛团队独立开发、测试和注册

赛事官网将这些内容描述为参考方向，而不是独立赛道；报名字段以赛事官方页面和最终规则为准。

## 项目目标

给定载荷、尺寸范围、材料候选和安全约束后，智能体协调确定性工程工具生成并评估结构候选方案，检查边界工况，并输出可审计的工程证据。

其中：

- Agnes模型负责任务理解、任务拆解、工具选择、参数决策、结果校验和失败后重规划；运行链路不接入其他大模型；
- AGH负责智能体运行、工具调度、任务状态和执行记录；
- 团队工具只负责数值计算、确定性仿真和规则校验。

## 当前状态

已完成并测试十个确定性工程工具：

- `tools/cantilever_calculator.py`：单点计算；
- `tools/hollow_cantilever_calculator.py`：实际圆角空心矩形截面单点计算，并对翼缘和腹板进行弹性局部屈曲筛查；
- `tools/hollow_design_search.py`：枚举外宽、外高、壁厚和圆角半径，跳过非法几何并筛选可行空心截面；
- `tools/hollow_design_sensitivity.py`：分析空心截面六个设计参数对静力和局部屈曲指标的相对影响；
- `tools/hollow_manufacturing_tolerance.py`：枚举六类制造/载荷边界，区分非法几何、静力失败和局部屈曲失败；
- `tools/design_search.py`：候选尺寸网格搜索；
- `tools/design_sensitivity.py`：局部敏感度分析；
- `tools/manufacturing_tolerance.py`：载荷、长度、宽度和高度公差边界验证。
- `tools/design_dossier.py`：根据已返回的结构化结果生成确定性 Markdown/HTML 工程报告。
- `tools/fe_beam_cantilever.py`：使用一维 Euler-Bernoulli 梁单元有限元作独立数值复核，不是通用三维 FEA。

材料库已扩展为 S235、S355、304不锈钢、6061-T6铝、7075-T6铝和 Ti-6Al-4V 六种工程参考材料；参数用于可复现计算，不代表真实实验验证。

项目专用`.venv`中已通过88项标准库测试；插件注册、空心演示和故障注入测试合计12项通过。AGH 插件已通过官方包管理事务更新、信任并启用；报告工具在安装包入口通过约190 KB中文嵌套结构化载荷的 HTML 生成回归。当前本机验证不替代其他电脑上的兼容性验收。AGH 插件源码位于同级目录`../agh-src/extensions/mechanical-agent-tools`。

空心截面工具对六种材料均启用基于经典弹性薄板理论的局部屈曲筛查，翼缘和腹板分别计算，材料差异由弹性模量与泊松比体现。该结果是工程筛查，不等同于材料专用规范的完整验算；适用范围和公式见`docs/hollow-section-mechanics-v2.md`。

制造公差工具具备以下防护：零公差边界自动去重；公差下限不得小于0.01mm；长度公差纳入边界组合；严重度计算设置有限值保护。验证失败时返回最差工况、失败约束和可供Agnes重规划的结构化证据。

## 项目目录

- `docs/`：项目说明、假设、接口、验证和演示文档
- `tools/`：确定性工程计算工具和AGH集成代码
- `tests/`：正常、边界、失败注入和端到端测试
- `cases/`：版本化的确定性输入案例
- `evidence/`：脱敏后的AGH执行记录、结果和验证证据

评审要求的可复现执行证据见 `evidence/agh_trace_sanitized.jsonl`，导出方法和脱敏边界见 `docs/可复现与AGH_trace说明.md`。该 trace 来自一次实际 AGH 会话的事件记录，保留工具调用顺序、失败反馈、重规划后的结果和报告生成修正过程，不包含原始会话数据库、个人路径、提示词或密钥。

本地空心演示案例位于`cases/hollow_demo_cases.json`，完整闭环的中文 HTML 演示报告位于`cases/hollow_demo_final.html`；这些文件来自本地确定性工具链，不代表新的 AGH 现场运行证据。

主目录的`report.html`由本地确定性工具重新生成，覆盖初始约束失败、候选搜索、最终复算、敏感性、公差和公开工程参考对照。修改工具或数据后，可在项目根目录运行`python scripts/generate_demo_report.py`复现报告；报告默认只包含计算工具实际返回的限值，不会为缺失约束编造裕度图。AGH 中的`generate_design_dossier`返回 HTML 内容，不负责将内容写入用户磁盘；保存成文件须使用 AGH 提供的附件/导出能力，或将返回内容写入 UTF-8 `.html` 文件。

不要提交API密钥、AGH本地状态、Python虚拟环境、缓存或未经脱敏的个人信息。

发布包不包含项目虚拟环境，但 `agh-plugin/tools/` 会包含运行所需的团队 Python 脚本。目标电脑须安装 AGH 和 Python 3.10 或更新版本；工具只依赖 Python 标准库。插件默认使用可找到的系统 Python；如未加入 `PATH`，仅在启动 AGH 的终端设置解释器路径：

```powershell
$env:PYTHON_EXEC = 'C:\完整路径\到\python.exe'
```

安装插件时应选择解压后发布包内完整的 `agh-plugin/` 文件夹，不能只复制 `index.mjs`。更换电脑后的 AGH 安装、信任、启用和工具调用仍需在目标环境实测，不能仅凭本机测试认定兼容。

## 报告工具的公开参考字段

`generate_design_dossier` 默认返回 Markdown；用户明确要求 HTML 时返回独立 UTF-8 HTML。除计算、搜索、敏感性、公差和重规划结果外，可以传入可选的 `public_reference_result`（或兼容字段 `public_reference_result_json`），其中应包含 `source`、`source_file`、`not_experimental: true`、`cases` 和 `limitations`。该字段只用于“公开工程参考对比”，不会改变任何计算结果，也不得写成真实实验验证。没有该字段时，工具仍按旧接口生成报告。
