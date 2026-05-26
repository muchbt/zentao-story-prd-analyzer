# zentao-story-prd-analyzer Skill 说明

`zentao-story-prd-analyzer` 用于从禅道获取需求或缺陷条目，并让具备仓库搜索能力的 Agent CLI 分析目标代码仓库，生成 PRD/ISSUE 文档、summary report 和 debug bundle。

## 支持的 Agent CLI

| Agent | 调用方式 |
| --- | --- |
| `claude` | 本机 `claude` CLI |
| `codex` | 本机 `codex exec` |
| `opencode` | 本机 `opencode run` |

直接运行 `main.py` 且未显式指定 `--agent` 时，默认检测顺序为 `claude`、`codex`、`opencode`。通过 `SKILL.md` 触发时应显式传入与宿主 CLI 一致的 `--agent`。

## 输入线索

| 类型 | 参数 | 说明 |
| --- | --- | --- |
| Search Hint | `--clues` / clues file 的 `clues` | 写入 prompt，指导 Agent 搜索 |
| Seed Path | `--paths` / clues file 的 `paths` | 预加载到 prompt 的仓库内文件 |

Seed Path 只接受 `repo_path` 内的文件，不接受目录。目录、模块名、函数名和符号名应作为 Search Hint 提供。

## Clues File 示例

```json
{
  "5939": {
    "clues": ["callback", "CallBackMode", "src/ecall"],
    "paths": ["src/ecall/xcall.c"]
  }
}
```

## 输出内容

- `docs/prd/` 或 `docs/issue/` 下的 PRD/ISSUE Markdown 文档。
- `docs/summary_report.json`。
- debug bundle，包含 prompt、response、seed locations、cited evidence locations、evidence validation issues 和 rejected seed paths。

## 安全边界

Agent CLI 子进程只应读取和搜索目标仓库，并把结构化 JSON 分析结果返回给 analyzer。它不得修改、创建或删除目标仓库源码、配置、测试、构建文件，也不得直接写 debug bundle、PRD/ISSUE 文档、summary、显式 `--output` 或显式 `--log-file`；这些输出只能由 analyzer 进程写入。

## 正式分析模式与交互预分析模式

当前已实现的是由 `SKILL.md` 调用 Python analyzer 的**正式分析模式**。仅依靠 `SKILL.md` 让宿主 Agent 直接获取条目、搜索代码和作答的方式，可作为未来讨论的**交互预分析模式**；该模式目前未实现，也不作为正式分析模式的等价替代。

### 能力差异

| 能力 | 正式分析模式（当前已实现） | 交互预分析模式（拟议） |
| --- | --- | --- |
| 调用链路 | Skill 调用 analyzer CLI，analyzer 调用 Agent 搜索代码 | 宿主 Agent 按 Skill 指引直接执行查询、搜索和答复 |
| 使用目标 | 正式评审、交付归档、批量处理、自动化消费 | 快速问答、初步定位、探索性判断 |
| 禅道条目获取 | analyzer 统一调用并结构化解析 | 依赖宿主 Agent 临时调用工具或用户提供内容 |
| 分析输出 | 结构化 `Analysis Result`，由 analyzer 渲染正式文档 | 会话中的自然语言答复或临时分析草稿 |
| PRD/ISSUE 文档 | 固定模板生成的正式输出 | 不承诺生成正式 PRD/ISSUE |
| `summary_report.json` | 提供机器可读索引 | 不提供固定索引 |
| Debug Bundle | 保存脱敏输入、prompt、response、日志与证据位置 | 默认不提供 |
| 代码证据校验 | 本地验证文件路径与行号，并影响结论和可信度 | 依赖宿主 Agent 自查，不形成程序保证 |
| 证据不足处理 | 程序按规则降级为无法可靠判断 | 依赖提示词和 Agent 表述 |
| 脱敏与失败诊断 | analyzer 统一处理，并输出结构化错误状态 | 依赖宿主环境能力和人工判断 |
| 批量分析 | 支持条目级状态、汇总索引与失败条目重试提示 | 不适合作为稳定批量流程 |
| 一致性与测试 | 文档、JSON 契约和行为可由自动测试验证 | 输出易随 Agent 和会话上下文变化 |
| 写入边界 | 仅 Analyzer Process 写正式产物 | 若允许宿主写文件，将改变现有安全边界 |

### 交互预分析模式可提供的能力

交互预分析模式可以用于单条条目的快速沟通：

1. 获取单个需求或缺陷的文字内容，或接受用户提供的上下文。
2. 在当前代码仓库中搜索可能相关的文件、符号和逻辑。
3. 给出初步实现判断、可能缺口、待确认点和少量代码引用。
4. 根据用户要求在会话中整理一份分析草稿。
5. 工具或读取失败时，直接向用户说明限制。

其结果应理解为交互式答复或分析草稿，不应标记为正式 `PRD Document`、`ISSUE Document` 或可供机器消费的正式 `Analysis Result`。

### 正式分析模式的收益

正式分析模式的价值在于将 Agent 判断纳入可复核的工具流程：

| 收益 | 说明 |
| --- | --- |
| 稳定输出契约 | 调用方可读取 `analysis`、`documents`、`summary_report` 与 `debug_bundle` 等固定结构 |
| 证据约束结论 | 无有效代码证据时可强制降低可信度或结论，避免仅凭描述宣告实现完成 |
| 可追溯性 | 可复核输入、模型响应、代码引用位置和文档生成结果 |
| 失败可诊断 | Agent 结构化响应失败等问题可被记录为诊断结果，而非伪装成正常分析 |
| 安全边界清晰 | Agent 子进程只读，输出写入和脱敏集中由 analyzer 控制 |
| 批量处理能力 | 多条条目可以统一生成结果，并针对失败条目单独处理 |
| 跨后端一致性 | Claude、Codex 或 OpenCode 的响应最终落入相同文档与 JSON 契约 |
| 可验证演进 | 规则和输出变更能够以自动测试覆盖，降低回归风险 |

正式分析模式的成本是需要 Python 运行环境、CLI 分发包和测试维护；交互预分析模式的优势是启动更轻、对话更直接，但不能提供相同的审计、批量与确定性保证。
