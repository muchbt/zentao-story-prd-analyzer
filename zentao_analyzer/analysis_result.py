import dataclasses
import re
from typing import Any, Dict, List, Optional, Tuple

from .zentao_client import ZentaoItem


VALID_SOURCE_ENUM = {"requirement", "code_context", "insufficient"}
VALID_ROLE_EVIDENCE_STATUSES = {"found", "not_found", "ambiguous", "not_searched"}
VALID_PROTOCOL_TRACE_STATUSES = {"closed_loop", "partial", "not_found", "ambiguous"}
VALID_PROTOCOL_HINT_TYPES = {"cmd_id", "msg", "field", "text"}


@dataclasses.dataclass
class InterpretationEntry:
    text: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "source": self.source}


@dataclasses.dataclass
class InterpretationTerm:
    term: str = ""
    definition: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"term": self.term, "definition": self.definition, "source": self.source}


@dataclasses.dataclass
class InterpretationRule:
    title: str = ""
    description: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "description": self.description, "source": self.source}


@dataclasses.dataclass
class RequirementScenario:
    title: str = ""
    precondition: str = ""
    trigger: str = ""
    expected_behavior: List[str] = dataclasses.field(default_factory=list)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "precondition": self.precondition,
            "trigger": self.trigger,
            "expected_behavior": self.expected_behavior,
            "source": self.source,
        }


@dataclasses.dataclass
class RequirementMatrix:
    title: str = ""
    columns: List[str] = dataclasses.field(default_factory=list)
    rows: List[List[str]] = dataclasses.field(default_factory=list)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "columns": self.columns, "rows": self.rows, "source": self.source}


@dataclasses.dataclass
class RequirementFlow:
    title: str = ""
    content: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "content": self.content, "source": self.source}


@dataclasses.dataclass
class RequirementInterpretation:
    summary: str = ""
    scope: List[InterpretationEntry] = dataclasses.field(default_factory=list)
    terms: List[InterpretationTerm] = dataclasses.field(default_factory=list)
    rules: List[InterpretationRule] = dataclasses.field(default_factory=list)
    scenarios: List[RequirementScenario] = dataclasses.field(default_factory=list)
    matrix: Optional[RequirementMatrix] = None
    flow: Optional[RequirementFlow] = None
    pending_confirmations: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "summary": self.summary,
            "scope": [e.to_dict() for e in self.scope],
            "terms": [t.to_dict() for t in self.terms],
            "rules": [r.to_dict() for r in self.rules],
            "scenarios": [s.to_dict() for s in self.scenarios],
            "pending_confirmations": self.pending_confirmations,
        }
        if self.matrix is not None:
            d["matrix"] = self.matrix.to_dict()
        else:
            d["matrix"] = None
        if self.flow is not None:
            d["flow"] = self.flow.to_dict()
        else:
            d["flow"] = None
        return d


@dataclasses.dataclass
class CodeImpactLocation:
    component: str = ""
    path: str = ""
    line_start: int = 0
    line_end: int = 0
    symbol: str = ""
    reason: str = ""
    role: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "symbol": self.symbol,
            "reason": self.reason,
            "role": self.role,
        }


@dataclasses.dataclass
class CodeImpactAnalysis:
    related_locations: List[CodeImpactLocation] = dataclasses.field(default_factory=list)
    impact_notes: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "related_locations": [loc.to_dict() for loc in self.related_locations],
            "impact_notes": self.impact_notes,
        }


@dataclasses.dataclass
class EvidenceLocation:
    path: str
    line_start: int
    line_end: int
    symbol: str = ""
    reason: str = ""
    source: str = ""
    role: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class EvidenceValidationIssue:
    path: str
    line_start: int = 0
    line_end: int = 0
    reason: str = ""
    requirement_point_ids: List[str] = dataclasses.field(default_factory=list)
    role: str = ""


