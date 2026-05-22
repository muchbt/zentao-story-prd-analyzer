import dataclasses
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from .run_logger import redact_sensitive

try:
    import openai
except ImportError:
    openai = None


@dataclasses.dataclass
class AgentConfig:
    agent: str = "openai"
    model: str = ""
    timeout: int = 900
    command: str = ""
    prompt_via: str = "stdin"
    extra_args: List[str] = dataclasses.field(default_factory=list)
    cwd: str = "."


@dataclasses.dataclass
class AgentResult:
    ok: bool
    text: str = ""
    json_data: Dict[str, Any] = dataclasses.field(default_factory=dict)
    raw_response: str = ""
    error: str = ""
    error_kind: str = ""
    duration_ms: int = 0
    agent: str = ""
    model: str = ""


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _extract_markdown_json(text: str) -> Optional[str]:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _extract_first_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return None


def extract_json_object(text: str) -> Dict[str, Any]:
    candidates = [text.strip()]
    markdown = _extract_markdown_json(text)
    if markdown:
        candidates.append(markdown.strip())
    embedded = _extract_first_json_object(text)
    if embedded:
        candidates.append(embedded.strip())
    last_error = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(data, dict):
            return data
    if last_error:
        raise last_error
    raise json.JSONDecodeError("No JSON object found", text, 0)


def classify_agent_error(text: str) -> str:
    lower = text.lower()
    if "unauthorized" in lower or "authentication" in lower or "api key" in lower or "anthropic_api_key" in lower:
        return "auth"
    if "rate limit" in lower or "429" in lower:
        return "auth"
    if "network" in lower or "timed out" in lower or "econn" in lower or "socket" in lower:
        return "network"
    return "runtime"


CLAUDE_SYSTEM_PROMPT = (
    "你是代码分析 Agent。只返回一个 JSON 对象，不要输出 Markdown。"
    "必须包含 conclusion、evidence、recommendations、verification、confidence 等字段。"
)


def _has_any_arg(args: List[str], names: List[str]) -> bool:
    return any(arg in names for arg in args)


def build_claude_command(config: AgentConfig, prompt: str):
    command = config.command or "claude"
    args = [command] + list(config.extra_args or [])
    if "--output-format" not in args:
        args.extend(["--output-format", "text"])
    if "--append-system-prompt" not in args:
        args.extend(["--append-system-prompt", CLAUDE_SYSTEM_PROMPT])
    if "--disallowedTools" not in args:
        args.extend(["--disallowedTools", "Task"])
    permission_flags = ["--dangerously-skip-permissions", "--permission-mode", "--allowedTools"]
    if not _has_any_arg(args, permission_flags):
        args.append("--dangerously-skip-permissions")
    prompt_via = (config.prompt_via or "stdin").lower()
    if prompt_via == "arg":
        args = [arg for arg in args if arg not in ("-p", "--print")]
        args.extend(["-p", prompt])
        return args, None
    args = [arg for arg in args if arg not in ("-p", "--print")]
    return args, prompt


def _safe_join_error(stdout: str, stderr: str) -> str:
    text = "\n".join(part for part in (stdout, stderr) if part)
    return redact_sensitive(text.strip())


