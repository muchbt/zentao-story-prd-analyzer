# zentao-story-prd-analyzer - 阶段七：深度 PRD 生成与双输入来源

**日期**: 2026-05-27
**版本**: 0.1
**状态**: 已确认，待实施

---

## 1. 背景与目标

当前 Feature Item 管线已经能从禅道条目生成需求点完成度、关键代码证据、缺口、建议和测试要点，但 PRD 的需求表达仍偏向分析报告。人工参考文档 `PRD-requirement-5932-FC_67165_v5a2_Ecall功能的优先级定义_TCAM_Priority_and_Parallelism_of_Services.md` 更易阅读，因为它将原始需求整理为范围、术语、业务规则、场景/矩阵和流程，再关联代码并提出实现策略。

经回溯 Claude 会话记录确认，该参考文档不是 analyzer 生成结果：Claude 收到用户直接粘贴的完整原始需求，搜索 `application/xcallapp` 源码后直接写入 Markdown。文档中既包含来自原文的规则整理，也包含代码关联和建议性内容；部分术语扩写或强化表述并没有足够来源约束。

阶段七的目标是将其可读性纳入正式 analyzer 流程，同时保留可复核边界：

- 支持从禅道 ID 获取需求内容，以及用户主动提供完整需求正文两种正式输入。
- PRD 固定展示便于理解需求的章节，即使原文信息不足也明确呈现缺口。
- 单次 Agent 调用同时产生需求解读、代码影响、逐点完成度和建议。
- Analyzer 继续负责写入正式文档、校验代码位置和派生完成度结论。
- 删除未实现的旧阶段七“多侧范围与责任侧分析”方向。

## 2. 阶段边界

### 2.1 继承阶段六

- `Requirement Point`、逐点 `status`/`gaps`/`evidence`、证据位置校验、顶层 `conclusion`/`confidence` 派生规则保持阶段六语义。
- Feature Item 的完成度分析仍为 PRD 必备内容，不能被需求整理章节取代。
- Defect Item 的 ISSUE 分析链路不在本阶段扩展范围内。

### 2.2 替换旧阶段七

- 原 `Code Side`、`Analysis Scope`、`Responsibility Hint`、`Candidate Location` 设计被废弃，不纳入本阶段。
- 原多侧规格和计划仅保留历史记录，不得作为实现输入。

### 2.3 来源边界

PRD 分离三类正式内容：

| 内容类型 | 来源与用途 | 不允许行为 |
| --- | --- | --- |
| Requirement Interpretation | 根据本次唯一 Requirement Source 整理摘要、范围、术语、规则、场景、矩阵和流程 | 把代码搜索或未确认推测写成需求事实 |
| Code Impact Analysis | 根据仓库搜索给出相关现有模块、文件和符号；位置需通过校验 | 将“相关位置”自动算作完成度证据 |
| Completion Assessment | 根据 Requirement Points 和有效 Code Evidence 派生完成度、缺口和可信度 | 用无依据解释或实施建议支撑正式结论 |

`Implementation Recommendation` 可以提出新模块、新接口、伪代码和测试策略，但必须独立标记为建议，不得描述为现有实现。

## 3. 双输入模式

### 3.1 Zentao Item 模式

现有命令保持有效：

```bash
python3 main.py --module requirement --id 5932 --analyze --repo-path <repo> --agent <agent>
```

- Analyzer 通过目标 `get requirement <id>` 请求读取需求正文和标题。
- 该请求同时验证本次读取所需认证权限，不增加 `zentao user` 前置检查。
- `Requirement Source` 为 fetched Zentao Item 的描述；标题使用禅道标题。

### 3.2 Provided Requirement 模式

新增非交互 CLI 输入：

```bash
python3 main.py \
  --module requirement \
  --id 5932 \
  --title "Ecall功能的优先级定义(CN&EU) - TCAM Priority and Parallelism of Services" \
  --requirement-file /tmp/requirement-5932.txt \
  --analyze \
  --repo-path <repo> \
  --agent <agent>
```

规则：

