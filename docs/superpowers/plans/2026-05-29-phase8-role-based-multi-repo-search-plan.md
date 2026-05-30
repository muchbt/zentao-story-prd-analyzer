# 阶段八：基于 Repository Role 的多 Repo 搜索执行计划

> **实施依据**：`CONTEXT.md` 中的 Target Repository Set / Protocol Hint 术语，以及 `docs/adr/0005-support-role-based-multi-repository-analysis.md`。

**Goal:** 将 analyzer 从单一 `Target Repository` 扩展为可分析 `Target Repository Set`，支持用户通过 Repository Role 描述多代码架构，并通过 Protocol Hint 引导 Agent 沿 MCU/SoC 等通信协议线索搜索跨仓库证据。

**Architecture:** 保持 Analyzer Process 唯一写入边界和 Agent CLI Subprocess 只读边界。新增仓库集合、结构化线索、协议线索和 role workspace 作为分析输入层；扩展 prompt、结果模型、证据校验、文档、summary 和 debug bundle，使多仓分析在同一次 Analysis Result 中完成，而不是拼接多次单仓结果。

**Tech Stack:** Python 3.8+, dataclasses, argparse, json, os/pathlib, tempfile, unittest, unittest.mock

---

## 实施约束

- `--repo` 是新入口；`--repo-path` 保留为单仓兼容入口，两者同时出现时报预处理错误。
- 单仓 `--repo <path>` 或旧 `--repo-path <path>` 内部归一为隐式 `main` role，单仓文档不展示 role 维度。
- 多仓必须全部使用 `--repo <role>=<path>`；多条匿名 repo 或匿名/具名混用均在预处理失败。
- Protocol Hint 是 Search Hint 的子类，只指导搜索，不是 Requirement Source 或 Code Evidence。
- `closed_loop` 只表示协议链路证据闭环，不等同于 Requirement Point 完成。
- 跨 Repository Role 的 Completion Assessment 不能由单侧 Code Evidence 单独确认完成。
- 不自动按 repo 数放大 Agent timeout；用户显式设置 `--agent-timeout`。
- 第一版不引入长期 relationships 架构图；Protocol Hint 的 `roles` 仅表示搜索范围，不表示方向。

---

## File Map

| File | Responsibility | Action |
| --- | --- | --- |
| `zentao_analyzer/repositories.py` | Target Repository Set、Repository Role、role workspace、路径解析 | Create |
| `zentao_analyzer/protocol_hints.py` | Protocol Hint 解析、归一化、校验 | Create |
| `zentao_analyzer/code_clues.py` | Structured Clue File、role-qualified Seed Path、兼容旧格式 | Modify |
| `zentao_analyzer/seed_loader.py` | Seed snippet 输出 role-aware path | Modify |
| `zentao_analyzer/prompts.py` | 多仓 prompt、Protocol Hint、role evidence / protocol trace JSON 合约 | Modify |
| `zentao_analyzer/analysis_result.py` | role-aware evidence、Role Evidence Status、Protocol Trace Status | Modify |
| `zentao_analyzer/analyzer.py` | 多仓分析入口、role workspace cwd、跨仓证据校验 | Modify |
| `zentao_analyzer/app_config.py` | Agent cwd 从 repo_path 迁移到分析准备阶段 | Modify |
| `zentao_analyzer/main.py` | CLI 预处理、仓库集合合并、normalized clues 写入 debug | Modify |
| `zentao_analyzer/document_generator.py` | 多仓证据展示、协议闭环摘要 | Modify |
| `zentao_analyzer/summary_report.py` | role evidence count、protocol trace status count | Modify |
| `zentao_analyzer/debug_bundle.py` | normalized structured clue input / repositories 输出 | Modify |
| `SKILL.md` / `SKILL.yaml` | Skill 输入说明、自然语言转 clues-file 规则、新 `repo` 参数 | Modify |
| `README.md` | CLI、clues-file、Protocol Hint、失败语义说明 | Modify |
| `tests/test_repositories.py` | repo 输入解析、workspace、路径校验 | Create |
| `tests/test_protocol_hints.py` | Protocol Hint flag/file 解析与校验 | Create |
| Existing tests | 单仓兼容、多仓主流程、输出契约回归 | Modify |

---

## Task 1: 建立 Target Repository Set 模型与 CLI 预处理

**Tests first:**

