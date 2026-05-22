from typing import Any, Dict, List, Optional

from .zentao_client import ZentaoItem
from .code_collector import collect, collect_with_clues
from .prompts import build_feature_prompt, build_defect_prompt
from .llm_client import call_llm
from .analysis_result import AnalysisResult


def analyze(
    item: ZentaoItem,
    repo_path: str,
    agent: str = "codex",
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
    agent_config: Any = None,
    debug_recorder: Any = None,
    code_clues: Any = None,
    collection_recorder: Any = None,
) -> AnalysisResult:
    """
    完整分析流程：收集代码 -> 选择模板 -> 调用 LLM -> 解析结果 -> 证据不足检查。
    """
    if code_clues is not None:
        collection_result = collect_with_clues(
            repo_path,
            code_clues,
            modified_files=modified_files,
            max_files=max_files,
            max_lines_per_file=max_lines_per_file,
            max_total_tokens=max_total_tokens,
        )
        if collection_recorder:
            collection_recorder(item, collection_result)
        code_snippets = collection_result.snippets
    else:
        code_snippets = collect(
            repo_path,
            keywords=item.keywords,
            modified_files=modified_files,
            max_files=max_files,
            max_lines_per_file=max_lines_per_file,
            max_total_tokens=max_total_tokens,
        )

    if not code_snippets:
        return AnalysisResult.from_error(item, "未找到相关代码证据")

    if item.type in ("story", "requirement"):
        prompt = build_feature_prompt(item, code_snippets)
    else:
        prompt = build_defect_prompt(item, code_snippets)

    if debug_recorder:
        debug_recorder("prompt", item, prompt)

    llm_data = call_llm(prompt, agent=agent, agent_config=agent_config)

    if debug_recorder:
        debug_recorder("response", item, llm_data.get("raw", ""))

    if "error" in llm_data:
        return AnalysisResult.from_error(item, llm_data["error"], raw_response=llm_data.get("raw", ""))

    result = AnalysisResult.from_llm_json(item, llm_data, raw_response=llm_data.get("raw", ""))

    # Post-hoc evidence check
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

    return result
