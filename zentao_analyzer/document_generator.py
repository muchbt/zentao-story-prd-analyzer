import dataclasses
import os
import re
from typing import Optional

import re

from .zentao_client import ZentaoItem
from .analysis_result import AnalysisResult, RequirementPoint, RPStatus, CodeImpactLocation
from .markdown_to_html import markdown_to_html


@dataclasses.dataclass
class DocumentResult:
    item_id: str
    item_type: str
    title: str
    document_type: str  # "PRD" | "ISSUE"
    document_path: str
    html_path: str = ""
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
    if analysis.error:
        return f"分析过程中出现错误：{analysis.error}。无法生成完整结论。"

    if analysis.understanding_summary:
        return analysis.understanding_summary

    if analysis.is_insufficient_evidence():
        return "未提供独立的需求理解摘要；当前分析证据不足，无法生成可靠理解说明。"

    parts = ["未提供独立的需求理解摘要。"]
    if analysis.conclusion:
        parts.append(f"代码分析结论为：{analysis.conclusion}。详细证据、缺口和建议见后续章节。")
    return "\n".join(parts)


def _unknown_type_notice(item_type: str) -> str:
    if item_type not in ("story", "requirement", "bug", "ticket", "feedback"):
        return f"\n> 未知条目类型 `{item_type}`，按问题类文档生成。\n"
    return ""


_INSUFFICIENT_MSG = "原始需求未提供足够信息"
_NO_CONTENT_MSG = "分析结果未提供有效内容"


def _source_label(source: str) -> str:
    if source == "code_context":
        return " *（代码侧候选上下文，不构成需求定义）*"
    return ""


def _interpretation_field_invalid(analysis: AnalysisResult, *fields: str) -> bool:
    issues = set(getattr(analysis, "rich_content_issues", []) or [])
    if "requirement_interpretation_invalid_schema" in issues:
        return True
    return any(f"requirement_interpretation_invalid_{field}" in issues for field in fields)


def _render_scope(analysis: AnalysisResult) -> str:
    if _interpretation_field_invalid(analysis, "scope"):
        return _NO_CONTENT_MSG
    interp = analysis.requirement_interpretation
    if interp is None:
        return _NO_CONTENT_MSG
    if not interp.scope:
        return _INSUFFICIENT_MSG
    lines = []
    for entry in interp.scope:
        if entry.source == "insufficient":
            lines.append(f"- {_INSUFFICIENT_MSG}")
        else:
            label = _source_label(entry.source)
            lines.append(f"- {entry.text}{label}")
    return "\n".join(lines) if lines else _INSUFFICIENT_MSG


def _render_terms(analysis: AnalysisResult) -> str:
    if _interpretation_field_invalid(analysis, "terms"):
        return _NO_CONTENT_MSG
    interp = analysis.requirement_interpretation
    if interp is None:
        return _NO_CONTENT_MSG
    if not interp.terms:
        return _INSUFFICIENT_MSG
    rows = ["| 术语 | 定义 |", "|---|---|"]
    for term in interp.terms:
        if term.source == "insufficient":
            rows.append(f"| {term.term or '（未提供）'} | {_INSUFFICIENT_MSG} |")
        else:
            label = _source_label(term.source)
            rows.append(f"| {term.term}{label} | {term.definition or '（未提供）'} |")
    return "\n".join(rows)


def _render_rules(analysis: AnalysisResult) -> str:
    if _interpretation_field_invalid(analysis, "rules"):
        return _NO_CONTENT_MSG
    interp = analysis.requirement_interpretation
    if interp is None:
        return _NO_CONTENT_MSG
    if not interp.rules:
        return _INSUFFICIENT_MSG
    lines = []
    for rule in interp.rules:
        if rule.source == "insufficient":
            lines.append(f"- **{rule.title or '（未命名）'}**: {_INSUFFICIENT_MSG}")
        else:
            label = _source_label(rule.source)
            desc = rule.description or "（未提供描述）"
            lines.append(f"- **{rule.title}**{label}: {desc}")
    return "\n".join(lines) if lines else _INSUFFICIENT_MSG


