# zentao-story-prd-analyzer - 阶段七：多侧范围与责任侧分析

**日期**: 2026-05-26
**版本**: 0.3
**状态**: 已确认，待重写实施计划

---

## 1. 背景与目标

实际目标工程可能在同一个根目录下包含多个独立实现侧，例如：

```text
root/
├── mcu_src/
└── soc_src/
```

现有分析器把 `repo_path` 作为单一 Target Repository 提交给 Agent 搜索，没有表达代码侧别、允许分析的范围或需求点级责任归属。对 MCU/SOC 全目录无边界搜索，可能扩大搜索耗时与 Agent 上下文消耗；只以条目级 evidence 评价完成度，又不能区分一个 requirement 中分别由 MCU、SOC 或双方承担的不同预期行为。

阶段七基于阶段六输出的 `Requirement Point`，引入 `Code Side`、`Analysis Scope`、`Responsibility Hint` 与 `Candidate Location`，使 Feature Item 在多侧仓库中能够按明确范围和责任侧评估实现，而不是将“选入分析的所有侧”误当成“每个需求点都必须实现的侧”。

---

## 2. 与既有阶段的边界

- 阶段六负责所有 Feature Item 的 `Requirement Point` 拆分、逐点证据追溯和基础结论汇总。
- 阶段七消费阶段六产生的 `Requirement Point`，只为显式多侧 Target Repository 增加范围、责任侧和候选位置规则。
- 阶段七不得在多侧模式下重新定义阶段六的需求点拆分语义或基础证据有效性规则。
- 需求内容仅以从禅道获取的 Feature Item 原始描述为依据；用户提供的 Code Clue 只能辅助检索代码，不能补充或修改需求。
- Code Clue 即使采用行为描述文本，也不得作为 Requirement Point 拆分、责任侧判断或完成度结论的需求依据。
- 禅道未提供责任侧字段时，用户可以通过 `Responsibility Hint` 指定既有 Requirement Point 的实现归属；该输入属于归属元数据，不是补充需求内容。
- 本设计扩展阶段六已有的 `Requirement Point`，引入多侧责任归属及范围受限判断。
- 阶段七仅针对 Feature Item 的完成度分析；Defect Item 是否需要多侧根因链路另行设计。

---

## 3. 已确认领域规则

### 3.1 Code Side 与目录映射

- 一个 Target Repository 可包含多个 Code Side，例如 `mcu` 与 `soc`。
- Code Side 由逻辑名称到仓库内目录的映射定义，而不是由固定目录名称定义。
- 显式映射始终优先。
- 只有配置文件或用户参数显式提供 Code Side 映射时，才激活多侧分析能力与 Analysis Scope 约束。
- 若没有显式映射，即使根目录同时存在 `mcu_src/` 与 `soc_src/`，分析器也保持现有单仓库行为，不根据目录名称猜测侧别或要求选择范围。

示意配置：

```json
{
  "code_sides": {
    "mcu": "mcu_src",
    "soc": "soc_src"
  }
}
```

### 3.2 Analysis Scope

- Analysis Scope 是本次允许评估的 Code Side 逻辑名称集合。
- 单侧和跨侧使用同一模型，例如 `["soc"]`、`["mcu"]`、`["mcu", "soc"]`。
- 选择多个侧即表达跨侧分析，不新增固定的 `cross_side` 特例。
- 多侧 Target Repository 未提供 Analysis Scope 时，停止代码分析并提示用户选择范围；不得依据需求文本自动推断。
- Analysis Scope 只表示允许调查的侧，不表示每个需求点都必须在所有选中侧找到证据。
- 未提供显式 Code Side 映射的 Target Repository 保持现有单仓库分析行为，不引入 Analysis Scope 要求。

### 3.3 阶段六 Requirement Point 的多侧扩展

- `Requirement Point` 的拆分、基础状态、运行内 ID、逐点缺口和基础证据关联由阶段六定义，阶段七不得重复生成或改写这些基础语义。
- 阶段七在阶段六产生的每个 `Requirement Point` 上追加责任侧、责任侧来源、范围评估状态及必要的候选位置诊断信息。
- 一个既有 `Requirement Point` 可由 MCU 单侧、SOC 单侧或多个 Code Side 共同承担；这一责任关系只影响多侧核查边界，不改变需求点描述。

