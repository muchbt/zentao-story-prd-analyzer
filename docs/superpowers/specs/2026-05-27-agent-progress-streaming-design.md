# Agent 真实进度事件与空闲超时设计

**日期**: 2026-05-27
**版本**: 0.1
**状态**: 讨论中，已确认核心边界

---

## 1. 背景

当前 `AgentClient` 通过 `subprocess.run(..., capture_output=True, timeout=...)` 等待 Agent 子进程结束后一次性读取最终输出。用户可看到分析开始与结束，但在长时间代码搜索过程中无法确认 Claude 或 Codex 正在执行的工具步骤。

本扩展只增加 Agent 调用的运行可观测性与空闲失败判定，不修改：

- Requirement Source、Requirement Interpretation 或 Completion Assessment 的含义。
- Agent 最终返回结构化分析载荷的责任。
- Analyzer Process 为正式文档唯一写入者的边界。
- `--agent-timeout` 作为整个 Agent 调用绝对时限的现有含义。

## 2. 已验证的后端能力

本机 CLI 帮助信息已确认：

- Claude 支持 `--output-format stream-json` 的实时事件输出，并提供 `--include-hook-events`、`--include-partial-messages` 选项。
- Codex 支持 `codex exec --json` 输出 JSONL 事件。
- OpenCode 尚未确认满足相同的结构化事件契约。

因此，进度事件必须来自 CLI 提供的结构化流，而不是要求模型在最终 JSON 前输出自然语言进度。最终分析载荷与进度事件解析保持分离。

## 3. 启用方式

新增显式参数：

```bash
python3 main.py ... --analyze --agent claude --agent-progress
python3 main.py ... --analyze --agent codex --agent-progress --quiet
```

已确认规则：

- `--agent-progress` 默认关闭；未指定时继续使用当前非流式 Agent 调用路径。
- 指定 `--agent-progress` 且 Agent 为 `claude` 或 `codex` 时，启用对应 CLI 的结构化事件流。
- 指定 `--agent-progress` 但选择尚未支持结构化事件流的 Agent 时，在启动调用前返回明确配置错误。
- 流式调用无法启动或 Agent 命令失败时，该次调用失败；不得自动切换为非流式模式后再次调用模型。

## 4. 可见进度事件

### 4.1 对外承诺

系统只展示 CLI 事件流中真实出现且可标准化的工具状态，不推测或补造缺失状态。

标准化事件形态：

```json
{
  "stage": "analyze",
  "event": "agent_tool",
  "agent": "claude",
  "tool": "Read",
  "status": "started",
  "item_id": "5932"
}
```

已确认规则：

- 可展示的工具名称为 `Read`、`Grep`、`Glob` 等工具类型。
- 可展示的状态为后端明确提供的 `started`、`done` 或 `failed`。
- 后端只提供开始事件时，仅展示 `started`；不得因出现后续事件或时间经过而补造 `done`。
- 不支持真实工具事件的后端不声称提供实时工具步骤，仍仅展示现有分析开始/结束信息。

### 4.2 信息保护

实时显示与结构化日志中只保留工具类型及状态，以及必要的运行关联字段，例如 `agent`、`item_id` 与时间信息。

禁止展示或记录到进度事件中：

- 文件路径，包括仓库内相对路径。
- 搜索关键词或匹配模式。
- 工具参数。
- 需求正文、prompt 内容或 Agent 思考文本。
- 读取到的代码片段或工具完整响应。

### 4.3 输出位置

- 默认运行：真实工具状态事件输出到 `stderr`。
- `--quiet`：抑制工具状态的实时 `stderr` 展示，但不抑制其结构化记录。
- `--log-file` 与默认 Debug Bundle 的 `run_log.jsonl`：记录同样经过限制的工具状态事件。
- PRD Document 与 Summary Report：不包含工具状态事件或工具统计。

## 5. 工具统计

一次 Agent 调用结束后，可在运行日志与 Debug Bundle 中记录仅按工具类型聚合的数量与可观测耗时，例如：

```json
{
  "stage": "analyze",
  "event": "agent_tools_summary",
  "agent": "claude",
  "item_id": "5932",
  "tool_counts": {"Read": 12, "Grep": 7, "Glob": 2},
  "observed_duration_ms": 84521
}
```

已确认规则：

- 汇总不包含路径、搜索词、参数或工具输出。
- 汇总写入运行日志与 Debug Bundle，不进入 `summary_report.json` 或正式 PRD。

## 6. 观测失败与分析结果隔离

已确认规则：

- 某条进度事件未知、字段变化或无法标准化时，仅记录运行诊断告警。
- 事件观测失败不得写入 `rich_content_issues`，不得改变有效的 PRD 内容或 Completion Assessment。
- 只要最终分析载荷有效，进度事件观测失败不阻止正式产物生成。
- 最终载荷缺失、不可解析或调用超时，继续沿用相应分析失败策略。

## 7. 超时语义

### 7.1 总超时

`--agent-timeout` 保持现有含义：整个 Agent 调用的绝对上限。进度事件不会延长该上限。

### 7.2 空闲超时

新增参数：

```bash
--agent-idle-timeout 300
```

已确认规则：

- 默认值为 `300` 秒。
- 仅在指定 `--agent-progress` 时生效。
- 未指定 `--agent-progress` 时，即使用户显式传入 `--agent-idle-timeout` 也忽略该值且不报错。
- 空闲超时用于检测流式 Agent 在连续一段时间内未产生可用于确认活动的结构化事件。
- 空闲超时触发后应返回独立于总超时的错误类型，并提示用户重试。
- 已产生的安全工具事件和工具统计仍保留在运行日志与 Debug Bundle 中。

## 8. 待确认事项

- 哪些结构化 Agent 事件可以重置 `--agent-idle-timeout`：仅可展示工具状态，还是所有经过识别但不展示内容的活动事件。
- 空闲超时错误的稳定名称、重试命令是否自动附带调整后的空闲阈值。
- 批量条目分析中某一条目触发空闲超时时，其余条目是否继续执行。
- 启用进度流时，Debug Bundle 是否保存无法标准化事件的类型摘要，以及摘要的脱敏格式。

