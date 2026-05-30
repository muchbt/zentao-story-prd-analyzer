import dataclasses
from typing import Any, Dict, List, Optional

from .code_clues import RejectedSeedPath, RoleSeedPath


@dataclasses.dataclass
class SeedLocation:
    path: str
    line_start: int
    line_end: int
    source: str = "seed"
    role: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class SeedLoadResult:
    snippets: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    seed_locations: List[SeedLocation] = dataclasses.field(default_factory=list)
    rejected_seed_paths: List[RejectedSeedPath] = dataclasses.field(default_factory=list)


def load_seed_context(
    seed_paths: List[str],
    rejected_seed_paths: Optional[List[RejectedSeedPath]] = None,
    max_seed_files: int = 3,
    max_lines_per_seed: int = 50,
    max_seed_tokens: int = 2000,
    max_seed_tokens_limit: int = 8000,
) -> SeedLoadResult:
    snippets: List[Dict[str, Any]] = []
    locations: List[SeedLocation] = []
    rejected = list(rejected_seed_paths or [])
    token_budget = min(max(max_seed_tokens, 0), max_seed_tokens_limit)
    token_ratio = 4
    truncated = False

    for seed_path in list(seed_paths or [])[:max_seed_files]:
        if isinstance(seed_path, RoleSeedPath):
            path = seed_path.path
            display_path = f"{seed_path.role}:{seed_path.relative_path}"
            role = seed_path.role
        else:
            path = seed_path
            display_path = path
            role = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            rejected.append(RejectedSeedPath(path, "seed_loader", "", "read_failed"))
            continue

        content_lines = lines[:max_lines_per_seed]
        content = "".join(content_lines)
        estimated_tokens = len(content) // token_ratio
        if estimated_tokens > token_budget:
            allowed_chars = token_budget * token_ratio
            content = content[:allowed_chars]
            content_lines = content.splitlines(keepends=True)
            estimated_tokens = len(content) // token_ratio
            truncated = True
        if not content and token_budget <= 0:
            truncated = True
            break

        token_budget -= estimated_tokens
        line_end = len(content_lines)
        snippets.append({
            "path": display_path,
            "content": content,
            "line_start": 1,
            "line_end": line_end,
        })
        locations.append(SeedLocation(path=display_path, line_start=1, line_end=line_end, role=role))
        if token_budget <= 0:
            truncated = True
            break

    if truncated and snippets:
        snippets[-1]["content"] += "\n[种子上下文已截断，仅展示部分内容]\n"
    return SeedLoadResult(snippets=snippets, seed_locations=locations, rejected_seed_paths=rejected)
