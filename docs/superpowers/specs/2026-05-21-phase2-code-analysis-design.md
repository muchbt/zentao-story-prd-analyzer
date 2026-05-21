# zentao-story-prd-analyzer — 阶段二：代码扫描与 Agent 分析闭环

**日期**: 2026-05-21
**版本**: 1.0
**状态**: 设计完成，待实现

---

## 1. 背景与目标

阶段一已完成稳定的禅道 CLI 数据获取能力。阶段二的目标是：

- 扫描本地代码仓库，提取与禅道条目相关的代码上下文。
- 根据条目类型（功能类 / 缺陷类）交给 LLM 做结构化分析。
- 输出统一的分析结果（`AnalysisResult`），为阶段三的 PRD/ISSUE 文档生成提供数据契约。

阶段二明确限定为"代码扫描 + Prompt 结构化分析 + AnalysisResult JSON 输出"，不实现复杂语义索引、自动修复或代码改写，也不负责 PRD/ISSUE 文档生成（阶段三）。

---

## 2. 范围

### 2.1 纳入范围

- 新增代码上下文收集器（支持 `rg` → `git grep` → `os.walk` 回退链）。
- 新增分析类型分流逻辑：功能类（`story`、`requirement`）与缺陷类（`bug`、`ticket`、`feedback`）。
- 新增两套 Prompt 模板：功能完成度模板、BUG 根因分析模板。
- 定义统一的 LLM 分析结果数据结构 `AnalysisResult`。
- 新增 `llm_client.py` 封装 LLM 调用接口：阶段二实现 Codex（OpenAI）真实调用和 mock 后端，Claude/OpenCode 仅保留接口占位并返回明确的"未配置/未实现"提示，不作为阶段二验收阻塞项。
- 支持增量分析：利用 `modified_files` 优先缩小搜索范围。
- 支持代码预算限制：最大文件数、每文件最大行数、总 token 预算估算。
- 支持"证据不足"分支：无相关代码时返回 `confidence="低"`，不编造结论。
- 重构 `main.py`：仅保留 CLI 参数解析和主流程编排，扫描、分析、Prompt、LLM 调用全部拆出。

### 2.2 暂不纳入范围

- 自动修改代码、自动提交 Git commit、自动回写禅道条目。
- AST 解析、语义向量索引、跨仓库依赖分析。
- 自动测试用例生成或执行。
- 多语言语法高亮、代码格式化。

---

## 3. 架构设计

阶段二在阶段一基础上新增 5 个模块，保留 `zentao_client.py` 不变。

| 模块 | 职责 | 说明 |
|------|------|------|
| `code_collector.py` | 收集代码上下文 | 实现 `rg` → `git grep` → `os.walk` 回退链 |
| `prompts.py` | 提供 Prompt 模板 | 功能类 / 缺陷类两套模板 |
| `llm_client.py` | 封装 LLM 调用 | 当前实现 Codex，预留 Claude/OpenCode 接口 |
| `analysis_result.py` | 定义统一结果结构 | 解析、验证 LLM JSON 输出 |
| `analyzer.py` | 编排分析流程 | 分流、组装 Prompt、调用 LLM、解析结果 |
| `main.py`（修改） | CLI 参数 + 主流程编排 | 读取禅道数据 → 收集代码 → 分析 → 输出 |

### 3.1 模块边界原则

1. `main.py` 不再直接调用 `rg`、不再直接拼接 Prompt、不再解析 LLM JSON。
2. `analyzer.py` 是唯一连接"禅道数据 + 代码 + LLM"的编排层。
3. `analysis_result.py` 是阶段三文档生成的**唯一数据契约**。阶段三只消费 `AnalysisResult`，不依赖 `analyzer` 内部实现。
4. `code_collector.py` 对调用方暴露单一接口：`collect(repo_path, keywords, modified_files, limits)`。

---

## 4. 数据流