@dataclasses.dataclass
class RoleEvidenceStatus:
    role: str
    status: str
    searched_for: List[str] = dataclasses.field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ProtocolTrace:
    roles: List[str]
    hint_type: str
    value: str
    status: str
    role_statuses: List[RoleEvidenceStatus] = dataclasses.field(default_factory=list)
    evidence: List[EvidenceLocation] = dataclasses.field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hint": {"roles": self.roles, "type": self.hint_type, "value": self.value},
            "status": self.status,
            "role_statuses": [status.to_dict() for status in self.role_statuses],
            "evidence": [location.to_dict() for location in self.evidence],
            "explanation": self.explanation,
        }


class RPStatus:
    COMPLETED = "完成"
    PARTIALLY_COMPLETED = "部分完成"
    NOT_COMPLETED = "未完成"
    INDETERMINATE = "无法判断"
    ALL = {COMPLETED, PARTIALLY_COMPLETED, NOT_COMPLETED, INDETERMINATE}


@dataclasses.dataclass
class RequirementPoint:
    id: str
    description: str
    status: str
    reason: str = ""
    gaps: List[str] = dataclasses.field(default_factory=list)
    evidence: List[EvidenceLocation] = dataclasses.field(default_factory=list)
    _original_status: str = ""
    _correction_reason: str = ""
    _invalid_evidence_issues: List[EvidenceValidationIssue] = dataclasses.field(default_factory=list, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "reason": self.reason,
            "gaps": self.gaps,
            "evidence": [loc.to_dict() for loc in self.evidence],
        }
        if self._original_status:
            d["_original_status"] = self._original_status
        if self._correction_reason:
            d["_correction_reason"] = self._correction_reason
        return d


@dataclasses.dataclass
class RPValidationResult:
    valid: bool = False
    requirement_points: Optional[List[RequirementPoint]] = None
    failure_reason: str = ""
    has_invalid_evidence: bool = False


def parse_requirement_points(data: Any) -> Tuple[List[RequirementPoint], bool, set]:
    if not isinstance(data, list):
        return [], True, set()
    rps: List[RequirementPoint] = []
    has_malformed_items = False
    rp_ids_with_invalid_evidence: set = set()
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            has_malformed_items = True
            continue
        rp_id = f"RP-{idx + 1:03d}"
        description = _coerce_str(item.get("description", ""))
        status = _coerce_str(item.get("status", ""))
        reason = _coerce_str(item.get("reason", ""))
        gaps = _coerce_str_list(item.get("gaps", []))
        evidence_data = item.get("evidence", [])
        rp_evidence: List[EvidenceLocation] = []
        invalid_evidence_issues: List[EvidenceValidationIssue] = []
        if isinstance(evidence_data, list):
            for ev in evidence_data:
                if isinstance(ev, dict):
                    loc = _location_from_evidence_object(ev)
                    if loc:
                        rp_evidence.append(loc)
                    else:
                        rp_ids_with_invalid_evidence.add(rp_id)
                        invalid_evidence_issues.append(_invalid_evidence_issue(ev, rp_id))
                elif isinstance(ev, str):
                    loc = _location_from_evidence_text(ev)
                    if loc:
                        rp_evidence.append(loc)
                    else:
                        rp_ids_with_invalid_evidence.add(rp_id)
                        invalid_evidence_issues.append(_invalid_evidence_issue(ev, rp_id))
                else:
                    rp_ids_with_invalid_evidence.add(rp_id)
                    invalid_evidence_issues.append(_invalid_evidence_issue(ev, rp_id))
        else:
            rp_ids_with_invalid_evidence.add(rp_id)
            invalid_evidence_issues.append(_invalid_evidence_issue(evidence_data, rp_id))
        rps.append(RequirementPoint(
            id=rp_id,
            description=description,
            status=status,
            reason=reason,
            gaps=gaps,
            evidence=rp_evidence,
            _invalid_evidence_issues=invalid_evidence_issues,
        ))
    return rps, has_malformed_items, rp_ids_with_invalid_evidence


