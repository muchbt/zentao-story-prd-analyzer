# zentao-story-prd-analyzer - 阶段六：需求点拆分与逐点追溯

**日期**: 2026-05-26
**版本**: 0.2
**状态**: 已确认，待编写实施计划

---

## 1. 背景与目标

一个禅道 `Feature Item` 可能同时描述多个可独立验证的预期行为。仅以条目级证据和结论分析，会掩盖“部分需求点已实现、部分需求点缺失或无法确认”的情况。

阶段六引入 `Requirement Point` 作为所有 `Feature Item` 分析的基础能力：

- 根据从禅道获取的原始需求描述提出可独立验证的需求点。
- 为每个需求点关联代码证据并独立判断实现状态。
- 根据逐点结论汇总条目级 `Analysis Result`。
- 保留拆分结果和证据关联，供用户复核。

该能力适用于普通单仓库模式，也适用于后续显式启用多侧分析的工程。阶段七消费阶段六输出，为需求点增加多侧范围和责任侧规则。

---

## 2. 阶段边界

- 阶段六仅针对 `Feature Item` 的实现完成度分析；`Defect Item` 不在本阶段范围内。
- 需求预期行为仅以从禅道获取的 `Feature Item` 原始描述为依据。
- `Code Clue` 和 `Search Hint` 只能辅助定位代码，不得作为新增需求、验收条件或 `Requirement Point` 拆分依据。
- 阶段六不引入 `Code Side`、`Analysis Scope`、`Responsibility Hint` 或 `Candidate Location`；这些属于阶段七的多侧扩展。
- 阶段六上线后，所有 `Feature Item` 分析默认启用需求点拆分，不提供显式启用开关。
- `Defect Item` 保持现有分析行为，不启用需求点拆分。
- 既有顶层结论字段继续保留，其值由需求点状态汇总产生；新增需求点输出不得移除既有字段。

---

## 3. Requirement Point 模型

- 一个 `Feature Item` 可以包含一个或多个 `Requirement Point`。
- `Requirement Point` 是可独立验证的预期行为单元，不是证据条目或代码文件。
- Agent 只能依据禅道原始需求描述提出拆分结果。
- 拆分结果必须作为分析产物保留，不得仅存在于 Agent 隐式推理中。
- Analyzer 按 Agent 返回顺序为本次运行分配稳定的临时标识，例如 `RP-001`、`RP-002`。
- 标识只保证同一次运行内在 PRD、Debug、Summary 和最终 JSON 中一致，不提供跨运行对齐语义。

---

## 4. 需求点状态与条目级汇总

每个 `Requirement Point` 使用以下基础状态：

| 状态 | 含义 |
|------|------|
| `完成` | 存在充分且有效的 `Code Evidence` 支持该预期行为已实现 |
| `部分完成` | 该需求点包含的行为仅部分得到有效证据支持 |
| `未完成` | 有效证据支持预期行为缺失或与实现不符 |
| `无法判断` | 当前证据不足或不可验证，不能确认是否完成 |

基础汇总规则：

- 所有需求点均为 `完成` 时，条目结论为 `完成`。
- 存在 `未完成` 或 `部分完成`，且同时存在已确认实现内容时，条目结论为 `部分完成`。
- 所有需求点均为 `未完成` 且不存在已确认实现内容时，条目结论为 `未完成`。
- 存在 `无法判断` 且没有已确认未完成需求点时，条目结论为 `无法判断`。
- 同时存在确认缺口和无法判断需求点时，条目结论为 `部分完成`，并明确披露仍无法判断的需求点。
- 缺少代码证据不等于确认缺口；完全无法确认时应表达为“无法确定是否存在缺口”，而不是“无可确认缺口”。
- 条目级 `gaps` 是逐点确认缺口的兼容聚合视图，不得独立于 `Requirement Point` 生成新的缺口结论。
- `Feature Item` 的顶层 `conclusion` 必须由 Analyzer 根据经校验的逐点状态按上述规则计算，不接受 Agent 提供的独立条目级完成度结论。

---

## 5. 需求点与代码证据

