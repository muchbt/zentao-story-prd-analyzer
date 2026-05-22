# Agent 自主搜索架构改造计划

## 1. 背景

两次 demo 分析（requirement 5930 和 5923）暴露出旧 `code_collector` 关键词搜索质量不可接受：

| 维度 | code_collector 收集 | Agent 自主引用 |
|------|---------------------|----------------|
| 文件数 | 5 | 6 |
| 相关率 | 0% | 100% |
| 与 Agent 引用重叠 | 0 个文件 | - |
| token 消耗 | 约 8310 tokens，均为噪声 | Agent 自行搜索 |

旧流程从禅道标题和描述中提取 `call`、`service`、`EA`、`x`、`callback` 等自然语言关键词，再用 grep 类搜索把匹配文件塞入 prompt。实际效果是匹配大量第三方头文件、构建文件和通用代码，而 Agent 真正需要的是 `CallBackMode`、`xcall_is_need_enter_callback`、`xcall_report_callback_status` 等精确代码标识符。

根本问题是：**自然语言关键词和代码标识符不在同一搜索空间**。本地 L1 关键词提取无法稳定完成 NL 到 Code 的映射，而具备仓库搜索能力的 Agent CLI 可以直接在目标仓库中迭代搜索、阅读和交叉验证。

架构决策已记录在 [ADR 0003](./adr/0003-agent-cli-performs-repository-search.md)。

## 2. 目标架构

旧架构：

```text
禅道关键词提取 -> code_collector grep -> 大段代码上下文 -> 单轮 LLM
```

新架构：

```text
Zentao Item + Target Repository + 可选 Search Hint + 可选 Seed Path
  -> Agent CLI 自主搜索仓库
  -> 本地校验 evidence path/line
  -> PRD/ISSUE + summary + debug bundle
```

核心术语以 `CONTEXT.md` 为准：

- **Search Hint**：写入 prompt 的搜索建议，不触发本工具读取源码，不是证据。
- **Seed Path**：用户明确指定的仓库内文件，作为起始上下文读入 prompt。
- **Seed Location**：从 Seed Path 加载进 prompt 的文件和行号范围。
- **Rejected Clue**：被拒绝的 Seed Path，例如越界、不是文件或不存在。
- **Code Evidence**：Agent 输出并通过本地校验的代码证据位置。

## 3. 已确认设计决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 本地关键词 collector | 删除，不再作为分析入口 |
| 2 | Search Hint | 仅写入 prompt，指导 Agent 搜索 |
| 3 | Seed Path | 只接受仓库内文件，不接受目录 |
| 4 | 无 Seed Path | 仍继续调用 Agent 分析 |
| 5 | Evidence 校验 | 本地校验 path 存在、repo 边界和行号范围 |
| 6 | `codex` 后端 | 表示 Codex CLI，不再表示 OpenAI SDK |
| 7 | OpenAI SDK 后端 | 移除 |
| 8 | 默认 agent | Skill 触发时跟宿主 CLI 一致；直接 `main.py` 时按 `claude -> codex -> opencode` 自动检测 |
| 9 | agent 命令配置 | 拆成 `--claude-command`、`--codex-command`、`--opencode-command` |
| 10 | model 参数 | 用户显式指定时才传；`claude --model`、`codex -m`、`opencode --model` |
| 11 | dangerous 权限 | 不默认启用 broad bypass；Agent CLI 子进程必须只读/只搜索 |
| 12 | 写入边界 | Agent CLI 子进程不得写任何文件；只有 analyzer 进程写生成输出 |
| 13 | 允许写入 | analyzer 进程写 debug bundle、PRD/ISSUE 文档、summary、显式 `--output`、显式 `--log-file` |
| 14 | 旧 CLI 参数 | 开发阶段直接移除 `--keywords`、`--symbols`、`--incremental`、`--last-commit` |
| 15 | `ZentaoItem.keywords` | 完整移除，不保留空字段 |
| 16 | 旧 clues file 格式 | 直接移除 `keywords`/`symbols` 字段，使用 `clues`/`paths` |
| 17 | debug/summary 字段 | 改为 `seed_locations`、`seed_location_count` |
| 18 | collector 命名 | `code_collector.py` 改为 `seed_loader.py`，公开 `load_seed_context()` |

