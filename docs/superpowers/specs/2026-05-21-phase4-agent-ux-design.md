# zentao-story-prd-analyzer — 阶段四：多 Agent 适配与用户体验闭环

**日期**: 2026-05-21
**版本**: 1.0
**状态**: 设计完成，待实现

---

## 1. 背景与目标

阶段四在前三阶段基础上，补齐 Agent 适配、日志诊断、debug bundle、配置化 CLI 和用户文档。阶段一负责禅道数据获取，阶段二负责代码扫描与结构化分析，阶段三负责 PRD/ISSUE 文档生成。阶段四不改变前三阶段的核心业务语义，而是让整条链路更可配置、可诊断、可回溯。

阶段四目标：

- 真实接入 OpenAI/Codex 与 Claude CLI。
- 预留 OpenCode Agent 名称和接口，但不实现真实调用。
- 保证所有 Agent 调用都返回结构化 `AgentResult`，避免非结构化 LLM 输出导致主流程崩溃。
- 提供默认开启的 debug bundle，用于回溯 LLM 行为和调整 SKILL/Prompt。
- 提供清晰的 stderr 日志、可选 JSONL 日志、`--verbose`、`--quiet`。
- 统一脱敏 token、password、API key 等敏感信息。
- 更新 README 和 `SKILL.yaml`，让用户知道如何配置和运行。

---

## 2. 范围

### 2.1 纳入范围

- 新增统一 Agent 调用层。
- 将现有 `llm_client.py` 的分支式实现迁移到 `AgentClient` 或兼容封装。
- OpenAI/Codex 使用 OpenAI SDK 后端。
- Claude 使用本机 Claude CLI 后端。
- OpenCode 返回明确 `not_implemented`。
- 新增运行日志模块。
- 新增 debug bundle 模块，默认开启。
- 新增应用配置解析模块。
- 扩展 `main.py` CLI 参数并接入日志/debug bundle。
- 更新 README 和 `SKILL.yaml`。

### 2.2 暂不纳入范围

- OpenCode 真实调用。
- 禅道回写。
- 自动修改代码。
- 自动提交 Git commit。
- Agent 自动安装或自动登录。
- 图形界面或 Web UI。
- 将 debug bundle 上传到远程服务。

---

## 3. 架构设计

阶段四新增或重构以下模块：

| 模块 | 职责 | 说明 |
|------|------|------|
| `agent_client.py` | 统一 Agent 调用 | 定义 `AgentConfig`、`AgentResult`、`AgentClient`，支持 OpenAI/Codex、Claude CLI、OpenCode 占位 |
| `run_logger.py` | 运行日志 | stderr 文本日志、verbose/quiet、可选 JSONL、脱敏 |
| `debug_bundle.py` | 调试包 | 默认保存脱敏配置、条目、扫描摘要、prompt、response、分析结果和输出路径 |
| `app_config.py` | 配置解析 | 统一合并 CLI 参数和环境变量 |
| `llm_client.py`（修改） | 兼容层 | 可保留 `call_llm()`，内部委托 `AgentClient` |
| `main.py`（修改） | 主流程编排 | 新增 CLI 参数，串联 logger/debug bundle |
| `README.md`（修改） | 用户文档 | 增加 Agent、日志、debug bundle 配置说明 |
| `SKILL.yaml`（修改） | Skill 参数 | 同步新增输入参数 |

### 3.1 模块边界原则

1. `agent_client.py` 是唯一执行 LLM/Agent 调用的模块。
2. `run_logger.py` 只负责日志输出和脱敏，不参与业务判断。
3. `debug_bundle.py` 只负责写入回溯文件，不改变分析结果。
4. `app_config.py` 只负责配置合并与默认值，不调用 Agent。
5. `main.py` 只编排阶段一至阶段四，不实现 Agent 细节。
6. 阶段四不修改阶段一禅道读取、阶段二代码扫描、阶段三文档模板的业务语义。

---

## 4. Agent 调用设计

### 4.1 AgentConfig