- 每个 `Requirement Point` 保留与其结论相关联的结构化 `Code Evidence`。
- Analyzer 必须继续校验证据文件路径和行号范围，不能因需求点拆分而放宽证据有效性要求。
- 同一有效代码位置可支持多个需求点，但必须在各需求点下明确关联理由。
- PRD 可聚合展示去重后的关键代码证据；Debug Bundle 必须保留需求点到证据的逐条关联。
- 完全没有有效代码证据的需求点显示为“无代码证据”；该展示不自动构成 `GAPS`，只有确认实现缺失或不一致时才能进入缺口结论。
- 既有顶层 `evidence` 字段继续保留，由各需求点的有效证据聚合生成，供现有调用方和 PRD 的“关键代码证据”展示继续消费。

---

## 6. 产物表达

阶段六应使需求点拆分和逐点结论可以复核：

- 所有 `Feature Item` 的 PRD 在实现完成度之后默认展示“需求点完成情况”，至少包含需求点标识、需求点描述、状态和说明。
- `GAPS` 仅呈现已经确认的实现缺失或差异；`无法判断` 需求点不得转换为缺口。
- Debug Bundle 保留拆分、逐点证据关联和解析诊断信息。
- Summary Report 与最终 JSON 默认增加需求点数量、状态分布及未确认需求点情况字段。
- Summary Report 与最终 JSON 保留既有字段；新增需求点字段只扩展现有输出，不以删除或重命名字段的方式要求既有调用方迁移。
- `Defect Item` 的 PRD、Summary Report 和最终 JSON 不因本阶段增加需求点输出。

### 6.1 PRD 需求点完成情况

`Feature Item` 的 PRD 在 `## 实现完成度` 之后、`## 关键代码证据` 之前新增 `## 需求点完成情况`，展示逐点状态摘要：

```markdown
## 需求点完成情况

| ID | 需求点 | 状态 | 说明 |
|---|---|---|---|
| RP-001 | MCU 上报指定状态 | 完成 | 已找到对应上报逻辑 |
| RP-002 | SOC 接收并更新状态 | 无法判断 | 无代码证据 |
```

展示规则：

- 表格只展示运行内 ID、需求点描述、状态和简短说明，不内联展开证据位置。
- `## 关键代码证据` 继续集中展示所有需求点引用的有效可定位证据，并按位置去重。
- 相同位置关联多个需求点时，PRD 不重复复制位置行；逐点到证据的完整映射由最终 JSON 和 Debug Bundle 保留。
- 表格中的“无代码证据”仅表示当前没有有效证据支撑该需求点结论，不等同于确认缺口。
- `## 差异与缺口` 仅展示由需求点确认差异聚合出的缺口，并标注对应的 `Requirement Point` ID。

### 6.2 最终 JSON 中的 Requirement Point

正常形成正式分析结果时，`Feature Item` 的最终 stdout JSON 增加 `requirement_points` 数组。每个需求点至少输出：

```json
{
  "id": "RP-001",
  "description": "可独立验证的需求点描述",
  "status": "完成",
  "reason": "判定说明",
  "gaps": [],
  "evidence": [
    {
      "path": "src/a.c",
      "line_start": 12,
      "line_end": 40,
      "symbol": "LoadCalibration",
      "reason": "该证据如何支持此需求点结论"
    }
  ]
}
```

字段规则：

- `id` 是本次运行内稳定的需求点标识。
- `description` 来自对禅道原始需求描述的拆分，不得来自用户补充文本或代码线索。
- `status` 使用阶段六定义的基础状态：`完成`、`部分完成`、`未完成`、`无法判断`。
- `reason` 说明该需求点状态如何由证据得出；完全没有有效代码证据时可显示“无代码证据”，但不得因此自动形成缺口。
- `gaps` 保存该需求点已经确认的实现缺失或不一致，不得从 `reason` 文本中二次解析生成。
- `evidence` 复用阶段五结构化 `Code Evidence` 对象格式及位置校验逻辑；阶段六不定义另一套证据位置模型。
- 对阶段五兼容的旧字符串 evidence，仅沿用既有 fallback 处理；不得为无法定位的字符串伪造结构化位置。
- 阶段六的 `requirement_points` 不输出 `responsible_sides`、`scope` 或 `candidate_locations`；这些字段只能由阶段七的多侧扩展增加。
- 需求点结构有效，但其 `evidence` 对象无效或引用位置未通过校验时，只将受影响需求点修正为 `无法判断`，不将整个条目标记为需求点合约失败。
- Feature Agent 只返回 `requirement_points` 中的逐点证据；顶层 `evidence` 由 Analyzer 汇总有效逐点证据后生成，Agent 不提供独立的顶层证据结论。

