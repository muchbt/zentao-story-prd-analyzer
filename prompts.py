from typing import Any, Dict, List

from zentao_client import ZentaoItem


_FEATURE_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道条目和代码上下文，判断功能实现完成度。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码上下文】
{code_context}

【任务要求】
1. 对比条目描述与代码实现，判断功能是否完成。
2. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
3. JSON Schema:
{{
  "conclusion": "完成|部分完成|未完成|无法判断",
  "evidence": ["文件路径:函数名 已实现的功能说明", "..."],
  "gaps": ["未实现点1", "..."],
  "suspected_causes": [],
  "affected_scope": [],
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": ""
}}

4. 如果代码上下文不足以判断，请设置 conclusion="无法判断"、confidence="低"，并在 evidence 中说明"相关代码证据不足"。禁止编造不存在的证据。
5. confidence="高" 意味着你有直接代码证据支持结论；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
"""

_DEFECT_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道缺陷条目和代码上下文，分析可能根因和影响范围。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码上下文】
{code_context}

【任务要求】
1. 分析缺陷描述对应的代码区域，找出可能根因。
2. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
3. JSON Schema:
{{
  "conclusion": "已定位|部分定位|无法定位",
  "evidence": ["文件路径:函数名 与缺陷相关的代码说明", "..."],
  "gaps": [],
  "suspected_causes": ["可能根因1", "..."],
  "affected_scope": ["文件A", "模块B"],
  "recommendations": ["修复方向1", "..."],
  "verification": ["复现步骤或验证建议", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": ""
}}

4. 如果代码上下文不足以分析，请设置 conclusion="无法定位"、confidence="低"，并在 suspected_causes 中说明"相关代码证据不足"。禁止编造不存在的根因。
5. confidence="高" 意味着你有直接代码证据支持结论；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
"""


def _format_code_context(snippets):
    if not snippets:
        return "[未提供代码上下文]"
    parts = []
    for s in snippets:
        parts.append(f"--- 文件: {s['path']} (行 {s['line_start']}-{s['line_end']}) ---\n{s['content']}")
    return "\n\n".join(parts)


def build_feature_prompt(item: ZentaoItem, code_snippets) -> str:
    return _FEATURE_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        code_context=_format_code_context(code_snippets),
    )


def build_defect_prompt(item: ZentaoItem, code_snippets) -> str:
    return _DEFECT_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        code_context=_format_code_context(code_snippets),
    )
