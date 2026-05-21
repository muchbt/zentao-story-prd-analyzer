import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from zentao_client import ZentaoItem
from analysis_result import AnalysisResult
from document_generator import DocumentResult


def build_summary_item(
    item: ZentaoItem,
    analysis: AnalysisResult,
    document: DocumentResult,
    writeback: Dict[str, Any],
) -> Dict[str, Any]:
    """为单个条目构建汇总数据结构，排除敏感信息"""
    return {
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
        "recommendation_count": len(analysis.recommendations),
        "verification_count": len(analysis.verification),
        "writeback": writeback,
    }


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
