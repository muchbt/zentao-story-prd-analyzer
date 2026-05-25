# zentao-story-prd-analyzer — 阶段五：证据可追溯性增强

**日期**: 2026-05-22
**版本**: 1.0
**状态**: 设计完成，待实现

---

## 1. 背景与目标

阶段一到阶段四已经形成从禅道条目获取、代码扫描、Agent 分析、PRD/ISSUE 文档生成到 debug bundle 回溯的可运行闭环。阶段五不重新定义前四阶段边界，而是在现有闭环上增强证据可追溯性。

阶段五目标：

- 支持用户显式提供代码线索，避免只依赖标题/描述关键词召回。
- 区分并记录“收集到并喂给 Agent 的代码位置”和“Agent 最终引用为证据的代码位置”。
- 升级 Prompt 与分析结果结构，优先支持结构化 evidence，同时兼容旧字符串 evidence。
- debug bundle 默认保存文件名和行号范围，不默认保存完整代码内容。
- summary report 增加证据位置计数和 debug bundle 索引，便于机器消费。
- PRD/ISSUE 文档只展示关键引用证据，保持人类可读。

---

## 2. 范围

### 2.1 纳入范围

- 新增显式代码线索输入：
  - `--keywords`
  - `--paths`
  - `--symbols`
  - `--clues-file`
- 支持全局线索和按禅道条目 ID 的专属线索。
- 路径线索必须限制在 `repo_path` 内，越界线索记为 rejected clue，不读取内容。
- 代码收集器返回代码片段时同步返回文件名和行号范围。
- Agent Prompt 要求返回结构化 evidence。
- 解析结构化 evidence，并从旧字符串 evidence 中尽力提取 fallback 位置。
- debug bundle 默认写入：
  - `code_evidence_locations.json`
  - `rejected_clues.json`
- summary report 增加证据计数字段。
- PRD/ISSUE 文档以表格展示关键引用证据。

### 2.2 暂不纳入范围

- 自动语义索引或向量检索。
- 自动 AST 级精确函数范围识别。
- 自动修改代码。
- 自动回写禅道。
- 默认保存完整代码内容。
- 将 debug bundle 上传到远程服务。

---

## 3. 术语边界

阶段五遵循根目录 `CONTEXT.md` 的术语：

- `ISSUE Document` 只表示输出文档类型，不是禅道输入模块。
- 阶段一只生成结构化 `Zentao Item`，不生成 `Analysis Result`。
- `Code Clue` 是召回线索，不是证据。
- `Code Evidence` 必须约束 `Analysis Result` 的结论和置信度。
- `Collected Location` 表示实际喂给 Agent 的代码位置。
- `Cited Evidence Location` 表示 Agent 最终引用为结论依据的位置。
- `Summary Report` 是机器可读索引，不是完整审阅报告。

---

## 4. 数据模型

### 4.1 CodeClue

```python
@dataclasses.dataclass
class CodeClue:
    kind: str                  # keyword | path | symbol
    value: str
    source: str                # zentao | cli | clues_file
    item_id: str = ""          # 空表示全局线索
```

### 4.2 RejectedClue

```python
@dataclasses.dataclass
class RejectedClue:
    kind: str
    value: str
    source: str
    item_id: str = ""
    reason: str = ""
```

### 4.3 CodeLocation

```python
@dataclasses.dataclass
class CodeLocation:
    path: str
    line_start: int
    line_end: int
    symbol: str = ""
    reason: str = ""
    source: str = ""           # collector | agent | fallback
    matched_clues: list[str] = dataclasses.field(default_factory=list)
```

### 4.4 CodeSnippet

阶段五建议将当前字典形式的代码片段收敛为结构化对象，或保持字典但字段必须完整：

```python
{
  "path": "src/a.c",
  "content": "...",
  "line_start": 1,
  "line_end": 120,
  "matched_clues": ["auth", "login"]
}
```

### 4.5 Structured Evidence

Agent 新格式 evidence：

```json
{
  "evidence": [
    {
      "path": "src/a.c",
      "line_start": 12,
      "line_end": 40,
      "symbol": "LoadCalibration",
      "reason": "这里实现了需求中的导入校验"
    }
  ]
}
```

旧格式继续兼容：

```json
{
  "evidence": ["src/a.c: LoadCalibration 实现了导入校验"]
}
```

兼容规则：

