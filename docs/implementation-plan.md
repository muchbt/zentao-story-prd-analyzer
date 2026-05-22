# zentao-story-prd-analyzer 实施计划

## 背景

目标是结合禅道命令行工具 `zentao` 和代码代理能力，完成从禅道条目获取、代码仓库分析、LLM 判断到 PRD/ISSUE 文档生成的闭环。

当前仓库已有 `SKILL.yaml` 和 `main.py` 原型，但仍存在以下差距：

- 禅道命令行工具应统一使用 `zentao`。
- 默认配置文件位于 `~/.config/zentao/zentao.json`，也可通过 `--config` 或 `ZENTAO_CONFIG_FILE` 指定。
- 当前只初步支持 story 分析，尚未完整覆盖 requirement、bug、ticket、feedback 等禅道条目。
- Claude 和 OpenCode 调用仍是占位函数。
- 日志、错误处理、参数校验、脱敏和用户交互仍不完整。

## 阶段一：禅道 CLI 数据闭环

### 目标

建立稳定的禅道数据获取能力，支持用户输入工程、story、requirement、bug 或其他条目 ID 后，自动获取对应内容，并统一转换为结构化禅道条目。阶段一不判断完成度、根因或修复建议。

### 范围

- 封装真实的 `zentao` 命令调用。
- 支持 `zentao login`、`zentao profile`、`zentao get`、`zentao list`。
- 支持通过环境变量、配置文件或已有 profile 完成登录。
- 明确沙箱或新环境的首次登录方式：先执行 `zentao login -s <server> -t <token>`，或通过 `ZENTAO_SERVER` 与 token/用户名密码由程序登录。
- 支持按单个 ID 获取详情。
- 支持按 project/product/execution 过滤列表。
- 建立模块映射，例如：
  - `story`：软件需求。
  - `requirement`：用户需求。
  - `bug`：缺陷。
  - `task`：任务。
  - `ticket` 或 `feedback`：缺陷类或反馈类输入。
- 将禅道返回内容统一转换为内部结构化对象。

### 交付物

- `ZentaoClient` 或等价封装模块。
- 统一的条目数据结构，包括 ID、类型、标题、描述、状态、优先级、所属项目、附件或备注等字段。
- CLI 参数或环境变量说明。
- 基础错误处理，包括未登录、权限不足、对象不存在、网络超时和返回格式异常。

### 验收点

- 能通过 `zentao story <id> --format json` 或等价命令获取 story 详情。
- 能通过 `zentao requirement <id> --format json` 获取 requirement 详情。
- 能通过 `zentao bug <id> --format json` 获取 bug 详情。
- 能在失败时输出明确错误原因，不泄露密码、token 等敏感信息。

## 阶段二：代码扫描与 Agent 分析闭环

### 目标

扫描本地代码仓库，提取与禅道条目相关的代码上下文，交给 LLM 或代码代理分析。对于功能类条目输出完成度；对于 bug 类条目输出可能问题点和验证建议。

### 范围

- 根据条目标题、描述、关键词、模块名和相关文件线索收集代码上下文。
- 支持全文检索和文件名检索，优先使用 `rg`。
- 支持限制文件数量、单文件行数和总 token 预算。
- 支持按语言扩展收集范围，包括 C/C++、Python、Shell、Batch、Makefile、CMake 等。
- 区分功能类和缺陷类 Prompt。
- 功能类输出：
  - 完成度。
  - 已实现证据。
  - 未实现或部分实现点。
  - 相关文件和函数。
  - 修改建议。
- 缺陷类输出：
  - 可能根因。
  - 疑似问题文件和函数。
  - 影响范围。
  - 复现或验证建议。
  - 修复方向。

### 交付物

- 代码扫描器。
- 代码摘要器。
- 功能分析 Prompt 模板。
- Bug 分析 Prompt 模板。
- 统一的 LLM 分析结果结构。

### 验收点

- 给定一个 story，能输出完成、部分完成或未完成结论，并给出代码证据。
- 给定一个 bug，能输出可能问题点、影响范围和验证建议。
- 当相关代码不足时，能明确标记“证据不足”，而不是编造结论。
- 扫描过程可配置，避免把整个大型仓库无控制地塞给 LLM。

## 阶段三：PRD/ISSUE 文档生成闭环

### 目标

将禅道条目内容、代码分析结果和 LLM 结论整理为可阅读、可追踪、可复核的 PRD 或 ISSUE 文档。

### 范围

- 为功能类条目生成 PRD 文档。
- 为缺陷类条目生成 ISSUE 文档。
- 输出 Markdown 文件。
- 生成汇总报告。
- 保留输入条目 ID、来源类型、分析时间、使用的 Agent、相关文件等追踪信息。

### PRD 输出建议

PRD 文档应包含：

- 条目来源：story 或 requirement。
- 条目 ID、标题、状态和原始描述摘要。
- 需要完成的功能列表。
- 当前实现完成度。
- 实现差异分析表。
- 修改建议。
- 优先级评分。
- 相关代码文件和函数。
- 验证建议。