### 3.4 证据完整性边界

- 不得仅因 Analysis Scope 为 `["mcu", "soc"]` 就要求条目中 MCU 与 SOC 都必须有证据。
- 每个 Requirement Point 只要求其责任侧所需的 Code Evidence。
- SOC-only 需求点即便在跨侧分析范围内，也不得因为缺少 MCU 证据而被降级。
- 跨侧协议或链路需求点若缺少某个责任侧的有效证据，不得判定该需求点为完成。

### 3.5 责任侧判定

- Agent 根据从禅道获取的 Feature Item 原始需求描述为每个 Requirement Point 提出 `responsible_sides`；用户提供的有效 Responsibility Hint 可覆盖 Agent 对未明确归属的责任侧推断。
- 若禅道原始需求描述已明确声明某个 Requirement Point 的责任侧，与之冲突的 Responsibility Hint 属于无效输入，不得覆盖禅道记录。
- Responsibility Hint 只能关联已从禅道需求拆分出的 Requirement Point，并指定其负责实现的 Code Side；不得用于创建、拆分、合并或改变 Requirement Point 的预期行为。
- Responsibility Hint 不是 Code Clue，也不是 Analysis Scope；提供责任侧不会自动提供搜索线索或扩大本次可分析范围。
- Responsibility Hint 是可选输入；单侧或跨侧 Analysis Scope 均不因缺少该提示而拒绝启动分析。
- Analyzer 不得根据证据最终命中在哪个目录中，反向推断该 Requirement Point 本应由哪些 Code Side 承担。
- 当责任侧无法从禅道描述或有效 Responsibility Hint 可靠确定时，该 Requirement Point 必须标识为待确认，不得仅凭已找到的单侧代码判定完成。
- Agent 可基于禅道描述中具有明确工程归属含义的行为提出 `agent_inferred` 责任侧，例如发送 MCU 所属总线消息；该推断必须同时输出可复核理由。
- `agent_inferred` 责任侧推断合理且 Code Evidence 充分时，可支持 Requirement Point 判定为 `完成`；若无法给出可靠推断理由，则必须使用 `责任侧待确认`。

### 3.6 多侧附加状态

阶段六定义 `完成`、`部分完成`、`未完成` 与 `无法判断` 四种基础状态。阶段七仅在显式启用多侧分析时增加以下状态：

| 状态 | 含义 |
|------|------|
| `责任侧待确认` | 无法从禅道原始需求描述或有效 Responsibility Hint 可靠确定应由哪些 Code Side 承担 |
| `范围外未评估` | 责任侧已明确，但至少一个责任侧不在本次 Analysis Scope 中，本次不对该需求点作实现判断 |

状态边界：

- `责任侧待确认` 不是实现缺口，不进入已确认 gaps。
- `责任侧待确认` 与 `无法判断` 不同：前者尚不知道需要在哪些侧核查，后者已知责任侧但无法获得充分证据。
- 当 Analysis Scope 覆盖全部已知 Code Side 时，Agent 可以为 `责任侧待确认` 需求点搜索所有已选侧中的候选代码，但搜索命中不得反向确认责任侧，也不得将该点提升为 `完成`。
- `范围外未评估` 不属于 `无法判断` 或实现缺口；该状态表示用户本次选择的范围不覆盖该需求点所需核查侧。
- 存在任一 `责任侧待确认` 的 Requirement Point 时，Feature Item 的条目级结论不得为 `完成`。
- 存在任一 `范围外未评估` 的 Requirement Point 时，Feature Item 的条目级结论不得表示完整条目 `完成`。

### 3.7 多侧范围对条目级汇总的扩展

阶段六负责基础 `conclusion` 汇总。显式多侧分析中出现责任侧或范围状态时，阶段七追加以下修正规则：