def validate_requirement_points(rps: List[RequirementPoint]) -> RPValidationResult:
    if not rps:
        return RPValidationResult(valid=False, failure_reason="empty_requirement_points")
    descriptions_seen: List[str] = []
    for rp in rps:
        if not rp.description:
            return RPValidationResult(valid=False, failure_reason="invalid_requirement_point_schema")
        if rp.status not in RPStatus.ALL:
            return RPValidationResult(valid=False, failure_reason="invalid_requirement_point_schema")
        if rp.status in (RPStatus.NOT_COMPLETED, RPStatus.PARTIALLY_COMPLETED):
            if not rp.gaps:
                return RPValidationResult(valid=False, failure_reason="invalid_point_gap_state_combination")
        if rp.status in (RPStatus.COMPLETED, RPStatus.INDETERMINATE):
            if rp.gaps:
                return RPValidationResult(valid=False, failure_reason="invalid_point_gap_state_combination")
        if rp.description in descriptions_seen:
            return RPValidationResult(valid=False, failure_reason="invalid_requirement_point_schema")
        descriptions_seen.append(rp.description)
    return RPValidationResult(valid=True, requirement_points=rps)


def compute_item_conclusion(rps: List[RequirementPoint]) -> str:
    if not rps:
        return RPStatus.INDETERMINATE
    statuses = {rp.status for rp in rps}
    has_completed = RPStatus.COMPLETED in statuses
    has_partially = RPStatus.PARTIALLY_COMPLETED in statuses
    has_not_completed = RPStatus.NOT_COMPLETED in statuses
    has_indeterminate = RPStatus.INDETERMINATE in statuses
    if statuses == {RPStatus.COMPLETED}:
        return RPStatus.COMPLETED
    if has_not_completed or has_partially:
        has_confirmed_implementation = any(
            rp.status in (RPStatus.COMPLETED, RPStatus.PARTIALLY_COMPLETED)
            for rp in rps
        )
        if has_confirmed_implementation or has_partially:
            return RPStatus.PARTIALLY_COMPLETED
        if has_indeterminate:
            return RPStatus.PARTIALLY_COMPLETED
        return RPStatus.NOT_COMPLETED
    if has_indeterminate:
        return RPStatus.INDETERMINATE
    if has_completed:
        return RPStatus.COMPLETED
    return RPStatus.INDETERMINATE


def compute_item_gaps(rps: List[RequirementPoint]) -> List[str]:
    gaps: List[str] = []
    for rp in rps:
        for gap in rp.gaps:
            tagged = f"{rp.id}: {gap}" if gap else f"{rp.id}"
            gaps.append(tagged)
    return gaps


def compute_item_confidence(
    rps: List[RequirementPoint],
    has_fallback_evidence: bool = False,
    has_invalid_evidence: bool = False,
) -> str:
    if not rps:
        return "低"
    if has_invalid_evidence:
        return "低"
    confirmed_count = sum(
        1 for rp in rps
        if rp.status in (RPStatus.COMPLETED, RPStatus.PARTIALLY_COMPLETED)
    )
    if confirmed_count == len(rps) and all(rp.status == RPStatus.COMPLETED for rp in rps):
        if has_fallback_evidence:
            return "中"
        return "高"
    if confirmed_count > 0:
        return "中"
    return "低"


def aggregate_evidence_from_rps(rps: List[RequirementPoint]) -> List[EvidenceLocation]:
    seen_keys: set = set()
    result: List[EvidenceLocation] = []
    for rp in rps:
        for loc in rp.evidence:
            key = (loc.role, loc.path, loc.line_start, loc.line_end, loc.symbol)
            if key not in seen_keys:
                seen_keys.add(key)
                result.append(loc)
    return result


