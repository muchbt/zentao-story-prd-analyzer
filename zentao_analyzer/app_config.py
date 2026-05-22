import dataclasses
import os
import shutil
from typing import Any, Dict, List


def _first_non_empty(*values: Any, default: Any = "") -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _int_value(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


@dataclasses.dataclass
class RuntimeConfig:
    agent: str = ""
    model: str = ""
    agent_timeout: int = 900
    claude_command: str = "claude"
    codex_command: str = "codex"
    opencode_command: str = "opencode"
    claude_prompt_via: str = "stdin"
    claude_extra_args: List[str] = dataclasses.field(default_factory=list)
    verbose: bool = False
    quiet: bool = False
    log_file: str = ""
    debug_bundle_enabled: bool = True
    debug_bundle_dir: str = ""
    debug_include_code: bool = False
    repo_path: str = "."

    def agent_config_dict(self) -> Dict[str, Any]:
        command_by_agent = {
            "claude": self.claude_command,
            "codex": self.codex_command,
            "opencode": self.opencode_command,
        }
        return {
            "agent": self.agent,
            "model": self.model,
            "timeout": self.agent_timeout,
            "command": command_by_agent.get(self.agent, ""),
            "prompt_via": self.claude_prompt_via,
            "extra_args": list(self.claude_extra_args),
            "cwd": self.repo_path or ".",
        }


def _detect_default_agent() -> str:
    for name in ("claude", "codex", "opencode"):
        if shutil.which(name):
            return name
    return ""


def build_runtime_config(args) -> RuntimeConfig:
    agent_arg = _first_non_empty(getattr(args, "agent", None), os.environ.get("LLM_AGENT"), default="")
    if agent_arg:
        agent = str(agent_arg).lower()
    else:
        agent = _detect_default_agent()
    prompt_via = str(_first_non_empty(getattr(args, "claude_prompt_via", None), os.environ.get("CLAUDE_PROMPT_VIA"), default="stdin")).lower()
    if prompt_via not in ("stdin", "arg"):
        prompt_via = "stdin"
    return RuntimeConfig(
        agent=agent,
        model=str(_first_non_empty(getattr(args, "model", None), default="")),
        agent_timeout=_int_value(_first_non_empty(getattr(args, "agent_timeout", None), os.environ.get("AGENT_TIMEOUT"), default=None), 900),
        claude_command=str(_first_non_empty(getattr(args, "claude_command", None), os.environ.get("CLAUDE_COMMAND"), default="claude")),
        codex_command=str(_first_non_empty(getattr(args, "codex_command", None), os.environ.get("CODEX_COMMAND"), default="codex")),
        opencode_command=str(_first_non_empty(getattr(args, "opencode_command", None), os.environ.get("OPENCODE_COMMAND"), default="opencode")),
        claude_prompt_via=prompt_via,
        claude_extra_args=list(getattr(args, "claude_extra_arg", None) or []),
        verbose=bool(getattr(args, "verbose", False)),
        quiet=bool(getattr(args, "quiet", False)),
        log_file=str(_first_non_empty(getattr(args, "log_file", None), default="")),
        debug_bundle_enabled=not bool(getattr(args, "no_debug_bundle", False)),
        debug_bundle_dir=str(_first_non_empty(getattr(args, "debug_bundle_dir", None), os.environ.get("DEBUG_BUNDLE_DIR"), default="")),
        debug_include_code=bool(getattr(args, "debug_include_code", False)),
        repo_path=str(_first_non_empty(getattr(args, "repo_path", None), default=".")),
    )