## 4. 数据结构改造

### 4.1 `zentao_client.py`

删除自动关键词提取：

- 删除 `_STOP_WORDS`
- 删除 `_TITLE_WEIGHT`
- 删除 `Counter top 20` 提取逻辑
- 从 `ZentaoItem` 完整移除 `keywords` 字段
- 从 `from_dict()` 完整移除 `keywords` 构造

同步删除所有公开输出中的 `keywords`：

- `main.py` 的 `base_result.items[]`
- debug bundle 的 `items.json`
- scan/config 类调试数据
- README/SKILL/SKILL.yaml/docs 中的参数说明
- 相关测试断言

### 4.2 `code_clues.py`

重写为 Search Hint / Seed Path 解析模块。

保留：

- `parse_csv_values()`
- clues file 加载能力

新增或替换：

```python
@dataclasses.dataclass
class RejectedSeedPath:
    value: str
    source: str
    item_id: str = ""
    reason: str = ""


def load_clues_file(path: str) -> Dict[str, Dict[str, List[str]]]:
    ...


def build_search_hints(item_id: str, cli_clues=None, clues_by_item=None) -> List[str]:
    ...


def build_seed_paths(item_id: str, repo_path: str, cli_paths=None, clues_by_item=None) -> Tuple[List[str], List[RejectedSeedPath]]:
    ...
```

`--clues-file` 新格式：

```json
{
  "5930": {
    "clues": ["callback", "ecall", "xcall_is_need_enter_callback"],
    "paths": ["src/ecall/xcall.c"]
  }
}
```

解析规则：

- `clues` 只生成 Search Hint，不做仓库边界校验。
- `paths` 只生成 Seed Path。
- Seed Path 必须在 repo 内、必须存在、必须是文件。
- 目录型路径拒绝，reason 使用 `not_file`。
- 越界路径拒绝，reason 使用 `outside_repo`。
- 不存在路径拒绝，reason 使用 `not_found`。
- 旧字段 `keywords` / `symbols` 不再识别。

### 4.3 `seed_loader.py`

用 `seed_loader.py` 替代 `code_collector.py`。

删除：

- `_find_executable()`
- `_rg_search()`
- `_git_grep_search()`
- `_os_walk_search()`
- `_search_files_by_text()`
- `_iter_allowed_files()`
- `_normalize_modified_files()`
- `collect()`
- `collect_with_clues()`
- `ALLOWED_EXTS`
- `BUILD_FILES`
- 旧 `CollectionResult`
- 旧 `CodeLocation`

新增：

```python
@dataclasses.dataclass
class SeedLocation:
    path: str
    line_start: int
    line_end: int
    source: str = "seed"


@dataclasses.dataclass
class SeedLoadResult:
    snippets: List[Dict[str, Any]]
    seed_locations: List[SeedLocation]
    rejected_seed_paths: List[RejectedSeedPath]


def load_seed_context(
    seed_paths: List[str],
    rejected_seed_paths: Optional[List[RejectedSeedPath]] = None,
    max_seed_files: int = 3,
    max_lines_per_seed: int = 50,
    max_seed_tokens: int = 2000,
    max_seed_tokens_limit: int = 8000,
) -> SeedLoadResult:
    ...
```

加载规则：

- 按传入顺序加载，最多 3 个文件。
- 每个文件最多 50 行。
- 总 seed 上下文默认估算最多 2000 tokens。
- 总 seed 上下文硬上限为 8000 tokens；用户配置超过该值时按 8000 tokens 截断。
- 不递归目录。
- 不按扩展名过滤。
- 读取失败不抛未处理异常，记录为 rejected seed path。

## 5. Agent 客户端改造

### 5.1 `agent_client.py`

删除 OpenAI SDK 后端：

- 删除 `import openai`
- 删除 `_call_openai()`
- 删除 `agent in ("openai", "codex")` 分支
- 未识别 `openai` 时返回 config error

新增 Codex CLI 后端：