- `--repo /repo/a` 解析为单仓 `main=/repo/a`，`is_single_repo=True`。
- `--repo soc=/repo/soc --repo mcu=/repo/mcu` 解析为两个唯一 Repository Role。
- 多条匿名 `--repo /a --repo /b` 报错。
- `--repo soc=/a --repo /b` 报错。
- role 重复、role 非 `[A-Za-z0-9_-]+`、path 不存在/不可读/非目录均报预处理错误。
- `--repo` 与 `--repo-path` 同时出现报错。
- 未传 `--repo` 时旧 `--repo-path` 和 `REPO_PATH` 行为保持单仓兼容。

**Implementation:**

- 新建 `repositories.py`：
  - `RepositorySpec(role: str, path: str)`
  - `RepositorySet(repositories: List[RepositorySpec], is_single_repo: bool, primary_role: str = "")`
  - `parse_repo_args(repo_values, repo_path, clues_file_repositories, cwd, clues_file_dir) -> RepositorySet`
  - `resolve_repo_relative_path(repo_set, role, value)` 和 `validate_role_name(role)`。
- `main.py` 增加 `parser.add_argument("--repo", action="append")`，保留 `--repo-path`。
- `build_runtime_config()` 暂时继续保留 `repo_path` 字段用于兼容输出，但主流程以 `RepositorySet` 为准。
- 预处理失败在进入 Agent 前返回输入错误码 `4`，错误信息明确指出冲突字段或无效 role/path。

**Verification:**

```bash
python3 -m unittest tests/test_repositories.py tests/test_app_config.py
```

---

## Task 2: 扩展 Structured Clue File 与 Protocol Hint

**Tests first:**

- 旧 clues-file `{ "5939": {"clues": [...], "paths": [...]}}` 仍可用于单仓，paths 归一为 `main`。
- 新 clues-file 支持顶层 `repositories` 和 `items`：

```json
{
  "repositories": {"soc": "../soc", "mcu": "../mcu"},
  "items": {
    "5939": {
      "primary_role": "soc",
      "clues": ["callback mode"],
      "protocol_hints": [
        {"roles": ["soc", "mcu"], "type": "cmd_id", "value": "0x1234"}
      ],
      "paths": {"soc": ["src/send.c"], "mcu": ["src/recv.c"]}
    }
  }
}
```

- clues-file 中相对 repository path 按 clues-file 所在目录解析。
- CLI 中相对 `--repo` path 按当前工作目录解析。
- `repositories` 同时来自 CLI 和 clues-file 且不一致时报错；一致时允许继续。
- clues-file 引用未知 role、非法 Protocol Hint type、空 value、空 roles 数组均报预处理错误。
- `--protocol-hint soc,mcu:cmd_id=0x1234` 解析为 roles `["soc", "mcu"]`、type `cmd_id`、value `0x1234`。
- `--protocol-hint CALLBACK_STATUS` 归一为 type `text`，roles 默认为全部 role。

**Implementation:**

- 新建 `protocol_hints.py`：
  - `ProtocolHint(roles: List[str], type: str, value: str, source: str = "")`
  - 支持类型 `cmd_id|msg|field|text`。
  - flag 语法：`[role1,role2:]type=value` 或 `[role1,role2:]text`。
  - roles 顺序不表达方向，归一时去重并保持用户顺序。
- 扩展 `code_clues.py`：
  - `load_clues_file()` 返回结构化对象，包含 `repositories`、`items`、兼容旧格式。
  - `build_search_hints()` 继续合并 CLI `--clues` 与 item clues。
  - `build_seed_paths()` 改为 role-aware：返回每个 Seed Path 的 role、绝对路径、repo-relative path。
  - `RejectedSeedPath` 增加可选 `role` 字段；旧测试仍可不传 role。
- `main.py` 增加 `--protocol-hint action=append`。

**Verification:**

```bash
python3 -m unittest tests/test_code_clues.py tests/test_protocol_hints.py tests/test_main_phase5.py
```

---

## Task 3: 支持 Role Workspace 与 Agent CWD

**Tests first:**

- 多仓时创建临时 workspace，目录下存在 role 名 symlink，AgentConfig.cwd 指向 workspace。
- workspace 失败或 symlink 不可用时回退到不创建 workspace，AgentConfig.cwd 使用当前工作目录或主 repo，同时 prompt 仍列出每个 role 的绝对 path。
- 单仓时默认不创建 role workspace，保持 Agent cwd 为单仓 repo path。
- role workspace 生命周期覆盖一次 analyze 调用，调用结束后清理临时目录。
- workspace 不复制源码。

**Implementation:**

- `repositories.py` 增加 `RoleWorkspace` context manager：
  - 多仓优先 `tempfile.TemporaryDirectory()` + `os.symlink(repo.path, workspace/role)`。
  - 捕获 symlink 失败，返回 `available=False` 和 fallback repo listing。
