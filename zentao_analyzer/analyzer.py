import os
from typing import Any, List, Optional

from .analysis_result import (
    AnalysisResult,
    EvidenceValidationIssue,
    RequirementPoint,
    RPStatus,
    _coerce_str,
    _coerce_str_list,
    aggregate_evidence_from_rps,
    aggregate_evidence_text_from_rps,
    compute_item_conclusion,
    compute_item_confidence,
    compute_item_gaps,
    correct_invalidated_rps,
    correct_rps_without_valid_evidence,
    parse_requirement_points,
    validate_requirement_points,
    validate_rp_evidence_locations,
)
from .llm_client import call_llm
from .prompts import build_defect_prompt, build_feature_prompt
from .seed_loader import load_seed_context
from .zentao_client import ZentaoItem


def _inside_repo(repo_path: str, candidate: str) -> bool:
    repo_abs = os.path.realpath(repo_path)
    if os.path.isabs(candidate):
        candidate_abs = os.path.realpath(candidate)
    else:
        candidate_abs = os.path.realpath(os.path.join(repo_abs, candidate))
    try:
        return os.path.commonpath([repo_abs, candidate_abs]) == repo_abs
    except ValueError:
        return False


def _resolve_repo_path(repo_path: str, candidate: str) -> str:
    repo_abs = os.path.realpath(repo_path)
    if os.path.isabs(candidate):
        return os.path.realpath(candidate)
    return os.path.realpath(os.path.join(repo_abs, candidate))


def _line_count(path: str) -> int:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def validate_evidence_locations(repo_path: str, result: AnalysisResult) -> List[EvidenceValidationIssue]:
    issues: List[EvidenceValidationIssue] = []
    for location in result.cited_evidence_locations or []:
        path = location.path
        resolved_path = _resolve_repo_path(repo_path, path)
        issue = EvidenceValidationIssue(path=path, line_start=location.line_start, line_end=location.line_end)
        if not _inside_repo(repo_path, path):
            issue.reason = "outside_repo"
            issues.append(issue)
            continue
        if not os.path.exists(resolved_path):
            issue.reason = "not_found"
            issues.append(issue)
            continue
        if location.line_start <= 0 or location.line_end <= 0 or location.line_start > location.line_end:
            issue.reason = "invalid_line_range"
            issues.append(issue)
            continue
        if location.line_end > _line_count(resolved_path):
            issue.reason = "line_out_of_range"
            issues.append(issue)
    return issues


def _apply_insufficient_evidence_guard(item: ZentaoItem, result: AnalysisResult) -> None:
    if result.is_insufficient_evidence():
        result.conclusion = "无法判断" if item.type in ("story", "requirement") else "无法定位"
        result.confidence = "低"
        msg = "分析依据不足：未找到与条目直接相关的代码证据。"
        if item.type in ("story", "requirement"):
            if msg not in result.evidence:
                result.evidence.append(msg)
        else:
            if msg not in result.suspected_causes:
                result.suspected_causes.append(msg)