class AgentClient:
    def __init__(self, config: AgentConfig):
        self.config = config

    def call(self, prompt: str) -> AgentResult:
        agent = (self.config.agent or "openai").lower()
        if agent in ("openai", "codex"):
            return self._call_openai(prompt, agent)
        if agent == "claude":
            return self._call_claude(prompt)
        if agent == "opencode":
            return self._call_opencode(prompt)
        return AgentResult(ok=False, error_kind="config", error=f"未识别 agent: {agent}", agent=agent, model=self.config.model)

    def _parse_text(self, text: str, raw_agent: str, model: str, duration_ms: int = 0) -> AgentResult:
        redacted_text = redact_sensitive(text)
        try:
            data = extract_json_object(text)
        except json.JSONDecodeError:
            return AgentResult(
                ok=False,
                text=redacted_text,
                raw_response=redacted_text,
                error="LLM 返回非 JSON",
                error_kind="parse",
                duration_ms=duration_ms,
                agent=raw_agent,
                model=model,
            )
        return AgentResult(
            ok=True,
            text=redacted_text,
            json_data=redact_sensitive(data),
            raw_response=redacted_text,
            duration_ms=duration_ms,
            agent=raw_agent,
            model=model,
        )

    def _call_openai(self, prompt: str, agent: str) -> AgentResult:
        started = _now_ms()
        model = self.config.model or os.environ.get("OPENAI_MODEL", "")
        if openai is None:
            return AgentResult(ok=False, error_kind="config", error=f"openai Python 模块未安装，无法使用 {agent} 后端。如果在 Claude Code 环境中运行，请使用 --agent claude；如果在 OpenCode 环境中运行，请使用 --agent opencode", agent=agent, model=model)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return AgentResult(ok=False, error_kind="config", error=f"缺少 OPENAI_API_KEY，{agent} 后端需要此环境变量", agent=agent, model=model)
        if not model:
            return AgentResult(ok=False, error_kind="config", error=f"缺少 OPENAI_MODEL 或 --model，{agent} 后端需要指定模型名", agent=agent, model=model)
        try:
            openai.api_key = api_key
            if os.environ.get("OPENAI_BASE_URL"):
                openai.base_url = os.environ.get("OPENAI_BASE_URL")
            response = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                request_timeout=self.config.timeout,
            )
            text = response.choices[0].message.content
            return self._parse_text(text or "", raw_agent=agent, model=model, duration_ms=_now_ms() - started)
        except TimeoutError as exc:
            return AgentResult(ok=False, error_kind="timeout", error=str(exc), duration_ms=_now_ms() - started, agent=agent, model=model)
        except Exception as exc:
            kind = classify_agent_error(str(exc))
            return AgentResult(ok=False, error_kind=kind, error=redact_sensitive(str(exc)), duration_ms=_now_ms() - started, agent=agent, model=model)

    def _call_claude(self, prompt: str) -> AgentResult:
        started = _now_ms()
        cmd, stdin_text = build_claude_command(self.config, prompt)
        try:
            completed = subprocess.run(
                cmd,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=self.config.cwd or ".",
                shell=False,
            )
        except FileNotFoundError as exc:
            return AgentResult(ok=False, error_kind="config", error=f"Claude 命令不存在: {exc}", duration_ms=_now_ms() - started, agent="claude", model=self.config.model)
        except subprocess.TimeoutExpired as exc:
            return AgentResult(ok=False, error_kind="timeout", error=f"Claude CLI 超时: {exc}", duration_ms=_now_ms() - started, agent="claude", model=self.config.model)
        except TimeoutError as exc:
            return AgentResult(ok=False, error_kind="timeout", error=f"Claude CLI 超时: {exc}", duration_ms=_now_ms() - started, agent="claude", model=self.config.model)
        except Exception as exc:
            return AgentResult(ok=False, error_kind=classify_agent_error(str(exc)), error=redact_sensitive(str(exc)), duration_ms=_now_ms() - started, agent="claude", model=self.config.model)

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            error_text = _safe_join_error(stdout, stderr)
            return AgentResult(
                ok=False,
                raw_response=redact_sensitive(stdout),
                error=error_text or f"Claude CLI 返回码 {completed.returncode}",
                error_kind=classify_agent_error(error_text),
                duration_ms=_now_ms() - started,
                agent="claude",
                model=self.config.model,
            )
        return self._parse_text(stdout.strip(), raw_agent="claude", model=self.config.model, duration_ms=_now_ms() - started)

    def _call_opencode(self, prompt: str) -> AgentResult:
        started = _now_ms()
        command = self.config.command or "opencode"
        args = [command, "agent"]
        if self.config.prompt_via == "arg":
            args.extend(["-p", prompt])
        try:
            completed = subprocess.run(
                args,
                input=prompt if self.config.prompt_via != "arg" else None,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=self.config.cwd or ".",
                shell=False,
            )
        except FileNotFoundError as exc:
            return AgentResult(ok=False, error_kind="config", error=f"opencode 命令不存在: {exc}", duration_ms=_now_ms() - started, agent="opencode", model=self.config.model)
        except subprocess.TimeoutExpired as exc:
            return AgentResult(ok=False, error_kind="timeout", error=f"opencode agent 超时: {exc}", duration_ms=_now_ms() - started, agent="opencode", model=self.config.model)
        except Exception as exc:
            return AgentResult(ok=False, error_kind=classify_agent_error(str(exc)), error=redact_sensitive(str(exc)), duration_ms=_now_ms() - started, agent="opencode", model=self.config.model)

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if completed.returncode != 0:
            error_text = _safe_join_error(stdout, stderr)
            return AgentResult(
                ok=False,
                raw_response=redact_sensitive(stdout),
                error=error_text or f"opencode agent 返回码 {completed.returncode}",
                error_kind=classify_agent_error(error_text),
                duration_ms=_now_ms() - started,
                agent="opencode",
                model=self.config.model,
            )
        return self._parse_text(stdout.strip(), raw_agent="opencode", model=self.config.model, duration_ms=_now_ms() - started)