```
CLI 参数解析 (main.py)
    │
    ├───> ZentaoClient (阶段一，不变)
    │     输出: ZentaoItem (id, title, description, type, status...)
    │
    ├───> code_collector.py
    │     输入: repo_path, keywords(from ZentaoItem), modified_files, limits
    │     输出: List[CodeSnippet] (path, content, line_start, line_end)
    │
    ├───> analyzer.py
    │     1. 判断 item_type：
    │        story/requirement → 功能分析流
    │        bug/ticket/feedback → 缺陷分析流
    │     2. 调用 prompts.py 组装 Prompt
    │     3. 调用 llm_client.py 发送请求
    │     4. 调用 analysis_result.py 解析 JSON
    │     输出: AnalysisResult
    │
    └───> main.py
          选择输出方式：
          - stdout JSON (阶段二)
          - 写入文件 (--output)
          - 若 --analyze 则继续调用阶段三的文档生成器
```

---

## 5. 搜索回退链详细设计

### 5.1 回退链顺序

1. **优先 `rg` (ripgrep)**：
   - 实现方式: 使用 `subprocess.run([...], shell=False)` 传递参数数组，避免 shell 注入。
   - 关键词组合策略: 对每个关键词分别执行 `rg --files-with-matches -i <keyword> <repo_path>`，收集命中文件后取并集（去重）。不使用裸拼多关键词的方式，避免路径/模式语义混淆。
   - 要求: 本地已安装 `rg`。
   - 优势: 全文搜索，速度快，跨语言。

2. **回退 `git grep`**：
   - 命令: `git -C <repo_path> grep -l -i <keyword1> --and -e <keyword2> ...`
   - 要求: 代码在 git 仓库中。
   - 劣势: 只能搜索已 tracked 的文件，不支持 untracked 文件。

3. **回退 `os.walk`**：
   - 遍历 `repo_path`，按扩展名白名单（`.c`, `.cpp`, `.h`, `.hpp`, `.sh`, `.bat`, `.py`, `Makefile`, `CMakeLists.txt`）筛选文件，再做字符串匹配。
   - 要求: 无。
   - 劣势: 速度慢，召回率低。

### 5.2 回退链降级策略

- 每一层尝试失败（命令不存在、返回非零、抛出异常）都**静默降级**，记录 `stderr` 到日志，不抛异常中断主流程。
- 三层全部失败时，`code_collector` 返回空列表，由 `analyzer` 触发"证据不足"分支。

### 5.3 增量模式

- 若传入 `modified_files`（非空列表），搜索**仅在这些文件范围内**进行。
- `modified_files` 由 `main.py` 通过 `get_modified_files()` 获取（已在阶段一修复 shell 注入）。

### 5.4 预算限制

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_files` | 50 | 最多读取的文件数 |
| `max_lines_per_file` | 200 | 每文件最多读取行数 |
| `max_total_tokens` | 8000 | 估算总 token 上限（简单按 1 token ≈ 4 字符估算） |

收集器在读取文件内容时累加 token 估算值，超过 `max_total_tokens` 时停止收集，已收集的内容保留。

---

## 6. Prompt 模板设计

### 6.1 功能类模板（story / requirement）

```
你是高级代码分析 Agent。请根据以下禅道条目和代码上下文，判断功能实现完成度。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码上下文】
{code_context}

【任务要求】
1. 对比条目描述与代码实现，判断功能是否完成。
2. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
3. JSON Schema:
{
  "conclusion": "完成|部分完成|未完成|无法判断",
  "evidence": ["文件路径:函数名 已实现的功能说明", "..."],
  "gaps": ["未实现点1", "..."],
  "suspected_causes": [],
  "affected_scope": [],
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": "# PRD 文档内容（可选）"
}

4. 如果代码上下文不足以判断，请设置 conclusion="无法判断"、confidence="低"，并在 evidence 中说明"相关代码证据不足"。禁止编造不存在的证据。
5. confidence="高" 意味着你有直接代码证据支持结论；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
```

### 6.2 缺陷类模板（bug / ticket / feedback）

```
你是高级代码分析 Agent。请根据以下禅道缺陷条目和代码上下文，分析可能根因和影响范围。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码上下文】
{code_context}