def aggregate_evidence_text_from_rps(rps: List[RequirementPoint]) -> List[str]:
    locations = aggregate_evidence_from_rps(rps)
    evidence_text: List[str] = []
    for loc in locations:
        role_prefix = f"{loc.role}:" if loc.role else ""
        text_parts = [f"{role_prefix}{loc.path}:{loc.line_start}-{loc.line_end}"]
        if loc.symbol:
            text_parts.append(loc.symbol)
        if loc.reason:
            text_parts.append(loc.reason)
        evidence_text.append(" ".join(text_parts))
    return evidence_text


def validate_rp_evidence_locations(
    repo_path: str, rps: List[RequirementPoint]
) -> List[Tuple[str, List[EvidenceValidationIssue]]]:
    from .analyzer import validate_evidence_locations as _validate_loc
    result: List[Tuple[str, List[EvidenceValidationIssue]]] = []
    for rp in rps:
        rp_result = AnalysisResult(
            item_id="", item_type="", item_title="",
            cited_evidence_locations=rp.evidence,
        )
        issues = _validate_loc(repo_path, rp_result)
        for issue in issues:
            issue.requirement_point_ids = [rp.id]
        result.append((rp.id, issues))
    return result


def correct_invalidated_rps(
    rps: List[RequirementPoint],
    rp_issues: List[Tuple[str, List[EvidenceValidationIssue]]],
) -> Tuple[List[RequirementPoint], List[EvidenceValidationIssue], int]:
    invalid_rp_ids: set = set()
    all_unique_issues: List[EvidenceValidationIssue] = []
    seen_issue_keys: set = set()
    for rp_id, issues in rp_issues:
        if issues:
            invalid_rp_ids.add(rp_id)
        for issue in issues:
            key = (issue.role, issue.path, issue.line_start, issue.line_end, issue.reason)
            if key not in seen_issue_keys:
                seen_issue_keys.add(key)
                all_unique_issues.append(issue)
            else:
                existing = next(
                    existing_issue for existing_issue in all_unique_issues
                    if (existing_issue.role, existing_issue.path, existing_issue.line_start, existing_issue.line_end, existing_issue.reason) == key
                )
                for point_id in issue.requirement_point_ids:
                    if point_id not in existing.requirement_point_ids:
                        existing.requirement_point_ids.append(point_id)
    corrected: List[RequirementPoint] = []
    for rp in rps:
        if rp.id in invalid_rp_ids:
            rp._original_status = rp._original_status or rp.status
            rp.status = RPStatus.INDETERMINATE
            rp._correction_reason = "evidence_location_validation_failed"
            rp.gaps = []
            rp.evidence = []
            rp.reason = "证据位置校验失败，修正为无法判断"
        corrected.append(rp)
    return corrected, all_unique_issues, len(all_unique_issues)


def correct_rps_without_valid_evidence(rps: List[RequirementPoint]) -> List[RequirementPoint]:
    for rp in rps:
        if rp.status in (RPStatus.COMPLETED, RPStatus.PARTIALLY_COMPLETED, RPStatus.NOT_COMPLETED):
            if not rp.evidence:
                rp._original_status = rp._original_status or rp.status
                rp.status = RPStatus.INDETERMINATE
                rp._correction_reason = rp._correction_reason or "no_valid_evidence_for_confirmed_status"
                rp.gaps = []
                rp.reason = "无有效代码证据支持确认状态，修正为无法判断"
    return rps


def _coerce_source(value: Any) -> str:
    s = _coerce_str(value)
    return s if s in VALID_SOURCE_ENUM else "insufficient"


def _add_issue(issues: List[str], issue: str) -> None:
    if issue not in issues:
        issues.append(issue)


