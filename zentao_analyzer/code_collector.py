import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from .code_clues import CodeClue, CodeLocation, CollectionResult, RejectedClue


ALLOWED_EXTS = (".c", ".cpp", ".h", ".hpp", ".sh", ".bat", ".py")
BUILD_FILES = {"Makefile", "CMakeLists.txt"}


def _find_executable(name: str) -> bool:
    try:
        subprocess.run([name, "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _rg_search(repo_path: str, keywords: List[str]) -> List[str]:
    matched = set()
    for kw in keywords:
        try:
            result = subprocess.run(
                ["rg", "--files-with-matches", "-i", kw, repo_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        matched.add(line)
            elif result.stderr:
                print(f"[rg stderr] {result.stderr.strip()}", file=sys.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break
    return list(matched)


def _git_grep_search(repo_path: str, keywords: List[str]) -> List[str]:
    matched = set()
    for kw in keywords:
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "grep", "-l", "-i", kw],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        matched.add(os.path.join(repo_path, line))
            elif result.stderr:
                print(f"[git grep stderr] {result.stderr.strip()}", file=sys.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break
    return list(matched)


def _os_walk_search(repo_path: str, keywords: List[str]) -> List[str]:
    matched = []
    for root, _, files in os.walk(repo_path):
        for f in files:
            if _is_allowed_file(f):
                path = os.path.join(root, f)
                if not keywords:
                    matched.append(path)
                    continue
                # Also match against filename / path
                if any(kw.lower() in f.lower() or kw.lower() in path.lower() for kw in keywords):
                    matched.append(path)
                    continue
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        if any(kw.lower() in content.lower() for kw in keywords):
                            matched.append(path)
                except:
                    continue
    return matched


def _is_allowed_file(filename: str) -> bool:
    return filename.endswith(ALLOWED_EXTS) or filename in BUILD_FILES


def _iter_allowed_files(path: str) -> List[str]:
    if os.path.isfile(path):
        return [path] if _is_allowed_file(os.path.basename(path)) else []
    if not os.path.isdir(path):
        return []
    result = []
    for root, _, files in os.walk(path):
        for filename in files:
            if _is_allowed_file(filename):
                result.append(os.path.join(root, filename))
    return result


def _normalize_modified_files(repo_path: str, modified_files: Optional[List[str]]) -> Optional[set]:
    if not modified_files:
        return None
    normalized = set()
    for path in modified_files:
        if not path:
            continue
        if not os.path.isabs(path):
            path = os.path.join(repo_path, path)
        normalized.add(os.path.abspath(path))
    return normalized


def _add_candidate(candidates: Dict[str, List[str]], path: str, clue_value: str, allowed_paths: Optional[set]) -> None:
    abs_path = os.path.abspath(path)
    if allowed_paths is not None and abs_path not in allowed_paths:
        return
    if not os.path.exists(abs_path):
        return
    candidates.setdefault(abs_path, [])
    if clue_value and clue_value not in candidates[abs_path]:
        candidates[abs_path].append(clue_value)


def _search_files_by_text(repo_path: str, value: str, allowed_paths: Optional[set]) -> List[str]:
    matched = []
    lowered = value.lower()
    for root, _, files in os.walk(repo_path):
        for filename in files:
            if not _is_allowed_file(filename):
                continue
            path = os.path.abspath(os.path.join(root, filename))
            if allowed_paths is not None and path not in allowed_paths:
                continue
            if lowered in filename.lower() or lowered in path.lower():
                matched.append(path)
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    if lowered in f.read().lower():
                        matched.append(path)
            except OSError:
                continue
    return matched


def _read_snippets(
    paths: List[str],
    max_lines_per_file: int,
    max_total_tokens: int,
    matched_clues: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    snippets = []
    token_budget = max_total_tokens
    TOKEN_ESTIMATE_RATIO = 4  # chars per token
    truncated = False

    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                content_lines = lines[:max_lines_per_file]
                content = "".join(content_lines)
                estimated_tokens = len(content) // TOKEN_ESTIMATE_RATIO
                if estimated_tokens > token_budget:
                    # Truncate to fit budget
                    allowed_chars = token_budget * TOKEN_ESTIMATE_RATIO
                    content = content[:allowed_chars]
                    if not content:
                        truncated = True
                        break
                    content_lines = content.splitlines(keepends=True)
                    estimated_tokens = len(content) // TOKEN_ESTIMATE_RATIO
                    truncated = True

                token_budget -= estimated_tokens
                snippets.append({
                    "path": path,
                    "content": content,
                    "line_start": 1,
                    "line_end": len(content_lines),
                    "matched_clues": (matched_clues or {}).get(os.path.abspath(path), []),
                })

                if token_budget <= 0:
                    truncated = True
                    break
        except:
            continue

    if truncated and snippets:
        snippets[-1]["content"] += "\n[代码上下文已截断，仅展示部分相关文件]\n"
    return snippets


def collect_with_clues(
    repo_path: str,
    clues: List[CodeClue],
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
    rejected_clues: Optional[List[RejectedClue]] = None,
) -> CollectionResult:
    """Collect code context and location metadata from explicit code clues."""
    allowed_paths = _normalize_modified_files(repo_path, modified_files)
    candidates: Dict[str, List[str]] = {}
    rejected = list(rejected_clues or [])

    for clue in clues:
        if clue.kind == "path":
            for path in _iter_allowed_files(clue.value):
                _add_candidate(candidates, path, clue.value, allowed_paths)

    for clue in clues:
        if clue.kind not in ("keyword", "symbol"):
            continue
        for path in _search_files_by_text(repo_path, clue.value, allowed_paths):
            _add_candidate(candidates, path, clue.value, allowed_paths)

    ordered_paths = list(candidates.keys())[:max_files]
    snippets = _read_snippets(ordered_paths, max_lines_per_file, max_total_tokens, candidates)
    collected_locations = [
        CodeLocation(
            path=snippet["path"],
            line_start=snippet["line_start"],
            line_end=snippet["line_end"],
            source="collector",
            matched_clues=snippet.get("matched_clues", []),
        )
        for snippet in snippets
    ]
    return CollectionResult(
        snippets=snippets,
        collected_locations=collected_locations,
        rejected_clues=rejected,
    )


def collect(
    repo_path: str,
    keywords: List[str],
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
) -> List[Dict[str, Any]]:
    """
    Collect code context with fallback: rg -> git grep -> os.walk.
    Returns: [{"path": str, "content": str, "line_start": int, "line_end": int}]
    """
    if modified_files:
        # Normalize relative paths to repo_path
        normalized = []
        for p in modified_files:
            if not os.path.isabs(p):
                p = os.path.join(repo_path, p)
            if os.path.exists(p):
                normalized.append(p)
        candidates = normalized
    else:
        candidates = []
        if _find_executable("rg"):
            candidates = _rg_search(repo_path, keywords)
        if not candidates and os.path.isdir(os.path.join(repo_path, ".git")):
            candidates = _git_grep_search(repo_path, keywords)
        if not candidates:
            candidates = _os_walk_search(repo_path, keywords)

    candidates = candidates[:max_files]
    return _read_snippets(candidates, max_lines_per_file, max_total_tokens)