- `--requirement-file` 仅允许 Feature Item 模块 `requirement` 或 `story`。
- `--requirement-file` 要求同时提供非空 `--id` 与 `--title`。
- 使用该模式时不调用 `ZentaoClient.get_item()`、`list_items()` 或登录流程；ID 仅作为输出关联标识。
- 文件必须可读取且内容去除首尾空白后非空，否则在 Agent 调用之前失败。
- `--requirement-file` 与列表查询、`--login` 及禅道读取参数组合应拒绝，防止混用来源。
- Analyzer 以读取到的正文创建内存中的 Feature Item，正文来源在产物中标识为 `provided_requirement`。

### 3.3 Skill 交互责任

在 Agent CLI Skill 被“分析以下需求内容”触发时：

1. 接收用户提供的完整需求正文。
2. 如用户未提供需求 ID，询问 ID。
3. 从正文已有标题提取或推荐标题，并要求用户确认。
4. 将正文写入受控临时文件，调用 Provided Requirement CLI 模式。

Python CLI 本身不交互询问 ID 或标题，以保持脚本可测、可自动化。

## 4. Agent 输出合约

阶段七延续一次 Feature Agent 调用。该响应同时覆盖可读 PRD 素材与现有完成度评估，不让 Agent 直接写正式 Markdown。

### 4.1 Requirement Interpretation

Feature Agent 新增输出对象：

```json
{
  "requirement_interpretation": {
    "summary": "需求摘要",
    "scope": [
      {"text": "范围项", "source": "requirement|code_context|insufficient"}
    ],
    "terms": [
      {"term": "MSD", "definition": "最小数据集", "source": "requirement|code_context|insufficient"}
    ],
    "rules": [
      {"title": "服务互斥规则", "description": "同一时刻仅激活 EA 或 AA", "source": "requirement"}
    ],
    "scenarios": [
      {
        "title": "EA 过程中收到 AA",
        "precondition": "EA 正在进行",
        "trigger": "收到 AA 请求",
        "expected_behavior": ["发送 MSD", "不挂断当前通话"],
        "source": "requirement"
      }
    ],
    "matrix": {
      "title": "服务并发矩阵",
      "columns": ["当前服务", "EA", "AA"],
      "rows": [["EA", "-", "参见需求原文规则"]],
      "source": "requirement|insufficient"
    },
    "flow": {
      "title": "流程说明",
      "content": "文本或 Mermaid/ASCII 流程",
      "source": "requirement|insufficient"
    },
    "pending_confirmations": ["待确认项"]
  }
}
```

规则：

- `summary` 必须根据 Requirement Source 生成。
- 固定章节字段允许为空，但 Agent 必须以 `source: "insufficient"` 表明原文不足；不得为了填满模板补造事实。
- `source: "requirement"` 仅用于从需求正文可支持的陈述。
- `source: "code_context"` 只表示仓库中存在相关上下文，例如同名状态或模块，不构成需求定义或完成度证据。
- Analyzer 不从 Requirement Interpretation 创建 `Requirement Point` 或 `gaps`；需求点仍由既有 `requirement_points` 字段独立承载并校验。

### 4.2 Code Impact Analysis

Feature Agent 新增输出对象：

```json
{
  "code_impact": {
    "related_locations": [
      {
        "component": "呼叫控制状态机",
        "path": "application/xcallapp/callaudio/src/xcall_call_control.c",
        "line_start": 914,
        "line_end": 920,
        "symbol": "xcall_switch_internal_xcall_status",
        "reason": "包含 Callback Mode 状态处理"
      }
    ],
    "impact_notes": ["可能受需求影响的现有模块说明"]
  }
}
```

规则：

- `related_locations` 是 Code Impact Analysis 的关联位置，与 Requirement Point 下的 `evidence` 分开存储。
- Analyzer 对关联位置应用与 Code Evidence 相同的路径/行号边界校验。
- 无效关联位置从正式 PRD 关联表中排除并写入 Debug Bundle 校验问题；不改变完成度结论。
- 同一位置只有在 Requirement Point 的 `evidence` 中被正式引用且校验有效时，才参与 Completion Assessment。

### 4.3 Completion Assessment 与建议

