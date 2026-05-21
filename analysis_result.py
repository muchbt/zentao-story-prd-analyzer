import dataclasses
from typing import Any, Dict, List

from zentao_client import ZentaoItem


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

    @classmethod
    def from_llm_json(cls, item: ZentaoItem, data: Dict[str, Any], raw_response: str = "") -> "AnalysisResult":
        if not isinstance(data, dict):
            data = {}
        return cls(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            conclusion=data.get("conclusion", ""),
            evidence=data.get("evidence", []),
            gaps=data.get("gaps", []),
            suspected_causes=data.get("suspected_causes", []),
            affected_scope=data.get("affected_scope", []),
            recommendations=data.get("recommendations", []),
            verification=data.get("verification", []),
            priority=data.get("priority", ""),
            confidence=data.get("confidence", ""),
            output_md=data.get("output_md", ""),
            raw_response=raw_response,
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
