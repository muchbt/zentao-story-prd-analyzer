import dataclasses
import json
import os
from typing import Any, Dict, Iterable, List, Tuple

from .repositories import RepositoryInputError, RepositorySet, parse_repo_args


@dataclasses.dataclass
class RejectedSeedPath:
    value: str
    source: str
    item_id: str = ""
    reason: str = ""
    role: str = ""


@dataclasses.dataclass
class RoleSeedPath:
    role: str
    path: str
    relative_path: str
    source: str = ""


class StructuredClueFile(dict):
    def __init__(self, items=None, repositories=None, source_path: str = ""):
        super().__init__(items or {})
        self.repositories = repositories or {}
        self.source_path = source_path
        self.directory = os.path.dirname(os.path.realpath(source_path)) if source_path else os.getcwd()


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


def _normalize_item_clues(clues: Dict[str, Any]) -> Dict[str, Any]:
    raw_paths = clues.get("paths")
    if isinstance(raw_paths, dict):
        paths = {str(role): parse_csv_values(values) for role, values in raw_paths.items()}
    else:
        paths = parse_csv_values(raw_paths)
    raw_protocol_hints = clues.get("protocol_hints", [])
    if not isinstance(raw_protocol_hints, list):
        raw_protocol_hints = [raw_protocol_hints]
    return {
        "clues": parse_csv_values(clues.get("clues")),
        "paths": paths,
        "protocol_hints": raw_protocol_hints,
        "primary_role": str(clues.get("primary_role", "") or "").strip(),
    }


def load_clues_file(path: str) -> StructuredClueFile:
    if not path:
        return StructuredClueFile()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return StructuredClueFile(source_path=path)
    if "items" in data or "repositories" in data:
        raw_items = data.get("items", {})
        repositories = data.get("repositories", {})
        if not isinstance(raw_items, dict):
            raise ValueError("clues-file.items 必须是对象")
        if not isinstance(repositories, dict):
            raise ValueError("clues-file.repositories 必须是对象")
    else:
        raw_items = data
        repositories = {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for item_id, clues in raw_items.items():
        if not isinstance(clues, dict):
            continue
        normalized[str(item_id)] = _normalize_item_clues(clues)
    return StructuredClueFile(items=normalized, repositories=repositories, source_path=path)


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
    repo_set = parse_repo_args([repo_path])
    role_paths, rejected = build_role_seed_paths(
        item_id=item_id,
        repo_set=repo_set,
        cli_paths=cli_paths,
        clues_by_item=clues_by_item,
    )
    return [item.path for item in role_paths], rejected


def _iter_file_seed_paths(paths: Any, repo_set: RepositorySet):
    if isinstance(paths, dict):
        for role, values in paths.items():
            for value in parse_csv_values(values):
                yield str(role).strip(), value
        return
    for value in parse_csv_values(paths):
        yield ("main" if repo_set.is_single_repo else ""), value


def _iter_cli_seed_paths(paths: Any, repo_set: RepositorySet):
    for value in parse_csv_values(paths):
        if "=" in value:
            role, raw = value.split("=", 1)
            yield role.strip(), raw.strip()
        else:
            yield ("main" if repo_set.is_single_repo else ""), value


def build_role_seed_paths(
    item_id: str,
    repo_set: RepositorySet,
    cli_paths: Any = None,
    clues_by_item: Dict[str, Dict[str, Any]] = None,
) -> Tuple[List[RoleSeedPath], List[RejectedSeedPath]]:
    seed_paths: List[RoleSeedPath] = []
    rejected: List[RejectedSeedPath] = []
    seen = set()
    item_id = str(item_id)
    item_clues = (clues_by_item or {}).get(item_id, {})
    sources = [
        ("cli", _iter_cli_seed_paths(cli_paths, repo_set)),
        ("clues_file", _iter_file_seed_paths(item_clues.get("paths", []), repo_set)),
    ]

    for source, values in sources:
        for role, value in values:
            raw = str(value).strip()
            if not raw:
                continue
            if not role:
                rejected.append(RejectedSeedPath(raw, source, item_id, "missing_role"))
                continue
            try:
                repo_path = repo_set.get(role).path
            except RepositoryInputError:
                rejected.append(RejectedSeedPath(raw, source, item_id, "unknown_role", role=role))
                continue
            normalized = _normalize_seed_path(repo_path, raw)
            if not _inside_repo(repo_path, normalized):
                rejected.append(RejectedSeedPath(raw, source, item_id, "outside_repo", role=role))
                continue
            if not os.path.exists(normalized):
                rejected.append(RejectedSeedPath(raw, source, item_id, "not_found", role=role))
                continue
            if not os.path.isfile(normalized):
                rejected.append(RejectedSeedPath(raw, source, item_id, "not_file", role=role))
                continue
            key = (role, normalized)
            if key in seen:
                continue
            seen.add(key)
            seed_paths.append(RoleSeedPath(
                role=role,
                path=normalized,
                relative_path=os.path.relpath(normalized, repo_path),
                source=source,
            ))
    return seed_paths, rejected
