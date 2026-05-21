# zentao-story-prd-analyzer — 阶段三：PRD/ISSUE 文档生成闭环

**日期**: 2026-05-21
**版本**: 1.0
**状态**: 设计完成，待实现

---

## 1. 背景与目标

阶段三承接阶段一的禅道条目数据和阶段二的代码分析结果，将 `ZentaoItem` 与 `AnalysisResult` 转换为可阅读、可追踪、可复核的本地 Markdown 文档，并生成机器可读的汇总报告。

阶段三目标：

- 为功能类条目生成 PRD 文档。
- 为缺陷类条目生成 ISSUE 文档。
- 在文档中保存 LLM 对该 PRD/ISSUE 的理解。
- 为分析失败或证据不足的条目生成诊断文档。
- 生成 `summary_report.json`，便于后续 CI、人工复核或回写禅道流程消费。
- 预留回写禅道接口，但阶段三不调用禅道写接口。

阶段三明确限定为本地文档生成与汇总报告生成，不自动修改代码、不自动提交 Git、不自动回写禅道。

---

## 2. 范围

### 2.1 纳入范围

- 新增 Markdown 文档生成器。
- 根据条目类型选择 PRD 或 ISSUE 文档类型。
- 按目录分离 PRD 与 ISSUE 输出。
- 生成诊断文档，覆盖 LLM 调用失败、JSON 解析失败、证据不足等情况。
- 生成机器可读的 `summary_report.json`。
- 在文档和 summary 中记录回写禅道预留状态。
- 提供文件名清洗和标题截断，避免非法路径或过长文件名。
- 扩展 `main.py` 编排逻辑，使 `--analyze` 能生成阶段三文档。

### 2.2 暂不纳入范围

- 自动回写禅道条目。
- 自动创建远程 issue。
- 自动修改代码。
- 自动提交 Git commit。
- 二次调用 LLM 重新生成 PRD/ISSUE 正文。
- 保存完整 LLM `raw_response`、完整代码片段或敏感凭证到 summary。

---

## 3. 架构设计

阶段三新增 3 个模块，并轻量修改 `main.py`。

| 模块 | 职责 | 说明 |
|------|------|------|
| `document_generator.py` | Markdown 文档生成 | 渲染 PRD、ISSUE、诊断文档，负责输出路径和文件名清洗 |
| `summary_report.py` | 汇总报告生成 | 生成 `docs/summary_report.json`，作为机器可读索引 |
| `writeback.py` | 禅道回写预留接口 | 默认返回 `not_implemented`，不执行任何写操作 |
| `main.py`（修改） | 主流程编排 | 获取条目和分析结果后调用文档生成器与 summary 生成器 |

### 3.1 模块边界原则

1. `document_generator.py` 只做 deterministic 模板渲染，不调用 LLM。
2. `summary_report.py` 只消费文档生成结果和 `AnalysisResult`，不读取 Markdown 正文。
3. `writeback.py` 只提供预留接口和状态结构，不调用 `zentao update`、`zentao create` 或其他写命令。
4. `main.py` 不拼接 Markdown 模板，不直接写 summary 字段细节，只负责编排。
5. 阶段三不修改 `ZentaoClient`、`AnalysisResult` 和阶段二分析逻辑。

---

## 4. 数据流

```
main.py
  │
  ├── ZentaoClient
  │     输出: List[ZentaoItem]
  │
  ├── analyzer.analyze()
  │     输出: List[AnalysisResult]
  │
  ├── document_generator.generate_document()
  │     输入: ZentaoItem + AnalysisResult
  │     输出: DocumentResult(document_type, document_path, is_diagnostic)
  │
  ├── writeback.prepare_writeback_status()
  │     输出: {"supported": false, "status": "not_implemented"}
  │
  └── summary_report.write_summary_report()
        输出: docs/summary_report.json
```

阶段三只在本地文件系统写入 Markdown 和 JSON。任何禅道回写都必须由后续阶段显式设计并实现。

---

## 5. 输出目录与命名规则

默认输出目录位于 `docs` 下：

| 文档类型 | 目录 | 命名规则 |
|----------|------|----------|
| PRD | `docs/prd/` | `PRD-{type}-{id}-{safe_title}.md` |
| ISSUE | `docs/issue/` | `ISSUE-{type}-{id}-{safe_title}.md` |
| 汇总报告 | `docs/` | `summary_report.json` |

### 5.1 文档类型映射

| 条目类型 | 文档类型 | 输出目录 |
|----------|----------|----------|
| `story` | PRD | `docs/prd/` |
| `requirement` | PRD | `docs/prd/` |
| `bug` | ISSUE | `docs/issue/` |
| `ticket` | ISSUE | `docs/issue/` |
| `feedback` | ISSUE | `docs/issue/` |
| 其他类型 | ISSUE | `docs/issue/` |

未知条目类型按 ISSUE 生成，并在文档中标记“未知条目类型，按问题类文档生成”。

### 5.2 文件名清洗

`safe_title` 规则：

