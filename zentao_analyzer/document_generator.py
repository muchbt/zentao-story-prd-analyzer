import dataclasses
import os
import re
from typing import Optional

import re

from .zentao_client import ZentaoItem
from .analysis_result import AnalysisResult


@dataclasses.dataclass
class DocumentResult:
    item_id: str
    item_type: str
    title: str
    document_type: str  # "PRD" | "ISSUE"
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


def _split_evidence(text: str) -> str:
    if not text:
        return "无"
    parts = re.split(r'[；;。]', text)
    lines = [p.strip() for p in parts if p.strip()]
    if not lines:
        return text
    return "\n".join(f"- {line}" for line in lines)


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
        parts.append(f"证据：\n{_split_evidence('; '.join(analysis.evidence))}")
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

    return "\n\n".join(parts) if parts else "未提供 LLM 分析摘要。"


def _unknown_type_notice(item_type: str) -> str:
    if item_type not in ("story", "requirement", "bug", "ticket", "feedback"):
        return f"\n> 未知条目类型 `{item_type}`，按问题类文档生成。\n"
    return ""


def _track_section(document_path: str, writeback_status: str) -> str:
    return f"""## 追踪信息

- 输出文件: {document_path}
- 回写禅道: {writeback_status}
"""


def _render_key_evidence_table(analysis: AnalysisResult) -> str:
    locations = getattr(analysis, "cited_evidence_locations", []) or []
    if not locations:
        return "无可定位代码证据"
    rows = ["| 文件 | 行号 | 符号 | 说明 |", "|---|---:|---|---|"]
    for location in locations:
        line_range = f"{location.line_start}-{location.line_end}"
        rows.append(
            "| {path} | {line_range} | {symbol} | {reason} |".format(
                path=location.path,
                line_range=line_range,
                symbol=location.symbol or "",
                reason=location.reason or "",
            )
        )
    return "\n".join(rows)


def _source_info(item: ZentaoItem, generated_at: str) -> str:
    return f"""## 来源信息

- 条目类型: {item.type}
- 条目 ID: {item.id}
- 状态: {item.status}
- 优先级: {item.priority or "未提供"}
- 生成时间: {generated_at}
"""


def _render_prd(item: ZentaoItem, analysis: AnalysisResult, generated_at: str, document_path: str, writeback_status: str) -> str:
    evidence = "\n".join(f"- {e}" for e in analysis.evidence) if analysis.evidence else "无"
    gaps = "\n".join(f"- {g}" for g in analysis.gaps) if analysis.gaps else "无"
    recommendations = "\n".join(f"- {r}" for r in analysis.recommendations) if analysis.recommendations else "无"
    verification = "\n".join(f"- {v}" for v in analysis.verification) if analysis.verification else "无"

    diagnostic_banner = ""
    if analysis.error or analysis.is_insufficient_evidence():
        diagnostic_banner = "> 诊断文档：当前条目未能生成完整 PRD。\n\n"

    return f"""# PRD: {item.title}

{diagnostic_banner}{_source_info(item, generated_at)}

## 原始需求摘要

{item.description or "未提供"}

## LLM 理解摘要

{_build_llm_summary(analysis)}

## 实现完成度

- **结论**：{analysis.conclusion or "未判断"}
- **优先级**：{analysis.priority or "未评估"}
- **可信度**：{analysis.confidence or "未评估"}

## 实现证据

{evidence}

## 关键代码证据

{_render_key_evidence_table(analysis)}

## 差异与缺口

{gaps}

## 修改建议

{recommendations}

## 验证建议

{verification}

{_track_section(document_path, writeback_status)}

---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
"""


def _render_issue(item: ZentaoItem, analysis: AnalysisResult, generated_at: str, document_path: str, writeback_status: str) -> str:
    evidence = "\n".join(f"- {e}" for e in analysis.evidence) if analysis.evidence else "无"
    suspected = "\n".join(f"- {s}" for s in analysis.suspected_causes) if analysis.suspected_causes else "无"
    affected = "\n".join(f"- {a}" for a in analysis.affected_scope) if analysis.affected_scope else "无"
    recommendations = "\n".join(f"- {r}" for r in analysis.recommendations) if analysis.recommendations else "无"
    verification = "\n".join(f"- {v}" for v in analysis.verification) if analysis.verification else "无"

    diagnostic_banner = ""
    if analysis.error or analysis.is_insufficient_evidence():
        diagnostic_banner = "> 诊断文档：当前条目未能生成完整 ISSUE。\n\n"

    unknown_notice = _unknown_type_notice(item.type)

    return f"""# ISSUE: {item.title}

{diagnostic_banner}{_source_info(item, generated_at)}
{unknown_notice}
## 问题描述摘要

{item.description or "未提供"}

## LLM 理解摘要

{_build_llm_summary(analysis)}

## 定位结论

- **结论**：{analysis.conclusion or "未判断"}
- **优先级**：{analysis.priority or "未评估"}
- **可信度**：{analysis.confidence or "未评估"}

## 代码证据

{evidence}

## 关键代码证据

{_render_key_evidence_table(analysis)}

## 可能根因

{suspected}

## 影响范围

{affected}

## 修复建议

{recommendations}

## 复现与验证建议

{verification}

{_track_section(document_path, writeback_status)}

---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
"""


def generate_document(
    item: ZentaoItem,
    analysis: AnalysisResult,
    output_root: str = "docs",
    generated_at: Optional[str] = None,
) -> DocumentResult:
    """生成单个 PRD/ISSUE Markdown 文档"""
    if generated_at is None:
        from datetime import datetime, timezone
        generated_at = datetime.now(timezone.utc).astimezone().isoformat()

    doc_type = _document_type_from_item_type(item.type)
    is_diagnostic = bool(analysis.error) or analysis.is_insufficient_evidence()

    safe_title = sanitize_title(item.title)
    if doc_type == "PRD":
        subdir = "prd"
        filename = f"PRD-{item.type}-{item.id}-{safe_title}.md"
    else:
        subdir = "issue"
        filename = f"ISSUE-{item.type}-{item.id}-{safe_title}.md"

    output_dir = os.path.join(output_root, subdir)
    os.makedirs(output_dir, exist_ok=True)
    document_path = os.path.join(output_dir, filename)

    writeback_status = "not_implemented"

    if doc_type == "PRD":
        content = _render_prd(item, analysis, generated_at, document_path, writeback_status)
    else:
        content = _render_issue(item, analysis, generated_at, document_path, writeback_status)

    with open(document_path, "w", encoding="utf-8") as f:
        f.write(content)

    return DocumentResult(
        item_id=item.id,
        item_type=item.type,
        title=item.title,
        document_type=doc_type,
        document_path=document_path,
        is_diagnostic=is_diagnostic,
        error=analysis.error,
    )