```python
@dataclasses.dataclass
class AgentConfig:
    agent: str = "openai"          # openai | codex | claude | opencode
    model: str = ""
    timeout: int = 120
    command: str = ""              # Claude CLI command, default claude
    prompt_via: str = "stdin"      # stdin | arg
    extra_args: list[str] = dataclasses.field(default_factory=list)
    cwd: str = "."
```

配置来源优先级：

1. CLI 参数。
2. 环境变量。
3. 默认值。

### 4.2 AgentResult

`AgentResult` 是所有 Agent 调用的唯一返回契约。

```python
@dataclasses.dataclass
class AgentResult:
    ok: bool
    text: str = ""
    json_data: dict = dataclasses.field(default_factory=dict)
    raw_response: str = ""
    error: str = ""
    error_kind: str = ""           # auth | network | timeout | config | runtime | parse | not_implemented
    duration_ms: int = 0
    agent: str = ""
    model: str = ""
```

### 4.3 结构化返回兜底

AgentClient 必须保证：

- 不向 `analyzer` 抛出裸异常。
- OpenAI 缺 key、Claude 命令不存在、子进程超时、返回码非 0、LLM 空输出、非 JSON 输出都必须返回 `AgentResult`。
- 失败时 `ok=false`，并设置 `error` 和 `error_kind`。
- `raw_response` 和 `text` 必须经过脱敏后再进入日志/debug bundle。

### 4.4 LLM JSON 解析兜底

AgentClient 对模型文本执行 JSON 解析：

1. 先尝试直接 `json.loads(text)`。
2. 若失败，尝试提取 Markdown 代码块中的 JSON。
3. 若失败，尝试从文本中提取第一个 JSON 对象。
4. 若仍失败，返回 `ok=false`、`error_kind="parse"`，并保留脱敏 raw response。

`analyzer` 收到失败结果后，应转换为 `AnalysisResult.from_error()`，阶段三继续生成诊断文档。
解析失败不得由分析器自动发起修复重试，也不得由宿主 Agent 绕过分析器直接生成分析结论。调用方应向用户说明结构化响应解析失败，并提示由用户决定是否重新执行分析。

当某个条目的 `error_kind="parse"` 时，Analyzer CLI 还必须：

- 在该条目的 `analysis[]` 结果中提供 `retryable=true` 与 `retry_reason="agent_response_parse_failed"`。
- 在最终 JSON 顶层提供聚合字段 `has_retryable_failure=true`；无可重试失败时为 `false`。
- 在 stderr 输出简短提示，说明 Agent 响应解析失败，并给出由用户选择是否重新执行的重试命令。
- 批量分析中，仅为每个解析失败条目给出带 `--id <item_id>` 的单条重试命令，不建议重新执行整个批次或重做成功条目。
- 重试命令应复用本次调用的 analyzer CLI 入口路径，形成可直接执行的脱敏条目级命令；保留 `--module`、失败条目 `--id`、`--analyze`、`--repo-path`、`--agent`、`--agent-timeout`、`--quiet`、代码线索与输出目录等非敏感分析参数。
- 重试命令不得输出 `--token`、`--password`、`--user`、`--login`、`--server`、`--use-env` 或任何经脱敏规则判定为敏感的参数值。
- 单条重试命令保留 `--output-root` 以更新主文档输出位置，但不得继承原运行的 `--output`，避免以单条结果覆盖批量或显式保存的组合 JSON。
- 不自动执行该命令。
- 用户明确选择重试后，新的运行沿用现有输出策略：该条目的 PRD/ISSUE 与 summary 可由最新结果覆盖；前一次解析失败的原始响应和诊断产物通过旧 Debug Bundle 保留用于追溯。
- 解析失败已经产生诊断文档、summary 和 Debug Bundle 时，CLI 仍以 exit code `0` 结束；调用方通过条目级可重试字段和顶层聚合字段区分完整分析与可重试诊断结果。

---

## 5. OpenAI/Codex 后端

`openai` 和 `codex` 使用同一 OpenAI SDK 后端。`codex` 作为历史兼容别名保留。

配置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `--model`
- `--agent-timeout`

行为：

- 未配置 API key 时返回 `AgentResult(ok=false, error_kind="config")`。
- 网络错误或超时返回 `network` 或 `timeout`。
- 返回文本后进入 JSON 解析兜底。
- 不在日志中输出 API key。
- 默认模型通过配置决定；SPEC 不硬编码不可长期维护的模型名。

