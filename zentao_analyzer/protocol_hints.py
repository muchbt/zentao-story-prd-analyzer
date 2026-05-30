import dataclasses
from typing import Any, Dict, Iterable, List

from .repositories import RepositorySet


PROTOCOL_HINT_TYPES = {"cmd_id", "msg", "field", "text"}


class ProtocolHintInputError(ValueError):
    pass


@dataclasses.dataclass
class ProtocolHint:
    roles: List[str]
    type: str
    value: str
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        value = str(value).strip()
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _validate_hint(roles: List[str], hint_type: str, value: str, repo_set: RepositorySet, source: str) -> ProtocolHint:
    roles = _unique(roles)
    if not roles:
        raise ProtocolHintInputError("Protocol Hint roles 不能为空")
    unknown_roles = [role for role in roles if role not in repo_set.roles]
    if unknown_roles:
        raise ProtocolHintInputError(f"Protocol Hint 引用了未知 Repository Role: {', '.join(unknown_roles)}")
    if hint_type not in PROTOCOL_HINT_TYPES:
        raise ProtocolHintInputError(f"不支持的 Protocol Hint 类型: {hint_type}")
    value = str(value).strip()
    if not value:
        raise ProtocolHintInputError("Protocol Hint value 不能为空")
    return ProtocolHint(roles=roles, type=hint_type, value=value, source=source)


def _parse_text_hint(raw: str, repo_set: RepositorySet, source: str) -> ProtocolHint:
    raw = str(raw).strip()
    roles = list(repo_set.roles)
    hint_value = raw
    if ":" in raw:
        role_part, hint_value = raw.split(":", 1)
        roles = [part.strip() for part in role_part.split(",")]
    hint_type = "text"
    value = hint_value
    if "=" in hint_value:
        hint_type, value = hint_value.split("=", 1)
        hint_type = hint_type.strip()
    return _validate_hint(roles, hint_type, value, repo_set, source)


def _parse_mapping_hint(raw: Dict[str, Any], repo_set: RepositorySet, source: str) -> ProtocolHint:
    roles = raw.get("roles")
    if roles is None:
        roles = repo_set.roles
    if not isinstance(roles, list):
        raise ProtocolHintInputError("Protocol Hint roles 必须是数组")
    return _validate_hint(roles, str(raw.get("type", "text")).strip(), raw.get("value", ""), repo_set, source)


def normalize_protocol_hints(values: Any, repo_set: RepositorySet, source: str = "cli") -> List[ProtocolHint]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        values = [values]
    result: List[ProtocolHint] = []
    seen = set()
    for value in values:
        if isinstance(value, dict):
            hint = _parse_mapping_hint(value, repo_set, source)
        else:
            hint = _parse_text_hint(str(value), repo_set, source)
        key = (tuple(hint.roles), hint.type, hint.value)
        if key not in seen:
            result.append(hint)
            seen.add(key)
    return result
