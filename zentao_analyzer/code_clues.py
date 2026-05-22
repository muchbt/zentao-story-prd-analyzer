import dataclasses
import json
import os
from typing import Any, Dict, Iterable, List, Tuple

from .zentao_client import ZentaoItem


MAX_VALUES = {
    "keyword": 100,
    "symbol": 100,
    "path": 200,
}

MAX_LENGTH = {
    "keyword": 120,
    "symbol": 160,
    "path": 500,
}


@dataclasses.dataclass
class CodeClue:
    kind: str
    value: str
    source: str
    item_id: str = ""


@dataclasses.dataclass
class RejectedClue:
    kind: str
    value: str
    source: str
    item_id: str = ""
    reason: str = ""


@dataclasses.dataclass
class CodeLocation:
    path: str
    line_start: int
    line_end: int
    symbol: str = ""
    reason: str = ""
    source: str = ""
    matched_clues: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class CollectionResult:
    snippets: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    collected_locations: List[CodeLocation] = dataclasses.field(default_factory=list)
    rejected_clues: List[RejectedClue] = dataclasses.field(default_factory=list)


def parse_csv_values(value: Any) -> List[str]:
    if value is None:
        return []
    raw_values: Iterable[Any]
    if isinstance(value, (list, tuple)):
        raw_values = value
    else:
        raw_values = [value]

    result: List[str] = []
    for raw in raw_values:
        if raw is None:
            continue
        for part in str(raw).split(","):
            cleaned = part.strip()
            if cleaned:
                result.append(cleaned)
    return result


def load_clues_file(path: str) -> Dict[str, Dict[str, List[str]]]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    normalized: Dict[str, Dict[str, List[str]]] = {}
    for item_id, clues in data.items():
        if not isinstance(clues, dict):
            continue
        normalized[str(item_id)] = {
            "keywords": parse_csv_values(clues.get("keywords")),
            "paths": parse_csv_values(clues.get("paths")),
            "symbols": parse_csv_values(clues.get("symbols")),
        }
    return normalized


def _inside_repo(repo_path: str, candidate: str) -> bool:
    repo_abs = os.path.abspath(repo_path)
    candidate_abs = os.path.abspath(candidate)
    try:
        return os.path.commonpath([repo_abs, candidate_abs]) == repo_abs
    except ValueError:
        return False


def _normalize_path_clue(repo_path: str, value: str) -> str:
    if os.path.isabs(value):
        return os.path.abspath(value)
    return os.path.abspath(os.path.join(repo_path, value))


def _append_limited(
    output: List[CodeClue],
    rejected: List[RejectedClue],
    seen: set,
    kind: str,
    values: Iterable[str],
    source: str,
    item_id: str,
    repo_path: str,
) -> None:
    count = len([c for c in output if c.kind == kind])
    for value in values:
        if count >= MAX_VALUES[kind]:
            rejected.append(RejectedClue(kind, str(value), source, item_id, "too_many"))
            continue
        value = str(value).strip()
        if not value:
            continue
        if len(value) > MAX_LENGTH[kind]:
            rejected.append(RejectedClue(kind, value, source, item_id, "too_long"))
            continue
        if kind == "path":
            normalized = _normalize_path_clue(repo_path, value)
            if not _inside_repo(repo_path, normalized):
                rejected.append(RejectedClue(kind, value, source, item_id, "outside_repo"))
                continue
            value = normalized
        key = (kind, value, source, item_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(CodeClue(kind, value, source, item_id))
        count += 1


def build_item_clues(
    item: ZentaoItem,
    repo_path: str,
    cli_keywords: Any = None,
    cli_paths: Any = None,
    cli_symbols: Any = None,
    clues_by_item: Dict[str, Dict[str, List[str]]] = None,
) -> Tuple[List[CodeClue], List[RejectedClue]]:
    clues: List[CodeClue] = []
    rejected: List[RejectedClue] = []
    seen = set()
    item_id = str(getattr(item, "id", ""))
    clues_by_item = clues_by_item or {}
    item_clues = clues_by_item.get(item_id, {})

    _append_limited(clues, rejected, seen, "keyword", getattr(item, "keywords", []) or [], "zentao", item_id, repo_path)
    _append_limited(clues, rejected, seen, "keyword", parse_csv_values(cli_keywords), "cli", item_id, repo_path)
    _append_limited(clues, rejected, seen, "path", parse_csv_values(cli_paths), "cli", item_id, repo_path)
    _append_limited(clues, rejected, seen, "symbol", parse_csv_values(cli_symbols), "cli", item_id, repo_path)
    _append_limited(clues, rejected, seen, "keyword", item_clues.get("keywords", []), "clues_file", item_id, repo_path)
    _append_limited(clues, rejected, seen, "path", item_clues.get("paths", []), "clues_file", item_id, repo_path)
    _append_limited(clues, rejected, seen, "symbol", item_clues.get("symbols", []), "clues_file", item_id, repo_path)
    return clues, rejected