### 6.3 缺口聚合约束

- 只有状态为 `未完成` 或 `部分完成`，且包含已确认实现缺失或不一致的 `Requirement Point` 才能产生缺口。
- 每一条正式缺口必须能够关联到一个 `Requirement Point` ID。
- 每个需求点以独立 `gaps` 数组保存其已确认差异；顶层 `gaps` 直接聚合这些数组，并在展示时附加对应 `Requirement Point` ID。
- 状态为 `无法判断` 的需求点不得产生缺口；仅存在“无代码证据”的需求点也不得产生缺口。
- 状态为 `完成` 或 `无法判断` 的需求点必须输出空 `gaps`。
- 状态为 `未完成` 或 `部分完成` 的需求点仅在存在非空 `gaps` 时有效；否则不得以缺口状态形成正式结论，应按 `无法判断` 处理。
- 顶层 `gaps` 字段为兼容既有调用方而保留，其内容只能由逐点确认缺口聚合形成，不再接受与需求点无关联的 Agent 自由结论。
- PRD 的“差异与缺口”章节展示顶层聚合结果，并保留需求点 ID 以支持人工追溯。

### 6.4 Feature Agent 与 Analyzer 职责

- Feature Agent 返回从禅道原文提出的 `Requirement Point` 及其逐点 `status`、`reason`、`gaps` 和 `evidence`。
- Analyzer 负责校验需求点结构、逐点缺口约束和逐点证据位置有效性。
- Analyzer 基于通过校验的逐点状态生成顶层 `conclusion`，并基于逐点 `gaps` 聚合顶层兼容字段 `gaps`。
- Feature Agent 不再为 `Feature Item` 提供可直接采用的独立顶层 `conclusion` 或独立顶层 `gaps`。
- `Defect Item` 继续沿用当前由 Agent 提供顶层定位结论的处理方式，不受阶段六约束影响。
- Feature Agent 不再为 `Feature Item` 提供可直接采用的顶层 `confidence`；Analyzer 根据逐点分析和证据有效性生成该兼容字段。
- 阶段六不为单个 `Requirement Point` 新增 `confidence` 字段。
- `priority`、`recommendations`、`verification` 与 `understanding_summary` 等既有 Feature 条目级字段继续由 Agent 输出并保留；阶段六只将 `conclusion`、`gaps`、`confidence` 和顶层 `evidence` 改为 Analyzer 基于逐点结果生成的字段。

顶层 `confidence` 派生规则：

- 存在任一 `无法判断` 需求点，或任一用于支持正式结论的证据位置校验失败时，顶层 `confidence` 为 `低`。
- 所有需求点状态均可确认，且用于支持正式结论的证据均为通过校验的结构化直接代码证据时，顶层 `confidence` 为 `高`。
- 各需求点结论可确认，且存在作为辅助说明保留的旧字符串 fallback evidence 时，顶层 `confidence` 为 `中`。
- 纯文本推断或无法定位的旧字符串 evidence 不能单独支撑 `完成`、`部分完成` 或 `未完成` 的正式逐点结论。
- `confidence` 是汇总结果的可信度表达，不得反向覆盖已按需求点状态生成的 `conclusion`；证据校验导致需求点不可确认时，应先修正对应需求点状态再汇总两者。
- `Defect Item` 继续沿用当前可信度处理规则，不受阶段六约束影响。

点级证据校验失败规则：