```python
def _call_codex(self, prompt: str) -> AgentResult:
    command = self.config.command or "codex"
    args = [command, "exec", "-C", self.config.cwd or "."]
    args.extend(self.config.extra_args or [])
    if self.config.model:
        args.extend(["-m", self.config.model])
    ...
```

权限策略：

- 不默认启用 broad bypass 权限。
- Claude 默认使用只读工具白名单。
- Codex 默认使用 read-only sandbox。
- OpenCode 不默认启用 `--dangerously-skip-permissions`。
- Prompt/README/SKILL 必须声明 Agent CLI 子进程只读，只有 analyzer 进程可以写生成输出。

模型传递：

- Claude CLI：`--model <model>`
- Codex CLI：`-m <model>`
- OpenCode：`--model <model>`
- 未显式指定 `--model` 时不传模型参数，不读取 `OPENAI_MODEL`。

输出解析：

- `extract_json_object()` 保留。
- `_parse_text()` 保留。
- Codex CLI 的 stdout/stderr 行为必须先用真实命令验证。

### 5.2 `app_config.py`

默认 agent 策略：

- 如果用户显式传 `--agent`，使用用户指定值。
- 如果通过 Skill 触发，Skill 应按宿主 CLI 显式传 `--agent`。
- 直接运行 `main.py` 且未指定 `--agent` 时，检测顺序为：
  1. `claude`
  2. `codex`
  3. `opencode`
- 三者都不存在时返回 config error，提示显式指定 `--agent` 或安装对应 CLI。

配置字段：

- 新增 `codex_command`
- 新增 `opencode_command`
- 保留 `claude_command`
- `agent_config_dict()` 根据最终 `agent` 选择对应 command。
- 删除 `OPENAI_MODEL`、`OPENAI_API_KEY`、`OPENAI_BASE_URL` 相关配置读取。

### 5.3 `llm_client.py`

保留 `call_llm()` 作为薄包装：

- 只调用 `AgentClient.call()`
- 不含 OpenAI SDK 分支

## 6. Prompt 和分析流程改造

### 6.1 `prompts.py`

新 prompt 必须包含：

```text
【禅道条目】
ID/标题/描述/类型/状态

【代码仓库】
路径: {repo_path}

【种子上下文】（仅当存在 Seed Path）
--- 文件: xxx.c (行 1-50) ---
...

【搜索建议】（仅当存在 Search Hint）
callback, ecall, xcall_is_need_enter_callback

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 你是 Agent CLI 子进程，只能返回 JSON 分析结果，不能写入任何文件。
- 只有 analyzer 进程可以写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
- 主动搜索代码仓库，查找与条目相关的代码实现。
- 从需求描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
- 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
- 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
- evidence 必须引用仓库中实际存在的文件和行号。
- 如果证据不足，设置低置信并说明证据不足。
```

接口变更：

```python
def build_feature_prompt(item, repo_path, seed_snippets=None, search_hints=None) -> str:
    ...


def build_defect_prompt(item, repo_path, seed_snippets=None, search_hints=None) -> str:
    ...
```

### 6.2 `analyzer.py`

新签名：

```python
def analyze(
    item,
    repo_path,
    agent,
    agent_config,
    seed_paths=None,
    search_hints=None,
    rejected_seed_paths=None,
    max_seed_files=3,
    max_lines_per_seed=50,
    max_seed_tokens=2000,
    debug_recorder=None,
) -> AnalysisResult:
    ...
```

流程：

```text
校验 repo_path
-> load_seed_context(seed_paths)
-> build prompt(repo_path, seed snippets, search hints)
-> call_llm()
-> AnalysisResult.from_llm_json()
-> validate_evidence_locations()
-> 返回 AnalysisResult + SeedLoadResult 元数据
```

关键要求：

- 没有 seed snippets 时不得提前返回“未找到相关代码证据”。
- 只有 `repo_path` 不存在、不可访问，或 agent 配置错误时才提前失败。
- `debug_recorder` 继续记录 prompt/response。
- 需要让 `main.py` 能拿到 `seed_locations` 和 `rejected_seed_paths`，可通过返回附加 metadata 或回调完成。

