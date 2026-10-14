# 可复现材料与 AGH trace

## 提交材料对应关系

评审要求的“说明文档或 README”对应项目根目录 [`README.md`](../README.md)。本文件补充说明如何复现确定性计算、如何理解 AGH 执行记录，以及哪些本地数据没有进入提交包。

“可复现部分”包括：

- `tools/`：确定性 Python 工具源码；
- `agh-plugin/`：AGH 插件注册、Schema 和插件内置工具；
- `tests/`：单元、边界、失败注入和插件一致性测试；
- `cases/`：版本化输入、结果和 HTML 报告；
- `validation/`：脱敏后的公开工程参考数据和对照结果；
- `evidence/agh_trace_sanitized.jsonl`：由 AGH 本地事件记录导出的脱敏 trace。

## 复现步骤

在 Python 3.10 或更新版本中，从项目根目录执行：

```powershell
python -m unittest discover -s tests -v
python scripts/generate_demo_report.py
```

插件测试需要 AGH 提供的 Node.js 运行环境，并在 AGH 中完成插件导入、信任和启用：

```powershell
node agh-plugin/test-registration.mjs
node agh-plugin/test-hollow-demo.mjs
node agh-plugin/test-failure-injection.mjs
```

工具只依赖 Python 标准库；目标机器需要自行安装 AGH 和 Python 3.10+。发布包不包含 AGH 运行时、用户会话数据库或 Python 虚拟环境。

## trace 的含义

`evidence/agh_trace_sanitized.jsonl` 来源于一次实际 AGH 会话的事件记录。它保留工具调用顺序、序号、时间、工具名和结构化结果摘要，展示了以下闭环：

1. 初始圆角空心截面方案返回 `constraint_failed`；
2. Agnes 根据失败约束调用空心设计搜索，得到 `feasible` 候选；
3. 对候选方案并行执行最终计算、敏感性分析和制造公差验证；
4. 调用 `fe_beam_cantilever` 完成一维梁单元复核；
5. 报告工具首次收到不符合 Schema 的参数时返回 `TOOL_ARGS_INVALID`；
6. 经过工具 Schema 识别和参数修正后，报告生成成功。

trace 特意不包含原始提示词、模型完整输出、个人路径、会话 ID、密钥和大段工程载荷。评审可结合 `cases/` 中的输入与结果复现数值，结合 trace 检查 AGH 的编排和失败恢复过程。

## 重新导出 trace

不要把 AGH 的整个本地目录复制到仓库。若需要从另一条 AGH 会话生成同类证据，在项目根目录运行：

```powershell
python scripts/export_agh_trace.py `
  --database "<AGH数据目录>\sessions.db" `
  --session "<待导出的会话键>" `
  --output evidence/agh_trace_sanitized.jsonl
```

导出脚本只写入脱敏摘要。导出前应确认会话不含个人隐私、API 密钥或未授权的第三方资料；原始 `sessions.db`、AGH profile、audit 日志和缓存不属于提交材料。

## 工程与证据边界

- trace 证明的是 AGH 调度、工具调用和结构化结果传递，不等同于真实实验或实体测试；
- 公开型材数据只作为工程参考对照；
- `fe_beam_cantilever` 是一维 Euler-Bernoulli 梁单元复核，不是通用三维有限元分析；
- 局部屈曲结果属于工程筛查，不宣称完成完整规范验算；
- 最终提交前仍需人工核对赛事规则、规范版本正式名称和现场 AGH 运行截图。
