import os
from typing import Any, List, Optional

from .analysis_result import AnalysisResult, EvidenceValidationIssue
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