| Requirement Point 状态组合 | Feature Item 条目级 `conclusion` |
|----------------------------|----------------------------------|
| 存在 `无法判断` 或 `责任侧待确认`，且没有已确认未完成点 | `无法判断` |
| 同时存在已确认缺口与 `无法判断` / `责任侧待确认` | `部分完成`，并明确仍存在未确认范围 |
| 范围内需求点全部为 `完成`，但存在 `范围外未评估` | 人工展示 `范围内完成`；机器字段兼容输出 `conclusion=无法判断`、`scope_conclusion=范围内完成`，并明确未评估的 Code Side 与需求点 |
| 范围内需求点全部为 `完成`，Analysis Scope 未覆盖全部已知 Code Side，但未识别出具体 `范围外未评估` 点 | 人工展示 `范围内完成`；机器字段兼容输出 `conclusion=无法判断`、`scope_conclusion=范围内完成`，并声明未选侧责任未被本次分析排除 |
| 存在范围内 `未完成` / `部分完成` 且存在 `范围外未评估` | `部分完成`，并明确结论仅覆盖 Analysis Scope |
| 范围内仅存在 `无法判断` / `责任侧待确认` 且存在 `范围外未评估` | `无法判断`，并明确仍存在范围外未评估点 |

汇总约束：

- `无法判断` 与 `责任侧待确认` 不得被汇总为已确认缺口。
- `范围外未评估` 不得进入 `GAPS` 或被汇总为证据不足；它只表示本次分析范围未覆盖完整责任侧。
- 当整体为 `部分完成` 且仍有未知范围时，PRD 不得只展示已确认 gaps 而隐藏待确认需求点。
- 当条目级结论为 `范围内完成` 时，PRD 必须显式声明该结论不是整个 Feature Item 的完整完成度结论。
- 当 Analysis Scope 仅选择已知 Code Sides 的子集时，即使没有识别出具体 `范围外未评估` 需求点，也不得汇总为完整 `完成`；不得凭局部分析推断未选侧不存在相关责任。
- 为兼容既有自动化调用方，stdout JSON 与 Summary Report 的顶层 `conclusion` 保持既有枚举；PRD 可展示新增的人读结论 `范围内完成`，机器输出通过 `scope_conclusion` 与 `is_scope_limited_analysis` 表达该含义。

### 3.8 多侧证据扩展

- 阶段六已经定义逐点结构化 `evidence`、位置校验和 PRD 去重展示；阶段七在每条逐点证据上追加所属 `Code Side`。
- Analyzer 除执行阶段六路径和行号校验外，还必须校验证据声明的 `side` 与实际路径所属侧一致，且该侧处于当前 Analysis Scope 中。
- Debug Bundle 在阶段六逐点关联基础上追加侧别与范围校验信息。

结构示例：

```json
{
  "requirement_points": [
    {
      "id": "RP-001",
      "description": "MCU 发送终止服务信号",
      "responsible_sides": ["mcu"],
      "status": "完成",
      "evidence": [
        {
          "side": "mcu",
          "path": "mcu_src/xcall_tx.c",
          "line_start": 40,
          "line_end": 55,
          "symbol": "send_terminate_service",
          "reason": "发送终止服务信号"
        }
      ]
    }
  ]
}
```

---

## 4. PRD Document

阶段六已经在 Feature Item 的 PRD 中生成基础 `## 需求点完成情况` 表格。阶段七在显式多侧分析时为该表格追加责任侧及其来源展示：

```md
## 实现完成度

- **结论**：部分完成
- **可信度**：中

## 需求点完成情况

| ID | 需求点 | 责任侧 | 状态 | 说明 |
|----|--------|--------|------|------|
| RP-001 | MCU 发送终止服务信号 | MCU | 完成 | 已找到发送逻辑 |
| RP-002 | SOC 收到信号后退出服务 | SOC | 完成 | 已找到状态切换逻辑 |
| RP-003 | MCU/SOC 消息字段一致 | MCU, SOC | 无法判断 | 缺少 MCU 侧字段定义证据 |

## 关键代码证据
```

规则：

