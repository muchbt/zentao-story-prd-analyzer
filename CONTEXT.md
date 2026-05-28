# Zentao Story PRD Analyzer

本上下文描述如何将需求或缺陷输入与本地代码依据结合，形成可复核的 PRD 或 ISSUE 文档。

## Language

### 输入

**Zentao Item**:
从禅道读取的输入对象，例如 `story`、`requirement`、`bug`、`task`、`ticket` 或 `feedback`。
_Avoid_: ISSUE、输出文档

**Provided Requirement**:
用户主动提交的完整需求正文，并由用户确认需求 ID 的功能需求输入。
_Avoid_: Search Hint、补充说明

**Provided Requirement Title**:
用户对 Provided Requirement 确认的文档标题。
_Avoid_: 模型临时摘要、未经确认的推荐标题

**Requirement Source**:
一次功能分析所采用的唯一需求正文来源，即 Zentao Item 的描述或 Provided Requirement 的正文。
_Avoid_: Code Clue、代码搜索结果

**Feature Item**:
用于描述期望产品行为的输入，来源可以是禅道需求/故事，也可以是 Provided Requirement。
_Avoid_: PRD Document

**Defect Item**:
用于描述待调查问题、失败或反馈的 Zentao Item。
_Avoid_: ISSUE Document

### 需求理解与分析

**Requirement Interpretation**:
将 Requirement Source 整理为便于阅读的摘要、范围、术语、规则、场景、矩阵或流程说明。
_Avoid_: Completion Assessment、Implementation Recommendation

**Requirement Point**:
Feature Item 中可独立验证的一条期望行为单元。
_Avoid_: 整条需求、Code Evidence、测试步骤

**Code Impact Analysis**:
对与 Feature Item 相关的现有代码区域及其可能影响的分析。在 PRD 中与 Completion Assessment 的证据位置合并展示为统一代码位置总览，但关联位置本身不自动支撑完成度结论。
_Avoid_: Completion Assessment、Requirement Source

**Completion Assessment**:
基于 Requirement Points 与有效 Code Evidence 得出的实现完成度、缺口和可信度结论。可信度按有确认证据的需求点比例分级：全部完成为高，至少有一个确认为中，无确认为低。
_Avoid_: Requirement Interpretation、搜索命中

**Implementation Recommendation**:
针对 Feature Item 提议的代码或测试变更，可包含新模块、新接口或伪代码。
_Avoid_: 现有实现事实、Code Evidence

**Analysis Result**:
针对 Feature Item 或 Defect Item 形成的代码依据分析结论。
_Avoid_: 原始输入、生成文档

### 代码依据

**Code Clue**:
用户提供的代码定位辅助信息。
_Avoid_: Requirement Source、Code Evidence

**Search Hint**:
写入 Agent 提示、用于指导代码搜索的文本线索。
_Avoid_: Seed Path、Code Evidence

**Seed Path**:
被预加载为 Agent 起始上下文的仓库内文件路径。
_Avoid_: Search Hint、Cited Evidence Location

**Rejected Clue**:
因越界、不存在或不是文件而未加载的 Seed Path。
_Avoid_: 缺少实现

**Code Evidence**:
支撑或限制 Completion Assessment 的具体源码引用。
_Avoid_: Search Hint、Code Impact Analysis

**Cited Evidence Location**:
Agent 明确作为结论依据引用的源码文件与行号范围。
_Avoid_: 搜索命中、Seed Path

### 输出与执行边界

**PRD Document**:
解释 Feature Item 需求，并以统一代码位置总览合并代码影响与完成度证据，包含需求解读、代码依据、完成度评估、缺口和建议的可复核 Markdown 文档。
_Avoid_: Feature Item、需求原文

**ISSUE Document**:
总结 Defect Item、代码依据、可能根因、影响范围和修复建议的 Markdown 文档。
_Avoid_: Bug 输入、PRD Document

**Summary Report**:
索引已分析输入、生成文档、分析状态、依据数量和诊断路径的机器可读汇总。
_Avoid_: PRD Document、完整分析正文

**Debug Bundle**:
保存复核一次 analyzer 运行所需输入摘要、提示、响应、日志与代码依据位置的本地诊断包。
_Avoid_: PRD Document、Summary Report

**Analyzer Process**:
拥有生成文档、汇总与诊断输出写入职责的运行进程。
_Avoid_: Agent CLI Subprocess

**Agent CLI Subprocess**:
由 Analyzer Process 调用、只读取和搜索目标仓库并返回结构化分析载荷的 Agent 进程。
_Avoid_: Analyzer Process、文档写入者

**Target Repository**:
被分析 Feature Item 或 Defect Item 对应实现所在的本地代码仓库。
_Avoid_: analyzer 源码仓库、输出目录

