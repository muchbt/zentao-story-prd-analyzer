from typing import List, Optional

from .zentao_client import ZentaoItem


_DEFECT_EVIDENCE_SCHEMA = '''  "evidence": [
    {
      "path": "文件路径",
      "line_start": 1,
      "line_end": 20,
      "symbol": "函数或类名，可为空",
      "reason": "该证据如何支持结论"
    }
  ],
  "gaps": [],
  "suspected_causes": [],
  "affected_scope": [],
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "understanding_summary": "用自然语言概述你对禅道条目需求或问题的理解，不要重复证据、缺口、建议或验证步骤"'''


_FEATURE_RP_EVIDENCE_SCHEMA = '''          {
            "path": "文件路径",
            "line_start": 1,
            "line_end": 20,
            "symbol": "函数或类名，可为空",
            "reason": "该证据如何支持此需求点结论"
          }'''


_FEATURE_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道条目和目标代码仓库，分析功能实现完成度。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码仓库】
路径: {repo_path}

【种子上下文】
{seed_context}

【搜索建议】
{search_hints}

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 你是 Agent CLI 子进程，只能返回 JSON 分析结果，不能写入任何文件。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 只有 analyzer 进程可以写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
1. 主动搜索代码仓库，查找与条目相关的代码实现。
2. 从需求描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
3. 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
4. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。

【需求点拆分要求】
5. 将禅道原始需求描述拆分为一个或多个可独立验证的需求点（Requirement Point）。
6. 每个需求点描述一个可独立验证的预期行为单元，不是代码文件名或测试步骤。
7. 需求点描述只能依据禅道原始需求，不能从用户搜索建议或代码线索中推导新需求。
8. 为每个需求点独立判断实现状态、给出判定理由、关联代码证据和确认缺口。
9. 如果代码仓库不足以判断某个需求点，该需求点状态设为"无法判断"，reason 说明证据不足。

【状态与缺口约束】
10. 需求点状态只能是：完成、部分完成、未完成、无法判断。
11. 状态为"未完成"或"部分完成"时，gaps 必须包含至少一条确认的实现缺失或差异。没有确认缺口时，状态不得为"未完成"或"部分完成"，应设为"无法判断"。
12. 状态为"完成"或"无法判断"时，gaps 必须为空数组。
13. 完全没有有效代码证据的需求点，reason 中可说明"无代码证据"，但这不等同于确认缺口。

【证据约束】
14. evidence 必须引用仓库中实际存在的文件和行号，禁止编造。
15. 每条 evidence 的 reason 必须说明该证据如何支持此需求点的结论。

【其他字段】
16. understanding_summary 只概述你对需求本身的理解，不要重复需求点判定、证据、缺口或建议。
17. priority 和 verification 分别为整体优先级和验证建议。

【JSON Schema】
{{
  "requirement_points": [
    {{
      "description": "可独立验证的需求点描述",
      "status": "完成|部分完成|未完成|无法判断",
      "reason": "判定说明",
      "gaps": ["确认的实现缺失或差异，状态为未完成或部分完成时必须非空"],
      "evidence": [
{rp_evidence_schema}
      ]
    }}
  ],
  "understanding_summary": "自然语言概述对需求本身的理解",
  "priority": "高|中|低",
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."]
}}
"""

_DEFECT_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道缺陷条目和目标代码仓库，分析可能根因和影响范围。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码仓库】
路径: {repo_path}

【种子上下文】
{seed_context}

【搜索建议】
{search_hints}

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 你是 Agent CLI 子进程，只能返回 JSON 分析结果，不能写入任何文件。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 只有 analyzer 进程可以写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
1. 主动搜索代码仓库，查找与缺陷描述相关的代码实现。
2. 从缺陷描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
3. 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
4. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
5. evidence 必须引用仓库中实际存在的文件和行号，禁止编造。
6. 如果代码仓库不足以分析，请设置 conclusion="无法定位"、confidence="低"，在 suspected_causes 中说明"相关代码证据不足"。
7. confidence="高" 意味着有直接代码证据支持；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
8. understanding_summary 只概述你对缺陷或反馈本身的理解，不要复制 conclusion、evidence、suspected_causes、recommendations 或 verification。
9. JSON Schema:
{{
  "conclusion": "已定位|部分定位|无法定位",
{defect_evidence_schema}
}}
"""


def _format_seed_context(snippets):
    if not snippets:
        return "[未提供种子上下文]"
    parts = []
    for snippet in snippets:
        parts.append(
            f"--- 文件: {snippet['path']} (行 {snippet['line_start']}-{snippet['line_end']}) ---\n"
            f"{snippet['content']}"
        )
    return "\n\n".join(parts)


def _format_search_hints(search_hints: Optional[List[str]]) -> str:
    if not search_hints:
        return "[未提供搜索建议]"
    return ", ".join(str(item) for item in search_hints if str(item).strip())


def build_feature_prompt(item: ZentaoItem, repo_path: str, seed_snippets=None, search_hints=None) -> str:
    return _FEATURE_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        repo_path=repo_path,
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        rp_evidence_schema=_FEATURE_RP_EVIDENCE_SCHEMA,
    )


def build_defect_prompt(item: ZentaoItem, repo_path: str, seed_snippets=None, search_hints=None) -> str:
    return _DEFECT_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        repo_path=repo_path,
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        defect_evidence_schema=_DEFECT_EVIDENCE_SCHEMA,
    )
