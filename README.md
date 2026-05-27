## zentao-story-prd-analyzer

结合禅道命令行工具 `zentao` 和代码代理能力，完成从禅道条目获取、代码仓库分析、LLM 判断到 PRD/ISSUE 文档生成的闭环。

代码实现位于 `zentao_analyzer` 包内；根目录 `main.py` 是兼容入口，既有 `python3 main.py ...` 命令保持可用。

### 当前运行方式

本项目当前主要作为命令行工具运行。推荐入口是仓库根目录的 `main.py`：

```bash
python3 main.py --module requirement --id 5939
```

`main.py` 只负责兼容旧命令，真实实现位于 `zentao_analyzer.main`。也可以用 Python package 方式运行：

```bash
python3 -m zentao_analyzer.main --help
```

常见运行模式：

```bash
# 阶段一：只抓取禅道条目，stdout 输出 JSON
python3 main.py --module requirement --id 5939

# 阶段二到六：抓取禅道条目后分析本地代码，生成 PRD/ISSUE、summary 和 debug bundle
python3 main.py --module requirement --id 5939 --analyze --repo-path .

# 指定 Agent
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude

# 显式提供代码线索
python3 main.py --module requirement --id 5939 --analyze --repo-path . \
  --clues calibration,LoadCalibration \
  --paths src/calib/import_config.c

# 提供需求正文模式：不从禅道读取，直接用用户提交的完整需求生成 PRD
python3 main.py --module requirement --id 5932 \
  --title "Ecall功能的优先级定义" \
  --requirement-file /tmp/requirement-5932.txt \
  --analyze --repo-path . --agent claude
```

运行前需要满足以下前置条件：

- `zentao` CLI 已安装，并可在 `PATH` 中直接调用。
- 已通过 `zentao login` 完成登录，或已配置 `ZENTAO_SERVER` 与 `ZENTAO_TOKEN` / `ZENTAO_USER` / `ZENTAO_PASSWORD`。如果 Token 失效，程序会以 exit code 2 退出并提示登录命令，登录后重试即可。
- 可通过以下方式确认 profile 并让实际读取请求验证认证状态：

  ```bash
  # 查看当前 profile（* 标记为活跃会话；该命令不验证 token）
  zentao profile

  # 直接读取待分析条目；成功即说明此次读取所需认证有效
  zentao --format json --machine-readable get requirement <需求ID>
  ```

  不要用 `zentao user` 检查登录状态：该命令读取用户模块，可能需要额外权限且不是当前会话身份查询。如果目标读取返回 `code: 1004` 或 "Token 已失效"，需要重新登录。注意 `zentao whoami` 命令不存在，请勿使用。
- 使用 Claude/Codex/OpenCode 后端时，本机分别可执行 `claude`、`codex` 或 `opencode` CLI。
- `--repo-path` 指向当前运行环境可访问的代码仓库。

### `SKILL.yaml` 的作用

`SKILL.yaml` 是本项目的能力声明文件，用于描述这个工具作为“技能”被外部 Agent 或自动化平台调用时需要的输入、输出和默认入口。它不是 Python 代码的直接运行入口，也不是 Codex/Claude Code 常规 Skill 的触发说明；常规 Agent CLI Skill 入口见根目录 `SKILL.md`。

当前 `SKILL.yaml` 主要说明：

- 技能名称：`zentao-story-prd-analyzer`
- 技能能力：从禅道获取需求/缺陷，结合本地代码分析完成度或问题原因，并生成 PRD/ISSUE 文档
- 输入参数：`project_id`、`item_type`、`repo_path`、`agent`、`model`、`clues`、`paths`、`clues_file` 等
- 输出结果：`prd_docs`
- 默认运行入口：

```yaml
run:
  python: main.py
```

因此：

- 人工或脚本调用时，直接使用 `python3 main.py ...`。
- 支持读取 `SKILL.yaml` 的 Agent/平台可以根据其中的输入定义和 `run.python` 自动组装命令。
- 通过 Codex/Claude Code 等 Agent CLI 的常规 Skill 方式安装时，使用根目录 `SKILL.md` 作为触发说明；`SKILL.md` 会指导 Agent 在目标代码仓库中调用本项目的 `main.py`。

### `SKILL.md` 的作用

`SKILL.md` 是面向 Codex、Claude Code 等 Agent CLI 的通用 Skill 说明文件。它采用薄封装策略：只说明何时使用本工具、如何收集参数、如何在目标代码仓库中调用 CLI、沙箱内需要满足哪些前置条件，以及如何解释输出。

`SKILL.md` 的边界：