1. 新结构化 evidence 优先。
2. 旧字符串 evidence 保留到 PRD/ISSUE 文档。
3. 旧字符串 evidence 仅尽力解析 path、line range、symbol；无法解析行号时不得伪造。
4. `cited_evidence_locations` 只包含可定位的位置。

---

## 5. CLI 与 Clues File

### 5.1 新增 CLI 参数

- `--keywords KW[,KW...]`
- `--paths PATH[,PATH...]`
- `--symbols SYMBOL[,SYMBOL...]`
- `--clues-file PATH`

### 5.2 Clues File 格式

JSON 格式：

```json
{
  "5939": {
    "keywords": ["calibration", "import"],
    "paths": ["src/calib"],
    "symbols": ["LoadCalibration"]
  },
  "5940": {
    "paths": ["src/auth/login.c"]
  }
}
```

### 5.3 线索合并规则

对每个条目，最终线索来源包括：

1. `zentao`：从标题、描述等字段提取的默认关键词。
2. `cli`：命令行提供的全局 `--keywords`、`--paths`、`--symbols`。
3. `clues_file`：`--clues-file` 中当前条目 ID 对应的专属线索。

合并后去重，但保留来源信息用于 debug bundle。

### 5.4 路径安全规则

- `--paths` 和 clues file 中的 path 可以是相对路径或绝对路径。
- 相对路径按 `repo_path` 解析。
- 绝对路径必须解析后位于 `repo_path` 内。
- 越界路径不读取内容，写入 `rejected_clues.json`。
- 关键词和符号需要限制数量和长度，防止异常输入导致扫描过慢。

建议默认限制：

| 类型 | 单次运行最大数量 | 单值最大长度 |
|------|------------------|--------------|
| keyword | 100 | 120 |
| symbol | 100 | 160 |
| path | 200 | 500 |

---

## 6. 代码收集设计

阶段五扩展 `code_collector.collect()`：

输入：

```python
collect(
    repo_path: str,
    clues: list[CodeClue],
    modified_files: list[str] | None,
    max_files: int,
    max_lines_per_file: int,
    max_total_tokens: int,
) -> CollectionResult
```

输出：

```python
@dataclasses.dataclass
class CollectionResult:
    snippets: list[dict]
    collected_locations: list[CodeLocation]
    rejected_clues: list[RejectedClue]
```

兼容要求：

- 可以保留旧 `collect(repo_path, keywords, ...) -> list[dict]` 作为包装接口。
- `analyzer.py` 优先使用新接口。
- 旧测试不应因返回类型变化被无关破坏。

收集规则：

1. path 线索优先，直接读取文件或目录下允许扩展名文件。
2. symbol 线索用于内容搜索。
3. keyword 线索用于内容和文件名搜索。
4. `modified_files` 非空时，搜索范围与显式 path 线索取交集；如果显式 path 不在增量范围内，应记录为未命中而非越界。
5. 每个 snippet 必须有 `path`、`line_start`、`line_end`。

---

## 7. Prompt 与 AnalysisResult

### 7.1 Prompt Schema 更新

功能类和缺陷类 Prompt 都必须要求 evidence 使用结构化对象：

```json
{
  "evidence": [
    {
      "path": "文件路径",
      "line_start": 1,
      "line_end": 20,
      "symbol": "函数或类名，可为空",
      "reason": "该证据如何支持结论"
    }
  ],
  "conclusion": "...",
  "confidence": "高|中|低"
}
```

Prompt 必须继续强调：

- 没有直接代码证据时不得给高置信度。
- 不得编造文件名、行号或函数名。
- 只能引用代码上下文中出现过的位置。

### 7.2 AnalysisResult 扩展

新增字段：

```python
cited_evidence_locations: list[CodeLocation]
evidence_text: list[str]
```

兼容策略：

- `evidence` 可继续保留旧 `list[str]`，用于文档展示和旧调用方。
- 新结构化 evidence 解析后同时生成：
  - `evidence_text`
  - `cited_evidence_locations`
- 旧字符串 evidence 解析失败时只进入 `evidence_text`，不进入 `cited_evidence_locations`。

---

## 8. Debug Bundle

默认新增文件：

```text
code_evidence_locations.json
rejected_clues.json
```

`code_evidence_locations.json` 结构：