- `analyzer.analyze()` 接收 `repo_set`，在多仓时通过 `RoleWorkspace` 包裹 prompt 构建与 Agent 调用。
- `AgentConfig.cwd` 不再由 `RuntimeConfig.repo_path` 一次性固定；`main.py` 在每个 item 调用前根据 `RepositorySet` / workspace 设置传给 AgentConfig。

**Verification:**

```bash
python3 -m unittest tests/test_repositories.py tests/test_analyzer.py tests/test_agent_client.py
```

---

## Task 4: 扩展 Prompt 合约与 Agent 输出 Schema

**Tests first:**

- 单仓 prompt 仍包含原有“代码仓库路径”和 Search Hint 语义，不暴露 `main` role。
- 多仓 prompt 包含 Target Repository Set 表格：role、workspace path、原始 repo path。
- prompt 明确 Protocol Hint 是搜索线索，不是需求来源或证据。
- prompt 要求多仓 evidence 使用 `role + path + line_start + line_end`。
- Feature prompt 要求返回：
  - `role_evidence_statuses`
  - `protocol_traces`
  - role-aware `requirement_points[].evidence`
  - role-aware `code_impact.related_locations`
- Defect prompt 同样支持 role-aware evidence 与 protocol traces，但不引入 Requirement Point。
- prompt 明确跨 role 完成度不能由单侧 evidence 确认。

**Implementation:**

- `prompts.py` 将 `repo_path` 参数扩展为 `repo_context`，保留单仓函数签名兼容包装。
- 增加格式化 helper：
  - `_format_repository_set(repo_set, workspace)`
  - `_format_protocol_hints(protocol_hints)`
  - `_format_role_aware_seed_context(snippets)`
- JSON Schema 中 evidence 允许 `role` 字段；多仓时要求必填，单仓兼容无 role。
- Protocol Trace Schema：

```json
{
  "protocol_traces": [
    {
      "hint": {"roles": ["soc", "mcu"], "type": "cmd_id", "value": "0x1234"},
      "status": "closed_loop|partial|not_found|ambiguous",
      "role_statuses": [
        {"role": "soc", "status": "found|not_found|ambiguous", "searched_for": ["0x1234"], "explanation": "..."}
      ],
      "evidence": [
        {"role": "soc", "path": "src/send.c", "line_start": 10, "line_end": 20, "symbol": "send_cmd", "reason": "..."}
      ],
      "explanation": "协议关联说明"
    }
  ]
}
```

**Verification:**

```bash
python3 -m unittest tests/test_prompts.py
```

---

## Task 5: 扩展 Analysis Result 与跨仓证据校验

**Tests first:**

- 多仓 evidence 缺 role 时校验失败并降低相关 RP 为无法判断。
- evidence role 未知、path 越界、文件不存在、目录、行号非法、行号越界均生成 validation issue。
- 单仓旧 evidence `{path, line_start, line_end}` 继续按 `main` 校验。
- `closed_loop` 必须每个 scoped role 至少有一条有效证据；缺任一 role 时纠正为 `partial` 或记录 validation issue。
- Protocol Trace Status 不直接改变 Requirement Point 状态；RP 状态仍由 RP evidence 和业务判断决定。
- role evidence status 可表达 `found|not_found|ambiguous|not_searched`，但不等同 Completion Assessment。

**Implementation:**

- `analysis_result.py`：
  - `EvidenceLocation` 增加可选 `role` 字段。
  - `CodeImpactLocation` 增加可选 `role` 字段。
  - 新增 `RoleEvidenceStatus`、`ProtocolTrace` dataclass。
  - `AnalysisResult` 增加 `role_evidence_statuses`、`protocol_traces`。
  - evidence 文本格式兼容 `role:path:start-end`。
- `analyzer.py`：
  - `validate_evidence_locations(repo_set, result)` 以 role 选择 repo root。
  - `validate_code_impact_locations(repo_set, locations)` 同步 role-aware。
  - `validate_protocol_traces(repo_set, protocol_traces)` 校验 trace evidence 并纠正不满足最低标准的 closed_loop。
  - 单仓兼容包装继续接受 `repo_path`，内部转换为 `RepositorySet(main)`.

**Verification:**

```bash
python3 -m unittest tests/test_analysis_result.py tests/test_analyzer.py tests/test_main_phase6.py
```

---

## Task 6: 主流程、Debug Bundle 与 Summary Report

**Tests first:**