**Agent CLI Skill**:
供 Codex 或 Claude Code 等环境发现并触发 analyzer 的安装式调用包装。
_Avoid_: `SKILL.yaml`、Python package

## Relationships

- 一个 **Feature Item** 在一次分析中只使用一个 **Requirement Source**。
- 一个 **Provided Requirement** 只有在用户确认需求 ID 后才能成为 **Feature Item**。
- 一个 **Provided Requirement** 在正式分析前必须具备用户确认的 **Provided Requirement Title**；Agent 可推荐标题但不能将未确认标题作为正式输出身份。
- **Provided Requirement** 的 ID 仅用于标识和文档关联，不触发禅道读取或需求正文合并。
- 一个 **Feature Item** 可拆分为一个或多个 **Requirement Points**。
- **Requirement Points** 只能源于当前 **Requirement Source**，不能由 **Code Clues** 或代码搜索结果新增或改写。
- **Requirement Interpretation**、**Code Impact Analysis** 与 **Completion Assessment** 必须针对同一个 **Feature Item** 和同一次分析运行。
- **Requirement Interpretation** 保留面向读者的固定章节；正文不足时明确说明需求来源信息不足，不编造内容或静默删节。
- **Requirement Interpretation** 可展示明确标记为代码侧候选上下文的信息，但该信息不定义需求含义，也不产生新的 **Requirement Point**。
- **Code Impact Analysis** 可展示经位置校验的相关源码；相关代码位置不自动证明需求已完成。
- **Completion Assessment** 以逐点有效 **Code Evidence** 为依据；无依据不能确认完成或缺口。
- **Implementation Recommendation** 与现有代码事实及完成度证据分开展示，并明确标记为建议。
- 一个成功生成文档的 **Feature Item** 产生一个 **PRD Document**。
- 一个成功生成文档的 **Defect Item** 产生一个 **ISSUE Document**。
- **PRD Document** 同时包含可理解的需求整理与代码依据约束的完成度分析；二者不可相互替代。
- **Search Hint** 只引导搜索，不是 **Requirement Source** 或 **Code Evidence**。
- **Seed Path** 必须位于 **Target Repository** 内且指向文件，否则成为 **Rejected Clue**。
- **Cited Evidence Location** 可支撑已实现、缺口或限制结论，但单独存在不等同于实现完成。
- **Analyzer Process** 是生成输出的唯一写入者。
- **Agent CLI Subprocess** 只读取和搜索 **Target Repository**，不得写入源码、配置、测试或 analyzer 输出。
- **ISSUE Document** 是输出类型，不是禅道输入模块名称。
- **Agent CLI Skill** 调用 analyzer 分析 **Target Repository**；它不是新的分析阶段。

## Example Dialogue

> **Dev:** “用户直接粘贴完整需求并提供编号时，还要再从禅道读取描述吗？”
> **Domain expert:** “不要。该运行的 **Requirement Source** 就是 **Provided Requirement**，编号只用于关联输出。”

> **Dev:** “代码里找到了 `XCALL_STATUS_INTERNAL_CALLBACK_MODE`，可以把它写成需求已定义的术语吗？”
> **Domain expert:** “只能作为代码侧候选上下文展示；除非需求原文定义了含义，否则它不是需求事实。”

> **Dev:** “建议新增一个仲裁器模块是否表示仓库已有该实现？”
> **Domain expert:** “不是。它属于 **Implementation Recommendation**，必须与已有代码关联和 **Code Evidence** 分开。”

## Flagged Ambiguities

- “ISSUE”曾同时表示输入和输出；已明确 **ISSUE Document** 仅为输出类型。
- “需求正文”曾被限制为只来自禅道；已明确 **Provided Requirement** 可作为独立且唯一的正式输入来源。
- “Provided Requirement 的编号”曾不明确是否触发查询；已明确编号只作标识和关联，不触发禅道读取或合并。
- “Provided Requirement 的标题”曾不明确由用户还是模型决定；已明确标题由用户确认，Agent 只能在确认前提出建议。
- “可读 PRD”曾不明确是否替代完成度分析；已明确 **PRD Document** 必须同时包含需求整理与 **Completion Assessment**。
- “代码相关”曾被误解为实现证据；已明确 **Code Impact Analysis** 不自动支撑完成度结论。
- “需求缺少范围或术语”曾不明确是否删节或补齐；已明确固定章节保留并说明来源信息不足。
- “代码中出现的术语或范围”曾被误解为需求定义；已明确只能作为带来源标识的候选上下文。
- “建议新增模块或接口”曾被误解为现有实现；已明确其属于 **Implementation Recommendation**。
- “Agent 写入文档”会模糊安全边界；已明确仅 **Analyzer Process** 写入正式产物。