- 默认从当前工作目录作为目标代码仓库运行分析。
- 默认执行完整分析链路，即带 `--analyze`。
- 不替代官方禅道 Skill；只查询禅道数据时应优先使用官方禅道 Skill 或 `zentao` CLI。
- 不在 Skill 层重复实现分析逻辑，不伪造 Zentao 内容、代码证据或 PRD/ISSUE 结论。
- 沙箱内必须能访问 `zentao` CLI、禅道配置/登录态、目标代码仓库，以及所选 Agent 后端。

### 资料链接

- 禅道 CLI: https://www.zentao.net/book/zentaopms/2377.html
- 禅道 SKILL: https://www.zentao.net/book/zentaopms/2315.html
- Token 消耗模型: [`docs/TOKEN_COST.md`](docs/TOKEN_COST.md)（第一版，随分析方案演进需更新）

### 提供需求正文模式

除从禅道读取需求外，支持用户直接提供完整需求正文：

```bash
python3 main.py --module requirement \
  --id 5932 \
  --title "Ecall功能的优先级定义(CN&EU) - TCAM Priority and Parallelism of Services" \
  --requirement-file /tmp/requirement-5932.txt \
  --analyze --repo-path . --agent claude --quiet
```

规则：

- `--requirement-file` 仅支持 `requirement` 或 `story` 模块。
- `--requirement-file` 需要同时提供非空 `--id` 和 `--title`。
- 该模式不调用禅道读取或登录；ID 仅作为输出关联标识。
- 文件必须可读且内容非空，否则在调用 Agent 前失败。
- `--requirement-file` 与 `--login`、禅道认证参数和列表查询参数不能同时使用。
- 产物中来源字段标识为 `provided_requirement`。

### 深度 PRD 内容

Feature Item 的 PRD 包含固定章节：

1. **概述**：需求摘要、范围、术语定义、来源信息
2. **需求详细描述**：业务规则、场景与流程、关系或并发矩阵、待确认事项
3. **功能影响分析**：现有代码关联、实现完成度、关键代码证据
4. **需求对照表**：需求点完成情况、差异与缺口
5. **建议实现策略**：代码变更建议、测试要点（明确为建议，不代表已有实现）
6. **参考信息**：追踪信息

内容边界：

- Requirement Interpretation（需求解读）仅依据 Requirement Source 整理。`source: "code_context"` 标记为"代码侧候选上下文，不构成需求定义"；`source: "insufficient"` 标记为"原始需求未提供足够信息"。
- Code Impact（代码影响）的关联位置与完成度证据分开存储；关联位置不作为完成度证据。
- Completion Assessment（完成度）严格依据有效 Requirement Point 和 Code Evidence。
- Interpretation 或 Code Impact 缺失时，PRD 仍生成，对应章节显示"分析结果未提供有效内容"。

---

## 阶段一：禅道 CLI 数据闭环

### 环境要求

- 已安装禅道 CLI 工具 `zentao`，并可在 PATH 中直接调用。
- Python 3.8+

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ZENTAO_CONFIG_FILE` | 禅道 CLI 配置文件路径 | `/path/to/config.json` |
| `ZENTAO_PROFILE` | 已保存的 profile 名称 | `admin@https://zentao.example.com` |
| `ZENTAO_TIMEOUT` | 请求超时毫秒数（默认 30000） | `30000` |
| `ZENTAO_SERVER` | 禅道服务地址 | `https://zentao.example.com` |
| `ZENTAO_USER` | 禅道用户名 | `admin` |
| `ZENTAO_PASSWORD` | 禅道密码 | `***` |
| `ZENTAO_TOKEN` | 禅道 Token | `***` |
| `PROJECT_ID` | 默认项目 ID | `1` |

### 命令行用法

沙箱或新环境内首次运行前，需要先让 `zentao` 完成登录。推荐使用 token 登录：

```bash
zentao login -s http://101.91.119.66:8000/ -t <token>
python3 main.py --module requirement --id 5939
```

也可以在 shell 环境中设置禅道服务和 token，之后直接运行分析命令：

```bash
export ZENTAO_SERVER="http://101.91.119.66:8000/"
export ZENTAO_TOKEN="<token>"
python3 main.py --module requirement --id 5939
```

```bash
# 获取单个 story 详情
python3 main.py --module story --id 123

# 获取某个项目下的 bug 列表
python3 main.py --module bug --project 5 --status active --limit 10

# 登录禅道（使用环境变量）
python3 main.py --login --use-env

# 登录禅道（使用命令行参数）
python3 main.py --login --server https://zentao.example.com --user admin --password ***

# 将阶段一结果写入文件
python3 main.py --module story --project 3 --output story_data.json

# 获取数据后继续执行代码分析与 PRD 生成（阶段二）
python3 main.py --module story --project 3 --analyze --repo-path ./my-repo
```