- `main.py --repo soc=... --repo mcu=... --clues-file clues.json` 将 `RepositorySet`、Protocol Hints、role-qualified Seed Paths 传入 `analyze()`。
- debug bundle 写入 `normalized_clues.json` 和 `repositories.json`，不复制源码内容。
- `scan_summary.json` 从 `repo_path` 扩展为 repositories 摘要。
- summary item 包含：
  - `repositories`: role、path、evidence_count
  - `protocol_trace_status_counts`
- Agent parse failure、timeout retry command 保留 `--repo` / `--clues-file` / `--protocol-hint` 参数。
- 多 item 批量中 item 专属线索错误只影响对应 item；全局 repositories 配置错误阻断整次分析。

**Implementation:**

- `main.py`：
  - 在 fetch items 后、构建 debug bundle 前完成全局 repository/clue 预处理。
  - 每个 item 构建 `NormalizedItemClues`，包含 search hints、protocol hints、seed paths、primary_role。
  - 将 normalized clues 写入 debug bundle。
  - retry command 构造函数支持重复 `--repo`、`--protocol-hint`。
- `debug_bundle.py`：
  - 新增 `write_normalized_clues(data)`、`write_repositories(data)`。
- `summary_report.py`：
  - 统计 role evidence count 和 protocol trace status count。
  - 单仓 summary 可省略 repositories 或只保留 `main`，以兼容现有消费者；建议保留 `repositories` 数组但不改变现有字段。

**Verification:**

```bash
python3 -m unittest tests/test_main_phase5.py tests/test_main_phase7.py tests/test_summary_report.py tests/test_debug_bundle.py
```

---

## Task 7: 文档生成与 Skill 入口

**Tests first:**

- 单仓 PRD/ISSUE 不展示 `main` role 标签，现有文档测试继续通过。
- 多仓 PRD 的统一代码位置表显示 `role:path:line_start-line_end`。
- Requirement Point 表或详情中展示各 role 的证据状态和协议闭环摘要。
- `partial/not_found/ambiguous` trace 在文档中呈现为证据不足或不确定，不写成已完成。
- `SKILL.md` 说明自然语言转 Structured Clue File 的确认边界。
- `SKILL.yaml` 暴露新参数 `repo`、`protocol_hint`，保留 `repo_path` 兼容。

**Implementation:**

- `document_generator.py`：
  - 位置渲染 helper 支持 role-aware path。
  - 多仓时增加“协议线索闭环”摘要小节；单仓时不显示。
  - 证据表保持以 Requirement Point 为主维度，Repository Role 为子维度。
- `SKILL.md`：
  - 更新术语：Target Repository Set、Repository Role、Protocol Hint、Structured Clue File。
  - 指导 Agent CLI Skill 将明确自然语言线索转为临时 clues-file。
  - 猜测 hint type、role 或 item 归属时必须先问用户确认。
- `README.md`：
  - 增加 `--repo`、`--protocol-hint`、新版 clues-file 示例。
  - 标明 `--repo-path` 为兼容入口。

**Verification:**

```bash
python3 -m unittest tests/test_document_generator.py tests/test_main_phase7.py
```

---

## Task 8: 回归、集成与验收

**Full regression:**

```bash
python3 -m unittest discover -s tests -v
```

**Manual smoke:**

```bash
python3 -m zentao_analyzer.main \
  --module requirement \
  --id 5939 \
  --analyze \
  --repo soc=/tmp/soc_repo \
  --repo mcu=/tmp/mcu_repo \
  --protocol-hint soc,mcu:cmd_id=0x1234 \
  --clues "callback status" \
  --agent claude \
  --no-debug-bundle
```

**Acceptance Criteria:**

- 单仓旧命令、旧 clues-file、旧 evidence JSON 继续通过现有测试。
- 多仓命令能在一次分析中生成同一个 PRD/ISSUE、summary report 和 debug bundle。
- 多仓 evidence 全部可由 role + repo-relative path + lines 校验。
- Protocol Hint 未命中或单侧命中时，不会被渲染为完成闭环。
- Agent CLI Subprocess 仍只读；Analyzer Process 仍是唯一写入者。

---

## 建议实施顺序

1. 先完成 Task 1-2，锁定输入模型和兼容规则。
2. 再完成 Task 3-5，打通 Agent 搜索、prompt 和结果校验。
3. 然后完成 Task 6-7，补齐输出、Skill 和用户文档。
4. 最后跑 Task 8 全量回归；若 Agent 实测 prompt 不稳定，只调整 prompt 和解析测试，不放宽证据校验。
