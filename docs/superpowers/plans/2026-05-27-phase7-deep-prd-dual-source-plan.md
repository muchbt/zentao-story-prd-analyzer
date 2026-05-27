# 阶段七：深度 PRD 生成与双输入来源 Implementation Plan

> **实施依据**：`docs/superpowers/specs/2026-05-27-phase7-deep-prd-dual-source-design.md`。原多侧阶段七规格与计划已废弃，不得混入本计划。

**Goal:** 支持禅道取数和用户提供完整需求正文两种 Feature Item 输入，并在保留逐点完成度证据约束的前提下生成更易理解的深度 PRD。

**Architecture:** 保持一次 Agent CLI 子进程调用与 Analyzer Process 唯一写入边界。`main.py`/`zentao_client.py` 边界负责构造唯一 Requirement Source；`prompts.py` 与结果模型扩展需求解读及代码影响结构；`analyzer.py` 独立校验代码影响位置和完成度证据；`document_generator.py` 只消费结构化结果渲染固定章节。

**Tech Stack:** Python 3.8+, dataclasses, argparse, json, pathlib/os, unittest, unittest.mock, tempfile

---

## 实施约束

- 文件名规则保持 `PRD-{type}-{id}-{sanitize_title(item.title)}.md`。
- `Provided Requirement` 模式不调用禅道，不将 ID 解释为回查指令。
- `Requirement Interpretation` 和 `Code Impact Analysis` 不得新增需求点或支撑完成度结论。
- `Completion Assessment` 继续以阶段六的 Requirement Point 与有效 Code Evidence 为唯一正式依据。
- 丰富章节缺失不阻断已有效的完成度 PRD；必须显式披露降级状态。
- ISSUE 流程不扩展。
- Agent CLI 子进程继续只读，文档由 Analyzer Process 生成。

## File Map

| File | Responsibility | Action |
| --- | --- | --- |
| `zentao_analyzer/zentao_client.py` | Feature Item 载体支持来源元数据 | Modify |
| `zentao_analyzer/main.py` | Provided Requirement CLI 模式与产物组装 | Modify |
| `zentao_analyzer/prompts.py` | 深度 PRD Feature Agent JSON 合约 | Modify |
| `zentao_analyzer/analysis_result.py` | 需求解读与代码影响结果模型/解析 | Modify |
| `zentao_analyzer/analyzer.py` | 关联位置校验与扩展字段降级 | Modify |
| `zentao_analyzer/document_generator.py` | 固定深度 PRD 模板渲染 | Modify |
| `zentao_analyzer/summary_report.py` | 来源与丰富内容状态索引 | Modify |
| `zentao_analyzer/debug_bundle.py` | 来源及关联位置校验诊断记录 | Modify |
| `SKILL.md` | 两类触发流程和正文输入调用规则 | Modify |
| `README.md` | CLI、输出与失败语义说明 | Modify |
| `tests/test_main_phase7.py` | 双输入及主流程回归 | Create |
| `tests/test_prompts.py` | 扩展 Schema 约束测试 | Modify |
| `tests/test_analysis_result.py` | 新结构解析与缺失降级测试 | Modify |
| `tests/test_analyzer.py` | Code Impact 位置校验测试 | Modify |
| `tests/test_document_generator.py` | 深度 PRD 章节与来源展示测试 | Modify |
| `tests/test_summary_report.py` | 新索引字段测试 | Modify |
| `tests/test_debug_bundle.py` | 扩展诊断写入测试 | Modify |

---

### Task 1: Add Provided Requirement Input Mode

**Files:**
- Modify: `zentao_analyzer/zentao_client.py`
- Modify: `zentao_analyzer/main.py`
- Create: `tests/test_main_phase7.py`

**Tests first:**