- 在阶段六基础列之外，表格展示每个 Requirement Point 的责任侧与责任侧来源；`agent_inferred` 应显示为“推断”，区别于禅道明确或用户提示。
- 对 `agent_inferred` 的责任侧，PRD 应显示简短的 `responsibility_reason`，使评审者可以核查责任归属为何从禅道行为描述推导得出。
- 对 `responsibility_hint` 来源的责任侧，PRD 只显示来源为“用户提示”，不显示原始匹配片段；原提示及应用关系仅在 Debug Bundle 中留存。
- `差异与缺口` 仅展示已确认缺口；状态为 `无法判断`、`责任侧待确认` 或 `范围外未评估` 的需求点必须在需求点表格中可见，不得转换为 gap。
- 对状态为 `责任侧待确认` 的需求点，PRD 仅提示查看 Debug Bundle 或提供 Responsibility Hint 后重试，不展示全范围搜索得到的候选代码位置。
- 若存在 Agent 启动后识别出的无效 Responsibility Hint，PRD 必须提示“存在未应用的责任侧提示”，不得使复核者误认为全部用户提示均已生效。
- 当 Analysis Scope 未覆盖全部已知 Code Sides 时，PRD 必须声明“本次结论仅覆盖所选 Code Side，不证明未选侧不存在相关实现责任”，无论是否已识别具体范围外需求点。
- 是否存在可可靠拆分的 Requirement Point 及正式 PRD 是否生成，遵循阶段六诊断失败规则；阶段七只在正式 PRD 已可生成时追加多侧信息。

## 5. Debug Bundle、Summary 与最终 JSON

### 5.1 Debug Bundle

Debug Bundle 保存复核多侧分析所需的完整结构：

- Code Side 逻辑名称到目录的映射。
- 本次 Analysis Scope。
- 用户提供的 Responsibility Hints、实际应用关联，以及无效提示的未应用原因。
- 每个 Requirement Point 的运行内 ID、描述、责任侧、状态和简短说明。
- 每个 Requirement Point 的责任侧来源；对 `agent_inferred` 保存 Agent 返回的完整推断理由。
- 每个 Requirement Point 的嵌套 Code Evidence，以及证据位置或所属侧目录边界校验问题。
- 对 `责任侧待确认` 需求点在全范围搜索中发现的候选代码位置及其候选性质说明；候选位置不得被记录为确认完成的 Code Evidence。

Debug Bundle 继续默认不保存完整代码正文，除非显式开启已有代码上下文保存选项。

`责任侧待确认` 需求点的候选位置使用独立 `candidate_locations` 字段：

```json
{
  "candidate_locations": [
    {
      "side": "soc",
      "path": "soc_src/service_state.c",
      "line_start": 120,
      "line_end": 138,
      "symbol": "handle_stop_service",
      "reason": "可能与终止服务状态同步相关，但责任侧未确认"
    }
  ]
}
```

规则：

- Candidate Location 复用 Code Evidence 的 `side`、`path`、`line_start`、`line_end`、`symbol` 与 `reason` 位置描述字段，但保存在独立列表中。
- Analyzer 对 Candidate Location 执行路径、行号、所属侧与 Analysis Scope 边界校验；校验失败的位置不得作为有效候选位置保留。
- Candidate Location 不计入 evidence 数量、不影响 Requirement Point 状态、条目级完成度或 `GAPS`。
- Candidate Location 默认不包含完整代码正文；仅在 Debug Bundle 已显式开启既有码文保存选项时按相同约束保存上下文。
- Candidate Location 仅属于发现它的本次诊断运行；后续重试不得自动从历史 Debug Bundle 加载候选位置。
- 用户希望在重试中利用既有候选路径时，必须将其显式提供为新的 Code Clue 或 Seed Path，重新接受本次 Analysis Scope 与证据校验。

### 5.2 Summary Report

阶段六已经定义需求点数量、基础状态分布与未确认标志。阶段七在显式多侧分析时追加以下索引字段：

```json
{
  "analysis_scope": ["mcu", "soc"],
  "is_scope_limited_analysis": false,
  "scope_conclusion": "",
  "responsibility_source_counts": {
    "zentao_explicit": 1,
    "responsibility_hint": 1,
    "agent_inferred": 1,
    "pending": 0
  },
  "agent_inferred_responsibility_point_count": 1,
  "has_out_of_scope_requirement_points": false,
  "invalid_responsibility_hint_count": 1,
  "has_invalid_responsibility_hints": true
}
```

