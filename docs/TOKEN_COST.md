# Token 消耗模型

## 概述

当前架构不再使用本地关键词 collector 预搜代码。分析阶段由 Agent CLI 在目标仓库中自主搜索，工具只把禅道条目、仓库路径、可选 Search Hint 和可选 Seed Path 片段放入 prompt。

token 估算按 4 字符 ≈ 1 token。

## 当前流程：Agent CLI 自主搜索

```text
禅道条目 + Target Repository(Set)
        │
        ├─ 可选 Search Hint（仅作为 prompt 搜索建议）
        ├─ 可选 Seed Path（读取仓库内文件作为起始上下文）
        ├─ 可选 Protocol Hint（跨仓库通信协议线索）
        ▼
  Agent CLI 自主搜索仓库（Read / Grep / Glob）
        │
        ├─ 搜索轮次消耗额外 token（工具调用、搜索结果、模型推理）
        ▼
  本地校验 evidence path / line
        ▼
  生成 PRD/ISSUE、summary、debug bundle
```

## Token 构成 — 初始 Prompt

### Feature Item（story / requirement）

| 组成部分 | 字符数 | 估算 token | 说明 |
|---------|-------|-----------|------|
| Prompt 模板（固定） | ~3935 | ~984 | `_FEATURE_TEMPLATE`，含内联 JSON Schema、权限边界、约束规则 |
| Claude System Prompt | ~154 | ~39 | `CLAUDE_SYSTEM_PROMPT`，追加为 `--append-system-prompt` |
| 禅道条目 | — | 200–800 | 取决于标题和描述长度 |
| Search Hint | — | 0–300 | `--clues` 或 clues file 提供 |
| Seed Context | — | 0–2000（默认），8000（硬上限） | 从 `--paths` 预加载的仓库文件片段 |
| Protocol Hint | — | 0–100 | `--protocol-hint` 提供 |
| Repository Context | — | 30–200 | 单仓约一行路径；多仓每增加一个 role 约增加一行 |
| **单次初始 prompt 合计** | — | **~1250–4500（典型）** | 不包含 Agent CLI 后续自主搜索消耗 |

### Defect Item（bug / task / ticket / feedback）

| 组成部分 | 字符数 | 估算 token | 说明 |
|---------|-------|-----------|------|
| Prompt 模板（固定） | ~1119 | ~280 | `_DEFECT_TEMPLATE`，模板较短（无需求解读和完成度评估章节） |
| Claude System Prompt | ~154 | ~39 | 同上 |
| 禅道条目 | — | 200–800 | 同上 |
| Search Hint | — | 0–300 | 同上 |
| Seed Context | — | 0–2000（默认），8000（硬上限） | 同上 |
| Protocol Hint | — | 0–100 | 同上 |
| Repository Context | — | 30–200 | 同上 |
| **单次初始 prompt 合计** | — | **~550–3700（典型）** | 模板明显小于 Feature 模式 |

## Token 构成 — Agent 搜索轮次

Agent CLI 子进程在收到初始 prompt 后，会自主进行多轮工具调用（Read / Grep / Glob），每轮额外消耗：

| 消耗来源 | 估算 | 说明 |
|---------|------|------|
| 工具调用参数 | 20–80 token/次 | Grep 关键词、Glob 模式、Read 路径 |
| 工具返回结果 | 可变 | 搜索结果行数决定；大文件 Read 可能消耗数千 token |
| 模型推理 | 可变 | 取决于搜索复杂度；通常每轮 200–800 token |
| 典型搜索轮次 | 3–10 轮 | 简单需求可能 2–3 轮，复杂需求可能 10+ 轮 |

**Agent 搜索总消耗高度可变**（数百到数万 token），取决于需求复杂度和仓库规模。目前工具不限制 Agent 搜索轮次，仅通过 `--agent-timeout`（默认 900s）间接约束。

## Claude JSON 信封开销

`claude` 后端使用 `--output-format json`，响应外层包裹 JSON 信封：

```json
{
  "type": "result",
  "result": "<Agent 实际回答文本>",
  "is_error": false
}
```

信封字段约 50–80 字符（~20 token），可忽略。信封使工具调用/思维过程与最终回答分离，避免思维文本污染结构化解析。

## 种子上下文参数

所有参数硬编码于 `zentao_analyzer/seed_loader.py`，不作为命令行参数暴露：

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `max_seed_files` | 3 | 最多预加载 3 个 Seed Path 文件 |
| `max_lines_per_seed` | 50 | 每个 Seed Path 最多 50 行 |
| `max_seed_tokens` | 2000 | 默认 Seed Context token 预算（共享池，非每文件） |
| `max_seed_tokens_limit` | 8000 | Seed Context 硬上限（`max_seed_tokens` 的夹紧上界） |
| `TOKEN_ESTIMATE_RATIO` | 4 chars/token | 字符到 token 的估算比例 |

### 预算消耗顺序

种子文件按传入顺序依次加载，共享同一个 token 预算池：

1. 取前 `max_seed_files` 个路径。
2. 每个文件取前 `max_lines_per_seed` 行。
3. 以 `len(content) // 4` 估算 token 数。
4. 若估算值超出剩余预算，截断至 `剩余预算 × 4` 字符。
5. 从预算池中扣除，预算耗尽则停止加载。
6. 任何截断发生后，末尾追加 `[种子上下文已截断，仅展示部分内容]`。

## 多仓库影响

多仓库模式（`--repo soc=... --repo mcu=...`）对 token 的影响：

| 因素 | 影响 |
|------|------|
| Repository Context 增长 | 每个额外 role 增加约一行路径描述（~30–60 字符/role） |
| Protocol Hint | 每条增加约一行描述（~40–80 字符） |
| Agent 搜索范围扩大 | 多仓通常导致更多搜索轮次和工具调用 |
| JSON Schema 要求 | evidence 和 related_locations 需额外 `role` 字段（每条约 +40 字符） |

多仓模式的 token 增量主要来自 Agent 搜索行为，而非初始 prompt 大小。

## Agent 工具限制

Claude 后端通过 `--tools Read,Grep,Glob` 限制为只读工具。这些工具名称本身也计入 token：

- 工具声明约 200–400 字符（~50–100 token），由 Claude CLI 自动追加到 system prompt
- Codex 后端通过 `--sandbox read-only` 限制；OpenCode 后端使用默认权限

## 更新记录

| 版本 | 日期 | 方案 | 说明 |
|------|------|------|------|
| v3 | 2026-06-02 | 精确模板测量 + 搜索轮次 | 实测模板字符数，区分 Feature/Defect 模式，补充搜索轮次消耗和 Claude 信封说明 |
| v2 | 2026-05-22 | Agent CLI 自主搜索 | 移除关键词 collector，使用 Search Hint 与 Seed Path |
| v1 | 2026-05-22 | 关键词预搜集 | 已废弃 |