def _render_scenarios_and_flow(analysis: AnalysisResult) -> str:
    if _interpretation_field_invalid(analysis, "scenarios", "flow"):
        return _NO_CONTENT_MSG
    interp = analysis.requirement_interpretation
    if interp is None:
        return _NO_CONTENT_MSG
    parts = []
    if interp.scenarios:
        for scenario in interp.scenarios:
            if scenario.source == "insufficient":
                parts.append(f"#### {scenario.title or '（未命名）'}\n\n{_INSUFFICIENT_MSG}")
            else:
                label = _source_label(scenario.source)
                lines = [f"#### {scenario.title}{label}"]
                if scenario.precondition:
                    lines.append(f"- 前置条件: {scenario.precondition}")
                if scenario.trigger:
                    lines.append(f"- 触发条件: {scenario.trigger}")
                if scenario.expected_behavior:
                    lines.append("- 期望行为:")
                    for behavior in scenario.expected_behavior:
                        lines.append(f"  - {behavior}")
                parts.append("\n".join(lines))
    if interp.flow:
        if interp.flow.source == "insufficient":
            parts.append(f"#### {interp.flow.title or '流程'}\n\n{_INSUFFICIENT_MSG}")
        else:
            label = _source_label(interp.flow.source)
            flow_content = interp.flow.content or "（未提供）"
            parts.append(f"#### {interp.flow.title or '流程'}{label}\n\n{flow_content}")
    if not parts:
        return _INSUFFICIENT_MSG
    return "\n\n".join(parts)


def _render_matrix(analysis: AnalysisResult) -> str:
    if _interpretation_field_invalid(analysis, "matrix"):
        return _NO_CONTENT_MSG
    interp = analysis.requirement_interpretation
    if interp is None:
        return _NO_CONTENT_MSG
    if interp.matrix is None:
        return _INSUFFICIENT_MSG
    matrix = interp.matrix
    if matrix.source == "insufficient":
        return _INSUFFICIENT_MSG
    if not matrix.columns or not matrix.rows:
        return _INSUFFICIENT_MSG
    label = _source_label(matrix.source)
    header = "| " + " | ".join(matrix.columns) + " |"
    sep = "| " + " | ".join("---" for _ in matrix.columns) + " |"
    rows = [header, sep]
    for row in matrix.rows:
        padded = row + [""] * (len(matrix.columns) - len(row))
        rows.append("| " + " | ".join(padded[:len(matrix.columns)]) + " |")
    title_line = f"**{matrix.title}**{label}" if matrix.title else ""
    if title_line:
        return title_line + "\n\n" + "\n".join(rows)
    return "\n".join(rows)


def _render_pending_confirmations(analysis: AnalysisResult) -> str:
    if _interpretation_field_invalid(analysis, "pending_confirmations"):
        return _NO_CONTENT_MSG
    interp = analysis.requirement_interpretation
    if interp is None:
        return _NO_CONTENT_MSG
    if not interp.pending_confirmations:
        return _INSUFFICIENT_MSG
    return "\n".join(f"- {item}" for item in interp.pending_confirmations)


def _render_code_impact_notes(analysis: AnalysisResult) -> str:
    impact = analysis.code_impact
    if impact is None or not impact.impact_notes:
        return _NO_CONTENT_MSG
    return "\n".join(f"- {n}" for n in impact.impact_notes)


