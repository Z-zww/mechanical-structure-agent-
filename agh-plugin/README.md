# AGH机械结构设计工具插件

这是本科生组项目的 AGH 后端插件，许可证为 MIT。插件只注册团队自行开发的确定性工程工具，不接入任何第三方大模型；Agnes 负责任务理解、规划、工具选择和结果校验，AGH 负责调度。

## 已注册工具

- `calculate_cantilever`：计算矩形截面悬臂支架的应力、挠度、质量和安全系数。
- `calculate_hollow_cantilever`：计算实际圆角空心矩形截面的力学指标，并分别筛查翼缘与腹板的弹性局部屈曲风险。
- `search_hollow_design_candidates`：对外宽、外高、壁厚和外圆角半径进行确定性四维网格搜索，记录非法几何并筛选满足静力和稳定性约束的候选。
- `analyze_hollow_design_sensitivity`：使用中心差分分析六个空心截面设计参数对静力和局部屈曲指标的影响；扰动跨出合法几何域时返回结构化输入错误。
- `verify_hollow_manufacturing_tolerance`：枚举长度、外宽、外高、壁厚、圆角和载荷六类边界，区分非法几何与力学/稳定性约束失败。
- `search_design_candidates`：遍历尺寸候选并按质量、挠度排序。
- `analyze_design_sensitivity`：使用中心差分分析载荷、长度、宽度和高度的影响。
- `verify_manufacturing_tolerance`：枚举载荷、长度、宽度和高度公差边界，输出最不利工况及失败约束。
- `generate_design_dossier`：将已返回的实心或圆角空心结构化计算、搜索、敏感性、公差、重规划和可选公开参考结果整理为工程报告内容。用户指定 HTML 时输出 HTML；未指定格式时默认输出 Markdown。工具默认只返回内容，不写入文件。公开参考结果必须标记 `not_experimental: true`，并且只用于工程参考对比。

报告工具的数据字段优先使用原生结构化值：`calculation_result`、`search_result`、`sensitivity_result`、`tolerance_result` 和数组 `replanning_trace`。`calculation_result` 与兼容字段 `calculation_result_json` 二选一即可；两端契约已统一。报告根输入允许 Agnes 附带 `success`、`elapsed_ms` 等非工程元数据，这些字段不会参与计算。旧会话也可以继续使用带 `_json` 后缀的字符串字段，工具会兼容解析；不要把长工具结果手工拼接成字符串，以免在 AGH 调用边界发生转义或截断。中文报告中的 `task_summary`、`evidence_note` 以及重规划轨迹自然语言应使用中文；工具名、字段名和状态码可以保留原样。模板不自动翻译调用方文本。

## 材料库

当前确定性材料库包括：S235钢、6061-T6铝合金、S355结构钢、304不锈钢、7075-T6铝合金和 Ti-6Al-4V钛合金。参数均为工程参考数据，仅用于可复现计算，不代表真实实验验证。材料选择由 Agnes 根据任务规划后传入 `material_id`，工具不会自行猜测材料。

空心截面稳定性筛查对六种材料均启用，使用材料各自的弹性模量和泊松比。它属于经典弹性薄板局部屈曲筛查，不是有限元结果，也不代表任何材料规范的完整设计验算。

## 运行方式

发布包中的 `agh-plugin/tools/` 已包含插件运行所需的团队计算脚本。插件从自身目录定位这些脚本，不依赖开发机的固定盘符、项目目录名或当前工作目录。完整源码包中的插件也可使用同级项目 `tools/` 目录。

运行环境要求：安装 AGH 和 Python 3.10 或更新版本；本项目工具仅使用 Python 标准库，无需额外 `pip install` 依赖。插件默认先查找项目专用虚拟环境，再使用系统 `python.exe`（Windows）或 `python`（Linux/macOS）。如果 Python 不在 `PATH`，请在启动 AGH 的同一个终端中设置：

```powershell
$env:PYTHON_EXEC = 'C:\\完整路径\\到\\python.exe'
```

Windows 可先用 `py -3 --version` 确认 Python。非 Windows 系统请将变量值设为可执行的 Python 路径。目标电脑需单独安装兼容版本的 AGH 和 Python；本项目不打包这些第三方运行时。

若 AGH 插件安装方式引用本地文件，请将发布包内完整的 `agh-plugin/` 文件夹作为插件源安装，并完成 AGH 的信任和启用步骤。若使用压缩包，请先解压；不要只复制 `index.mjs`，因为 `tools/` 子目录是插件运行必需文件。

插件默认将单次 Python 工具执行限制为 10 秒。测试或受控演示环境可通过 `PYTHON_TOOL_TIMEOUT_MS` 覆盖，例如：

```powershell
$env:PYTHON_TOOL_TIMEOUT_MS = '10000'
```

发布 ZIP 不包含 `.venv`、AGH 本地数据、API 密钥或第三方原始资料。跨电脑运行仍需在目标设备实际完成安装、信任、启用和工具调用；自动化测试不能代替目标设备上的 AGH 兼容性验收。不要把个人解释器路径或 API key 写入插件文件。

## 安全与许可

- 插件元数据声明 `MIT` 许可证。
- 工具标记为只读、非破坏、可并发安全、可重放。
- Python 子进程默认设置 10 秒超时，并将启动失败、执行失败、超时、空输出和无效 JSON 分别转换为结构化错误。
- 插件监听 stdin 管道错误，避免 Python 进程提前退出时产生未捕获的管道异常。
- 不在插件中保存 API 密钥，不修改用户全局 Python 环境。
- 报告工具只接收结构化 JSON，不调用大模型，不自行补全缺失工程数据；默认只返回报告文本，不直接写入文件。

## 测试

在项目根目录执行：

```powershell
& .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
node --test agh-plugin/test-registration.mjs
node --test agh-plugin/test-hollow-demo.mjs
node --test agh-plugin/test-failure-injection.mjs
```

第一条命令验证确定性工程计算和报告生成；第二条命令验证 10 个工具是否唯一注册、路径是否可定位，以及每个工具能否完成一次合法调用；第三条命令通过插件封装验证空心方案通过、约束失败、非法几何和六种材料稳定性筛查；最后一条命令验证脚本缺失、解释器缺失、空输出、非法 JSON 和超时等插件故障场景。当前基线为 Python `88/88`，插件注册、空心演示、故障注入分别为 `1/1`、`4/4`、`7/7`。插件注册测试还会验证长中文结构化载荷、报告附加元数据、输入契约兼容和 HTML 输出。

可复现实例输入和本地结果分别保存在 `cases/hollow_demo_cases.json` 与 `cases/hollow_demo_results.json`。结果文件采用标准 JSON Unicode 转义，避免不同 Windows 终端代码页影响中文诊断信息。