def _parse_interpretation_list(
    data: Dict[str, Any], field: str, parser: Any, issues: List[str]
) -> List[Any]:
    if field not in data:
        return []
    raw_items = data.get(field)
    if not isinstance(raw_items, list):
        _add_issue(issues, f"requirement_interpretation_invalid_{field}")
        return []
    parsed: List[Any] = []
    for item in raw_items:
        if not isinstance(item, dict):
            _add_issue(issues, f"requirement_interpretation_invalid_{field}")
            parsed.append(parser({"source": "insufficient"}))
            continue
        if _coerce_str(item.get("source", "")) not in VALID_SOURCE_ENUM:
            _add_issue(issues, "requirement_interpretation_invalid_source")
            parsed.append(parser({"source": "insufficient"}))
            continue
        parsed.append(parser(item))
    return parsed


def _parse_interpretation_entry(item: Any) -> InterpretationEntry:
    if not isinstance(item, dict):
        return InterpretationEntry(text=_coerce_str(item), source="insufficient")
    return InterpretationEntry(
        text=_coerce_str(item.get("text", "")),
        source=_coerce_source(item.get("source", "")),
    )


def _parse_interpretation_term(item: Any) -> InterpretationTerm:
    if not isinstance(item, dict):
        return InterpretationTerm(term=_coerce_str(item), definition="", source="insufficient")
    return InterpretationTerm(
        term=_coerce_str(item.get("term", "")),
        definition=_coerce_str(item.get("definition", "")),
        source=_coerce_source(item.get("source", "")),
    )


def _parse_interpretation_rule(item: Any) -> InterpretationRule:
    if not isinstance(item, dict):
        return InterpretationRule(title=_coerce_str(item), description="", source="insufficient")
    return InterpretationRule(
        title=_coerce_str(item.get("title", "")),
        description=_coerce_str(item.get("description", "")),
        source=_coerce_source(item.get("source", "")),
    )


def _parse_requirement_scenario(item: Any) -> RequirementScenario:
    if not isinstance(item, dict):
        return RequirementScenario(title=_coerce_str(item), source="insufficient")
    behavior = item.get("expected_behavior", [])
    if isinstance(behavior, list):
        behavior = [_coerce_str(b) for b in behavior if _coerce_str(b)]
    else:
        behavior = []
    return RequirementScenario(
        title=_coerce_str(item.get("title", "")),
        precondition=_coerce_str(item.get("precondition", "")),
        trigger=_coerce_str(item.get("trigger", "")),
        expected_behavior=behavior,
        source=_coerce_source(item.get("source", "")),
    )


def _parse_requirement_matrix(data: Any) -> Optional[RequirementMatrix]:
    if not isinstance(data, dict):
        return None
    columns = data.get("columns", [])
    if not isinstance(columns, list):
        columns = []
    columns = [_coerce_str(c) for c in columns if _coerce_str(c)]
    rows_data = data.get("rows", [])
    if not isinstance(rows_data, list):
        rows_data = []
    rows = []
    for row in rows_data:
        if isinstance(row, list):
            rows.append([_coerce_str(c) for c in row])
    return RequirementMatrix(
        title=_coerce_str(data.get("title", "")),
        columns=columns,
        rows=rows,
        source=_coerce_source(data.get("source", "")),
    )


def _parse_requirement_flow(data: Any) -> Optional[RequirementFlow]:
    if not isinstance(data, dict):
        return None
    return RequirementFlow(
        title=_coerce_str(data.get("title", "")),
        content=_coerce_str(data.get("content", "")),
        source=_coerce_source(data.get("source", "")),
    )