【任务要求】
1. 分析缺陷描述对应的代码区域，找出可能根因。
2. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
3. JSON Schema:
{
  "conclusion": "已定位|部分定位|无法定位",
  "evidence": ["文件路径:函数名 与缺陷相关的代码说明", "..."],
  "gaps": [],
  "suspected_causes": ["可能根因1", "..."],
  "affected_scope": ["文件A", "模块B"],
  "recommendations": ["修复方向1", "..."],
  "verification": ["复现步骤或验证建议", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": "# ISSUE 文档内容（可选）"
}

4. 如果代码上下文不足以分析，请设置 conclusion="无法定位"、confidence="低"，并在 suspected_causes 中说明"相关代码证据不足"。禁止编造不存在的根因。
5. confidence 定义同上。
```

### 6.3 代码上下文格式化

每个代码片段按以下格式拼入 Prompt：

```
--- 文件: {path} (行 {start}-{end}) ---
{content}
```

总代码上下文长度超过 `max_total_tokens * 0.8` 时，截断并附加说明"[代码上下文已截断，仅展示部分相关文件]"。

---

## 7. LLM 输出 Schema（AnalysisResult）

```python
@dataclasses.dataclass
class AnalysisResult:
    item_id: str
    item_type: str
    item_title: str
    conclusion: str          # 功能类: 完成/部分完成/未完成/无法判断; 缺陷类: 已定位/部分定位/无法定位
    evidence: List[str]      # 支持结论的代码证据
    gaps: List[str]          # 未实现点或遗漏（功能类）
    suspected_causes: List[str]  # 可能根因（缺陷类）
    affected_scope: List[str]    # 影响范围（缺陷类）
    recommendations: List[str]   # 修改/修复建议
    verification: List[str]      # 验证/复现建议
    priority: str            # 高/中/低
    confidence: str          # 高/中/低
    output_md: str           # 可选的 Markdown 内容
    error: str = ""          # 若 LLM 调用或解析失败，记录错误信息
    raw_response: str = ""   # LLM 原始返回（调试/审计用，repr=False）
```

### 7.1 字段映射规则

- LLM 返回的 JSON 字段名与 `AnalysisResult` 字段名一一对应。
- 若 LLM 返回的 JSON 缺少某些字段，`analysis_result.py` 的解析器自动补齐为空列表或空字符串。
- 若 LLM 返回的 JSON 包含未定义字段，静默忽略，不报错。
- 若 LLM 返回非 JSON（例如 Markdown 代码块包裹的 JSON），先尝试提取代码块内容再解析；失败则设置 `error="JSON 解析失败"`。

---

## 8. 证据不足分支

### 8.1 触发条件（满足任一）

1. `code_collector` 返回空列表（无相关代码）。
2. `confidence == "低"`。
3. `evidence` 为空列表且 `conclusion != "无法判断"`（视为 LLM 未遵守指令，强制修正）。

### 8.2 处理行为

- `analyzer.py` 在返回 `AnalysisResult` 前检查触发条件。
- 若触发：
  - 设置 `conclusion = "无法判断"`（功能类）或 `"无法定位"`（缺陷类）。
  - 设置 `confidence = "低"`。
  - 在 `evidence`（功能类）或 `suspected_causes`（缺陷类）中追加 `"分析依据不足：未找到与条目直接相关的代码证据。"`。
  - `output_md` 保持为空字符串；阶段二不生成 Markdown 文档，仅输出 JSON 结构。Markdown 文档生成由阶段三负责。
- 此分支**不阻塞主流程**，继续输出到 stdout 或文件。

---

## 9. 接口定义

### 9.1 code_collector.py

```python
def collect(
    repo_path: str,
    keywords: List[str],
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
) -> List[Dict[str, Any]]:
    """
    收集代码上下文。
    
    返回: [{"path": str, "content": str, "line_start": int, "line_end": int}]
    """
```

### 9.2 prompts.py

```python
from typing import Any, Dict, List

def build_feature_prompt(item: ZentaoItem, code_snippets: List[Dict[str, Any]]) -> str:
    """功能类 Prompt"""

def build_defect_prompt(item: ZentaoItem, code_snippets: List[Dict[str, Any]]) -> str:
    """缺陷类 Prompt"""
```

### 9.3 llm_client.py

```python
def call_llm(prompt: str, agent: str = "codex") -> Dict[str, Any]:
    """
    调用 LLM，返回原始 JSON 字典。
    若失败，返回 {"error": "错误描述", "raw": "原始响应文本"}。
    """
```

### 9.4 analysis_result.py

```python
@dataclasses.dataclass
class AnalysisResult:
    ...

    @classmethod
    def from_llm_json(cls, item: ZentaoItem, data: Dict[str, Any], raw_response: str = "") -> "AnalysisResult":
        """从 LLM JSON 构建 AnalysisResult，自动补齐缺失字段。"""

    @classmethod
    def from_error(cls, item: ZentaoItem, error: str, raw_response: str = "") -> "AnalysisResult":
        """从错误信息构建诊断型 AnalysisResult。"""

    def is_insufficient_evidence(self) -> bool:
        """判断是否证据不足。"""
```

### 9.5 analyzer.py

```python
def analyze(
    item: ZentaoItem,
    repo_path: str,
    agent: str = "codex",
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
) -> AnalysisResult:
    """
    完整分析流程：收集代码 -> 选择模板 -> 调用 LLM -> 解析结果 -> 证据不足检查。
    """
```

---

## 10. 错误处理

| 场景 | 处理行为 | 输出 |
|------|----------|------|
| `rg` 未安装 | 静默降级到 `git grep` | 日志记录 |
| `git grep` 失败 | 静默降级到 `os.walk` | 日志记录 |
| 无相关代码 | 不调用 LLM，直接返回证据不足结果 | `AnalysisResult(confidence="低")` |
| LLM 调用超时 | 返回 `error="LLM 调用超时"` | `AnalysisResult.from_error()` |
| LLM 返回非 JSON | 尝试提取 Markdown 代码块；失败则返回 `error="JSON 解析失败"` | `AnalysisResult.from_error()` |
| LLM 返回字段缺失 | 自动补齐空值，不中断 | 完整 `AnalysisResult` |
| 敏感信息泄露 | `llm_client.py` 对 API key、token 做脱敏处理 | 日志中不输出密钥 |

---

## 11. 测试策略

### 11.1 新增测试文件

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/test_code_collector.py` | rg → git grep → os.walk 回退链；预算限制；增量文件范围；空关键词 |
| `tests/test_prompts.py` | 功能类/缺陷类模板渲染；关键词替换；长描述截断 |
| `tests/test_llm_client.py` | Codex 调用 mock；超时处理；非 JSON 响应；敏感信息脱敏 |
| `tests/test_analysis_result.py` | JSON 解析、字段补齐、证据不足检测、错误构造 |
| `tests/test_analyzer.py` | 分流逻辑、空代码直接返回、完整流程 mock（不调用真实 LLM） |

### 11.2 测试原则

- 所有 LLM 相关测试使用 `unittest.mock.patch` 模拟，**不调用真实 API**。
- `code_collector` 测试使用临时目录创建真实文件，验证搜索回退链。
- `main.py` 的集成测试使用 `subprocess` 运行 CLI，验证端到端参数传递。

---

## 12. 验收点

- [ ] 给定一个 `story`，能输出 `AnalysisResult`，包含完成度结论、实现证据、未实现点、修改建议。
- [ ] 给定一个 `bug`，能输出 `AnalysisResult`，包含可能根因、影响范围、修复方向、验证建议。
- [ ] 当相关代码不足时，`confidence` 为 `低`，`conclusion` 为 `无法判断`/`无法定位`，不编造结论。
- [ ] 代码扫描过程可配置，能在大型仓库中限制文件数量和 token 预算。
- [ ] `rg` 不可用时自动降级到 `git grep`，再不可用时降级到 `os.walk`，不报错退出。
- [ ] LLM 调用失败时仍能生成带错误原因的诊断 `AnalysisResult`。
- [ ] stdout 在 `--output` 未指定时输出可解析的 JSON。
- [ ] 所有新增代码通过单元测试，不破坏阶段一的 18 个现有测试。

---

## 13. 风险与假设

1. **假设**: `rg` 或 `git grep` 至少有一个可用；若都没有，`os.walk` 降级虽然慢但不会阻塞。
2. **假设**: LLM 能遵守 Prompt 中的 JSON Schema 和"禁止编造证据"指令；若不能，`analysis_result.py` 的后置检查会兜底。
3. **风险**: 大型仓库中 `os.walk` 全量遍历可能很慢；缓解措施是通过 `max_files` 和 `max_total_tokens` 限制。
4. **风险**: LLM 幻觉导致编造文件路径或函数名；缓解措施是通过 `confidence` 字段和证据不足分支人工复核。

---

## 14. 依赖关系

- 阶段二依赖阶段一的 `ZentaoClient` 和 `ZentaoItem` 数据结构，**不修改** `zentao_client.py`。
- 阶段三将依赖阶段二的 `AnalysisResult` 数据结构。

---

*文档结束*