- 保留中英文、数字、下划线、短横线。
- 空格和其他符号替换为下划线。
- 连续下划线压缩为单个下划线。
- 去除首尾下划线。
- 标题为空时使用 `untitled`。
- 最长保留 80 个字符。

---

## 6. Markdown 文档内容

### 6.1 PRD 文档结构

PRD 文档用于 `story` 与 `requirement`。

```md
# PRD: {title}

## 来源信息

- 条目类型: {item_type}
- 条目 ID: {item_id}
- 状态: {status}
- 优先级: {priority}
- 生成时间: {generated_at}

## 原始需求摘要

{description}

## LLM 理解摘要

{llm_understanding}

## 实现完成度

- 结论: {conclusion}
- 置信度: {confidence}

## 实现证据

{evidence_list}

## 差异与缺口

{gaps_list}

## 修改建议

{recommendations_list}

## 验证建议

{verification_list}

## 追踪信息

- 输出文件: {document_path}
- 回写禅道: {writeback_status}
```

### 6.2 ISSUE 文档结构

ISSUE 文档用于 `bug`、`ticket`、`feedback` 和未知条目类型。

```md
# ISSUE: {title}

## 来源信息

- 条目类型: {item_type}
- 条目 ID: {item_id}
- 状态: {status}
- 优先级: {priority}
- 生成时间: {generated_at}

## 问题描述摘要

{description}

## LLM 理解摘要

{llm_understanding}

## 定位结论

- 结论: {conclusion}
- 置信度: {confidence}

## 代码证据

{evidence_list}

## 可能根因

{suspected_causes_list}

## 影响范围

{affected_scope_list}

## 修复建议

{recommendations_list}

## 复现与验证建议

{verification_list}

## 追踪信息

- 输出文件: {document_path}
- 回写禅道: {writeback_status}
```

### 6.3 LLM 理解摘要

每份 PRD/ISSUE 文档必须包含“LLM 理解摘要”。

生成规则：

1. 优先使用 `AnalysisResult.output_md` 中可复用的摘要内容。
2. 若 `output_md` 为空，则由模板渲染器根据结构化字段生成摘要：
   - PRD：基于 `conclusion`、`evidence`、`gaps`、`recommendations` 描述 LLM 认为该需求要完成什么、当前代码完成到什么程度、主要缺口是什么。
   - ISSUE：基于 `conclusion`、`evidence`、`suspected_causes`、`affected_scope`、`recommendations` 描述 LLM 认为问题表现是什么、疑似触发条件是什么、优先怀疑的代码区域是什么。
3. 若证据不足或存在错误，摘要必须明确说明“当前理解受限于代码证据不足或分析错误”，不得写成确定结论。
4. 不进行二次 LLM 调用，不新增推断事实。

---

## 7. 诊断文档

当满足任一条件时，生成诊断文档：

- `AnalysisResult.error` 非空。
- `AnalysisResult.is_insufficient_evidence()` 为真。
- 文档生成器收到的必要字段缺失到无法渲染完整分析。

诊断文档仍使用正常命名规则和目录：

- 功能类诊断文档仍写入 `docs/prd/PRD-{type}-{id}-{safe_title}.md`。
- 缺陷类诊断文档仍写入 `docs/issue/ISSUE-{type}-{id}-{safe_title}.md`。

诊断文档开头必须包含：

```md
> 诊断文档：当前条目未能生成完整 PRD/ISSUE。
```

诊断文档必须包含：

- 来源信息。
- 原始描述摘要。
- LLM 理解摘要，明确说明证据不足或错误限制。
- 错误原因。
- 已有证据数量。
- 下一步建议，例如补充关键词、扩大扫描范围、检查 LLM 配置或人工定位代码。
- 追踪信息和回写状态。

诊断文档不得伪造成完整分析结论。

---

## 8. Summary Report

`docs/summary_report.json` 是机器可读索引，不保存完整 Markdown 正文、完整代码片段、敏感凭证或 LLM 原始响应。

### 8.1 顶层结构

```json
{
  "generated_at": "2026-05-21T10:30:00+08:00",
  "count": 2,
  "prd_dir": "docs/prd",
  "issue_dir": "docs/issue",
  "items": []
}
```

### 8.2 条目结构

```json
{
  "item_id": "5939",
  "item_type": "requirement",
  "title": "需求标题",
  "document_type": "PRD",
  "document_path": "docs/prd/PRD-requirement-5939-title.md",
  "conclusion": "部分完成",
  "priority": "高",
  "confidence": "中",
  "has_error": false,
  "error": "",
  "insufficient_evidence": false,
  "evidence_count": 3,
  "recommendation_count": 2,
  "verification_count": 1,
  "writeback": {
    "supported": false,
    "status": "not_implemented"
  }
}
```

### 8.3 敏感信息约束

summary 不保存：

- `OPENAI_API_KEY`、`ZENTAO_TOKEN`、密码等凭证。
- `AnalysisResult.raw_response`。
- 完整代码片段。
- 完整 Markdown 文档正文。