其中阶段六已有的 `has_unconfirmed_requirement_points` 在阶段七扩展为：存在 `无法判断` 或 `责任侧待确认` 的 Requirement Point 时为 `true`。
其中 `has_out_of_scope_requirement_points` 在存在 `范围外未评估` 的 Requirement Point 时为 `true`，用于区分完整条目结论与范围内结论。
其中 `is_scope_limited_analysis` 在 Analysis Scope 未覆盖全部已知 Code Sides 时为 `true`，即使没有识别出具体范围外需求点，也限制条目级结论不得为完整 `完成`。
其中 `scope_conclusion` 仅在范围受限分析形成可读的范围内结论时输出，例如 `"范围内完成"`；顶层 `conclusion` 仍保持现有枚举以兼容既有调用方。
其中 `responsibility_source_counts` 与 `agent_inferred_responsibility_point_count` 只统计责任侧来源，不保存推断理由正文。
其中 `has_invalid_responsibility_hints` 表示用户提供的 Responsibility Hint 是否存在未应用项，仅用于复核提示输入是否全部生效，不保存提示原文。

### 5.3 最终 JSON

阶段六已在最终 stdout JSON 的 `analysis[]` 中保存完整 Requirement Point 基础结构。阶段七在显式多侧分析时追加侧别和责任归属字段；其中 Code Evidence 只额外保存侧别，不保存完整源代码正文。

每个已形成责任侧结论的 Requirement Point 输出：

```json
{
  "responsible_sides": ["soc"],
  "responsibility_source": "agent_inferred",
  "responsibility_reason": "需求描述要求发送 MCU 所属总线消息，因此推断责任侧为 MCU"
}
```

`responsibility_source` 允许值：

- `zentao_explicit`：责任侧由禅道需求文本明确声明。
- `responsibility_hint`：责任侧由已应用的用户 Responsibility Hint 提供。
- `agent_inferred`：责任侧由 Agent 基于禅道需求文本推断。
- `pending`：责任侧仍为待确认。

stdout JSON 边界：

- 当 `responsibility_source` 为 `agent_inferred` 时，`responsibility_reason` 必须提供可复核的简短推断理由；其他来源可为空或省略。
- 不输出用户提供的原始 Responsibility Hint 文本、未应用原因或冲突明细；这些仅由 Debug Bundle 保留，Summary Report 只记录无效提示索引。
- 不输出 `candidate_locations`；Candidate Location 只属于 Debug Bundle 中的诊断复核材料，不得使调用方误认为其为正式 Code Evidence。
- 顶层 `conclusion` 不新增 `范围内完成` 枚举；范围受限且范围内已完成时输出既有 `conclusion: "无法判断"`，并增加 `scope_conclusion: "范围内完成"` 与 `is_scope_limited_analysis: true`。
- 阶段七新增字段仅在用户通过配置文件或参数显式启用多侧分析时追加；普通单仓库模式按阶段六定义的需求点结构与结论语义输出，不追加阶段七字段。

## 6. Code Side 与 Analysis Scope 输入

### 6.1 工程配置文件

Code Side 目录映射通常属于 Target Repository 的稳定工程结构，第一版支持通过配置文件提供：

```json
{
  "code_sides": {
    "mcu": "mcu_src",
    "soc": "soc_src"
  }
}
```

命令示例：

```bash
python3 main.py \
  --module requirement \
  --id 5929 \
  --analyze \
  --repo-path root \
  --code-sides-file root/.zentao-analyzer-sides.json \
  --analysis-scope mcu,soc
```

### 6.2 CLI 覆盖

单次运行可通过可重复参数覆盖或补充侧别映射：

```bash
python3 main.py \
  --module requirement \
  --id 5929 \
  --analyze \
  --repo-path root \
  --code-side mcu=mcu_src \
  --code-side soc=soc_src \
  --analysis-scope soc
```

Code Side 映射来源：

```text
显式 --code-side > --code-sides-file
```

### 6.3 Analysis Scope 输入边界

- `--analysis-scope` 使用逗号分隔的 Code Side 逻辑名称集合，例如 `soc` 或 `mcu,soc`。
- 当配置文件或用户参数提供了多个 Code Side 映射时，`--analysis-scope` 必须由用户显式提供。
- 未提供显式映射时，目录结构不自动触发多侧模式，也不自动选择 `mcu`、`soc` 或二者组合。
- Analysis Scope 中不存在于已解析 Code Side 映射的名称属于输入错误，分析不得启动。