---

## 6. Claude CLI 后端

Claude 后端通过本机 CLI 子进程调用，不使用 SDK。

默认配置：

- 命令：`claude`
- prompt 传递方式：`stdin`
- 可选 `arg` 模式

配置：

- `CLAUDE_COMMAND`
- `CLAUDE_PROMPT_VIA`
- `--claude-command`
- `--claude-prompt-via {stdin,arg}`
- `--claude-extra-arg ARG` 可重复
- `--agent-timeout`

命令构造参考 `/home/ubuntu/code/cppcheck_misra_agents_bundle_v2` 的 provider 模式，适配本项目：

- 默认补齐 `--output-format text`。
- 默认追加 `--append-system-prompt <本项目分析约束>`。
- 默认追加 `--disallowedTools Task`，避免 Claude 自行 spawn subagent。
- 若未配置权限参数，追加 `--dangerously-skip-permissions`，避免非交互运行挂起。
- `prompt_via=stdin` 时通过 stdin 传入 prompt，并移除 `-p`/`--print`。
- `prompt_via=arg` 时使用 `-p` 或 `--print`，确保 prompt 紧随 print 参数。
- 使用 `subprocess.run([...], shell=False)`，禁止 shell 字符串拼接。

错误分类：

- 命令不存在：`config`
- 超时：`timeout`
- 认证、登录、unauthorized、anthropic_api_key：`auth`
- rate limit、429：`auth`
- network、timed out、econn、socket：`network`
- 非零返回码且无法分类：`runtime`
- stdout 非 JSON：进入 JSON 解析兜底，最终可能为 `parse`

---

## 7. OpenCode 预留

`opencode` 保留为合法 agent 名称，但阶段四不实现真实调用。

行为：

```json
{
  "ok": false,
  "error_kind": "not_implemented",
  "error": "OpenCode 适配尚未实现"
}
```

README 必须说明 OpenCode 是预留接口。

---

## 8. 日志设计

### 8.1 stderr 文本日志

默认输出简洁进度到 stderr：

- `fetch_items started/done`
- `analyze started/done`
- `generate_docs started/done`
- `summary_report written`

`--verbose` 增加：

- stage
- event
- status
- duration
- agent
- model
- item_id
- repo_path
- output_path
- error_kind
- error 摘要

`--quiet` 抑制进度日志，保持 stdout 只输出机器可读 JSON。严重错误仍可输出到 stderr。

### 8.2 JSONL 日志

`--log-file path.jsonl` 时额外写 JSONL，每行一个事件：

```json
{
  "timestamp": "2026-05-21T10:00:00+08:00",
  "stage": "analyze",
  "event": "agent_call",
  "status": "done",
  "duration_ms": 1234,
  "agent": "claude",
  "model": "",
  "item_id": "5939",
  "output_path": "",
  "error_kind": "",
  "error": ""
}
```

### 8.3 脱敏

日志和 debug bundle 必须脱敏：

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `ZENTAO_TOKEN`
- `token`
- `password`
- `api_key`
- `authorization`
- 任何形如 `Bearer <value>` 的内容

脱敏后显示为 `***`。

---

## 9. Debug Bundle

debug bundle 默认开启，用于回溯 LLM 行为、排查失败和调整 SKILL/Prompt。

默认目录：

```text
debug_runs/{timestamp}-{module}-{id_or_project}/
```

CLI：

- `--no-debug-bundle`
- `--debug-bundle-dir DIR`
- `--debug-include-code`

默认保存：

| 文件 | 内容 |
|------|------|
| `run_config.redacted.json` | 脱敏后的 CLI/env 配置 |
| `items.json` | 禅道条目摘要 |
| `scan_summary.json` | 扫描文件清单、命中数量、截断说明 |
| `prompts/{item_id}.txt` | 脱敏 prompt |
| `responses/{item_id}.txt` | 脱敏 Agent 原始响应 |
| `analysis_results.json` | 结构化分析结果 |
| `documents.json` | 生成文档路径 |
| `summary_report_path.txt` | summary 路径 |
| `run_log.jsonl` | 本次运行结构化日志 |

