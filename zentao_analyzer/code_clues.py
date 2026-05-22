import dataclasses
import json
import os
from typing import Any, Dict, Iterable, List, Tuple


@dataclasses.dataclass
class RejectedSeedPath:
    value: str
    source: str
    item_id: str = ""
    reason: str = ""


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
            "clues": parse_csv_values(clues.get("clues")),
            "paths": parse_csv_values(clues.get("paths")),
        }
    return normalized


def _append_unique(output: List[str], values: Iterable[str]) -> None:
    seen = set(output)
    for value in values:
        value = str(value).strip()
        if value and value not in seen:
            output.append(value)
            seen.add(value)


def build_search_hints(
    item_id: str,
    cli_clues: Any = None,
    clues_by_item: Dict[str, Dict[str, List[str]]] = None,
) -> List[str]:
    hints: List[str] = []
    item_clues = (clues_by_item or {}).get(str(item_id), {})
    _append_unique(hints, parse_csv_values(cli_clues))
    _append_unique(hints, item_clues.get("clues", []))
    return hints


def _inside_repo(repo_path: str, candidate: str) -> bool:
    repo_abs = os.path.realpath(repo_path)
    candidate_abs = os.path.realpath(candidate)
    try:
        return os.path.commonpath([repo_abs, candidate_abs]) == repo_abs
    except ValueError:
        return False


def _normalize_seed_path(repo_path: str, value: str) -> str:
    if os.path.isabs(value):
        return os.path.realpath(value)
    return os.path.realpath(os.path.join(repo_path, value))


def build_seed_paths(
    item_id: str,
    repo_path: str,
    cli_paths: Any = None,
    clues_by_item: Dict[str, Dict[str, List[str]]] = None,
) -> Tuple[List[str], List[RejectedSeedPath]]:
    seed_paths: List[str] = []
    rejected: List[RejectedSeedPath] = []
    seen = set()
    item_id = str(item_id)
    item_clues = (clues_by_item or {}).get(item_id, {})
    sources = [
        ("cli", parse_csv_values(cli_paths)),
        ("clues_file", item_clues.get("paths", [])),
    ]

    for source, values in sources:
        for value in values:
            raw = str(value).strip()
            if not raw:
                continue
            normalized = _normalize_seed_path(repo_path, raw)
            if not _inside_repo(repo_path, normalized):
                rejected.append(RejectedSeedPath(raw, source, item_id, "outside_repo"))
                continue
            if not os.path.exists(normalized):
                rejected.append(RejectedSeedPath(raw, source, item_id, "not_found"))
                continue
            if not os.path.isfile(normalized):
                rejected.append(RejectedSeedPath(raw, source, item_id, "not_file"))
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            seed_paths.append(normalized)
    return seed_paths, rejected