- 单个需求点包含无效 evidence 对象或无效证据位置时，Analyzer 将该点状态修正为 `无法判断`。
- 即使同一需求点同时包含其他有效证据，只要该点用于形成结论的 evidence 中存在无效对象或无效位置，第一版仍统一将该点修正为 `无法判断`；Analyzer 不尝试判断剩余证据是否独立充分。
- Agent 返回 `完成`、`部分完成` 或 `未完成`，但对应需求点不存在可支持该状态的有效直接代码证据时，Analyzer 将该点修正为 `无法判断`。
- 被修正为 `无法判断` 的需求点必须清空其逐点 `gaps`，不得以无效证据继续支撑正式缺口。
- 多个需求点引用同一无效证据位置时，所有依赖该位置形成结论的需求点分别按上述规则修正；Debug Bundle 保存该位置到全部受影响需求点的引用关联。
- 校验失败原因写入 Debug Bundle，并纳入沿用阶段五语义的无效证据统计；`invalid_evidence_count` 按唯一无效位置去重计数，不按需求点引用次数重复累计。
- 其他结构和证据均有效的需求点保留其逐点结论；顶层 `conclusion`、`gaps` 与 `confidence` 均基于修正后的完整需求点集合重新生成。
- 只有需求点必要字段缺失、集合为空或状态/缺口合约冲突等需求点结构问题，才进入 `requirement_points_unavailable`。

### 6.5 Summary Report 索引字段

正常形成正式分析结果时，`Feature Item` 的 Summary item 增加以下轻量索引字段：

```json
{
  "requirement_point_count": 3,
  "requirement_point_status_counts": {
    "完成": 1,
    "部分完成": 1,
    "未完成": 0,
    "无法判断": 1
  },
  "has_unconfirmed_requirement_points": true
}
```

字段规则：

- `requirement_point_count` 是正式分析结果中 `Requirement Point` 的总数。
- `requirement_point_status_counts` 固定包含阶段六四种基础状态；没有命中的状态仍以 `0` 保留。
- `has_unconfirmed_requirement_points` 在存在任一 `无法判断` 需求点时为 `true`，否则为 `false`。
- Summary Report 不保存需求点描述、逐点判定理由或逐点证据；完整需求点内容由最终 JSON、PRD 和 Debug Bundle 承载。
- 无法可靠拆分需求点而形成诊断失败时，Summary item 记录 `analysis_status: "requirement_points_unavailable"` 及 Debug Bundle 索引，不伪造需求点计数或状态分布。

### 6.6 Debug Bundle 与证据兼容视图

- Debug Bundle 保存完整的 `Requirement Point` 结构及逐点 evidence、逐点 gaps、点级修正原因。
- 同一无效证据位置被多个需求点引用时，Debug Bundle 保存该位置对应的全部需求点 ID，支持人工追溯点级降级原因。
- 阶段五已有的顶层去重证据位置视图继续保留，由所有需求点中有效证据按位置聚合生成；它不得替代逐点关联结构。
- Debug Bundle 继续默认不保存完整代码正文，除非用户显式启用既有代码上下文保存能力。

---

## 7. 无法可靠拆分时的行为

- Agent 启动后若无法从禅道原始描述可靠提出可验证的 `Requirement Point`，本次分析不得生成正式 PRD。
- 分析器应输出诊断性质的 Summary Report 与 Debug Bundle，并提示用户完善禅道需求后重新执行。
- 该情况不得归纳为 `GAPS`，也不得由 Analyzer 自动重试或由 LLM 自动接管继续生成结论。
- 最终 stdout JSON 仍保留该条目的标识信息和诊断状态，例如 `analysis_status: "requirement_points_unavailable"`，使调用方能够关联本次失败条目。
- 诊断失败条目不得输出可被误认为正式分析结果的 `conclusion`、`gaps` 或空 `requirement_points`。
- 命令执行返回非成功状态，调用方不得将该结果作为正常完成的分析处理。

### 7.1 需求点合约失败分类

- Agent 响应 JSON 可解析，但 `requirement_points` 字段缺失、为空或结构无效时，统一标记为 `analysis_status: "requirement_points_unavailable"`。
- 需求点状态与逐点缺口约束冲突时，例如 `未完成` 缺少非空 `gaps`、`完成` 却包含 `gaps`，同样标记为 `requirement_points_unavailable`。
- 旧 Feature Agent 合约仅返回顶层 `conclusion`、`evidence` 或 `gaps` 而不返回 `requirement_points` 时，不自动包装为单一需求点，也不回退到旧分析模式；该结果按 `requirement_points_unavailable` 处理。
- Agent 返回完全重复的需求点描述时，按 `invalid_requirement_point_schema` 处理，不由 Analyzer 自动合并。
- 对非精确重复但可能语义重叠的需求点，Analyzer 不进行语义合并猜测；若 Agent 或校验阶段已标识该风险，则记录到 Debug Bundle 供人工复核。
- Debug Bundle 必须记录可操作的失败原因，例如 `empty_requirement_points`、`invalid_requirement_point_schema` 或 `invalid_point_gap_state_combination`。
- 该失败分类表示 Feature 分析合约未形成可用的逐点结论，不等同于确认实现缺口。

