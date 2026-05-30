import dataclasses
import os
import re
import tempfile
from typing import Dict, Iterable, List, Optional


ROLE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class RepositoryInputError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class RepositorySpec:
    role: str
    path: str

    def to_dict(self) -> Dict[str, str]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class RepositorySet:
    repositories: List[RepositorySpec]
    is_single_repo: bool
    show_roles: bool = False
    primary_role: str = ""

    @property
    def roles(self) -> List[str]:
        return [repo.role for repo in self.repositories]

    def get(self, role: str) -> RepositorySpec:
        for repo in self.repositories:
            if repo.role == role:
                return repo
        raise RepositoryInputError(f"未知 Repository Role: {role}")

    def to_dict(self) -> Dict[str, object]:
        return {
            "repositories": [repo.to_dict() for repo in self.repositories],
            "is_single_repo": self.is_single_repo,
            "show_roles": self.show_roles,
            "primary_role": self.primary_role,
        }


def validate_role_name(role: str) -> None:
    if not role or not ROLE_PATTERN.fullmatch(role):
        raise RepositoryInputError(f"非法 Repository Role: {role!r}")


def _resolve_path(value: str, base_dir: str) -> str:
    if os.path.isabs(value):
        return os.path.realpath(value)
    return os.path.realpath(os.path.join(base_dir, value))


def _validate_repo(role: str, value: str, base_dir: str) -> RepositorySpec:
    validate_role_name(role)
    path = _resolve_path(str(value).strip(), base_dir)
    if not os.path.isdir(path):
        raise RepositoryInputError(f"代码仓库路径不存在、不可访问或不是目录: {path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise RepositoryInputError(f"代码仓库路径不可读: {path}")
    return RepositorySpec(role=role, path=path)


def _parse_cli_repositories(repo_values: Iterable[str], cwd: str) -> List[RepositorySpec]:
    raw_values = [str(value).strip() for value in repo_values or [] if str(value).strip()]
    if not raw_values:
        return []
    qualified = ["=" in value for value in raw_values]
    if len(raw_values) > 1 and not all(qualified):
        if any(qualified):
            raise RepositoryInputError("具名与匿名 --repo 不能混用")
        raise RepositoryInputError("多条匿名 --repo 不受支持；多仓模式必须使用 role=path")
    if len(raw_values) == 1 and not qualified[0]:
        return [_validate_repo("main", raw_values[0], cwd)]
    result: List[RepositorySpec] = []
    seen = set()
    for value in raw_values:
        role, path = value.split("=", 1)
        role = role.strip()
        if role in seen:
            raise RepositoryInputError(f"重复 Repository Role: {role}")
        seen.add(role)
        result.append(_validate_repo(role, path.strip(), cwd))
    return result


def _parse_file_repositories(values: Optional[Dict[str, str]], base_dir: str) -> List[RepositorySpec]:
    if not values:
        return []
    if not isinstance(values, dict):
        raise RepositoryInputError("clues-file.repositories 必须是 role 到 path 的对象")
    result: List[RepositorySpec] = []
    for role, path in values.items():
        result.append(_validate_repo(str(role).strip(), str(path).strip(), base_dir))
    return result


def _same_repositories(first: List[RepositorySpec], second: List[RepositorySpec]) -> bool:
    return {repo.role: repo.path for repo in first} == {repo.role: repo.path for repo in second}


def parse_repo_args(
    repo_values: Optional[Iterable[str]] = None,
    repo_path: str = "",
    clues_file_repositories: Optional[Dict[str, str]] = None,
    cwd: str = "",
    clues_file_dir: str = "",
) -> RepositorySet:
    cwd = os.path.realpath(cwd or os.getcwd())
    clues_file_dir = os.path.realpath(clues_file_dir or cwd)
    cli_repositories = _parse_cli_repositories(repo_values or [], cwd)
    if cli_repositories and repo_path:
        raise RepositoryInputError("--repo 与 --repo-path 不能同时使用")
    file_repositories = _parse_file_repositories(clues_file_repositories, clues_file_dir)
    if cli_repositories and file_repositories and not _same_repositories(cli_repositories, file_repositories):
        raise RepositoryInputError("命令行与 clues-file 中的 repositories 不一致")
    if cli_repositories:
        repositories = cli_repositories
        show_roles = any(repo.role != "main" for repo in repositories)
    elif repo_path:
        repositories = [_validate_repo("main", repo_path, cwd)]
        show_roles = False
        if file_repositories and not _same_repositories(repositories, file_repositories):
            raise RepositoryInputError("--repo-path 与 clues-file 中的 repositories 不一致")
    elif file_repositories:
        repositories = file_repositories
        show_roles = any(repo.role != "main" for repo in repositories)
    else:
        repositories = [_validate_repo("main", cwd, cwd)]
        show_roles = False
    return RepositorySet(
        repositories=repositories,
        is_single_repo=len(repositories) == 1,
        show_roles=show_roles,
    )


def resolve_repo_relative_path(repo_set: RepositorySet, role: str, value: str) -> str:
    repo = repo_set.get(role)
    if os.path.isabs(value):
        return os.path.realpath(value)
    return os.path.realpath(os.path.join(repo.path, value))


def coerce_repository_set(value) -> RepositorySet:
    if isinstance(value, RepositorySet):
        return value
    return RepositorySet(
        repositories=[RepositorySpec(role="main", path=os.path.realpath(str(value)))],
        is_single_repo=True,
        show_roles=False,
    )


def inside_repository(repo_set: RepositorySet, role: str, value: str) -> bool:
    repo = repo_set.get(role)
    candidate = resolve_repo_relative_path(repo_set, role, value)
    try:
        return os.path.commonpath([repo.path, candidate]) == repo.path
    except ValueError:
        return False


@dataclasses.dataclass
class RoleWorkspace:
    repo_set: RepositorySet
    available: bool = False
    path: str = ""
    error: str = ""
    _temp_dir: Optional[tempfile.TemporaryDirectory] = dataclasses.field(default=None, repr=False)

    def __enter__(self):
        if self.repo_set.is_single_repo:
            self.path = self.repo_set.repositories[0].path
            return self
        try:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="zentao-analyzer-repos-")
            self.path = self._temp_dir.name
            for repo in self.repo_set.repositories:
                os.symlink(repo.path, os.path.join(self.path, repo.role), target_is_directory=True)
            self.available = True
        except (AttributeError, NotImplementedError, OSError) as exc:
            self.error = str(exc)
            self.close()
        return self

    def close(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None
        if not self.available:
            self.path = ""

    def __exit__(self, exc_type, exc, tb):
        self.close()