def parse_requirement_interpretation(data: Any) -> Tuple[Optional[RequirementInterpretation], List[str]]:
    issues: List[str] = []
    if data is None:
        return None, ["requirement_interpretation_missing"]
    if not isinstance(data, dict):
        return None, ["requirement_interpretation_invalid_schema"]
    if "summary" in data and not isinstance(data.get("summary"), str):
        _add_issue(issues, "requirement_interpretation_invalid_summary")
    scope = _parse_interpretation_list(data, "scope", _parse_interpretation_entry, issues)
    terms = _parse_interpretation_list(data, "terms", _parse_interpretation_term, issues)
    rules = _parse_interpretation_list(data, "rules", _parse_interpretation_rule, issues)
    scenarios = _parse_interpretation_list(data, "scenarios", _parse_requirement_scenario, issues)
    for scenario in data.get("scenarios", []) if isinstance(data.get("scenarios", []), list) else []:
        if isinstance(scenario, dict) and "expected_behavior" in scenario and not isinstance(scenario.get("expected_behavior"), list):
            _add_issue(issues, "requirement_interpretation_invalid_scenarios")
    matrix_data = data.get("matrix")
    parsed_matrix_data = matrix_data
    if matrix_data is not None:
        if not isinstance(matrix_data, dict):
            _add_issue(issues, "requirement_interpretation_invalid_matrix")
        else:
            if _coerce_str(matrix_data.get("source", "")) not in VALID_SOURCE_ENUM:
                _add_issue(issues, "requirement_interpretation_invalid_source")
                parsed_matrix_data = {"source": "insufficient"}
            if not isinstance(matrix_data.get("columns", []), list) or not isinstance(matrix_data.get("rows", []), list):
                _add_issue(issues, "requirement_interpretation_invalid_matrix")
    flow_data = data.get("flow")
    parsed_flow_data = flow_data
    if flow_data is not None:
        if not isinstance(flow_data, dict):
            _add_issue(issues, "requirement_interpretation_invalid_flow")
        elif _coerce_str(flow_data.get("source", "")) not in VALID_SOURCE_ENUM:
            _add_issue(issues, "requirement_interpretation_invalid_source")
            parsed_flow_data = {"source": "insufficient"}
    matrix = _parse_requirement_matrix(parsed_matrix_data)
    flow = _parse_requirement_flow(parsed_flow_data)
    pending = data.get("pending_confirmations", [])
    if not isinstance(pending, list):
        _add_issue(issues, "requirement_interpretation_invalid_pending_confirmations")
        pending = []
    pending = [_coerce_str(p) for p in pending if _coerce_str(p)]
    interp = RequirementInterpretation(
        summary=_coerce_str(data.get("summary", "")),
        scope=scope,
        terms=terms,
        rules=rules,
        scenarios=scenarios,
        matrix=matrix,
        flow=flow,
        pending_confirmations=pending,
    )
    return interp, issues


def _parse_code_impact_location(item: Any) -> Optional[CodeImpactLocation]:
    if not isinstance(item, dict):
        return None
    path = _coerce_str(item.get("path", ""))
    line_start = _safe_int(item.get("line_start"))
    line_end = _safe_int(item.get("line_end"), line_start)
    return CodeImpactLocation(
        component=_coerce_str(item.get("component", "")),
        path=path,
        line_start=line_start,
        line_end=line_end,
        symbol=_coerce_str(item.get("symbol", "")),
        reason=_coerce_str(item.get("reason", "")),
        role=_coerce_str(item.get("role", "")),
    )


def parse_code_impact(data: Any) -> Tuple[Optional[CodeImpactAnalysis], List[str]]:
    issues: List[str] = []
    if data is None:
        return None, ["code_impact_missing"]
    if not isinstance(data, dict):
        return None, ["code_impact_invalid_schema"]
    locs_data = data.get("related_locations", [])
    if not isinstance(locs_data, list):
        _add_issue(issues, "code_impact_invalid_related_locations")
        locs_data = []
    raw_locs: List[CodeImpactLocation] = []
    for item in locs_data:
        loc = _parse_code_impact_location(item)
        if loc is not None:
            raw_locs.append(loc)
        else:
            _add_issue(issues, "code_impact_invalid_related_locations")
    notes_data = data.get("impact_notes", [])
    if not isinstance(notes_data, list):
        _add_issue(issues, "code_impact_invalid_impact_notes")
        notes_data = []
    elif any(not isinstance(note, str) for note in notes_data):
        _add_issue(issues, "code_impact_invalid_impact_notes")
    impact_notes = [_coerce_str(n) for n in notes_data if _coerce_str(n)]
    return CodeImpactAnalysis(related_locations=raw_locs, impact_notes=impact_notes), issues


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _invalid_evidence_issue(value: Any, rp_id: str) -> EvidenceValidationIssue:
    if isinstance(value, dict):
        path = _coerce_str(value.get("path", ""))
        line_start = _safe_int(value.get("line_start"))
        line_end = _safe_int(value.get("line_end"), line_start)
        role = _coerce_str(value.get("role", ""))
    else:
        path = ""
        line_start = 0
        line_end = 0
        role = ""
    return EvidenceValidationIssue(
        path=path,
        line_start=line_start,
        line_end=line_end,
        reason="invalid_evidence_object",
        requirement_point_ids=[rp_id],
        role=role,
    )


