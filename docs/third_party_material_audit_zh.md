# 第三方资料上传审计

审计目的：在公开上传到 GitHub 前，区分团队自有成果、公开事实数据和第三方原始资料，避免把受版权或许可限制的原始文件直接发布。

## 审计结论

结论：允许上传团队代码、测试、中文文档、确定性工具生成的报告、脱敏后的运行截图和公开数据的派生对照结果；不上传第三方原始网页和 PDF。

## 明确排除

以下文件保留在本地，不进入 Git 提交：

| 路径 | 判定 | 原因 |
|---|---|---|
| `validation/sources/steel_for_life_hfrhs_page_2026-10-11.html` | 排除 | Steel for Life / SCI 页面原始存档，含第三方页面内容和标识 |
| `validation/sources/steel_for_life_hfrhs_table_2026-10-11.html` | 排除 | SCI 表格原始网页，页面标注版权和 “All rights reserved” |
| `validation/sources/alpine_pipe_bs_en_10210_rhs_2026-10-11.pdf` | 排除 | 制造商公开 PDF 原件，许可范围未确认 |
| `cases/generated_dossier.html` | 排除 | 旧版示例文件，避免与 v3 报告混淆 |
| `cases/generated_dossier.md` | 排除 | 旧版示例文件，避免与 v3 报告混淆 |
| `cases/generated_dossier_html_fixed.json` | 排除 | 旧版 v1 工具输出，避免版本混淆 |

这些文件的来源网址、访问日期、SHA-256 和使用边界保留在 `validation/source_registry.md`；仓库只保留少量用于计算复现的派生数据、脚本和结果，不重新分发原始页面或原始 PDF。

## 允许上传

- `tools/`、`tests/` 和 `agh-plugin/`：团队编写的确定性工具、插件和测试。
- `docs/`、`README.md`、`LICENSE`、`report.html` 和 `cases/generated_dossier_v3.*`：团队文档及工具生成结果。
- `validation/data/steel_for_life_hfrhs_reference.csv`：有限的事实型截面属性摘录，带来源登记和用途限制，不包含原始网页布局、图片或 PDF 内容。
- `validation/results/` 和 `validation/scripts/`：团队计算得到的派生结果和复现脚本。
- `pictures/`：团队在 AGH 本地运行过程中截取的项目演示证据，不包含第三方原始资料文件。

## 仍需人工确认

1. 提交前核对赛事规则是否允许公开 AGH 界面截图；如果不确定，可从提交包中移除 `pictures/`。
2. 核对最终采用的 EN 1993-1-5 标准文本及年份；仓库只引用标准名称，不上传标准原文。
3. 不提交 API key、AGH 本地会话数据、个人路径、日志、虚拟环境或备份目录。

## 自动排除规则

`.gitignore` 已加入 `validation/sources/` 和旧版示例文件。即使本地保留这些文件，正常 `git add .` 也不会将其加入提交。