- `--requirement-file` + `--id` + `--title` creates one `requirement` Feature Item from file content.
- Provided Requirement 模式中 mock `ZentaoClient.get_item/list_items/login` 均未被调用。
- 缺 `--id`、缺 `--title`、空文件、不可读取文件返回前置输入错误且不调用 Agent。
- `--requirement-file` 与 `--login`、列表查询参数或缺陷模块组合被拒绝。
- 既有 `--module requirement --id ...` 继续从 ZentaoClient 读取。

**Implementation:**

- 为 `ZentaoItem` 增加可选的 `requirement_source` 字段，禅道取数默认 `zentao`，手工输入为 `provided_requirement`。
- 在 CLI 增加 `--requirement-file` 与 `--title`。
- 将正文文件读取、输入组合校验封装为小函数，返回内存中的 `ZentaoItem`。
- 手工输入路径跳过登录和 fetch 阶段的禅道调用，但仍以统一 item 列表进入 analyze/doc/summary/debug 流程。

**Verification:**

```bash
python3 -m unittest tests/test_main_phase7.py tests/test_zentao_client.py
```

---

### Task 2: Extend Feature Agent Contract For Deep PRD Content

**Files:**
- Modify: `zentao_analyzer/prompts.py`
- Modify: `tests/test_prompts.py`

**Tests first:**

- Feature prompt 要求返回 `requirement_interpretation`、`code_impact` 与既有 `requirement_points`。
- Prompt 明确三类边界：需求正文事实、代码侧候选上下文、逐点完成度证据。
- Prompt 明确固定章节信息不足时返回 `source: "insufficient"`，不能编造。
- Defect prompt 不增加深度 PRD Schema。

**Implementation:**

- 扩展 `_FEATURE_TEMPLATE` 的任务约束与 JSON Schema。
- 规定 `source` 枚举 `requirement|code_context|insufficient`。
- 规定 `code_impact.related_locations` 不是完成度 evidence。
- 规定 recommendations 仅为建议，不代表现存实现。

**Verification:**

```bash
python3 -m unittest tests/test_prompts.py
```

---

### Task 3: Parse Rich Results Without Weakening Completion Assessment

**Files:**
- Modify: `zentao_analyzer/analysis_result.py`
- Modify: `zentao_analyzer/analyzer.py`
- Modify: `tests/test_analysis_result.py`
- Modify: `tests/test_analyzer.py`

**Tests first:**

- 有效 `requirement_interpretation` 可解析 summary/scope/terms/rules/scenarios/matrix/flow/pending confirmations。
- 有效 `code_impact.related_locations` 可解析为独立位置类型。
- Code Impact 位置校验失败时从正式关联位置移除并记录问题，但不改变有效 Requirement Point 派生的完成度结论。
- `requirement_interpretation` 或 `code_impact` 缺失/无效时设置丰富内容不可用标志，仍保留有效完成度结果。
- Requirement Point evidence 的无效位置仍按阶段六规则降低完成度，不因新位置模型变化。

**Implementation:**

- 新增数据结构：`RequirementInterpretation`、`InterpretationEntry`、`RequirementScenario`、`RequirementMatrix`、`RequirementFlow`、`CodeImpactLocation`、`CodeImpactAnalysis`。
- 扩展 `AnalysisResult`：`requirement_source`、`requirement_interpretation`、`code_impact`、`rich_content_issues`。
- 在 Feature 分析路径解析丰富字段；解析失败不返回 `requirement_points_unavailable`。
- 对 Code Impact 使用独立校验集合，复用路径/行号验证机制但不进入 `cited_evidence_locations`。

**Verification:**

```bash
python3 -m unittest tests/test_analysis_result.py tests/test_analyzer.py tests/test_main_phase6.py
```

---

### Task 4: Render Deep PRD Sections And Preserve Filename Contract

**Files:**
- Modify: `zentao_analyzer/document_generator.py`
- Modify: `tests/test_document_generator.py`
- Modify: `tests/test_main_phase6.py`

**Tests first:**