### 6.4 Responsibility Hint 输入

第一版通过需求点原文片段到 Code Side 的映射提供责任侧提示，不支持按运行内 `RP-xxx` 提前绑定。

单条 CLI 分析支持可重复参数：

```bash
python3 main.py \
  --module requirement \
  --id 5923 \
  --analyze \
  --responsibility-hint '发送终止服务信号=mcu' \
  --responsibility-hint '退出服务状态=soc'
```

CLI 中 `=` 左侧为需求原文片段，右侧为逗号分隔的 Code Side 逻辑名称；跨侧责任点例如：

```bash
--responsibility-hint '消息字段一致=mcu,soc'
```

批量分析通过 clues file 中按条目的结构化数组提供：

```json
{
  "5923": {
    "responsibility_hints": [
      { "fragment": "发送终止服务信号", "sides": ["mcu"] },
      { "fragment": "退出服务状态", "sides": ["soc"] }
    ]
  }
}
```

通过 Skill 触发时可表达为：

```text
分析禅道需求 5923，责任侧提示: "发送终止服务信号"=mcu; "退出服务状态"=soc
```

规则：

- 文件形式为规范结构，CLI 和 Skill 提取结果均归一化为 `{fragment, sides}` 列表后进入分析。
- 单条 CLI 参数和 clues file 对同一条目同时提供 Responsibility Hints 时，属于输入冲突，直接拒绝执行，不进行拼接或覆盖。
- `--responsibility-hint` 仅适用于绑定明确 `--id` 的单条分析；批量运行必须使用 clues file 中按条目绑定的结构化输入。
- Skill 可将用户明确表达的责任侧提示转换为 CLI 参数，但不得把责任侧提示解释为新增需求内容。
- 同一输入来源中，`fragment` 与 `sides` 集合完全相同的重复 Responsibility Hint 去重后接受；Debug Bundle 记录曾发生重复输入。
- 同一输入来源中，相同 `fragment` 对应不同 `sides` 集合时，属于前置输入冲突，拒绝执行且不生成分析产物；不得自动合并为跨侧责任。
- 责任侧提示中的文本片段用于识别禅道原文中对应的既有预期行为，侧别值必须是已解析 Code Side 映射中的逻辑名称。
- Analyzer 将 Responsibility Hint 作为独立输入传递给 Agent，与 Code Clue 和原始需求正文分区展示。
- Agent 先依据禅道原始需求描述提出 Requirement Points，再仅对能够与单一需求点明确匹配的 Responsibility Hint 应用 `responsible_sides`。
- 提示片段无法匹配或可能匹配多个 Requirement Points 时，该提示无效；不得猜测应用对象，对应需求点按缺少有效责任侧输入处理，并记录用户提供的无效提示及未应用原因。
- Responsibility Hint 不构成 Code Clue，不因包含函数名、消息名或侧别而自动满足跨侧分析启动所需的显式引导线索。
- Responsibility Hint 指定的每个 Code Side 必须包含在本次 Analysis Scope 中；包含多个责任侧的提示要求 Analysis Scope 覆盖其声明的全部侧。若任一责任侧未选择，则属于前置输入错误，不调用 Agent，不生成 PRD Document、Summary Report 或 Debug Bundle，并提示用户扩大 Analysis Scope 或修正提示。
- 若 Responsibility Hint 与禅道原始需求中明确声明的责任侧冲突，则属于前置输入错误，不调用 Agent，不生成分析产物，并提示用户修正提示或在确有需求变更时先更新禅道。

无效提示记录规则：

- 对 Agent 已启动后才能识别的无效提示，例如未匹配到 Requirement Point 或匹配多个 Requirement Points，Debug Bundle 必须保存原提示的脱敏内容、指定侧别和未应用原因。
- 不同 `fragment` 在 Agent 拆分后匹配到同一 Requirement Point 且声明的 `sides` 集合冲突时，属于执行中识别的无效提示冲突；不得选择任一提示或自动合并责任侧，Debug Bundle 必须保留冲突关系与原因。
- 此类无效提示本身不终止已启动的分析，也不单独阻止生成正式 PRD。
- 若 Agent 在未应用提示的情况下仍能依据禅道原文可靠判断相关 Requirement Point 的责任侧，则该点按其有效证据正常形成状态与条目级结论。
- 若提示无效或执行中发生提示冲突，且 Agent 也无法依据禅道原文可靠判断相关 Requirement Point 的责任侧，则该点标记为 `责任侧待确认`；PRD 可生成，但 Feature Item 条目级结论不得为 `完成`。
- Summary Report 仅记录无效提示数量与 `has_invalid_responsibility_hints` 索引，不保存提示原文。