### 7.2 与既有 Agent 响应解析失败的边界

- Agent 响应无法被解析为 JSON 时，继续沿用既有 `error_kind: "parse"`、诊断产物和人工重试流程；阶段六不改变其退出码或既有机器字段。
- `requirement_points_unavailable` 只适用于已经解析出 JSON、但无法形成合法需求点结果的情况。
- 两类失败均不得触发 Analyzer 自动重试，也不得由宿主 LLM 绕过 Analyzer 接管分析结论。

### 7.3 批量执行与人工后续动作

- 批量分析中某个 `Feature Item` 发生 `requirement_points_unavailable` 时，其他已经成功形成的条目结果、PRD 与诊断索引继续保留，不因单条失败被丢弃。
- 只要本次运行存在任一 `requirement_points_unavailable`，命令整体返回非成功状态；第一版使用 exit code `1` 表达分析未全部完成，并保留既有认证、配置类错误的现有退出语义。
- 需求文本本身无法拆分可验证行为时，诊断结果输出 `recommended_action: "update_zentao_requirement"`，提示先更新禅道后人工重试。
- Agent 返回 JSON 但未满足需求点结构合约时，诊断结果输出 `recommended_action: "manual_retry"`，提示用户主动重试以重新获取结构化响应。
- 两种后续动作均不触发 Analyzer 自动重试，也不授权宿主 LLM 直接生成替代结论。

---

## 8. Agent 调用与合约迁移

- 阶段六第一版采用单次 Feature Agent 调用：一次响应同时返回依据禅道原文拆分的 `Requirement Point`、逐点状态、逐点缺口和逐点 evidence。
- 第一版不采用“先拆分需求点、再单独搜索证据”的两阶段 Agent 调用，避免额外执行成本和两次响应之间的需求点漂移。
- Feature Agent 合约必须要求返回非空 `requirement_points` 数组，并停止要求 Agent 返回可直接采用的顶层 `conclusion`、`gaps`、`confidence` 或顶层 `evidence`。
- 阶段六的合约变化只适用于 `Feature Item`；`Defect Item` 的 Agent 合约保持既有行为。

---

## 9. 已废弃的替代方案：补充需求内容

曾讨论通过用户输入引入 `Supplemental Requirement Context`，该方案已撤销并禁止实现：

- 需求内容仅以禅道中获取的原始描述为唯一来源。
- Analyzer、Skill、PRD、Debug Bundle、Summary Report 和最终 JSON 均不得实现或输出“补充需求上下文”能力。
- 不新增 `--supplemental-requirement-context` 参数，也不在 clues file 中新增同类字段。
- 用户通过 Skill 明确输入“补充需求内容: ...”时，Skill 应拒绝执行分析，提示先在禅道更新需求后重试。
- Skill 不得将“补充需求内容”静默转换为 `Code Clue`。
- 被拒绝的补充需求输入不启动 Analyzer，也不生成分析产物。

允许用户提供的行为描述型代码线索仅为 `Search Hint`，不得用于拆分或变更 `Requirement Point`。

---

## 10. 与阶段七的关系

- 阶段六负责所有 `Feature Item` 的 `Requirement Point` 拆分、基础逐点证据追溯和基础条目汇总。
- 阶段七只在显式配置多侧工程时扩展阶段六结果，追加 `Code Side`、`Analysis Scope`、`Responsibility Hint`、`Candidate Location` 和范围受限结论。
- 阶段七不得重新定义阶段六的需求来源、需求点拆分或基础证据有效性规则。

---

## 11. 待确认分支

- 暂无。阶段六设计已确认，下一步应另行编写实施计划；本文件确认完成后不自动进入代码实现。