- 现有 `requirement_points`、`priority`、`recommendations`、`verification` 字段继续返回。
- `recommendations` 明确为 `Implementation Recommendation`，允许建议新增模块、接口或伪代码。
- `verification` 用于 PRD 测试要点。
- Analyzer 仍从校验后的 Requirement Points 派生顶层证据、结论、缺口和可信度。

## 5. PRD Document 输出

Feature Item 的 PRD 保留固定章节骨架：

```markdown
# PRD: {title}

## 1. 概述
### 1.1 需求摘要
### 1.2 范围
### 1.3 术语定义
### 1.4 来源信息

## 2. 需求详细描述
### 2.1 业务规则
### 2.2 场景与流程
### 2.3 关系或并发矩阵
### 2.4 待确认事项

## 3. 功能影响分析
### 3.1 现有代码关联
### 3.2 实现完成度
### 3.3 关键代码证据

## 4. 需求对照表
### 4.1 需求点完成情况
### 4.2 差异与缺口

## 5. 建议实现策略
### 5.1 代码变更建议
### 5.2 测试要点

## 6. 参考信息
### 6.1 追踪信息
```

渲染规则：

- 所有固定章节均输出；无可靠内容时显示“原始需求未提供足够信息”。
- `requirement` 来源内容可直接作为需求表述展示。
- `code_context` 来源内容以“代码侧候选上下文，不构成需求定义”提示展示。
- `现有代码关联` 仅渲染通过 Analyzer 校验的 Code Impact 位置。
- `关键代码证据` 仅渲染支撑 Completion Assessment 的有效 evidence，不混入仅相关的位置。
- `建议实现策略` 明确声明其为建议项，不代表仓库已有实现。
- 文件名生成规则保持既有 `PRD-{type}-{id}-{sanitize_title(item.title)}.md` 不变。

## 6. 输出与诊断扩展

### 6.1 最终 JSON

Feature Item 成功分析的 `analysis[]` 新增：

```json
{
  "requirement_source": "zentao|provided_requirement",
  "requirement_interpretation": {},
  "code_impact": {
    "related_locations": [],
    "impact_notes": []
  },
  "requirement_points": []
}
```

### 6.2 Summary Report

Summary item 新增轻量字段：

```json
{
  "requirement_source": "provided_requirement",
  "code_impact_location_count": 4,
  "has_pending_requirement_confirmation": true
}
```

Summary 不重复保存完整需求整理正文或代码关联表。

### 6.3 Debug Bundle

Debug Bundle 新增记录：

- `requirement_source` 与 Provided Requirement 的脱敏来源摘要，不保存外部秘密。
- 原始 Agent 响应中 `requirement_interpretation` 与 `code_impact`。
- Code Impact 位置校验问题，与完成度 evidence 校验问题区分存储。

## 7. 安全与失败策略

- Provided Requirement 文件读取失败、为空、缺 ID 或缺标题时，在启动 Agent 之前失败，不生成正式 PRD。
- Provided Requirement 正文可能包含敏感业务信息；日志只记录来源类型、ID、标题及必要诊断信息，不重复输出完整正文。
- Feature Agent 无法返回有效 `requirement_points` 时沿用阶段六的诊断失败策略。
- `requirement_interpretation` 或 `code_impact` 缺失/结构无效，但 `requirement_points` 与 Completion Assessment 有效时，仍生成正式 PRD；对应章节显示“分析结果未提供有效内容”，并在 Summary Report 与 Debug Bundle 中记录丰富内容不可用。
- 丰富展示字段不可用不得改变基于有效 Requirement Points 派生的 `conclusion`、`gaps` 或 `confidence`。
- Agent CLI Subprocess 继续只读；正式 PRD 始终由 Analyzer Process 模板生成。

## 8. 不在本阶段范围

- 恢复或重做旧阶段七多侧范围分析。
- 从用户正文提取 ID 后自动回查或合并禅道需求内容。
- 让 Agent 直接写入正式 PRD Markdown。
- 为 Defect Item 增加深度需求解释章节。
- 自动把多次运行生成的 PRD 合并为一个产品级文档。