### ISSUE 输出建议

ISSUE 文档应包含：

- 条目来源：bug、ticket、feedback 或其他 issue 类输入。
- 条目 ID、标题、状态和原始描述摘要。
- 问题描述。
- 可能根因。
- 疑似影响范围。
- 相关文件和函数。
- 修复建议。
- 复现或验证建议。
- 优先级评分。

### 交付物

- PRD Markdown 模板。
- ISSUE Markdown 模板。
- `prd_docs` 或等价输出目录。
- `summary_report.json` 汇总文件。

### 验收点

- story/requirement 默认生成 PRD。
- bug/issue 类条目默认生成 ISSUE。
- 每份文档都能追溯到禅道原始条目和代码分析证据。
- LLM 分析失败时仍能生成带错误原因的诊断文档。

## 阶段四：多 Agent 适配与用户体验闭环

### 目标

适配 Claude、Codex、OpenCode 等不同 Agent，并提供清晰、可诊断、用户友好的命令行体验。

### 范围

- 抽象统一的 Agent 调用接口。
- 支持 `codex`、`claude`、`opencode`。
- 优先兼容禅道 CLI 的 `add-skill` 和 `add-mcp` 能力。
- 支持通过配置选择 Agent。
- 提供详细日志，包括：
  - 输入参数。
  - 禅道命令调用摘要。
  - 代码扫描范围。
  - Prompt 类型。
  - Agent 名称。
  - 输出路径。
  - 错误原因。
- 对敏感信息进行脱敏。
- 支持静默模式和详细模式。
- 支持机器可读输出，便于 CI 或其他工具集成。

### 交付物

- `AgentClient` 或等价适配层。
- Codex 适配实现。
- Claude 适配实现。
- OpenCode 适配实现。
- 日志模块。
- 用户配置示例。
- README 使用说明。

### 验收点

- 用户能通过参数或环境变量选择 Agent。
- 未配置某个 Agent 时，能给出明确配置提示。
- 日志能帮助定位失败发生在登录、获取禅道数据、代码扫描、LLM 调用还是文档生成阶段。
- 日志不会输出密码、token、API key 等敏感信息。
- 支持在 CI 或脚本中读取最终生成路径和汇总结果。

## 阶段五：证据可追溯性增强

### 目标

在阶段一到阶段四已形成可运行闭环后，增强代码线索输入、证据位置记录和 debug bundle 审计能力，让用户可以复核 Agent 到底看过哪些代码、引用了哪些代码作为结论依据。

### 范围

- 支持用户显式提供代码线索：
  - `--keywords`
  - `--paths`
  - `--symbols`
  - `--clues-file`
- 支持全局线索和按禅道条目 ID 的专属线索。
- 路径线索必须限制在 `repo_path` 内，越界线索记录为 rejected clue，不读取内容。
- 代码收集器默认记录 collected locations，即实际喂给 Agent 的文件名和行号范围。
- Prompt 和分析结果优先支持结构化 evidence，旧字符串 evidence 作为 fallback。
- debug bundle 默认保存 collected locations 与 cited evidence locations，不默认保存完整代码内容。
- PRD/ISSUE 文档只展示关键引用证据。
- `summary_report.json` 增加 collected/cited/rejected 计数和 debug bundle 索引。

### 交付物

- 代码线索解析与合并模块。
- 扩展后的代码收集结果结构。
- 结构化 evidence 解析能力。
- debug bundle 证据位置文件。
- PRD/ISSUE 关键代码证据表格。
- summary 证据计数字段。

### 验收点

- 用户可通过 CLI 或 clues file 提供代码线索。
- 越界路径线索不会读取仓库外文件。
- debug bundle 默认包含实际收集位置和 Agent 引用位置。
- 不传 `--debug-include-code` 时不保存完整代码内容。
- 旧 evidence 字符串仍可兼容。
- 无可定位证据时结论和置信度按证据不足规则降级。

## 建议实施顺序

1. 先完成阶段一，确保禅道数据获取可靠。
2. 再完成阶段二，让分析结果有足够代码证据支撑。
3. 接着完成阶段三，把结果稳定落盘为 PRD/ISSUE。
4. 完成阶段四，扩展 Agent 生态并提升用户体验。
5. 最后完成阶段五，增强证据可追溯性和批量分析线索输入。

该顺序的原因是：禅道数据是输入源，代码分析依赖输入源，文档生成依赖分析结果，多 Agent 和用户体验依赖前三个阶段的稳定接口；证据可追溯性增强建立在已有闭环之上，不重新定义前四阶段。

## 暂不纳入范围

- 自动修改代码。
- 自动提交 Git commit。
- 自动回写禅道条目。
- 自动删除或关闭禅道条目。
- 未经用户确认的批量写操作。

这些能力涉及更高风险，应在读取、分析、文档生成闭环稳定后，单独设计权限、确认和审计机制。