默认不保存完整代码片段。只有传 `--debug-include-code` 时，才保存代码上下文快照；保存前仍需脱敏。

最终 stdout JSON 必须包含：

```json
{
  "debug_bundle": "debug_runs/20260521-100000-requirement-5939",
  "debug_bundle_error": ""
}
```

若 debug bundle 写入失败，不阻塞主流程；最终 JSON 设置 `debug_bundle_error`。

---

## 10. CLI 与环境变量

新增 CLI 参数：

- `--agent {openai,codex,claude,opencode}`
- `--model MODEL`
- `--agent-timeout SECONDS`
- `--claude-command COMMAND`
- `--claude-prompt-via {stdin,arg}`
- `--claude-extra-arg ARG`，可重复
- `--verbose`
- `--quiet`
- `--log-file PATH`
- `--no-debug-bundle`
- `--debug-bundle-dir DIR`
- `--debug-include-code`

环境变量：

- `LLM_AGENT`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `CLAUDE_COMMAND`
- `CLAUDE_PROMPT_VIA`
- `AGENT_TIMEOUT`
- `DEBUG_BUNDLE_DIR`

现有 `--agent` 默认值继续兼容 `LLM_AGENT`。

---

## 11. 主流程集成

`main.py` 需要：

1. 解析阶段四新增 CLI 参数。
2. 通过 `app_config.py` 合并环境变量和 CLI 参数。
3. 初始化 `RunLogger`。
4. 默认初始化 debug bundle，除非 `--no-debug-bundle`。
5. 将 `AgentConfig` 传入 analyzer 或 `llm_client.call_llm()` 的兼容层。
6. 在每个关键阶段记录日志：
   - 禅道数据获取
   - 代码扫描
   - Agent 调用
   - 分析结果解析
   - 文档生成
   - summary 写入
7. 最终 JSON 增加：
   - `debug_bundle`
   - `debug_bundle_error`
   - `log_file`
   - `analysis[]` 对可重试解析失败提供 `retryable` 和 `retry_reason`
   - 顶层提供 `has_retryable_failure`

stdout 必须保持单个可解析 JSON 对象，不被日志污染。

---

## 12. 错误处理

| 场景 | 行为 |
|------|------|
| OpenAI key 缺失 | `AgentResult(ok=false, error_kind="config")` |
| OpenAI 网络错误 | `error_kind="network"` |
| OpenAI 超时 | `error_kind="timeout"` |
| Claude 命令不存在 | `error_kind="config"` |
| Claude 超时 | 杀掉进程，`error_kind="timeout"` |
| Claude 返回非零 | 分类为 auth/network/runtime |
| Claude 输出非 JSON 或 JSON 格式损坏 | JSON 解析兜底，失败则 `parse`；提示用户决定是否重新执行，不自动重试或接管分析 |
| 批量分析中部分条目为 `parse` | 保留其余条目结果；只提示按失败条目 ID 分别重试 |
| 输出重试命令 | 仅打印脱敏后的条目级可执行命令；不回显认证参数或敏感值 |
| 原运行包含 `--output` | 单条重试命令不继承该参数；保留 `--output-root` |
| 用户确认重试且新运行成功 | 使用最新 PRD/ISSUE 与 summary 覆盖主输出；历史失败证据保留在原 Debug Bundle |
| 解析失败但诊断输出已生成 | 保持 exit code `0`；由 `retryable` / `has_retryable_failure` 表达需人工选择重试 |
| OpenCode | `not_implemented` |
| 日志写入失败 | stderr 警告，不影响主流程 |
| debug bundle 写入失败 | 不影响主流程，最终 JSON 标记 `debug_bundle_error` |

---

## 13. 测试策略