```json
{
  "items": [
    {
      "item_id": "5939",
      "collected_locations": [
        {
          "path": "src/a.c",
          "line_start": 1,
          "line_end": 120,
          "matched_clues": ["login"],
          "source": "collector"
        }
      ],
      "cited_evidence_locations": [
        {
          "path": "src/a.c",
          "line_start": 12,
          "line_end": 40,
          "symbol": "Login",
          "reason": "支持登录完成度判断",
          "source": "agent"
        }
      ]
    }
  ]
}
```

默认不保存完整代码内容。`--debug-include-code` 仍控制代码内容快照。

---

## 9. PRD/ISSUE 文档

PRD/ISSUE 文档新增或强化“关键代码证据”表格：

```md
## 关键代码证据

| 文件 | 行号 | 符号 | 说明 |
|---|---:|---|---|
| src/a.c | 12-40 | Login | 支持登录功能已实现 |
```

规则：

- 只展示 `cited_evidence_locations`。
- 不展示所有 `collected_locations`。
- 如果没有可定位引用证据，明确写“无可定位代码证据”。
- 诊断文档同样应说明收集到了多少位置、引用到了多少位置。
- PRD 文档移除阶段三的独立“实现证据”章节，将证据展示统一收敛到“关键代码证据”章节。
- PRD 的旧字符串 evidence 若无法被定位表格表达，应在同一“关键代码证据”章节中作为补充说明保留，不得静默丢弃。
- PRD 完全无证据时，应说明当前无法验证实现状态；证据不足且无已确认缺口时，“差异与缺口”显示“无法确定是否存在缺口”。
- ISSUE 文档仍保留“代码证据”文本列表与“关键代码证据”位置表格：缺陷定位叙述和可追溯位置承担不同职责，不随 PRD 合并。

---

## 10. Summary Report

每个 summary item 新增：

```json
{
  "collected_location_count": 12,
  "cited_evidence_location_count": 3,
  "rejected_clue_count": 1,
  "debug_bundle": "debug_runs/..."
}
```

summary report 不保存完整 prompt、response 或代码内容。

---

## 11. 测试策略

新增或扩展测试：

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/test_code_clues.py` | CLI/clues file 解析、合并、去重、来源标记、越界路径拒绝 |
| `tests/test_code_collector.py` | path/symbol/keyword 线索收集、collected_locations、modified_files 交集 |
| `tests/test_analysis_result.py` | 结构化 evidence 解析、旧字符串 fallback、不可解析位置不伪造 |
| `tests/test_prompts.py` | Prompt 要求结构化 evidence 和证据约束 |
| `tests/test_debug_bundle.py` | 默认写 code_evidence_locations 和 rejected_clues，不写完整代码 |
| `tests/test_document_generator.py` | PRD/ISSUE 关键代码证据表格 |
| `tests/test_summary_report.py` | evidence 计数和 debug_bundle 索引 |
| `tests/test_main_phase5.py` | CLI 参数、clues file、debug bundle 与 summary 串联 |

---

## 12. 验收点

- [ ] 用户可通过 `--keywords`、`--paths`、`--symbols` 提供全局代码线索。
- [ ] 用户可通过 `--clues-file` 为批量条目提供专属代码线索。
- [ ] 路径线索越界时不读取内容，并写入 `rejected_clues.json`。
- [ ] debug bundle 默认包含 `code_evidence_locations.json`。
- [ ] `code_evidence_locations.json` 同时区分 `collected_locations` 与 `cited_evidence_locations`。
- [ ] 不传 `--debug-include-code` 时不保存完整代码内容。
- [ ] Agent Prompt 要求结构化 evidence。
- [ ] 旧字符串 evidence 仍可作为 fallback。
- [ ] PRD/ISSUE 文档展示关键引用证据表格。
- [ ] summary report 包含 collected/cited/rejected 计数。
- [ ] 无代码证据时结论和置信度按证据不足规则降级。

---

## 13. 风险与假设

1. **Agent 仍可能不返回结构化 evidence**：通过旧字符串 fallback 和诊断提示缓解。
2. **行号范围可能只是收集片段范围，不是精确函数范围**：阶段五只承诺可回溯位置，不承诺 AST 精确定位。
3. **用户线索可能污染批量分析**：通过 `--clues-file` 支持按条目隔离线索。
4. **路径线索有安全风险**：强制限制在 `repo_path` 内，并记录 rejected clue。
5. **debug bundle 被外部脚本依赖**：文件结构应通过测试固定，后续变更需兼容。

---

*文档结束*
