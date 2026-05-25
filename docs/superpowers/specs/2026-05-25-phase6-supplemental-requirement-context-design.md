# zentao-story-prd-analyzer - 阶段六：补充需求上下文

**日期**: 2026-05-25
**版本**: 0.1
**状态**: 设计讨论中

---

## 1. 背景与目标

阶段一到阶段五能够从禅道读取条目，基于目标仓库中的代码证据生成 PRD/ISSUE，并保留证据可追溯信息。但禅道中的 Feature Item 可能缺少本次评审所需的具体预期行为，用户目前只能提供代码线索，不能提供明确区分于原始条目的补充需求约束。

阶段六引入 `Supplemental Requirement Context`（补充需求上下文），让用户能够为单个 Feature Item 提供只作用于本次分析的附加预期行为。分析器应在不改写禅道原始描述的前提下，以原始需求和补充需求构成的合并目标评估实现完成度。

---

## 2. 已确认边界

- 补充需求上下文仅适用于 `story` 与 `requirement`，不适用于 `bug`、`ticket` 或 `feedback`。
- 补充需求上下文必须绑定到一个明确的禅道条目 ID，不支持对批量运行中的所有条目施加全局补充内容。
- 补充需求上下文不修改、不替换、不回写禅道原始描述。
- 当补充需求上下文存在时，完成度、缺口与验证建议针对“原始需求 + 补充需求”的合并目标进行评估。
- 第一版不要求每条 gap 或 verification 分别标注其来源；PRD 通过独立展示补充上下文和声明合并评估范围说明依据。
- 不将补充需求上下文混入 `Code Clue`、`Search Hint` 或 `Seed Path`。

---

## 3. 输入入口

### 3.1 单条 CLI 输入

单条 Feature Item 分析支持：

```bash
python3 main.py \
  --module requirement \
  --id 5923 \
  --analyze \
  --supplemental-requirement-context "回拨模式期间收到来电应拒绝，并保持 25 分钟计时继续运行。"
```

约束：

- `--supplemental-requirement-context` 必须与 `--id` 同时使用。
- `--module` 必须属于 Feature Item 类型。
- 在没有 `--id` 的批量运行中提供该参数应直接报错。
- 显式提供 `--supplemental-requirement-context` 时必须同时提供 `--analyze`；仅抓取模式没有合法消费者，应返回输入配置错误。

### 3.2 按 ID 文件输入

`--clues-file` 的单条对象扩展 `supplemental_requirement_context` 字段：

```json
{
  "5923": {
    "supplemental_requirement_context": "回拨模式期间收到来电应拒绝，并保持 25 分钟计时继续运行。",
    "clues": ["callback", "CallBackMode"],
    "paths": ["src/ecall/xcall.c"]
  }
}
```

该字段只应用到键名所标识的单个 Feature Item。

### 3.3 Skill 自然语言触发

通过 `SKILL.md` 触发时，Agent 可从如下指令中提取按 ID 绑定的补充内容：

```text
分析禅道需求 5923，补充需求内容: 回拨模式期间收到来电应拒绝，并保持 25 分钟计时继续运行。
```

Skill 只负责识别用户提供的条目 ID 和补充内容，并将其映射为 analyzer CLI 参数；它不得将补充内容伪装为代码线索，也不得在自身重新实现完成度分析。

Skill 的自然语言模块映射规则：

- 用户仅说“需求”时，默认映射为 `--module requirement`。
- 用户明确说 `requirement` 或“用户需求”时，映射为 `--module requirement`。
- 用户明确说 `story` 或“软件需求”时，映射为 `--module story`。
- 选定模块后若获取条目失败，不自动改用另一 Feature Item 模块重试；应报告失败并提示用户明确条目类型。

---

## 4. 输入校验

- 补充需求上下文允许中文、换行与普通业务描述文本。
- 空字符串或仅空白字符视为未提供补充上下文。
- 非空内容最多 4000 个字符；超过限制直接报错，不做静默截断。
- 单条 CLI 参数和 `--clues-file` 对同一条目同时提供非空补充需求时，直接报冲突错误，不拼接且不静默覆盖。
- 缺陷类条目提供补充需求上下文时，直接报参数错误。
- 所有补充需求输入应在任何条目进入分析之前整体校验；批量输入中任意一项非法时，整个运行失败，不生成部分分析结果。
- `--clues-file` 中未匹配到本次实际获取条目的补充需求不参与本次校验和消费，也不输出警告。
- 未启用 `--analyze` 时不读取或校验 `--clues-file` 中可能存在的补充需求字段。
- 校验错误可指出条目 ID 与失败原因，但不得在错误信息中回显补充需求全文。
- 补充需求输入校验失败时进程返回 exit code `3`，表示用户提供的分析输入配置无效。
- 返回 exit code `3` 时，不创建 PRD、summary report 或 debug bundle。

拒绝截断的原因是：补充需求属于分析依据，截断后的内容可能改变完成度结论。

---

## 5. Prompt 与分析语义

Feature Item 的 prompt 应将补充需求上下文作为独立区块，与禅道条目原始描述明确分离，并明确：

- 补充需求是本次分析需要验证的预期行为。
- 补充需求不是代码线索，也不是已经实现的事实。
- `conclusion`、`gaps` 与 `verification` 针对原始描述和补充需求组成的合并目标。

Defect Item prompt 不接受补充需求上下文。

---

## 6. 数据契约

补充需求上下文属于本次分析输入，不写入代表禅道原始数据的 `ZentaoItem`。`AnalysisResult` 增加：

```python
supplemental_requirement_context: str = ""
supplemental_requirement_context_source: str = ""  # cli | clues_file
```

即使 Agent 调用失败，诊断用的 `AnalysisResult` 仍保留这两个字段，从而让 PRD 与 debug bundle 可以复核本次分析依据。

最终 JSON 与 summary 从 `supplemental_requirement_context` 是否非空派生布尔索引，不暴露内容或来源。

---

## 7. PRD、Debug Bundle 与 Summary

### 7.1 PRD Document

存在补充需求上下文时，PRD 在原始摘要之后单独显示：

```md
## 原始需求摘要

{禅道原文}

## 人工补充需求上下文

{补充需求原文}
```

PRD 还应明确完成度结论基于原始需求与人工补充需求的合并目标。

### 7.2 Debug Bundle

补充需求上下文应进入发送给 Agent 的脱敏 prompt，并额外写入独立的脱敏结构化文件：

```json
{
  "items": [
    {
      "item_id": "5923",
      "source": "cli",
      "content": "回拨模式期间收到来电应拒绝，并保持 25 分钟计时继续运行。"
    }
  ]
}
```

文件名为 `supplemental_requirement_context.json`。其中 `source` 为 `cli` 或 `clues_file`，用于复核本次分析输入来源及冲突校验行为。Debug bundle 应按业务敏感资料管理。

### 7.3 Summary Report

`summary_report.json` 保持机器可读索引职责，不保存补充需求上下文全文，但每个 item 增加：

```json
{
  "has_supplemental_requirement_context": true
}
```

最终 stdout JSON 的 `analysis` 每项同样增加 `has_supplemental_requirement_context` 布尔字段，供自动化调用方识别本条结论是否基于额外人工输入。正文与输入来源只保留在 PRD 和 debug bundle 中。

---

## 8. 暂不纳入范围

- 缺陷类条目的人工复现或现场上下文补充。
- 对每一条 gap 或 verification 建立需求来源标注。
- 条款级需求 ID 或需求到证据的逐条关联。
- 将补充需求回写禅道。
- 将补充需求作为全局输入应用于多个条目。
