import dataclasses
import re
from typing import Any, Dict, List

from .code_clues import CodeLocation
from .zentao_client import ZentaoItem


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_evidence_object(data: Dict[str, Any]) -> str:
    path = str(data.get("path", "")).strip()
    line_start = _safe_int(data.get("line_start"))
    line_end = _safe_int(data.get("line_end"), line_start)
    symbol = str(data.get("symbol", "")).strip()
    reason = str(data.get("reason", "")).strip()
    location = path
    if path and line_start > 0 and line_end > 0:
        location = f"{path}:{line_start}-{line_end}"
    parts = [location]
    if symbol:
        parts.append(symbol)
    if reason:
        parts.append(reason)
    return " ".join(part for part in parts if part).strip()


def _location_from_evidence_object(data: Dict[str, Any]) -> CodeLocation:
    path = str(data.get("path", "")).strip()
    line_start = _safe_int(data.get("line_start"))
    line_end = _safe_int(data.get("line_end"), line_start)
    if not path or line_start <= 0 or line_end <= 0:
        return None
    return CodeLocation(
        path=path,
        line_start=line_start,
        line_end=line_end,
        symbol=str(data.get("symbol", "")).strip(),
        reason=str(data.get("reason", "")).strip(),
        source="agent",
    )


def _location_from_evidence_text(text: str) -> CodeLocation:
    match = re.search(r"(?P<path>[\w./\\-]+\.[A-Za-z0-9_]+):(?P<start>\d+)(?:-(?P<end>\d+))?", text)
    if not match:
        return None
    start = _safe_int(match.group("start"))
    end = _safe_int(match.group("end"), start)
    if start <= 0 or end <= 0:
        return None
    return CodeLocation(
        path=match.group("path"),
        line_start=start,
        line_end=end,
        source="fallback",
        reason=text,
    )


def parse_evidence(evidence: Any):
    evidence_text: List[str] = []
    cited_locations: List[CodeLocation] = []
    if not isinstance(evidence, list):
        return evidence_text, cited_locations
    for item in evidence:
        if isinstance(item, dict):
            text = _format_evidence_object(item)
            if text:
                evidence_text.append(text)
            location = _location_from_evidence_object(item)
            if location:
                cited_locations.append(location)
        else:
            text = str(item)
            evidence_text.append(text)
            location = _location_from_evidence_text(text)
            if location:
                cited_locations.append(location)
    return evidence_text, cited_locations


@dataclasses.dataclass
class AnalysisResult:
    item_id: str
    item_type: str
    item_title: str
    conclusion: str = ""
    evidence: List[str] = dataclasses.field(default_factory=list)
    gaps: List[str] = dataclasses.field(default_factory=list)
    suspected_causes: List[str] = dataclasses.field(default_factory=list)
    affected_scope: List[str] = dataclasses.field(default_factory=list)
    recommendations: List[str] = dataclasses.field(default_factory=list)
    verification: List[str] = dataclasses.field(default_factory=list)
    priority: str = ""
    confidence: str = ""
    output_md: str = ""
    error: str = ""
    raw_response: str = dataclasses.field(default="", repr=False)
    evidence_text: List[str] = dataclasses.field(default_factory=list)
    cited_evidence_locations: List[CodeLocation] = dataclasses.field(default_factory=list)

    @classmethod
    def from_llm_json(cls, item: ZentaoItem, data: Dict[str, Any], raw_response: str = "") -> "AnalysisResult":
        if not isinstance(data, dict):
            data = {}
        evidence_text, cited_locations = parse_evidence(data.get("evidence", []))
        return cls(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            conclusion=data.get("conclusion", ""),
            evidence=evidence_text,
            gaps=data.get("gaps", []),
            suspected_causes=data.get("suspected_causes", []),
            affected_scope=data.get("affected_scope", []),
            recommendations=data.get("recommendations", []),
            verification=data.get("verification", []),
            priority=data.get("priority", ""),
            confidence=data.get("confidence", ""),
            output_md=data.get("output_md", ""),
            raw_response=raw_response,
            evidence_text=evidence_text,
            cited_evidence_locations=cited_locations,
        )

    @classmethod
    def from_error(cls, item: ZentaoItem, error: str, raw_response: str = "") -> "AnalysisResult":
        return cls(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            conclusion="无法判断" if item.type in ("story", "requirement") else "无法定位",
            error=error,
            raw_response=raw_response,
        )

    def is_insufficient_evidence(self) -> bool:
        if self.error:
            return True
        if self.confidence == "低":
            return True
        if not self.evidence:
            return True
        return False