### 6.3 Evidence 本地校验

新增校验函数：

```python
def validate_evidence_locations(repo_path: str, result: AnalysisResult) -> List[EvidenceValidationIssue]:
    ...
```

校验规则：

- `path` 必须存在。
- `path` 必须在 repo 内。
- `line_start` 和 `line_end` 必须为正整数。
- `line_start <= line_end`。
- `line_end` 不得超过文件总行数。
- 不默认读取或写入完整源码内容，只做边界校验。

处理策略：

- 无效 evidence 不静默接受。
- 若关键 evidence 均无效，将 `confidence` 降为低。
- 在 Analysis Result 中追加验证失败说明，或记录到 debug bundle。
- debug bundle 记录 evidence validation issues，便于审计。

## 7. CLI 入口改造

### 7.1 参数变更

删除：

- `--keywords`
- `--symbols`
- `--incremental`
- `--last-commit`

新增：

- `--clues`：逗号分隔 Search Hint
- `--codex-command`
- `--opencode-command`

保留并改义：

- `--paths`：逗号分隔 Seed Path，只接受 repo 内文件，不接受目录
- `--clues-file`：只识别新格式 `clues`/`paths`
- `--model`：用户显式指定时传给所选 Agent CLI

### 7.2 `main.py` 流程

删除：

- `get_modified_files()`
- `modified_files` 相关逻辑
- `build_item_clues()` 调用
- `collection_recorder`
- `collection_by_item`
- `rejected_clues_by_item`
- `all_rejected_clues`
- `keywords` 输出字段

新增：

- 加载 clues file 新格式
- 为每个 item 构造 Search Hint
- 为每个 item 构造 Seed Path 与 rejected seed path
- 调用 `analyze(..., seed_paths=..., search_hints=...)`
- 汇总 `seed_locations`
- 汇总 `rejected_seed_paths`
- 汇总 evidence validation issues

debug bundle 输出字段：

```json
{
  "items": [
    {
      "item_id": "5930",
      "seed_locations": [],
      "cited_evidence_locations": [],
      "evidence_validation_issues": []
    }
  ]
}
```

summary item 字段：

- `seed_location_count`
- `cited_evidence_location_count`
- `rejected_seed_path_count`
- 移除 `collected_location_count`
- 移除 `rejected_clue_count`

## 8. Debug Bundle 和 Summary 改造

### 8.1 `debug_bundle.py`

调整：

- `_item_to_dict()` 移除 `keywords`
- `write_code_evidence_locations()` 输出 `seed_locations`
- `write_rejected_clues()` 改为 `write_rejected_seed_paths()`
- 可新增 `write_evidence_validation_issues()`

保留：

- 默认不写完整源码内容
- `--debug-include-code` 仍控制代码上下文快照
- prompt/response/config/items/documents/summary path 继续记录

### 8.2 `summary_report.py`

调整 `build_summary_item()` 参数和字段：

- `collected_location_count` -> `seed_location_count`
- `rejected_clue_count` -> `rejected_seed_path_count`
- 保留 `cited_evidence_location_count`
- 可新增 `invalid_evidence_count`

## 9. 文档更新

### 9.1 README.md

必须同步说明：

- 新架构由 Agent CLI 自主搜索仓库。
- `codex` 表示 Codex CLI，不是 OpenAI SDK。
- 移除 OpenAI SDK 配置说明。
- 默认 agent：直接 `main.py` 时 `claude -> codex -> opencode`。
- Skill 触发时 `--agent` 应与宿主 CLI 一致。
- `--clues` 是 Search Hint。
- `--paths` 是 Seed Path，只接受仓库内文件，不接受目录。
- `--clues-file` 新格式为 `clues`/`paths`。
- 删除 `--keywords`、`--symbols`、`--incremental`、`--last-commit`。
- Agent CLI 子进程只读/只搜索，不得写任何文件。
- analyzer 进程负责写 debug bundle、PRD/ISSUE、summary、显式 `--output`、显式 `--log-file`。

### 9.2 SKILL.md

必须同步说明：