- PRD 总是包含六章固定结构和新增小节：范围、术语定义、业务规则、场景与流程、矩阵、现有代码关联。
- 有效 Interpretation 字段正确渲染为可读列表/表格。
- 任何缺失或 `insufficient` 小节输出“原始需求未提供足够信息”或“分析结果未提供有效内容”。
- `code_context` 项目明确显示“不构成需求定义”的来源标记。
- Code Impact 表格仅展示校验通过的位置，关键代码证据继续只展示 Completion Assessment evidence。
- 建议区明确为建议内容，不代表已有实现。
- PRD 与 ISSUE 既有文件名断言均保持通过，ISSUE 内容模板不变。

**Implementation:**

- 将当前六章骨架扩展为规格所列小节。
- 增加小型渲染 helper 处理固定章节缺省、来源标签、代码关联表格。
- 保持 `generate_document()` 文件名构造不变。

**Verification:**

```bash
python3 -m unittest tests/test_document_generator.py tests/test_main_phase6.py
```

---

### Task 5: Expose Source And Rich-Content Diagnostics In Outputs

**Files:**
- Modify: `zentao_analyzer/main.py`
- Modify: `zentao_analyzer/summary_report.py`
- Modify: `zentao_analyzer/debug_bundle.py`
- Modify: `tests/test_main_phase7.py`
- Modify: `tests/test_summary_report.py`
- Modify: `tests/test_debug_bundle.py`

**Tests first:**

- stdout JSON 的 Feature `analysis[]` 输出 `requirement_source`、丰富结构与验证后的 Code Impact 位置。
- Summary 输出 `requirement_source`、`code_impact_location_count`、`has_pending_requirement_confirmation` 及丰富内容降级标志。
- Debug Bundle 记录来源类型、丰富内容原始结果和 Code Impact 校验问题。
- 日志及 stderr 不回显完整 Provided Requirement 正文。
- 旧 Zentao 输入与 ISSUE 输出保持兼容。

**Implementation:**

- 为输出序列化新增 plain helper，避免直接输出内部错误对象。
- 将 Code Impact 验证问题与完成度 evidence 验证问题分栏保存。
- Debug 配置仅记录正文来源与文件路径元信息，不复制正文到普通日志。

**Verification:**

```bash
python3 -m unittest tests/test_main_phase7.py tests/test_summary_report.py tests/test_debug_bundle.py tests/test_run_logger.py
```

---

### Task 6: Publish The New Skill And User Contract

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Test: affected tests and manual text checks

**Required documentation:**

- 说明禅道 ID 模式与 Provided Requirement 模式的命令模板。
- 说明 Skill 接收用户正文后应询问缺失的 ID，并推荐/确认标题，再调用 `--requirement-file`。
- 明确 Provided Requirement 模式不会回查或合并禅道内容。
- 描述 PRD 三类内容边界和丰富字段降级语义。
- 保留不得用 `zentao user` 作为认证检查的既有修正。
- 删除所有将旧多侧阶段七描述为未来能力的有效文档引用。

**Verification:**

```bash
rg -n "requirement-file|Provided Requirement|提供.*需求|zentao user|多侧|Analysis Scope|Code Side" README.md SKILL.md CONTEXT.md docs/superpowers/specs docs/superpowers/plans
python3 -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

---

## Done Criteria

- 两种需求正文来源都能进入同一正式 Feature Item 分析链路，且来源互斥清晰。
- 用户正文模式在不访问禅道的情况下使用确认 ID 和标题生成 PRD。
- PRD 输出固定、可读的深度章节，并明确来源不足或候选上下文。
- 完成度、缺口与可信度仍严格来自经校验的逐点 Code Evidence。
- Code Impact 位置不能误计为完成度 evidence。
- 正式文档仅由 Analyzer Process 写入。
- 旧多侧阶段七仅保留带废弃声明的历史文件，不再出现在有效能力描述中。
- 全量测试和 diff 校验通过。
