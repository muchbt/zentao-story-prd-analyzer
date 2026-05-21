import dataclasses
import os
import re
from typing import Optional

from zentao_client import ZentaoItem
from analysis_result import AnalysisResult


@dataclasses.dataclass
class DocumentResult:
    item_id: str
    item_type: str
    item_title: str
    document_type: str  # "PRD" | "ISSUE" | "DIAGNOSTIC"
    document_path: str
    is_diagnostic: bool = False
    error: str = ""


def sanitize_title(title: str, max_len: int = 80) -> str:
    """清理标题中的非法文件名字符，保留中英文、数字、_-"""
    if not title or not title.strip():
        return "untitled"
    # 保留中文、英文、数字、_-，其余替换为下划线
    cleaned = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9_\-]", "_", title.strip())
    # 合并连续下划线
    cleaned = re.sub(r"_+", "_", cleaned)
    # 去除首尾下划线
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "untitled"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def _document_type_from_item_type(item_type: str) -> str:
    if item_type in ("story", "requirement"):
        return "PRD"
    if item_type in ("bug", "ticket", "feedback"):
        return "ISSUE"
    return "ISSUE"


def _build_llm_summary(analysis: AnalysisResult) -> str:
    """构建 LLM 理解摘要"""
    if analysis.output_md:
        return analysis.output_md

    if analysis.error:
        return f"分析过程中出现错误：{analysis.error}。无法生成完整结论。"

    if analysis.is_insufficient_evidence():
        return "证据不足：未找到与条目直接相关的代码证据，无法做出可靠判断。"

    parts = []
    if analysis.conclusion:
        parts.append(f"结论：{analysis.conclusion}")
    if analysis.evidence:
        parts.append(f"证据：{'; '.join(analysis.evidence)}")
    if analysis.gaps:
        parts.append(f"未实现：{'; '.join(analysis.gaps)}")
    if analysis.suspected_causes:
        parts.append(f"可能根因：{'; '.join(analysis.suspected_causes)}")
    if analysis.affected_scope:
        parts.append(f"影响范围：{'; '.join(analysis.affected_scope)}")
    if analysis.recommendations:
        parts.append(f"建议：{'; '.join(analysis.recommendations)}")
    if analysis.verification:
        parts.append(f"验证：{'; '.join(analysis.verification)}")

    return "\n".join(parts) if parts else "未提供 LLM 分析摘要。"


def _render_prd(item: ZentaoItem, analysis: AnalysisResult, generated_at: str) -> str:
    safe_title = sanitize_title(item.title)
    evidence = "\n".join(f"- {e}" for e in analysis.evidence) if analysis.evidence else "无"
    gaps = "\n".join(f"- {g}" for g in analysis.gaps) if analysis.gaps else "无"
    recommendations = "\n".join(f"- {r}" for r in analysis.recommendations) if analysis.recommendations else "无"
    verification = "\n".join(f"- {v}" for v in analysis.verification) if analysis.verification else "无"

    return f"""# PRD: {item.title}

> 自动生成于 {generated_at}
> 来源：禅道 {item.type} #{item.id}
> 状态：{item.status}

## 需求描述

{item.description or "未提供"}

## LLM 理解摘要

{_build_llm_summary(analysis)}

## 实现完成度

- **结论**：{analysis.conclusion or "未判断"}
- **优先级**：{analysis.priority or "未评估"}
- **可信度**：{analysis.confidence or "未评估"}

## 实现证据

{evidence}

## 未实现或部分实现点

{gaps}

## 修改建议

{recommendations}

## 验证建议

{verification}

---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
"""


def _render_issue(item: ZentaoItem, analysis: AnalysisResult, generated_at: str) -> str:
    safe_title = sanitize_title(item.title)
    evidence = "\n".join(f"- {e}" for e in analysis.evidence) if analysis.evidence else "无"
    suspected = "\n".join(f"- {s}" for s in analysis.suspected_causes) if analysis.suspected_causes else "无"
    affected = "\n".join(f"- {a}" for a in analysis.affected_scope) if analysis.affected_scope else "无"
    recommendations = "\n".join(f"- {r}" for r in analysis.recommendations) if analysis.recommendations else "无"
    verification = "\n".join(f"- {v}" for v in analysis.verification) if analysis.verification else "无"

    return f"""# ISSUE: {item.title}

> 自动生成于 {generated_at}
> 来源：禅道 {item.type} #{item.id}
> 状态：{item.status}

## 问题描述

{item.description or "未提供"}

## LLM 理解摘要

{_build_llm_summary(analysis)}

## 定位结论

- **结论**：{analysis.conclusion or "未判断"}
- **优先级**：{analysis.priority or "未评估"}
- **可信度**：{analysis.confidence or "未评估"}

## 相关证据

{evidence}

## 可能根因

{suspected}

## 影响范围

{affected}

## 修复建议

{recommendations}

## 验证建议

{verification}

---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
"""


def _render_diagnostic(item: ZentaoItem, analysis: AnalysisResult, generated_at: str) -> str:
    return f"""# 诊断文档：{item.title}

> 自动生成于 {generated_at}
> 来源：禅道 {item.type} #{item.id}
> 状态：{item.status}

## 说明

本次分析未能生成完整的 PRD 或 ISSUE 文档。

## 原因

{analysis.error or "证据不足，无法做出可靠判断。"}

## LLM 理解摘要

{_build_llm_summary(analysis)}

---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
"""


def generate_document(
    item: ZentaoItem,
    analysis: AnalysisResult,
    output_root: str = "docs",
    generated_at: Optional[str] = None,
) -> DocumentResult:
    """生成 PRD/ISSUE/诊断 Markdown 文档"""
    if generated_at is None:
        from datetime import datetime, timezone
        generated_at = datetime.now(timezone.utc).astimezone().isoformat()

    doc_type = _document_type_from_item_type(item.type)
    is_diagnostic = bool(analysis.error) or analysis.is_insufficient_evidence()

    safe_title = sanitize_title(item.title)
    if is_diagnostic:
        subdir = "diagnostic"
        filename = f"DIAG-{item.type}-{item.id}-{safe_title}.md"
        content = _render_diagnostic(item, analysis, generated_at)
    elif doc_type == "PRD":
        subdir = "prd"
        filename = f"PRD-{item.type}-{item.id}-{safe_title}.md"
        content = _render_prd(item, analysis, generated_at)
    else:
        subdir = "issue"
        filename = f"ISSUE-{item.type}-{item.id}-{safe_title}.md"
        content = _render_issue(item, analysis, generated_at)

    output_dir = os.path.join(output_root, subdir)
    os.makedirs(output_dir, exist_ok=True)
    document_path = os.path.join(output_dir, filename)

    with open(document_path, "w", encoding="utf-8") as f:
        f.write(content)

    return DocumentResult(
        item_id=item.id,
        item_type=item.type,
        item_title=item.title,
        document_type=doc_type if not is_diagnostic else "DIAGNOSTIC",
        document_path=document_path,
        is_diagnostic=is_diagnostic,
        error=analysis.error,
    )