def _coerce_str_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    result: List[str] = []
    for item in items:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                result.append(stripped)
        elif isinstance(item, dict):
            best = ""
            for v in item.values() if isinstance(item, dict) else []:
                s = str(v).strip() if v is not None else ""
                if len(s) > len(best):
                    best = s
            if best:
                result.append(best)
            else:
                text = str(item).strip()
                if text:
                    result.append(text)
        else:
            text = str(item).strip()
            if text:
                result.append(text)
    return result


def _coerce_str(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _format_evidence_object(data: Dict[str, Any]) -> str:
    role = str(data.get("role", "")).strip()
    path = str(data.get("path", "")).strip()
    line_start = _safe_int(data.get("line_start"))
    line_end = _safe_int(data.get("line_end"), line_start)
    symbol = str(data.get("symbol", "")).strip()
    reason = str(data.get("reason", "")).strip()
    location = path
    if path and line_start > 0 and line_end > 0:
        role_prefix = f"{role}:" if role else ""
        location = f"{role_prefix}{path}:{line_start}-{line_end}"
    parts = [location]
    if symbol:
        parts.append(symbol)
    if reason:
        parts.append(reason)
    return " ".join(part for part in parts if part).strip()


def _location_from_evidence_object(data: Dict[str, Any]) -> EvidenceLocation:
    path = str(data.get("path", "")).strip()
    line_start = _safe_int(data.get("line_start"))
    line_end = _safe_int(data.get("line_end"), line_start)
    if not path or line_start <= 0 or line_end <= 0:
        return None
    return EvidenceLocation(
        path=path,
        line_start=line_start,
        line_end=line_end,
        symbol=str(data.get("symbol", "")).strip(),
        reason=str(data.get("reason", "")).strip(),
        source="agent",
        role=str(data.get("role", "")).strip(),
    )


def _location_from_evidence_text(text: str) -> EvidenceLocation:
    match = re.search(r"(?:(?P<role>[A-Za-z0-9_-]+):)?(?P<path>[\w./\\-]+\.[A-Za-z0-9_]+):(?P<start>\d+)(?:-(?P<end>\d+))?", text)
    if not match:
        return None
    start = _safe_int(match.group("start"))
    end = _safe_int(match.group("end"), start)
    if start <= 0 or end <= 0:
        return None
    return EvidenceLocation(
        path=match.group("path"),
        line_start=start,
        line_end=end,
        source="fallback",
        reason=text,
        role=match.group("role") or "",
    )


def parse_evidence(evidence: Any):
    evidence_text: List[str] = []
    cited_locations: List[EvidenceLocation] = []
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


def parse_role_evidence_statuses(data: Any) -> List[RoleEvidenceStatus]:
    if not isinstance(data, list):
        return []
    result: List[RoleEvidenceStatus] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        role = _coerce_str(item.get("role", ""))
        status = _coerce_str(item.get("status", ""))
        if not role or status not in VALID_ROLE_EVIDENCE_STATUSES:
            continue
        result.append(RoleEvidenceStatus(
            role=role,
            status=status,
            searched_for=_coerce_str_list(item.get("searched_for", [])),
            explanation=_coerce_str(item.get("explanation", "")),
        ))
    return result


def parse_protocol_traces(data: Any) -> List[ProtocolTrace]:
    if not isinstance(data, list):
        return []
    result: List[ProtocolTrace] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        hint = item.get("hint", {})
        if not isinstance(hint, dict):
            continue
        roles = _coerce_str_list(hint.get("roles", []))
        hint_type = _coerce_str(hint.get("type", ""))
        value = _coerce_str(hint.get("value", ""))
        status = _coerce_str(item.get("status", ""))
        if not roles or hint_type not in VALID_PROTOCOL_HINT_TYPES or not value or status not in VALID_PROTOCOL_TRACE_STATUSES:
            continue
        _, evidence = parse_evidence(item.get("evidence", []))
        result.append(ProtocolTrace(
            roles=roles,
            hint_type=hint_type,
            value=value,
            status=status,
            role_statuses=parse_role_evidence_statuses(item.get("role_statuses", [])),
            evidence=evidence,
            explanation=_coerce_str(item.get("explanation", "")),
        ))
    return result


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
    understanding_summary: str = ""
    error: str = ""
    error_kind: str = ""
    raw_response: str = dataclasses.field(default="", repr=False)
    evidence_text: List[str] = dataclasses.field(default_factory=list)
    cited_evidence_locations: List[EvidenceLocation] = dataclasses.field(default_factory=list)
    seed_locations: List[Any] = dataclasses.field(default_factory=list)
    rejected_seed_paths: List[Any] = dataclasses.field(default_factory=list)
    evidence_validation_issues: List[EvidenceValidationIssue] = dataclasses.field(default_factory=list)
    requirement_points: List[RequirementPoint] = dataclasses.field(default_factory=list)
    analysis_status: str = ""
    analysis_status_detail: str = ""
    recommended_action: str = ""
    requirement_source: str = "zentao"
    requirement_interpretation: Optional[RequirementInterpretation] = None
    code_impact: Optional[CodeImpactAnalysis] = None
    rich_content_issues: List[str] = dataclasses.field(default_factory=list)
    code_impact_validation_issues: List[EvidenceValidationIssue] = dataclasses.field(default_factory=list)
    role_evidence_statuses: List[RoleEvidenceStatus] = dataclasses.field(default_factory=list)
    protocol_traces: List[ProtocolTrace] = dataclasses.field(default_factory=list)
    protocol_trace_validation_issues: List[EvidenceValidationIssue] = dataclasses.field(default_factory=list)

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
            gaps=_coerce_str_list(data.get("gaps", [])),
            suspected_causes=_coerce_str_list(data.get("suspected_causes", [])),
            affected_scope=_coerce_str_list(data.get("affected_scope", [])),
            recommendations=_coerce_str_list(data.get("recommendations", [])),
            verification=_coerce_str_list(data.get("verification", [])),
            priority=data.get("priority", ""),
            confidence=data.get("confidence", ""),
            understanding_summary=_coerce_str(data.get("understanding_summary", "")),
            raw_response=raw_response,
            evidence_text=evidence_text,
            cited_evidence_locations=cited_locations,
            role_evidence_statuses=parse_role_evidence_statuses(data.get("role_evidence_statuses", [])),
            protocol_traces=parse_protocol_traces(data.get("protocol_traces", [])),
        )

    @classmethod
    def from_error(cls, item: ZentaoItem, error: str, raw_response: str = "", error_kind: str = "") -> "AnalysisResult":
        return cls(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            conclusion="无法判断" if item.type in ("story", "requirement") else "无法定位",
            error=error,
            error_kind=error_kind,
            raw_response=raw_response,
            requirement_source=getattr(item, "requirement_source", "zentao") or "zentao",
        )

    def is_insufficient_evidence(self) -> bool:
        if self.error:
            return True
        if not self.evidence:
            return True
        return False