### 支持的模块映射

| 模块参数 | 说明 |
|----------|------|
| `story` | 软件需求 |
| `requirement` | 用户需求 |
| `bug` | 缺陷 |
| `task` | 任务 |
| `ticket` | 工单 |
| `feedback` | 反馈 |

### 错误处理

- 当未找到 `zentao` 命令时，会提示安装禅道 CLI。
- 当未登录或认证失败时，会明确提示 `禅道认证失败`，不会泄露密码或 Token。
- 当对象不存在时，会提示 `禅道对象不存在`。
- 当网络超时时，会提示超时信息。
- 所有日志和异常信息均已对敏感字段做脱敏处理。

### 认证失败恢复

当 Token 失效或未登录导致认证失败时（exit code 2，或 stderr 包含 `Token 已失效`/`认证失败`/`未登录`/`auth`/`unauthorized`），按以下步骤恢复：

1. 从环境变量 `ZENTAO_SERVER` 获取服务地址，或从错误上下文中提取。
2. 在终端手动执行登录命令：
   ```bash
   zentao login -s <服务地址> -u <用户名> -p <密码>
   ```
   或使用 token：
   ```bash
   zentao login -s <服务地址> -t <token>
   ```
3. 登录成功后，重新执行原来的分析命令（无需再加 `--login` 参数，zentao CLI 会保存登录态）。
4. 如果重试仍然认证失败，报告完整错误信息并停止，不再重试。

> **注意**：不要在日志、输出或调试信息中记录密码或 Token。不要硬编码服务地址。

---

## 阶段四：Agent、日志与 Debug Bundle

### Agent 选择

`--agent` 参数选择 LLM 后端，**应与宿主 Agent CLI 环境一致**：

| 宿主环境 | `--agent` 参数 | 说明 |
|----------|--------------|------|
| Claude Code | `claude` | 调用本机 `claude` CLI |
| OpenCode | `opencode` | 调用本机 `opencode run` |
| Codex | `codex` | 调用本机 `codex exec` |

如果未指定 `--agent` 且未设置 `LLM_AGENT` 环境变量，程序会自动检测：`claude` -> `codex` -> `opencode`。

```bash
# Claude Code 环境（推荐）
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude

# OpenCode 环境
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent opencode

# Codex 环境
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent codex
```

`claude` 使用本机 Claude CLI。默认命令是 `claude`，默认通过 stdin 传入 prompt：

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --claude-command claude --claude-prompt-via arg
```

`codex` 调用本机 `codex exec` 命令；`opencode` 调用本机 `opencode run` 命令。显式传入 `--model` 时才会把模型参数传给对应 CLI。

Agent CLI 子进程只用于读取和搜索目标仓库，并返回结构化 JSON 分析结果。只有 analyzer 进程可以写入 debug bundle、PRD/ISSUE 文档、summary、显式 `--output` 和显式 `--log-file`。

默认权限策略：

- Claude 默认限制为只读工具 `Read,Grep,Glob`。
- Codex 默认使用 `codex exec --sandbox read-only`。
- OpenCode 不默认启用 `--dangerously-skip-permissions`，只使用宿主 CLI 的默认权限行为。

不要通过额外参数授予 Agent CLI 子进程写文件能力，除非你明确接受其可能修改目标仓库或生成文档的风险。

### 日志

运行日志默认写入 stderr，stdout 保持最终 JSON：

```bash
python3 main.py --module requirement --id 5939 --analyze --quiet
python3 main.py --module requirement --id 5939 --analyze --verbose
python3 main.py --module requirement --id 5939 --analyze --log-file logs/run.jsonl
```

日志会脱敏 token、password、API key、Authorization 和 Bearer token。

### Debug Bundle

`--analyze` 时 debug bundle 默认开启，默认写入：

```text
.zentao-story-prd-analyzer/{timestamp}-{module}-{id_or_project}/
```

其中包含脱敏配置、禅道条目摘要、扫描摘要、prompt、Agent response、分析结果、文档路径、summary 路径和本次 JSONL 日志引用。默认不保存完整代码片段。

```bash
python3 main.py --module requirement --id 5939 --analyze --debug-bundle-dir .zentao-story-prd-analyzer
python3 main.py --module requirement --id 5939 --analyze --no-debug-bundle
python3 main.py --module requirement --id 5939 --analyze --debug-include-code
```

Debug bundle 会默认脱敏，但仍可能包含业务上下文、prompt 和模型响应，应按项目敏感资料管理。

### Agent 响应解析失败

如果 Agent 返回的内容无法解析为结构化 JSON，分析器不会自动重试，也不会由宿主 Agent 绕过分析器继续生成替代结论。该条目仍会生成诊断文档、summary 和 debug bundle，并以 exit code `0` 结束。

最终 JSON 会标记可人工重试的条目：

```json
{
  "analysis": [
    {
      "item_id": "5929",
      "error_kind": "parse",
      "retryable": true,
      "retry_reason": "agent_response_parse_failed"
    }
  ],
  "has_retryable_failure": true
}
```

stderr 会输出脱敏后的单条重试命令。只有用户确认后才重新执行；批量分析仅重试失败条目，不重做已成功条目。重试命令保留 `--output-root`，但不会继承 `--output`，避免以单条结果覆盖原组合 JSON 文件。

---

## 阶段五：证据可追溯性

### 代码线索

代码线索分为两类：

| 类型 | 参数 | 说明 |
|------|------|------|
| Search Hint | `--clues` / `clues_file.clues` | 写入 prompt，指导 Agent 自主搜索，不读取源码 |
| Seed Path | `--paths` / `clues_file.paths` | 预加载到 prompt 的仓库内文件，只接受文件，不接受目录 |

目录名、模块名或符号名应放入 `--clues`；只有明确要预加载的文件才放入 `--paths`。

显式提供代码线索：

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . \
  --clues calibration,LoadCalibration,src/calib \
  --paths src/calib/import_config.c
```