def _analyze_feature(
    item: ZentaoItem,
    data: dict,
    raw_response: str,
    repo_path: str,
    seed_locations: list,
    rejected_seed_paths: list,
) -> AnalysisResult:
    def unavailable_result(detail: str) -> AnalysisResult:
        action = "update_zentao_requirement" if detail == "empty_requirement_points" else "manual_retry"
        return AnalysisResult(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            raw_response=raw_response,
            seed_locations=seed_locations,
            rejected_seed_paths=rejected_seed_paths,
            analysis_status="requirement_points_unavailable",
            analysis_status_detail=detail,
            recommended_action=action,
        )

    rps, has_malformed_items, rp_ids_with_invalid_evidence = parse_requirement_points(data.get("requirement_points"))
    if has_malformed_items:
        return unavailable_result("invalid_requirement_point_schema")
    validation = validate_requirement_points(rps)
    if not validation.valid or not validation.requirement_points:
        return unavailable_result(validation.failure_reason)
    rps = validation.requirement_points
    rp_issues = validate_rp_evidence_locations(repo_path, rps)
    rps, unique_evidence_issues, _invalid_location_count = correct_invalidated_rps(rps, rp_issues)
    rps = correct_rps_without_valid_evidence(rps)
    for rp in rps:
        if rp.id in rp_ids_with_invalid_evidence:
            rp._original_status = rp._original_status or rp.status
            rp.status = RPStatus.INDETERMINATE
            rp._correction_reason = rp._correction_reason or "invalid_evidence_object"
            rp.gaps = []
            rp.evidence = []
            rp.reason = "存在无效证据对象，修正为无法判断"
    issue_keys = {
        (issue.path, issue.line_start, issue.line_end, issue.reason): issue
        for issue in unique_evidence_issues
    }
    for rp in rps:
        for issue in rp._invalid_evidence_issues:
            key = (issue.path, issue.line_start, issue.line_end, issue.reason)
            existing = issue_keys.get(key)
            if existing is None:
                unique_evidence_issues.append(issue)
                issue_keys[key] = issue
            else:
                for point_id in issue.requirement_point_ids:
                    if point_id not in existing.requirement_point_ids:
                        existing.requirement_point_ids.append(point_id)
    conclusion = compute_item_conclusion(rps)
    gaps = compute_item_gaps(rps)
    aggregated_evidence = aggregate_evidence_from_rps(rps)
    aggregated_evidence_text = aggregate_evidence_text_from_rps(rps)
    has_fallback = any(
        loc.source == "fallback" for loc in aggregated_evidence
    )
    total_invalid_evidence = len(unique_evidence_issues)
    confidence = compute_item_confidence(
        rps,
        has_fallback_evidence=has_fallback,
        has_invalid_evidence=total_invalid_evidence > 0,
    )
    if not aggregated_evidence_text and conclusion == RPStatus.INDETERMINATE:
        aggregated_evidence_text = ["相关代码证据不足"]
    result = AnalysisResult(
        item_id=item.id,
        item_type=item.type,
        item_title=item.title,
        conclusion=conclusion,
        evidence=aggregated_evidence_text,
        gaps=gaps,
        suspected_causes=[],
        affected_scope=[],
        recommendations=_coerce_str_list(data.get("recommendations", [])),
        verification=_coerce_str_list(data.get("verification", [])),
        priority=_coerce_str(data.get("priority", "")),
        confidence=confidence,
        understanding_summary=_coerce_str(data.get("understanding_summary", "")),
        raw_response=raw_response,
        evidence_text=aggregated_evidence_text,
        cited_evidence_locations=aggregated_evidence,
        seed_locations=seed_locations,
        rejected_seed_paths=rejected_seed_paths,
        evidence_validation_issues=unique_evidence_issues,
        requirement_points=rps,
        analysis_status="",
    )
    return result


def analyze(
    item: ZentaoItem,
    repo_path: str,
    agent: str = "claude",
    agent_config: Any = None,
    seed_paths: Optional[List[str]] = None,
    search_hints: Optional[List[str]] = None,
    rejected_seed_paths: Optional[List[Any]] = None,
    max_seed_files: int = 3,
    max_lines_per_seed: int = 50,
    max_seed_tokens: int = 2000,
    debug_recorder: Any = None,
) -> AnalysisResult:
    if not os.path.isdir(repo_path):
        return AnalysisResult.from_error(item, f"代码仓库路径不存在或不可访问: {repo_path}", error_kind="config")

    seed_result = load_seed_context(
        seed_paths or [],
        rejected_seed_paths=rejected_seed_paths,
        max_seed_files=max_seed_files,
        max_lines_per_seed=max_lines_per_seed,
        max_seed_tokens=max_seed_tokens,
    )

    if item.type in ("story", "requirement"):
        prompt = build_feature_prompt(item, repo_path, seed_result.snippets, search_hints)
    else:
        prompt = build_defect_prompt(item, repo_path, seed_result.snippets, search_hints)

    if debug_recorder:
        debug_recorder("prompt", item, prompt)

    llm_data = call_llm(prompt, agent=agent, agent_config=agent_config)

    if debug_recorder:
        debug_recorder("response", item, llm_data.get("raw", ""))

    if "error" in llm_data:
        result = AnalysisResult.from_error(item, llm_data["error"], raw_response=llm_data.get("raw", ""), error_kind=llm_data.get("error_kind", ""))
        result.seed_locations = seed_result.seed_locations
        result.rejected_seed_paths = seed_result.rejected_seed_paths
        return result

    if item.type in ("story", "requirement"):
        result = _analyze_feature(
            item=item,
            data=llm_data,
            raw_response=llm_data.get("raw", ""),
            repo_path=repo_path,
            seed_locations=seed_result.seed_locations,
            rejected_seed_paths=seed_result.rejected_seed_paths,
        )
    else:
        result = AnalysisResult.from_llm_json(item, llm_data, raw_response=llm_data.get("raw", ""))
        result.seed_locations = seed_result.seed_locations
        result.rejected_seed_paths = seed_result.rejected_seed_paths
        result.evidence_validation_issues = validate_evidence_locations(repo_path, result)
        if result.evidence_validation_issues:
            result.confidence = "低"
            msg = "部分代码证据未通过本地文件或行号校验。"
            if msg not in result.evidence:
                result.evidence.append(msg)
        _apply_insufficient_evidence_guard(item, result)
    return result
