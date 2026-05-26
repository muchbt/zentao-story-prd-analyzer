import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .zentao_client import ZentaoItem
from .analysis_result import AnalysisResult, RequirementPoint, RPStatus, _coerce_str
from .document_generator import DocumentResult


def build_summary_item(
    item: ZentaoItem,
    analysis: AnalysisResult,
    document: DocumentResult,
    writeback: Dict[str, Any],
    seed_location_count: int = 0,
    rejected_seed_path_count: int = 0,
    invalid_evidence_count: int = 0,
    debug_bundle: str = "",
) -> Dict[str, Any]:
    """为单个条目构建汇总数据结构，排除敏感信息"""
    result: Dict[str, Any] = {
        "item_id": item.id,
        "item_type": item.type,
        "title": item.title,
        "status": item.status,
        "priority": item.priority,
        "document_type": document.document_type,
        "document_path": document.document_path,
        "is_diagnostic": document.is_diagnostic,
        "conclusion": analysis.conclusion,
        "confidence": analysis.confidence,
        "has_error": bool(analysis.error or document.error),
        "error": analysis.error or document.error,
        "insufficient_evidence": analysis.is_insufficient_evidence(),
        "evidence_count": len(analysis.evidence),
        "seed_location_count": seed_location_count,
        "cited_evidence_location_count": len(getattr(analysis, "cited_evidence_locations", []) or []),
        "rejected_seed_path_count": rejected_seed_path_count,
        "invalid_evidence_count": invalid_evidence_count,
        "debug_bundle": debug_bundle,
        "recommendation_count": len(analysis.recommendations),
        "verification_count": len(analysis.verification),
        "writeback": writeback,
    }
    rps_raw = getattr(analysis, "requirement_points", None)
    rps = list(rps_raw) if rps_raw else []
    analysis_status = str(getattr(analysis, "analysis_status", "") or "")
    if item.type in ("story", "requirement"):
        if analysis_status == "requirement_points_unavailable":
            result["has_unconfirmed_requirement_points"] = True
            result["analysis_status"] = analysis_status
            result["analysis_status_detail"] = getattr(analysis, "analysis_status_detail", "") or ""
            result["recommended_action"] = _coerce_str(getattr(analysis, "recommended_action", "")) or (
                "update_zentao_requirement"
                if result["analysis_status_detail"] == "empty_requirement_points"
                else "manual_retry"
            )
        elif rps:
            counts = {
                RPStatus.COMPLETED: 0,
                RPStatus.PARTIALLY_COMPLETED: 0,
                RPStatus.NOT_COMPLETED: 0,
                RPStatus.INDETERMINATE: 0,
            }
            for rp in rps:
                status = rp.status
                if status in counts:
                    counts[status] += 1
            result["requirement_point_count"] = len(rps)
            result["requirement_point_status_counts"] = counts
            result["has_unconfirmed_requirement_points"] = any(
                rp.status == RPStatus.INDETERMINATE for rp in rps
            )
            result["analysis_status"] = analysis_status
    return result


def write_summary_report(
    items: List[Dict[str, Any]],
    output_root: str = "docs",
    generated_at: str = None,
) -> str:
    """写入汇总报告 JSON 文件，返回文件路径"""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).astimezone().isoformat()

    os.makedirs(output_root, exist_ok=True)
    path = os.path.join(output_root, "summary_report.json")

    report = {
        "generated_at": generated_at,
        "count": len(items),
        "prd_dir": os.path.join(output_root, "prd"),
        "issue_dir": os.path.join(output_root, "issue"),
        "items": items,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return path