批量分析时可使用 `--clues-file` 为不同条目指定不同线索：

```json
{
  "5939": {
    "clues": ["calibration", "LoadCalibration", "src/calib"],
    "paths": ["src/calib/import_config.c"]
  }
}
```

```bash
python3 main.py --module requirement --project 3 --analyze --repo-path . --clues-file clues.json
```

Seed Path 必须是 `--repo-path` 内的文件。越界、目录或不存在的路径不会被读取，会记录到 debug bundle 的 `rejected_seed_paths.json`。

### 证据位置

debug bundle 默认保存证据位置文件：

```text
code_evidence_locations.json
rejected_seed_paths.json
```

`code_evidence_locations.json` 区分：

- `seed_locations`：由 Seed Path 预加载给 Agent 的文件名和行号范围。
- `cited_evidence_locations`：Agent 最终引用为结论依据的文件名和行号范围。
- `evidence_validation_issues`：本地文件/行号校验失败的证据位置。

PRD/ISSUE 文档只展示关键引用证据。完整代码内容仍只有在传入 `--debug-include-code` 时才保存。

### 实现完成度字段

PRD 的 `## 实现完成度` 展示以下分析字段。它们来自 Agent 对需求与代码证据的分析结果，不等同于“来源信息”中从禅道读取的字段。

| 字段 | 可选值 | 当前产生方式 |
|------|--------|--------------|
| 结论 | `完成` / `部分完成` / `未完成` / `无法判断` | Agent 先判断；证据不足或证据校验失败导致低可信度时，程序将功能类结论强制降为 `无法判断` |
| 优先级 | `高` / `中` / `低` | Agent 返回；当前没有程序化评分或枚举校验 |
| 可信度 | `高` / `中` / `低` | Agent 先按证据强弱判断；程序可因证据不足或引用位置校验失败强制降为 `低` |

Agent 未返回优先级或可信度时，文档以 `未评估` 展示；程序当前不校验 Agent 返回的非空字段是否属于上述枚举。

#### 结论

对于 `story` 与 `requirement`，Agent 应返回 `完成`、`部分完成`、`未完成` 或 `无法判断`。程序在以下情况将结论改为 `无法判断`：

- Agent 调用或解析失败；此时可信度显示为 `未评估`。
- `confidence` 为 `低`。
- `evidence` 为空。
- 引用的证据位置未通过本地文件或行号校验；此时程序先将可信度降为 `低`，再触发结论降级。

#### 可信度

| 等级 | 含义 |
|------|------|
| `高` | 有直接代码证据支持结论 |
| `中` | 有间接证据或推断 |
| `低` | 证据不足，无法可靠判断实现状态 |

程序对可信度的强制修正规则：

- 证据位置越界、不存在、行号无效或超过文件范围时，强制降为 `低`。
- 证据为空或结果已处于低可信度时，保持或设为 `低` 并将结论降为 `无法判断`。

#### 优先级

PRD 中存在两个名称相同但来源不同的优先级：

| 显示位置 | 来源 | 当前语义 |
|----------|------|----------|
| `来源信息` 中的优先级 | 禅道条目 `priority` | 禅道原始优先级 |
| `实现完成度` 中的优先级 | Agent 输出 `analysis.priority` | Agent 给出的分析优先级，目前没有固定评定标准 |

因此，当前不能将“实现完成度”中的优先级解释为程序按缺口、影响范围或禅道优先级自动计算的结果。