新增或修改测试：

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/test_agent_client.py` | OpenAI mock、Claude stdin/arg、Claude 超时、命令不存在、OpenCode 未实现、非 JSON 兜底、脱敏 |
| `tests/test_run_logger.py` | quiet、verbose、JSONL、脱敏 |
| `tests/test_debug_bundle.py` | 默认创建、关闭、指定目录、默认不保存代码、include-code、脱敏 |
| `tests/test_app_config.py` | CLI/env 合并、默认值、兼容旧 `LLM_AGENT` |
| `tests/test_main_phase4.py` | CLI 参数映射、最终 JSON 包含 debug bundle、解析失败可重试提示、stdout 单 JSON |
| `tests/test_llm_client.py` | 确认兼容层委托 AgentClient |

测试原则：

- 不调用真实 OpenAI。
- 不调用真实 Claude CLI。
- Claude CLI 使用 `subprocess.run` mock。
- Debug bundle 使用临时目录。
- 敏感信息用测试 token 验证脱敏。
- 回归运行全量 `python3 -m unittest discover -v tests`。

---

## 14. 文档更新

README 需要新增：

- Agent 选择示例：
  - `--agent openai`
  - `--agent codex`
  - `--agent claude`
  - `--agent opencode`
- OpenAI 环境变量说明。
- Claude CLI 前置条件和参数说明。
- `--quiet`、`--verbose`、`--log-file` 示例。
- debug bundle 默认开启说明。
- 如何关闭 debug bundle。
- 安全注意事项：debug bundle 包含 prompt/response，默认脱敏但仍应妥善保管。

`SKILL.yaml` 需要同步新增输入：

- `agent`
- `model`
- `agent_timeout`
- `claude_command`
- `claude_prompt_via`
- `verbose`
- `quiet`
- `log_file`
- `debug_bundle_dir`
- `no_debug_bundle`
- `debug_include_code`

---

## 15. 验收点

- [ ] 用户可通过 CLI/env 选择 `openai`、`codex`、`claude`、`opencode`。
- [ ] OpenAI/Codex 后端可 mock 验证成功与失败。
- [ ] Claude CLI 后端可 mock 验证 stdin 与 arg 模式。
- [ ] OpenCode 返回 `not_implemented`，不伪造成功。
- [ ] 所有 Agent 调用失败都返回结构化 `AgentResult`。
- [ ] LLM 非 JSON 输出不会导致主流程崩溃。
- [ ] LLM JSON 解析失败时条目结果标记可重试，stderr 只提示用户选择重试，不自动再次调用 Agent。
- [ ] 批量分析中部分条目解析失败时，仅为失败条目提示 `--id` 重试命令，不要求重跑成功条目。
- [ ] stderr 中的重试命令保留非敏感分析上下文，且不泄露认证参数或敏感值。
- [ ] 原运行指定 `--output` 时，单条重试提示不会覆盖其组合 JSON 输出文件。
- [ ] 用户手动重试成功后更新主文档与 summary，同时原失败 Debug Bundle 仍可复核。
- [ ] 解析失败且诊断输出已成功生成时进程返回 `0`，机器可读结果明确标识可重试状态。
- [ ] 默认创建 debug bundle。
- [ ] `--no-debug-bundle` 可关闭 debug bundle。
- [ ] `--debug-include-code` 才保存代码上下文快照。
- [ ] `--log-file` 写 JSONL。
- [ ] `--quiet` 保持 stdout 单 JSON。
- [ ] 日志和 debug bundle 不泄露 token/password/API key。
- [ ] README 和 `SKILL.yaml` 已同步新参数。
- [ ] 阶段一、二、三现有测试不回退。

---

## 16. 风险与假设

1. **Claude CLI 版本差异**：不同版本参数可能不同。缓解方式是允许 `--claude-extra-arg` 和 `--claude-command` 覆盖。
2. **debug bundle 默认开启可能保存敏感业务上下文**：缓解方式是默认脱敏、默认不保存代码片段、支持 `--no-debug-bundle`。
3. **LLM 非 JSON 输出常见**：缓解方式是三层 JSON 解析兜底和结构化 `AgentResult`。
4. **OpenAI SDK 版本差异**：实现时应尽量封装调用点，并通过 mock 测试覆盖。
5. **日志污染 stdout**：所有日志默认走 stderr，stdout 仅输出最终 JSON。

---

## 17. 依赖关系

- 阶段四依赖阶段二 Prompt 和 `AnalysisResult`。
- 阶段四依赖阶段三输出路径和 summary。
- 阶段四不依赖禅道写接口。

---

*文档结束*