- Skill 触发时 `--agent` 与宿主 CLI 一致。
- Claude Code 使用 `--agent claude`。
- Codex 使用 `--agent codex`。
- OpenCode 使用 `--agent opencode`。
- 不再提 OpenAI SDK / `OPENAI_API_KEY`。
- 不再使用 `--keywords` / `--symbols`。
- `--paths` 只能传文件。
- 不允许 Agent 修改目标仓库代码。

### 9.3 SKILL.yaml / docs/skill-overview.md / docs/TOKEN_COST.md

同步移除旧输入和旧后端说明：

- `keywords`
- `symbols`
- OpenAI SDK 后端
- 自动关键词提取
- 旧 token 消耗模型中的 collector 说明

## 10. 测试更新

| 测试文件 | 变更 |
|----------|------|
| `test_zentao_client.py` | 删除 `keywords` 字段断言 |
| `test_code_clues.py` | 改测 Search Hint、Seed Path、RejectedSeedPath、clues file 新格式 |
| `test_code_collector.py` | 删除或重命名为 `test_seed_loader.py`，测试 seed 文件加载限制 |
| `test_prompts.py` | 验证 repo_path、seed context、search hints、写入边界、主动搜索要求 |
| `test_analyzer.py` | 验证无 seed 仍调用 Agent，验证 evidence 校验 |
| `test_agent_client.py` | 删除 OpenAI 测试，新增 Codex CLI、model 参数、command 参数测试 |
| `test_llm_client.py` | 删除 OpenAI fallback 测试 |
| `test_app_config.py` | 测试默认 agent 检测顺序和 agent 专属 command |
| `test_main_phase*.py` | 更新 CLI 参数、summary/debug 字段、移除 keywords/incremental |
| `test_debug_bundle.py` | 移除 collected/rejected clue 字段，新增 seed/evidence validation 字段 |
| `test_summary_report.py` | 更新 seed/rejected seed path 计数字段 |

建议验证命令：

```bash
python3 -m unittest
```

Codex CLI 行为需单独手工验证：

```bash
printf '%s\n' '{"conclusion":"无法判断","evidence":[],"recommendations":[],"verification":[],"confidence":"低"}' \
  | codex exec -C . -
```

实际命令格式以本地 Codex CLI `--help` 输出为准。

## 11. dist 同步

实现完成并测试通过后运行：

```bash
./sync_dist.sh <version>
```

同步范围必须包含：

- `main.py`
- `README.md`
- `SKILL.md`
- `zentao_analyzer/`
- 新增或重命名后的 `seed_loader.py`

## 12. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Agent CLI 输出格式不稳定 | 先验证 Claude/Codex/OpenCode stdout/stderr，再写解析测试 |
| Agent CLI 写入面扩大 | 默认只读/只搜索；Claude 使用只读工具，Codex 使用 read-only sandbox，OpenCode 不默认跳过权限 |
| Agent 编造 evidence | 本地校验 path 和行号，校验失败降低置信并记录 debug |
| 无 seed 时搜索耗时增加 | 保持 900s 默认超时，允许 Search Hint 缩小搜索方向 |
| `--paths` 不再支持目录 | README/SKILL 明确目录应放入 `--clues` 作为 Search Hint |
| 直接移除旧参数影响开发使用者 | 当前仍处开发阶段，按不留包袱处理 |
| OpenAI SDK 后端移除 | 文档说明必须使用具备仓库搜索能力的 Agent CLI |

## 13. 待验证项

- [ ] Codex CLI `exec` 的实际 stdin/stdout/stderr 行为。
- [ ] Codex CLI `-m` 参数是否与当前版本一致。
- [ ] OpenCode `--model` 参数实际行为。
- [x] Agent CLI 子进程只读边界是否足够清晰，并由命令级默认约束支撑。
- [ ] Seed context 默认限制：3 文件、50 行、2000 tokens 是否适合 demo 仓库。
- [ ] Seed context 8000 tokens 硬上限是否足以覆盖用户显式指定的大文件入口。
- [ ] 本地 evidence 校验失败时的用户可见表达是否清晰。
