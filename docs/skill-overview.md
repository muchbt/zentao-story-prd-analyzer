# zentao-story-prd-analyzer SKILL 作用说明

## 概述

`zentao-story-prd-analyzer` 是一个面向禅道需求与缺陷分析的代码代理技能。它的目标是从禅道获取指定项目下的 story 或 bug，结合本地代码仓库内容进行实现情况分析，并输出可发布的 PRD Markdown 文档和汇总报告。

该技能适用于以下场景：

- 需要批量检查禅道 story 或 bug 与代码实现是否一致。
- 需要根据现有代码实现情况生成需求差异分析。
- 需要把分析结论、修改建议和优先级评分整理成 PRD 文档。
- 需要让 Codex、Claude、OpenCode 等代码代理参与需求实现评估。

## 技能元数据

技能定义文件为仓库根目录下的 `SKILL.yaml`。

| 字段 | 说明 |
| --- | --- |
| `name` | 技能名称：`zentao-story-prd-analyzer` |
| `description` | 从禅道获取 story/bug，由 AGENT 主动分析代码实现情况，对比描述并生成修改建议、优先级评分和 PRD 文档 |
| `run.python` | 入口脚本：`main.py` |
| `agents` | 支持 `codex`、`claude`、`opencode` |

## 输入参数

| 参数 | 类型 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `project_id` | `string` | 无 | 禅道项目编号，用于筛选目标项目 |
| `item_type` | `string` | `story` | 禅道条目类型，可用于 story 或 bug |
| `status` | `string` | `open` | 禅道条目状态过滤条件 |
| `repo_path` | `string` | 无 | 需要分析的本地代码仓库路径 |

当前 `main.py` 主要从环境变量读取运行参数：

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `PROJECT_ID` | `1` | 禅道项目编号 |
| `REPO_PATH` | `.` | 本地代码仓库路径 |
| `LLM_AGENT` | `codex` | 使用的代码代理或大模型接口 |
| `INCREMENTAL` | `False` | 是否启用增量分析 |
| `LAST_COMMIT` | 无 | 增量分析时的起始提交 |

## 输出内容

技能输出为 `prd_docs`，包括：

- 每个禅道条目对应的 PRD Markdown 文档。
- `prd_docs/summary_report.json` 汇总报告。
- 每个 PRD 文档包含实现结论、差异分析、修改建议、相关文件/函数和优先级评分。

## 核心流程

1. 使用 `zentao` 获取禅道 story 或 bug 列表。
2. 根据运行配置获取本地仓库文件列表，支持全量或基于提交范围的增量分析。
3. 从 story 或 bug 的标题和描述中提取关键词。
4. 在本地仓库中收集相关代码片段。
5. 从代码片段中提取函数、类、结构体、注释和预处理信息，生成代码摘要。
6. 构造面向代码代理的分析 Prompt。
7. 调用指定代理或大模型，要求返回结构化 JSON。
8. 从 JSON 中提取 `prd_md`，生成 PRD Markdown 文档。
9. 生成 `summary_report.json` 汇总所有条目的文档路径。

## 分析能力

该技能会要求代理完成以下判断：

- story 描述与代码实现是否一致。
- 功能是否已完成、未完成或部分完成。
- 未完成内容的原因。
- 建议修改方向。
- 优先级评分，格式为高/中/低加 1-10 分。
- 可直接发布的 Markdown PRD 内容。

生成的 PRD 预期包含：

- Story ID、标题和描述。
- 实现差异分析表。
- 功能描述、实现状态、修改建议、相关文件或函数。
- 对未完成或部分完成内容的重点标记。
- 优先级评分。
- 清晰的章节结构和必要的代码片段引用。

## 依赖与前置条件

运行该技能前需要满足以下条件：

- 已安装并配置禅道命令行工具 `zentao`，且可通过命令行访问禅道数据。
- 默认配置文件位于 `~/.config/zentao/zentao.json`，也可通过 `--config` 或 `ZENTAO_CONFIG_FILE` 指定其他配置文件。
- 沙箱或新环境内首次运行前，需要先执行 `zentao login -s <server> -t <token>`，或提供 `ZENTAO_SERVER` 与 `ZENTAO_TOKEN`/`ZENTAO_USER`/`ZENTAO_PASSWORD` 后由程序登录。
- 本地存在待分析代码仓库。
- 若使用 Codex/OpenAI 调用，需要配置 `OPENAI_API_KEY`。
- 若使用 `claude` 或 `opencode`，需要补齐对应的调用实现。
- Python 环境需要具备脚本中使用的依赖，例如 `openai`。

## 当前实现注意事项

当前代码是原型级实现，使用前需要关注以下限制：

- `claude_api_call` 和 `opencode_api_call` 仍是占位调用，尚未在 `main.py` 中实现。
- 禅道数据获取应通过 `zentao` 命令完成，命令参数需要保持结构化传递，避免外部输入拼接到 shell 字符串。
- `collect_code` 主要覆盖 C/C++、Python、Shell、Batch、Makefile 和 CMake 文件。
- 关键词匹配当前主要基于文件名，不是完整语义检索。
- `main.py` 中的 `item_type` 和 `status` 在技能定义中存在，但主流程目前主要读取 `PROJECT_ID`，未完整接入所有 `SKILL.yaml` 输入参数。
- 大模型返回必须是合法 JSON，否则会降级为“未知”结论并把原始文本写入原因。

## 适合的使用方式

建议将该技能用于需求评审、迭代盘点、代码实现核查和 PRD 初稿生成。它可以减少人工整理禅道条目与代码差异的成本，但生成结果仍应由研发或产品负责人复核后再作为正式交付物使用。