### 6.5 SKILL.md 自然语言触发

通过 Skill 触发多侧分析时，用户可显式表达代码侧映射、分析范围、责任侧提示与代码检索线索：

```text
分析禅道需求 5923，
代码侧: mcu=mcu_src, soc=soc_src；
分析范围: mcu,soc；
责任侧提示: "发送终止服务信号"=mcu, "退出服务状态"=soc；
代码线索: StopServiceMsg
```

转换规则：

- `代码侧:` 转换为一个或多个 `--code-side name=path` 参数。
- `分析范围:` 转换为 `--analysis-scope side[,side]` 参数。
- `责任侧提示:` 转换为一个或多个 `--responsibility-hint 'fragment=side[,side]'` 参数。
- `代码线索:` 继续按既有 Code Clue / Search Hint 规则转换。
- Skill 只抽取并转交用户显式提供的输入；不得依据目录名称、需求语义或搜索命中自动补充 Code Side、Analysis Scope 或 Responsibility Hint。
- 用户未提供显式 Code Side 映射时，Skill 不因工作目录包含 `mcu_src/` 或 `soc_src/` 而自动进入多侧分析模式。

## 7. 范围执行边界

Analysis Scope 必须由 Analyzer 的执行边界强制落实，不能仅通过 prompt 告知 Agent。

规则：

- 单侧范围（例如 `["soc"]`）时，Agent 只能读取和搜索映射到该侧的目录。
- 多侧范围（例如 `["mcu", "soc"]`）时，Agent 可读取和搜索所有被选择侧目录，但不得访问未被选择的其他 Code Side。
- Seed Path 必须位于某个已选 Code Side 的目录内；即使其位于 Target Repository 内，但属于未选侧，也必须拒绝并记录范围拒绝原因。
- 每条 Requirement Point evidence 必须位于已选 Code Side 内，且证据声明的 `side` 必须与路径归属一致；否则该证据校验失败。
- Prompt 应展示允许分析的 Code Side 与路径，帮助 Agent 正确搜索，但 prompt 说明不是范围控制的安全边界。

现有实现差距：

- 当前 Agent CLI 仅以整个 `repo_path` 作为工作目录，没有选定侧目录的读取/搜索限制。
- 当前 Seed Path 与 evidence 校验只验证文件位于 `repo_path` 内，没有验证文件所属 Code Side 是否属于 Analysis Scope。

### 7.1 第一版可保证的范围组合

- 领域模型仍支持任意数量、任意逻辑名称的 Code Side，不固定为 MCU/SOC 二选一。
- 单侧 Analysis Scope 可严格执行：Agent 的搜索根目录设为该 Code Side 对应目录。
- 单侧 Analysis Scope 可以分析包含多个责任侧需求点的 Feature Item；责任侧完全落在选择范围内的需求点正常评估，已知责任侧超出范围的需求点标记为 `范围外未评估`。
- 任何未覆盖全部已知 Code Side 的 Analysis Scope 都属于范围受限分析；未识别出范围外需求点时不虚构 Requirement Point，但结论仍不得表述为完整条目 `完成`。
- 当 Analysis Scope 包含全部已配置 Code Side 时，第一版允许以共同父级 Target Repository 进行分析，因为不存在配置中已声明但被排除的侧。
- 当存在三个或更多已配置 Code Side，且 Analysis Scope 选择多个但不是全部侧时，第一版拒绝执行；否则以父目录启动 Agent 无法保证其不读取未选侧。
- 被拒绝的多侧子集分析应提示用户改为单侧分析、选择全部侧，或等待后续支持多个受限搜索根的隔离能力。

### 7.2 跨侧分析启动门槛

