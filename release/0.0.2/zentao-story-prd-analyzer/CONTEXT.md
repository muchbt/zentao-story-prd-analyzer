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

**Protocol Hint**:
指向跨仓库通信协议标识的 Search Hint，例如通信命令、消息 ID 或协议字段。
_Avoid_: Requirement Source、Code Evidence、RPC

**Protocol Hint Type**:
Protocol Hint 在通信协议中的层级，包括 `cmd_id`、`msg`、`field` 或 `text`。
_Avoid_: 代码符号类型、证据类型

**Rejected Clue**:
因越界、不存在或不是文件而未加载的 Seed Path。
_Avoid_: 缺少实现

**Code Evidence**:
支撑或限制 Completion Assessment 的具体源码引用。
_Avoid_: Search Hint、Code Impact Analysis

**Cited Evidence Location**:
Agent 明确作为结论依据引用的源码文件与行号范围。
_Avoid_: 搜索命中、Seed Path

**Role Evidence Status**:
某个 Repository Role 对特定 Requirement Point 或 Protocol Hint 的证据命中状态。
_Avoid_: Completion Assessment、搜索日志

**Protocol Trace Status**:
Protocol Hint 对应的跨 Repository Role 证据闭环状态。
_Avoid_: Role Evidence Status、Completion Assessment

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
被分析 Feature Item 或 Defect Item 对应实现所在的一个本地代码仓库。
_Avoid_: analyzer 源码仓库、输出目录

**Target Repository Set**:
一次分析中共同承载同一 Feature Item 或 Defect Item 实现依据的一个或多个 Target Repository。
_Avoid_: 多次独立分析结果、输出目录集合

**Repository Role**:
Target Repository Set 中用于区分代码职责边界的用户可读名称。
_Avoid_: 路径别名、模块名推断

**Primary Repository Role**:
一次分析中优先理解需求或缺陷触发语境的 Repository Role。
_Avoid_: 唯一证据范围、所有者断言

**Agent CLI Skill**:
供 Codex 或 Claude Code 等环境发现并触发 analyzer 的安装式调用包装。
_Avoid_: `SKILL.yaml`、Python package

**Structured Clue File**:
保存 Search Hint、Protocol Hint、Seed Path 与仓库角色输入的机器可读线索文件。
_Avoid_: Requirement Source、PRD Document

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
- 跨 **Repository Role** 的 **Completion Assessment** 不能由单侧 **Code Evidence** 单独确认完成。
- 跨仓库输出以 **Requirement Point** 为主维度，以 **Repository Role** 作为证据子维度。
- **Implementation Recommendation** 与现有代码事实及完成度证据分开展示，并明确标记为建议。
- 一个成功生成文档的 **Feature Item** 产生一个 **PRD Document**。
- 一个成功生成文档的 **Defect Item** 产生一个 **ISSUE Document**。
- **PRD Document** 同时包含可理解的需求整理与代码依据约束的完成度分析；二者不可相互替代。
- **Search Hint** 只引导搜索，不是 **Requirement Source** 或 **Code Evidence**。
- **Protocol Hint** 是 **Search Hint** 的一种，表示跨 **Repository Role** 的通信协议线索。
- **Protocol Hint Type** 用于指导搜索起点和闭环判定重点，不能替代 **Code Evidence**。
- **Protocol Hint** 可限定适用的 **Repository Role**；未限定时适用于整个 **Target Repository Set**。
- 一个 **Target Repository Set** 包含一个或多个带 **Repository Role** 的 **Target Repository**。
- **Repository Role** 由用户提供，用于表达 MCU、SoC、应用、Bootloader 或协议栈等代码职责边界。
- **Primary Repository Role** 只影响搜索和展示优先级，不限制 **Code Evidence** 的有效范围。
- 单仓输入在内部视为只有隐式 `main` **Repository Role** 的 **Target Repository Set**，但单仓输出不展示角色维度。
- **Structured Clue File** 可承载按条目隔离的 **Search Hint**、**Protocol Hint** 与带 **Repository Role** 的 **Seed Path**。
- **Agent CLI Skill** 可将用户自然语言整理为 **Structured Clue File**，但不得改变 **Requirement Source**。
- **Agent CLI Skill** 可自动转写用户明确提供的线索；需要猜测线索类型、仓库角色或条目归属时必须先取得用户确认。
- **Seed Path** 必须位于 **Target Repository** 内且指向文件，否则成为 **Rejected Clue**。
- 多仓 **Cited Evidence Location** 必须包含 **Repository Role**、仓库相对路径和行号范围。
- **Cited Evidence Location** 可支撑已实现、缺口或限制结论，但单独存在不等同于实现完成。
- **Role Evidence Status** 表示角色维度的命中、未命中或不确定状态，不等同于最终 **Completion Assessment**。
- **Protocol Trace Status** 可为 closed_loop、partial、not_found 或 ambiguous，不等同于最终 **Completion Assessment**。
- **Analyzer Process** 是生成输出的唯一写入者。
- **Agent CLI Subprocess** 只读取和搜索 **Target Repository Set**，不得写入源码、配置、测试或 analyzer 输出。
- **ISSUE Document** 是输出类型，不是禅道输入模块名称。
- **Agent CLI Skill** 调用 analyzer 分析 **Target Repository Set**；它不是新的分析阶段。

## Example Dialogue

> **Dev:** “用户直接粘贴完整需求并提供编号时，还要再从禅道读取描述吗？”
> **Domain expert:** “不要。该运行的 **Requirement Source** 就是 **Provided Requirement**，编号只用于关联输出。”

> **Dev:** “代码里找到了 `XCALL_STATUS_INTERNAL_CALLBACK_MODE`，可以把它写成需求已定义的术语吗？”
> **Domain expert:** “只能作为代码侧候选上下文展示；除非需求原文定义了含义，否则它不是需求事实。”

> **Dev:** “用户提供了 MCU 和 SoC 通信协议的命令 ID，可以把它当作需求点吗？”
> **Domain expert:** “不能。它是 **Protocol Hint**，只能指导跨仓库搜索，不能改写 **Requirement Source**。”

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
- “RPC”曾被用来泛指 MCU 与 SoC 的跨仓库关联；已明确采用 **Protocol Hint** 表达通信协议线索，避免把协议线索误写成需求来源或代码证据。
- “Repository Role”和“Seed Path”曾被混用；已明确 **Repository Role** 标识仓库职责，**Seed Path** 标识仓库内起始文件。