def _render_unified_code_table(analysis: AnalysisResult) -> str:
    impact = analysis.code_impact
    impact_locs = impact.related_locations if impact else []
    rps = getattr(analysis, "requirement_points", []) or []

    impact_map: dict = {}
    for loc in impact_locs:
        if loc.path and loc.line_start > 0 and loc.line_end > 0:
            key = (loc.path, loc.line_start, loc.line_end)
            impact_map[key] = (loc.component or "", loc.symbol or "", loc.reason or "")

    evidence_map: dict = {}
    for rp in rps:
        for ev in rp.evidence:
            if ev.path and ev.line_start > 0 and ev.line_end > 0:
                key = (ev.path, ev.line_start, ev.line_end)
                if key not in evidence_map:
                    evidence_map[key] = {}
                evidence_map[key][rp.id] = (ev.symbol or "", ev.reason or "")

    cited_locs = getattr(analysis, "cited_evidence_locations", []) or []
    cited_fallback: dict = {}
    for loc in cited_locs:
        if loc.path and loc.line_start > 0 and loc.line_end > 0:
            key = (loc.path, loc.line_start, loc.line_end)
            if key not in evidence_map:
                evidence_map[key] = {}
            cited_fallback[key] = (loc.symbol or "", loc.reason or "")

    all_keys = set()
    all_keys.update(impact_map.keys())
    all_keys.update(evidence_map.keys())

    if not all_keys:
        return _NO_CONTENT_MSG

    rows = ["| 关联模块 | 文件 | 行号 | 符号 | 影响说明 | 证据说明 |",
            "|---|---|---|---|---|---|"]

    MAX_EVID_PREVIEW = 50

    def _shorten(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "…"

    for key in sorted(all_keys):
        path, line_start, line_end = key
        component, impact_symbol, impact_reason = impact_map.get(key, ("", "", ""))
        rp_entries = evidence_map.get(key, {})
        all_rp_ids = sorted(rp_entries.keys())

        symbol = impact_symbol
        if not symbol and rp_entries:
            for sid, sreason in rp_entries.values():
                if sid:
                    symbol = sid
                    break
        if not symbol and key in cited_fallback:
            symbol = cited_fallback[key][0]

        impact_text = impact_reason or "—"

        if all_rp_ids:
            preview = ""
            for pid, (esym, ereason) in rp_entries.items():
                if ereason:
                    first_sent = ereason.split("。")[0].split(": ")[-1]
                    parts = [p.strip() for p in first_sent.split("，") if p.strip()]
                    preview = parts[0] if parts else first_sent
                    break
            ref_ids = "、".join(f"见 {pid}" for pid in all_rp_ids)
            if preview:
                evidence_text = f"{_shorten(preview, MAX_EVID_PREVIEW)}（{ref_ids}）"
            else:
                evidence_text = ref_ids
        elif key in cited_fallback:
            fallback_reason = cited_fallback[key][1]
            evidence_text = _shorten(fallback_reason, MAX_EVID_PREVIEW) or "—"
        else:
            evidence_text = "—"

        line_range = f"{line_start}-{line_end}"
        rows.append(
            f"| {component} | {path} | {line_range} | {symbol} | {impact_text} | {evidence_text} |"
        )

    return "\n".join(rows)


def _render_interpretation_summary(analysis: AnalysisResult, item_description: str = "") -> str:
    if _interpretation_field_invalid(analysis, "summary"):
        return _NO_CONTENT_MSG
    if analysis.requirement_interpretation and analysis.requirement_interpretation.summary:
        return analysis.requirement_interpretation.summary
    if analysis.understanding_summary:
        return analysis.understanding_summary
    if item_description:
        return item_description
    return _build_llm_summary(analysis)


def _track_section(document_path: str, writeback_status: str) -> str:
    return f"""## 追踪信息

- 输出文件: {document_path}
- 回写禅道: {writeback_status}
"""


def _render_requirement_points_table(analysis: AnalysisResult) -> str:
    rps = getattr(analysis, "requirement_points", []) or []
    if not rps:
        return ""
    rows = ["| ID | 需求点 | 状态 | 说明 |", "|---|---|---|---|"]
    for rp in rps:
        reason = rp.reason or ""
        rows.append(f"| {rp.id} | {rp.description} | {rp.status} | {reason} |")
    return "\n".join(rows)


def _render_prd_gaps(analysis: AnalysisResult) -> str:
    rps = getattr(analysis, "requirement_points", []) or []
    if rps:
        gaps = analysis.gaps
        if gaps:
            return "\n".join(f"- {g}" for g in gaps)
        if analysis.conclusion in (RPStatus.INDETERMINATE,):
            return "无法确定是否存在缺口"
        return "无"
    if analysis.gaps:
        return "\n".join(f"- {g}" for g in analysis.gaps)
    if analysis.is_insufficient_evidence():
        return "无法确定是否存在缺口"
    return "无"


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


def _render_supplemental_evidence(analysis: AnalysisResult) -> str:
    locations = getattr(analysis, "cited_evidence_locations", []) or []
    evidence = getattr(analysis, "evidence", []) or []
    if not evidence:
        return ""
    represented = {
        " ".join(
            part for part in (
                f"{loc.path}:{loc.line_start}-{loc.line_end}",
                loc.symbol or "",
                loc.reason or "",
            ) if part
        )
        for loc in locations
    }
    supplemental = [item for item in evidence if item not in represented]
    if not supplemental:
        return ""
    notes = "\n".join(f"- {item}" for item in supplemental)
    return f"补充说明：\n\n{notes}"


def validate_document_consistency(analysis: AnalysisResult, document: DocumentResult):
    issues = []
    try:
        with open(document.document_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return ["document_unreadable"]

    expected_diagnostic = bool(analysis.error) or analysis.is_insufficient_evidence()
    if document.is_diagnostic != expected_diagnostic:
        issues.append("diagnostic_flag_mismatch")
    if not expected_diagnostic and "诊断文档：当前条目未能生成完整" in content:
        issues.append("unexpected_diagnostic_banner")
    locations = getattr(analysis, "cited_evidence_locations", []) or []
    if locations:
        evidence_heading = "### 3.1 代码位置总览" if document.document_type == "PRD" else "## 关键代码证据"
        if evidence_heading not in content:
            issues.append("missing_key_evidence_section")
        if not any(location.path and location.path in content for location in locations):
            issues.append("missing_cited_evidence_path")
    return issues


def _source_info(item: ZentaoItem, generated_at: str) -> str:
    return f"""## 来源信息

- 条目类型: {item.type}
- 条目 ID: {item.id}
- 状态: {item.status}
- 优先级: {item.priority or "未提供"}
- 生成时间: {generated_at}
"""


def _prd_source_info(item: ZentaoItem, generated_at: str, requirement_source: str = "zentao") -> str:
    source_desc = "禅道" if requirement_source == "zentao" else "用户提交"
    return f"""### 1.4 来源信息

- 条目类型: {item.type}
- 条目 ID: {item.id}
- 需求来源: {source_desc}
- 状态: {item.status}
- 优先级: {item.priority or "未提供"}
- 生成时间: {generated_at}
"""


def _prd_track_section(document_path: str, writeback_status: str) -> str:
    return f"""### 6.1 追踪信息

- 输出文件: {document_path}
- 回写禅道: {writeback_status}
"""


def _render_completion_ratio(analysis: AnalysisResult) -> str:
    rps = getattr(analysis, "requirement_points", []) or []
    if not rps:
        return ""
    total = len(rps)
    counts: dict = {}
    for rp in rps:
        counts[rp.status] = counts.get(rp.status, 0) + 1
    labels = {"完成": "完成", "部分完成": "部分完成", "未完成": "未完成", "无法判断": "无法判断"}
    parts = [f"{counts[s]} {labels[s]}" for s in labels if counts.get(s, 0) > 0]
    return f"- **需求点统计**：{'、'.join(parts)}（共 {total}）"


def _render_prd(item: ZentaoItem, analysis: AnalysisResult, generated_at: str, document_path: str, writeback_status: str) -> str:
    gaps = _render_prd_gaps(analysis)
    recommendations = "\n".join(f"- {r}" for r in analysis.recommendations) if analysis.recommendations else "无"
    verification = "\n".join(f"- {v}" for v in analysis.verification) if analysis.verification else "无"

    diagnostic_banner = ""
    if analysis.error or analysis.is_insufficient_evidence():
        diagnostic_banner = "> 诊断文档：当前条目未能生成完整 PRD。\n\n"

    rp_table = _render_requirement_points_table(analysis) or "未提取结构化需求点。"
    scope = _render_scope(analysis)
    terms = _render_terms(analysis)
    summary_text = _render_interpretation_summary(analysis, item.description or "")
    source_description = item.description or _INSUFFICIENT_MSG
    rules = _render_rules(analysis)
    scenarios = _render_scenarios_and_flow(analysis)
    matrix = _render_matrix(analysis)
    pending = _render_pending_confirmations(analysis)
    source_info = _prd_source_info(item, generated_at, analysis.requirement_source)
    unified_table = _render_unified_code_table(analysis)
    impact_notes = _render_code_impact_notes(analysis)
    supplemental = _render_supplemental_evidence(analysis)
    ratio_line = _render_completion_ratio(analysis)

    return f"""# PRD: {item.title}

{diagnostic_banner}## 1. 概述

### 1.1 需求摘要

{summary_text}

### 1.2 范围

{scope}

### 1.3 术语定义

{terms}

{source_info}

## 2. 需求解读

原始需求正文：

{source_description}

### 2.1 业务规则

{rules}

### 2.2 场景与流程

{scenarios}

### 2.3 关系或并发矩阵

{matrix}

### 2.4 待确认事项

{pending}

## 3. 代码依据

### 3.1 代码位置总览

{unified_table}

{supplemental}

### 3.2 影响说明

{impact_notes}

### 3.3 实现完成度

- **结论**：{analysis.conclusion or "未判断"}
- **优先级**：{analysis.priority or "未评估"}
- **可信度**：{analysis.confidence or "未评估"}
{ratio_line}

## 4. 完成度评估

### 4.1 需求点完成情况

{rp_table}

### 4.2 差异与缺口

{gaps}

## 5. 实现建议

> 以下建议为参考性质，不构成现有实现描述。

### 5.1 代码变更建议

{recommendations}

### 5.2 测试要点

{verification}

## 6. 参考信息

{_prd_track_section(document_path, writeback_status)}

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

    html_path = ""
    html_filename = filename.rsplit(".", 1)[0] + ".html"
    html_path = os.path.join(output_dir, html_filename)
    html_content = markdown_to_html(content, title=item.title)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return DocumentResult(
        item_id=item.id,
        item_type=item.type,
        title=item.title,
        document_type=doc_type,
        document_path=document_path,
        html_path=html_path,
        is_diagnostic=is_diagnostic,
        error=analysis.error,
    )