- 单侧 Analysis Scope 允许在没有显式 Code Clue 的情况下启动，由 Agent 在已限制的单侧范围内搜索。
- 包含多个 Code Side 的 Analysis Scope 必须在启动前具备至少一项有效引导线索，避免在多套工程中无边界探索。
- 有效引导线索只可来自显式 Code Clue：`--clues`、`--paths` 或按条目配置的 clues file。
- 仅包含宽泛业务目标的需求描述，例如“功能结束异常”，不能单独视为跨侧引导线索。
- 用户明确作为 Code Clue 提供的行为描述可以作为 Search Hint 满足跨侧引导要求，但 Agent prompt 必须将其标识为检索线索而非需求依据。
- 跨侧分析缺少有效引导线索时，不调用 Agent，并提示用户补充消息名、协议字段、函数/模块名或至少一个已知文件路径。
- 跨侧分析具备有效 Code Clue 时，即使未提供 Responsibility Hint 也可启动；若 Agent 无法从禅道描述可靠判定某个需求点的责任侧，则该点标识为 `责任侧待确认`。

### 7.3 全范围下的责任侧待确认搜索

- 当 Analysis Scope 覆盖全部已配置 Code Side，且存在 `责任侧待确认` 的 Requirement Point 时，Agent 允许在所有已选侧搜索可能相关的代码位置，辅助用户后续确认实现归属。
- 搜索命中的位置仅作为 `candidate_locations` 记录到 Debug Bundle，不作为确认该 Requirement Point 状态的 Code Evidence，也不得据此反向填写 `responsible_sides`。
- PRD Document 不展示上述候选代码位置，也不将其汇总到 `关键代码证据`；候选位置只服务于诊断复核。
- 未提供有效 Responsibility Hint 且禅道文本仍无法明确责任侧时，该 Requirement Point 始终保持 `责任侧待确认`；不得进入 `GAPS`，条目级结论不得为 `完成`。

### 7.4 超时与搜索成本边界

- 单侧与跨侧分析使用相同的默认 Agent 超时；第一版沿用现有默认值 `900` 秒，不因 Analysis Scope 包含多个 Code Side 而自动缩短超时。
- 用户可继续通过 `--agent-timeout` 为单次分析显式覆盖超时值，该能力对单侧和跨侧一致。
- 跨侧搜索成本风险通过显式 Analysis Scope、范围执行约束和跨侧启动前必须提供 Code Clue 来控制，而不是通过不同的默认超时策略控制。
- 第一版不声明能够精确限制或统计 Agent 的 Token 消耗，也不声明能够按工具调用次数限制自主搜索量；当前可执行边界仅包括分析范围、启动门槛和整体调用超时。
- 发生 Agent 超时时，沿用既有诊断结果与人工重试流程；提示用户优先补充更精确的 Code Clue，或在确有需要时显式提高 `--agent-timeout`，不得自动重试。

### 7.5 前置失败与执行中断的产物边界

- 在 Agent 尚未启动前发现的范围或输入错误属于前置失败，包括：多侧 Target Repository 未指定 Analysis Scope、Analysis Scope 包含未知 Code Side、Responsibility Hint 指向 Analysis Scope 外的 Code Side、同一片段存在冲突 Responsibility Hints、Responsibility Hint 与禅道中明确责任侧冲突、跨侧分析缺少有效 Code Clue，以及第一版无法隔离执行的多侧子集范围。
- 前置失败时不得生成 PRD Document、Summary Report 或 Debug Bundle；应直接返回可操作的错误提示，说明需要补充或修正的输入。
- Agent 已实际启动后发生的超时、响应解析失败或其他分析执行中断属于诊断结果，而非前置失败。
- 执行中断继续生成既有诊断产物，并按既有人工重试流程提示用户处理；不得自动重试，也不得将诊断产物表述为已完成分析结论。

## 8. 待决设计分支

- 暂无。`Requirement Point` 无法拆分、基础证据校验和基础 PRD 输出均由阶段六规格负责，阶段七不再重复定义。

---

## 9. 暂不纳入范围

- 由 Analysis Scope 自动推断所有 Requirement Point 的责任侧。
- 未经用户选择范围即对多侧目标仓库执行全量跨侧分析。