---

## 9. 回写禅道预留接口

阶段三只预留接口，不实现回写。

建议接口：

```python
def prepare_writeback_status() -> dict:
    return {
        "supported": False,
        "status": "not_implemented",
    }

def writeback_to_zentao(*args, **kwargs) -> dict:
    return {
        "supported": False,
        "status": "not_implemented",
        "message": "阶段三不实现禅道回写",
    }
```

任何真实回写都应在后续阶段单独设计权限、确认、审计和失败恢复机制。

---

## 10. 错误处理

| 场景 | 处理行为 |
|------|----------|
| 输出目录创建失败 | 返回错误，主流程失败 |
| 单条 Markdown 渲染失败 | 记录该条错误，继续处理其他条目 |
| 字段为空 | Markdown 中显示“无”或“未提供” |
| 文件名为空或非法 | 使用 `untitled` |
| 未知条目类型 | 按 ISSUE 生成，并写明未知类型提示 |
| 分析失败或证据不足 | 生成诊断文档 |
| summary 写入失败 | 主流程失败 |

---

## 11. 接口定义

### 11.1 document_generator.py

```python
@dataclasses.dataclass
class DocumentResult:
    item_id: str
    item_type: str
    title: str
    document_type: str
    document_path: str
    is_diagnostic: bool
    error: str = ""

def generate_document(
    item: ZentaoItem,
    analysis: AnalysisResult,
    output_root: str = "docs",
    generated_at: Optional[str] = None,
) -> DocumentResult:
    """生成单个 PRD/ISSUE Markdown 文档。"""
```

### 11.2 summary_report.py

```python
def build_summary_item(
    item: ZentaoItem,
    analysis: AnalysisResult,
    document: DocumentResult,
    writeback: dict,
) -> dict:
    """生成 summary_report 中的单条索引。"""

def write_summary_report(
    items: List[dict],
    output_root: str = "docs",
    generated_at: Optional[str] = None,
) -> str:
    """写入 docs/summary_report.json 并返回路径。"""
```

### 11.3 writeback.py

```python
def prepare_writeback_status() -> dict:
    """返回阶段三的默认回写状态。"""

def writeback_to_zentao(*args, **kwargs) -> dict:
    """预留接口，不执行真实回写。"""
```

---

## 12. 测试策略

新增测试：

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/test_document_generator.py` | PRD 生成、ISSUE 生成、诊断文档、LLM 理解摘要、文件名清洗 |
| `tests/test_summary_report.py` | summary 字段完整性、计数字段、writeback 状态、敏感信息排除 |
| `tests/test_writeback.py` | 默认 `not_implemented` 状态 |
| `tests/test_main_phase3.py` | mock `AnalysisResult` 验证 `--analyze` 后生成文档和 summary |

测试原则：

- 不调用真实 LLM。
- 不调用真实禅道写接口。
- 使用临时目录验证文件输出。
- 对 Markdown 内容只断言关键章节和关键字段，不对完整正文做脆弱匹配。
- 验证 summary 可被 `json.load()` 解析。

---

## 13. 验收点

- [ ] `story` 和 `requirement` 默认生成 PRD 文档。
- [ ] `bug`、`ticket`、`feedback` 默认生成 ISSUE 文档。
- [ ] PRD/ISSUE 分别写入 `docs/prd/` 和 `docs/issue/`。
- [ ] 文件命名符合 `PRD-{type}-{id}-{safe_title}.md` 与 `ISSUE-{type}-{id}-{safe_title}.md`。
- [ ] 每份文档包含来源信息、原始描述摘要、LLM 理解摘要、分析结论、证据、建议和验证项。
- [ ] 分析失败或证据不足时仍生成诊断文档。
- [ ] `docs/summary_report.json` 可解析，并包含文档路径、结论、置信度、错误状态和 writeback 状态。
- [ ] summary 不包含敏感信息、完整代码片段或 `raw_response`。
- [ ] 回写禅道接口存在，但默认返回 `not_implemented`，不执行写操作。
- [ ] 阶段一和阶段二现有测试不回退。

---

## 14. 风险与假设

1. **假设**: 阶段二已经稳定输出 `AnalysisResult`。
2. **假设**: `AnalysisResult.output_md` 可能为空，阶段三必须能从结构化字段生成 LLM 理解摘要。
3. **风险**: LLM 理解摘要被误读为最终事实。缓解方式是在证据不足或低置信度时明确标记限制。
4. **风险**: 文档文件名过长或包含非法字符。缓解方式是统一清洗和截断。
5. **风险**: 后续回写需求被误认为已实现。缓解方式是在接口、summary 和文档中都明确 `not_implemented`。

---

## 15. 依赖关系

- 阶段三依赖阶段一的 `ZentaoItem`。
- 阶段三依赖阶段二的 `AnalysisResult`。
- 阶段四可复用阶段三的 summary 和 writeback 状态，扩展日志、用户体验和真实 Agent 适配。

---

*文档结束*
