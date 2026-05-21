# Phase 4: Agent UX and Debug Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable OpenAI/Codex and Claude CLI Agent execution, structured AgentResult fallback, default debug bundle, structured logs, and user-facing documentation.

**Architecture:** Introduce focused modules for config, logging/redaction, Agent execution, and debug bundle writing. Keep `main.py` as orchestration only, keep `llm_client.call_llm()` as a compatibility wrapper for existing `analyzer.py`, and preserve phase 1-3 behavior unless `--analyze` or new phase 4 options are used.

**Tech Stack:** Python 3.8+, dataclasses, json, pathlib/os, subprocess with `shell=False`, argparse, unittest, unittest.mock, tempfile

---

## File Map

| File | Responsibility | Status |
|------|----------------|--------|
| `run_logger.py` | Redaction, stderr progress logs, optional JSONL logs, quiet/verbose behavior | Create |
| `app_config.py` | Merge CLI arguments and environment variables into runtime config | Create |
| `agent_client.py` | Define `AgentConfig`, `AgentResult`, JSON extraction, OpenAI/Codex, Claude CLI, OpenCode reserved backend | Create |
| `debug_bundle.py` | Default debug bundle writer for config, items, scan summary, prompts, responses, analysis, documents, logs | Create |
| `llm_client.py` | Keep `call_llm()` API, delegate to `AgentClient`, return legacy dict shape | Modify |
| `analyzer.py` | Accept optional config/logger/debug callbacks, record prompt/response, convert Agent failures to `AnalysisResult.from_error()` | Modify |
| `main.py` | Add phase 4 CLI args, build config/logger/debug bundle, wire logs and final JSON fields | Modify |
| `README.md` | Document Agent selection, OpenAI/Codex, Claude CLI, logs, debug bundle, safety | Modify |
| `SKILL.yaml` | Add phase 4 inputs | Modify |
| `tests/test_run_logger.py` | Redaction, quiet/verbose, JSONL behavior | Create |
| `tests/test_app_config.py` | CLI/env merge and defaults | Create |
| `tests/test_agent_client.py` | AgentResult fallback, OpenAI mock, Claude stdin/arg mock, timeout, missing command, OpenCode | Create |
| `tests/test_debug_bundle.py` | Default create, disabled, custom dir, redaction, include-code behavior | Create |
| `tests/test_llm_client.py` | Update compatibility wrapper tests | Modify |
| `tests/test_analyzer.py` | Update analyzer tests for Agent config/debug hooks | Modify |
| `tests/test_main_phase4.py` | CLI arg mapping, stdout single JSON, default debug bundle, `--no-debug-bundle`, log file | Create |

---

## Task 1: Runtime Logger and Redaction

**Files:**
- Create: `run_logger.py`
- Test: `tests/test_run_logger.py`

**Dependencies:** None

- [ ] **Step 1: Write failing tests**

```python
# tests/test_run_logger.py
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_logger import RunLogger, redact_sensitive


class TestRunLogger(unittest.TestCase):
    def test_redact_sensitive_values(self):
        data = {
            "token": "abc123",
            "password": "secret",
            "api_key": "key",
            "authorization": "Bearer xyz",
            "nested": {"OPENAI_API_KEY": "sk-test", "safe": "value"},
            "text": "Authorization: Bearer live-token and password=abc",
        }
        redacted = redact_sensitive(data)
        self.assertEqual(redacted["token"], "***")
        self.assertEqual(redacted["password"], "***")
        self.assertEqual(redacted["api_key"], "***")
        self.assertEqual(redacted["authorization"], "***")
        self.assertEqual(redacted["nested"]["OPENAI_API_KEY"], "***")
        self.assertIn("Bearer ***", redacted["text"])
        self.assertNotIn("live-token", redacted["text"])
        self.assertNotIn("password=abc", redacted["text"])

    def test_quiet_suppresses_progress_stderr(self):
        stream = io.StringIO()
        logger = RunLogger(quiet=True)
        with redirect_stderr(stream):
            logger.info("fetch_items", "started", status="running")
        self.assertEqual(stream.getvalue(), "")

    def test_verbose_writes_more_fields_to_stderr(self):
        stream = io.StringIO()
        logger = RunLogger(verbose=True)
        with redirect_stderr(stream):
            logger.info("analyze", "agent_call", status="done", item_id="5939", agent="claude", duration_ms=12)
        text = stream.getvalue()
        self.assertIn("analyze", text)
        self.assertIn("agent_call", text)
        self.assertIn("5939", text)
        self.assertIn("claude", text)

    def test_jsonl_log_file_is_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "run.jsonl")
            logger = RunLogger(log_file=path)
            logger.info("analyze", "agent_call", token="abc123", error="Authorization: Bearer abc123")
            with open(path, "r", encoding="utf-8") as f:
                line = f.readline()
            event = json.loads(line)
            self.assertEqual(event["token"], "***")
            self.assertEqual(event["error"], "Authorization: Bearer ***")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_run_logger -v`

Expected: `ModuleNotFoundError: No module named 'run_logger'`.

- [ ] **Step 3: Implement `run_logger.py`**

```python
# run_logger.py
import copy
import datetime
import json
import os
import re
import sys
from typing import Any, Dict


SENSITIVE_KEYS = {
    "openai_api_key",
    "anthropic_api_key",
    "zentao_token",
    "token",
    "password",
    "api_key",
    "apikey",
    "authorization",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or normalized.endswith("_token") or normalized.endswith("_password")


def _redact_string(value: str) -> str:
    value = re.sub(r"Bearer\s+[^\\s,;]+", "Bearer ***", value, flags=re.IGNORECASE)
    value = re.sub(r"(password|token|api_key|authorization)=([^\\s,;]+)", r"\\1=***", value, flags=re.IGNORECASE)
    return value


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[key] = "***"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


class RunLogger:
    def __init__(self, verbose: bool = False, quiet: bool = False, log_file: str = ""):
        self.verbose = bool(verbose)
        self.quiet = bool(quiet)
        self.log_file = log_file or ""
        if self.log_file:
            parent = os.path.dirname(os.path.abspath(self.log_file))
            if parent:
                os.makedirs(parent, exist_ok=True)

    def event(self, stage: str, event: str, level: str = "info", **fields: Any) -> Dict[str, Any]:
        payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds"),
            "level": level,
            "stage": stage,
            "event": event,
        }
        payload.update(fields)
        redacted = redact_sensitive(copy.deepcopy(payload))
        self._write_stderr(redacted)
        self._write_jsonl(redacted)
        return redacted

    def info(self, stage: str, event: str, **fields: Any) -> Dict[str, Any]:
        return self.event(stage, event, "info", **fields)

    def warning(self, stage: str, event: str, **fields: Any) -> Dict[str, Any]:
        return self.event(stage, event, "warning", **fields)

    def error(self, stage: str, event: str, **fields: Any) -> Dict[str, Any]:
        return self.event(stage, event, "error", **fields)

    def _write_stderr(self, payload: Dict[str, Any]) -> None:
        if self.quiet and payload.get("level") != "error":
            return
        if self.verbose:
            details = " ".join(f"{key}={value}" for key, value in payload.items() if key not in ("timestamp", "level"))
            print(f"[{payload['level']}] {details}", file=sys.stderr)
            return
        if payload.get("level") == "error":
            print(f"[error] {payload.get('stage')} {payload.get('event')}: {payload.get('error', '')}", file=sys.stderr)
            return
        print(f"{payload.get('stage')} {payload.get('event')} {payload.get('status', '')}".strip(), file=sys.stderr)

    def _write_jsonl(self, payload: Dict[str, Any]) -> None:
        if not self.log_file:
            return
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_run_logger -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add run_logger.py tests/test_run_logger.py
git commit -m "feat: add run logger and redaction"
```

---

## Task 2: Application Config Merge

**Files:**
- Create: `app_config.py`
- Test: `tests/test_app_config.py`

**Dependencies:** `agent_client.AgentConfig` will be created in Task 3. To keep this task independent, define `RuntimeConfig` here with an `agent_config_dict()` method and have Task 3 consume it.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_app_config.py
import argparse
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_config import RuntimeConfig, build_runtime_config


class TestAppConfig(unittest.TestCase):
    def test_defaults_match_phase4_spec(self):
        args = argparse.Namespace(
            agent=None,
            model=None,
            agent_timeout=None,
            claude_command=None,
            claude_prompt_via=None,
            claude_extra_arg=None,
            verbose=False,
            quiet=False,
            log_file=None,
            no_debug_bundle=False,
            debug_bundle_dir=None,
            debug_include_code=False,
            repo_path=".",
        )
        with patch.dict(os.environ, {}, clear=True):
            config = build_runtime_config(args)
        self.assertEqual(config.agent, "codex")
        self.assertEqual(config.agent_timeout, 120)
        self.assertEqual(config.claude_command, "claude")
        self.assertEqual(config.claude_prompt_via, "stdin")
        self.assertTrue(config.debug_bundle_enabled)
        self.assertFalse(config.debug_include_code)

    def test_env_values_are_used_when_cli_missing(self):
        args = argparse.Namespace(
            agent=None,
            model=None,
            agent_timeout=None,
            claude_command=None,
            claude_prompt_via=None,
            claude_extra_arg=None,
            verbose=False,
            quiet=False,
            log_file=None,
            no_debug_bundle=False,
            debug_bundle_dir=None,
            debug_include_code=False,
            repo_path="/repo",
        )
        env = {
            "LLM_AGENT": "claude",
            "OPENAI_MODEL": "gpt-test",
            "AGENT_TIMEOUT": "9",
            "CLAUDE_COMMAND": "claude-dev",
            "CLAUDE_PROMPT_VIA": "arg",
            "DEBUG_BUNDLE_DIR": "/tmp/debugs",
        }
        with patch.dict(os.environ, env, clear=True):
            config = build_runtime_config(args)
        self.assertEqual(config.agent, "claude")
        self.assertEqual(config.model, "gpt-test")
        self.assertEqual(config.agent_timeout, 9)
        self.assertEqual(config.claude_command, "claude-dev")
        self.assertEqual(config.claude_prompt_via, "arg")
        self.assertEqual(config.debug_bundle_dir, "/tmp/debugs")

    def test_cli_values_override_env(self):
        args = argparse.Namespace(
            agent="openai",
            model="cli-model",
            agent_timeout=30,
            claude_command="claude-cli",
            claude_prompt_via="stdin",
            claude_extra_arg=["--foo", "bar"],
            verbose=True,
            quiet=False,
            log_file="run.jsonl",
            no_debug_bundle=True,
            debug_bundle_dir="debug",
            debug_include_code=True,
            repo_path="/repo",
        )
        with patch.dict(os.environ, {"LLM_AGENT": "claude", "AGENT_TIMEOUT": "9"}, clear=True):
            config = build_runtime_config(args)
        self.assertEqual(config.agent, "openai")
        self.assertEqual(config.model, "cli-model")
        self.assertEqual(config.agent_timeout, 30)
        self.assertEqual(config.claude_extra_args, ["--foo", "bar"])
        self.assertTrue(config.verbose)
        self.assertEqual(config.log_file, "run.jsonl")
        self.assertFalse(config.debug_bundle_enabled)
        self.assertTrue(config.debug_include_code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_app_config -v`

Expected: `ModuleNotFoundError: No module named 'app_config'`.

- [ ] **Step 3: Implement `app_config.py`**

```python
# app_config.py
import dataclasses
import os
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
    agent: str = "codex"
    model: str = ""
    agent_timeout: int = 120
    claude_command: str = "claude"
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
        return {
            "agent": self.agent,
            "model": self.model,
            "timeout": self.agent_timeout,
            "command": self.claude_command,
            "prompt_via": self.claude_prompt_via,
            "extra_args": list(self.claude_extra_args),
            "cwd": self.repo_path or ".",
        }


def build_runtime_config(args) -> RuntimeConfig:
    agent = str(_first_non_empty(getattr(args, "agent", None), os.environ.get("LLM_AGENT"), default="codex")).lower()
    prompt_via = str(_first_non_empty(getattr(args, "claude_prompt_via", None), os.environ.get("CLAUDE_PROMPT_VIA"), default="stdin")).lower()
    if prompt_via not in ("stdin", "arg"):
        prompt_via = "stdin"
    return RuntimeConfig(
        agent=agent,
        model=str(_first_non_empty(getattr(args, "model", None), os.environ.get("OPENAI_MODEL"), default="")),
        agent_timeout=_int_value(_first_non_empty(getattr(args, "agent_timeout", None), os.environ.get("AGENT_TIMEOUT"), default=None), 120),
        claude_command=str(_first_non_empty(getattr(args, "claude_command", None), os.environ.get("CLAUDE_COMMAND"), default="claude")),
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_app_config -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add app_config.py tests/test_app_config.py
git commit -m "feat: add phase4 runtime config"
```

---

## Task 3: AgentClient Core, OpenAI/Codex, and OpenCode

**Files:**
- Create: `agent_client.py`
- Test: `tests/test_agent_client.py`

**Dependencies:** `run_logger.redact_sensitive`

- [ ] **Step 1: Write failing tests for core and OpenAI/OpenCode**

```python
# tests/test_agent_client.py
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_client import AgentClient, AgentConfig, AgentResult, extract_json_object


class TestAgentClientCore(unittest.TestCase):
    def test_extract_json_direct_markdown_and_embedded(self):
        self.assertEqual(extract_json_object('{"conclusion":"完成"}'), {"conclusion": "完成"})
        self.assertEqual(extract_json_object('```json\\n{"conclusion":"完成"}\\n```'), {"conclusion": "完成"})
        self.assertEqual(extract_json_object('prefix {"conclusion":"完成"} suffix'), {"conclusion": "完成"})

    def test_parse_failure_returns_structured_result(self):
        client = AgentClient(AgentConfig(agent="opencode"))
        result = client._parse_text("not json", raw_agent="opencode", model="")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse")
        self.assertEqual(result.raw_response, "not json")

    def test_opencode_is_reserved(self):
        client = AgentClient(AgentConfig(agent="opencode"))
        result = client.call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "not_implemented")
        self.assertIn("OpenCode", result.error)


class TestAgentClientOpenAI(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_openai_missing_key_returns_config_error(self):
        client = AgentClient(AgentConfig(agent="openai", model="gpt-test"))
        result = client.call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertIn("OPENAI_API_KEY", result.error)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_openai_missing_model_returns_config_error(self):
        client = AgentClient(AgentConfig(agent="openai"))
        result = client.call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertIn("OPENAI_MODEL", result.error)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_openai_success_uses_sdk_and_parses_json(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = '{"conclusion":"完成","evidence":["src/a.py"],"confidence":"高"}'
        with patch("agent_client.openai") as mock_openai:
            mock_openai.ChatCompletion.create.return_value = response
            client = AgentClient(AgentConfig(agent="codex", model="gpt-test", timeout=8))
            result = client.call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.agent, "codex")
        self.assertEqual(result.model, "gpt-test")
        self.assertEqual(result.json_data["conclusion"], "完成")
        mock_openai.ChatCompletion.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_openai_non_json_is_parse_error(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "not json"
        with patch("agent_client.openai") as mock_openai:
            mock_openai.ChatCompletion.create.return_value = response
            client = AgentClient(AgentConfig(agent="openai", model="gpt-test"))
            result = client.call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse")
        self.assertEqual(result.raw_response, "not json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_agent_client -v`

Expected: `ModuleNotFoundError: No module named 'agent_client'`.

- [ ] **Step 3: Implement Agent dataclasses, JSON extraction, OpenAI/Codex, OpenCode**

```python
# agent_client.py
import dataclasses
import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from run_logger import redact_sensitive

try:
    import openai
except ImportError:
    openai = None


@dataclasses.dataclass
class AgentConfig:
    agent: str = "openai"
    model: str = ""
    timeout: int = 120
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
    match = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", text, flags=re.IGNORECASE | re.DOTALL)
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
            return AgentResult(ok=False, error_kind="not_implemented", error="OpenCode 适配尚未实现", agent=agent, model=self.config.model)
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
            return AgentResult(ok=False, error_kind="config", error="openai 模块未安装", agent=agent, model=model)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return AgentResult(ok=False, error_kind="config", error="缺少 OPENAI_API_KEY", agent=agent, model=model)
        if not model:
            return AgentResult(ok=False, error_kind="config", error="缺少 OPENAI_MODEL 或 --model", agent=agent, model=model)
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
        return AgentResult(ok=False, error_kind="not_implemented", error="Claude CLI 适配未接入", agent="claude", model=self.config.model)
```

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_agent_client -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_client.py tests/test_agent_client.py
git commit -m "feat: add agent client core and openai backend"
```

---

## Task 4: Claude CLI Backend

**Files:**
- Modify: `agent_client.py`
- Modify: `tests/test_agent_client.py`

**Dependencies:** Task 3

- [ ] **Step 1: Add failing Claude tests**

Append to `tests/test_agent_client.py`:

```python
class TestAgentClientClaude(unittest.TestCase):
    def test_claude_stdin_success(self):
        completed = subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("agent_client.subprocess.run", return_value=completed) as mock_run:
            client = AgentClient(AgentConfig(agent="claude", command="claude", prompt_via="stdin", timeout=5, cwd="/repo"))
            result = client.call("prompt")
        self.assertTrue(result.ok)
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][0], "claude")
        self.assertIn("--output-format", args[0])
        self.assertIn("--append-system-prompt", args[0])
        self.assertIn("--disallowedTools", args[0])
        self.assertIn("--dangerously-skip-permissions", args[0])
        self.assertEqual(kwargs["input"], "prompt")
        self.assertEqual(kwargs["cwd"], "/repo")
        self.assertFalse(any(part == "-p" or part == "--print" for part in args[0]))
        self.assertEqual(result.json_data["conclusion"], "完成")

    def test_claude_arg_success(self):
        completed = subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("agent_client.subprocess.run", return_value=completed) as mock_run:
            client = AgentClient(AgentConfig(agent="claude", command="claude", prompt_via="arg", extra_args=["--foo"], timeout=5))
            result = client.call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertIn("--foo", cmd)
        self.assertIn("-p", cmd)
        self.assertEqual(cmd[-1], "prompt")
        self.assertIsNone(mock_run.call_args.kwargs.get("input"))

    def test_claude_timeout(self):
        with patch("agent_client.subprocess.run", side_effect=TimeoutError("expired")):
            result = AgentClient(AgentConfig(agent="claude", command="claude")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "timeout")

    def test_claude_missing_command(self):
        with patch("agent_client.subprocess.run", side_effect=FileNotFoundError("missing")):
            result = AgentClient(AgentConfig(agent="claude", command="missing")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")

    def test_claude_auth_error_is_classified(self):
        completed = subprocess_completed(stdout="", stderr="unauthorized anthropic_api_key", returncode=1)
        with patch("agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude", command="claude")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "auth")


def subprocess_completed(stdout="", stderr="", returncode=0):
    completed = MagicMock()
    completed.stdout = stdout
    completed.stderr = stderr
    completed.returncode = returncode
    return completed
```

Also add `import subprocess` only if the final test uses concrete `subprocess.CompletedProcess`; the helper above avoids that import.

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m unittest tests.test_agent_client -v`

Expected: Claude tests fail because `_call_claude()` still returns `not_implemented`.

- [ ] **Step 3: Implement Claude command building and execution**

Replace `_call_claude()` in `agent_client.py` and add helpers:

```python
CLAUDE_SYSTEM_PROMPT = (
    "你是代码分析 Agent。只返回一个 JSON 对象，不要输出 Markdown。"
    "必须包含 conclusion、evidence、recommendations、verification、confidence 等字段。"
)


def _has_any_arg(args: List[str], names: List[str]) -> bool:
    return any(arg in names for arg in args)


def build_claude_command(config: AgentConfig, prompt: str) -> (List[str], Optional[str]):
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
    text = "\\n".join(part for part in (stdout, stderr) if part)
    return redact_sensitive(text.strip())
```

Then replace `_call_claude()`:

```python
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
```

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_agent_client -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add agent_client.py tests/test_agent_client.py
git commit -m "feat: add claude cli agent backend"
```

---

## Task 5: LLM Compatibility Wrapper and Analyzer Hooks

**Files:**
- Modify: `llm_client.py`
- Modify: `analyzer.py`
- Modify: `tests/test_llm_client.py`
- Modify: `tests/test_analyzer.py`

**Dependencies:** Tasks 3-4

- [ ] **Step 1: Replace `tests/test_llm_client.py` with compatibility tests**

```python
# tests/test_llm_client.py
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_client import AgentConfig, AgentResult
from llm_client import call_llm


class TestLLMClient(unittest.TestCase):
    def test_call_llm_returns_json_data_and_raw(self):
        result_obj = AgentResult(ok=True, json_data={"conclusion": "完成"}, raw_response='{"conclusion":"完成"}')
        with patch("llm_client.AgentClient") as mock_client:
            mock_client.return_value.call.return_value = result_obj
            result = call_llm("prompt", agent="codex", agent_config=AgentConfig(agent="codex", model="gpt-test"))
        self.assertEqual(result["conclusion"], "完成")
        self.assertEqual(result["raw"], '{"conclusion":"完成"}')

    def test_call_llm_failure_returns_legacy_error_shape(self):
        result_obj = AgentResult(ok=False, error="LLM 返回非 JSON", error_kind="parse", raw_response="bad")
        with patch("llm_client.AgentClient") as mock_client:
            mock_client.return_value.call.return_value = result_obj
            result = call_llm("prompt", agent="claude", agent_config=AgentConfig(agent="claude"))
        self.assertEqual(result["error"], "LLM 返回非 JSON")
        self.assertEqual(result["error_kind"], "parse")
        self.assertEqual(result["raw"], "bad")

    def test_call_llm_builds_config_from_agent_name(self):
        with patch("llm_client.AgentClient") as mock_client:
            mock_client.return_value.call.return_value = AgentResult(ok=False, error="OpenCode 适配尚未实现", error_kind="not_implemented")
            result = call_llm("prompt", agent="opencode")
        created_config = mock_client.call_args[0][0]
        self.assertEqual(created_config.agent, "opencode")
        self.assertEqual(result["error_kind"], "not_implemented")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Add analyzer hook tests**

Append to `tests/test_analyzer.py`:

```python
    def test_analyzer_passes_agent_config_to_llm_client(self):
        item = ZentaoItem(id="6", type="story", title="S")
        agent_config = MagicMock()
        with patch("analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="claude", agent_config=agent_config)
        self.assertEqual(mock_llm.call_args.kwargs["agent_config"], agent_config)

    def test_analyzer_records_prompt_and_response_with_debug_recorder(self):
        item = ZentaoItem(id="7", type="story", title="S")
        records = []
        def recorder(kind, item_obj, payload):
            records.append((kind, item_obj.id, payload))
        with patch("analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高", "raw": '{"ok":true}'}):
                analyze(item, ".", agent="codex", debug_recorder=recorder)
        self.assertEqual(records[0][0], "prompt")
        self.assertEqual(records[0][1], "7")
        self.assertIn("功能实现完成度", records[0][2])
        self.assertEqual(records[1], ("response", "7", '{"ok":true}'))
```

- [ ] **Step 3: Run tests to verify failure**

Run: `python3 -m unittest tests.test_llm_client tests.test_analyzer -v`

Expected: failures because wrapper and analyzer signatures have not been updated.

- [ ] **Step 4: Update `llm_client.py`**

```python
# llm_client.py
from typing import Any, Dict, Optional

from agent_client import AgentClient, AgentConfig


def call_llm(prompt: str, agent: str = "codex", agent_config: Optional[AgentConfig] = None) -> Dict[str, Any]:
    config = agent_config or AgentConfig(agent=agent)
    result = AgentClient(config).call(prompt)
    if not result.ok:
        return {
            "error": result.error,
            "error_kind": result.error_kind,
            "raw": result.raw_response,
        }
    data = dict(result.json_data)
    data["raw"] = result.raw_response
    return data
```

- [ ] **Step 5: Update `analyzer.py` signature and debug hooks**

Change the function signature:

```python
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
) -> AnalysisResult:
```

After prompt construction and before LLM call:

```python
    if debug_recorder:
        debug_recorder("prompt", item, prompt)

    llm_data = call_llm(prompt, agent=agent, agent_config=agent_config)

    if debug_recorder:
        debug_recorder("response", item, llm_data.get("raw", ""))
```

Keep existing error conversion:

```python
    if "error" in llm_data:
        return AnalysisResult.from_error(item, llm_data["error"], raw_response=llm_data.get("raw", ""))
```

- [ ] **Step 6: Run focused tests**

Run: `python3 -m unittest tests.test_llm_client tests.test_analyzer -v`

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add llm_client.py analyzer.py tests/test_llm_client.py tests/test_analyzer.py
git commit -m "feat: route analysis through agent client"
```

---

## Task 6: Debug Bundle Writer

**Files:**
- Create: `debug_bundle.py`
- Test: `tests/test_debug_bundle.py`

**Dependencies:** `run_logger.redact_sensitive`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_debug_bundle.py
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from debug_bundle import DebugBundle, build_debug_bundle


class TestDebugBundle(unittest.TestCase):
    def test_build_default_path_and_write_config(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = build_debug_bundle(
                enabled=True,
                base_dir=td,
                module="requirement",
                run_id="5939",
                timestamp="20260521-100000",
            )
            self.assertTrue(bundle.enabled)
            self.assertTrue(bundle.path.endswith("20260521-100000-requirement-5939"))
            bundle.write_config({"OPENAI_API_KEY": "sk-test", "safe": "value"})
            with open(os.path.join(bundle.path, "run_config.redacted.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["OPENAI_API_KEY"], "***")
            self.assertEqual(data["safe"], "value")

    def test_disabled_bundle_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = build_debug_bundle(enabled=False, base_dir=td, module="story", run_id="1")
            bundle.write_items([])
            self.assertFalse(os.listdir(td))

    def test_prompt_response_analysis_documents_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle"))
            item = MagicMock()
            item.id = "1"
            item.type = "story"
            item.title = "T"
            bundle.write_items([item])
            bundle.write_scan_summary({"files": ["a.py"], "matched_count": 1})
            bundle.write_prompt("1", "password=abc")
            bundle.write_response("1", "Authorization: Bearer token")
            bundle.write_analysis_results([{"item_id": "1", "raw_response": "token=abc"}])
            bundle.write_documents([{"document_path": "docs/prd/a.md"}])
            bundle.write_summary_path("docs/summary_report.json")
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "items.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "scan_summary.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "prompts", "1.txt")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "responses", "1.txt")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "analysis_results.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "documents.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "summary_report_path.txt")))
            with open(os.path.join(bundle.path, "prompts", "1.txt"), encoding="utf-8") as f:
                self.assertIn("password=***", f.read())

    def test_code_context_only_written_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle"), include_code=False)
            bundle.write_code_context({"snippets": [{"content": "secret"}]})
            self.assertFalse(os.path.exists(os.path.join(bundle.path, "code_context.json")))
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle2"), include_code=True)
            bundle.write_code_context({"snippets": [{"content": "password=abc"}]})
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "code_context.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_debug_bundle -v`

Expected: `ModuleNotFoundError: No module named 'debug_bundle'`.

- [ ] **Step 3: Implement `debug_bundle.py`**

```python
# debug_bundle.py
import dataclasses
import datetime
import json
import os
import re
from typing import Any, Dict, Iterable, List

from run_logger import redact_sensitive


def _safe_part(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_.\\-\\u4e00-\\u9fff]+", "_", str(value or "unknown"))
    value = re.sub(r"_+", "_", value).strip("._-")
    return value or "unknown"


def _item_to_dict(item: Any) -> Dict[str, Any]:
    return {
        "id": getattr(item, "id", ""),
        "type": getattr(item, "type", ""),
        "title": getattr(item, "title", ""),
        "status": getattr(item, "status", ""),
        "priority": getattr(item, "priority", ""),
        "keywords": getattr(item, "keywords", []),
    }


@dataclasses.dataclass
class DebugBundle:
    enabled: bool
    path: str = ""
    include_code: bool = False
    error: str = ""

    def _ensure_dir(self) -> bool:
        if not self.enabled:
            return False
        try:
            os.makedirs(self.path, exist_ok=True)
            return True
        except OSError as exc:
            self.error = str(exc)
            return False

    def _write_json(self, relative_path: str, data: Any) -> None:
        if not self._ensure_dir():
            return
        try:
            path = os.path.join(self.path, relative_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(redact_sensitive(data), f, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.error = str(exc)

    def _write_text(self, relative_path: str, text: str) -> None:
        if not self._ensure_dir():
            return
        try:
            path = os.path.join(self.path, relative_path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(redact_sensitive(text or ""))
        except OSError as exc:
            self.error = str(exc)

    def write_config(self, config: Dict[str, Any]) -> None:
        self._write_json("run_config.redacted.json", config)

    def write_items(self, items: Iterable[Any]) -> None:
        self._write_json("items.json", [_item_to_dict(item) for item in items])

    def write_scan_summary(self, summary: Dict[str, Any]) -> None:
        self._write_json("scan_summary.json", summary)

    def write_prompt(self, item_id: str, prompt: str) -> None:
        self._write_text(os.path.join("prompts", f"{_safe_part(item_id)}.txt"), prompt)

    def write_response(self, item_id: str, response: str) -> None:
        self._write_text(os.path.join("responses", f"{_safe_part(item_id)}.txt"), response)

    def write_analysis_results(self, results: List[Dict[str, Any]]) -> None:
        self._write_json("analysis_results.json", results)

    def write_documents(self, documents: List[Dict[str, Any]]) -> None:
        self._write_json("documents.json", documents)

    def write_summary_path(self, path: str) -> None:
        self._write_text("summary_report_path.txt", path)

    def write_code_context(self, context: Dict[str, Any]) -> None:
        if not self.include_code:
            return
        self._write_json("code_context.json", context)


def build_debug_bundle(enabled: bool, base_dir: str = "", module: str = "", run_id: str = "", timestamp: str = "", include_code: bool = False) -> DebugBundle:
    if not enabled:
        return DebugBundle(enabled=False, include_code=include_code)
    stamp = timestamp or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = base_dir or "debug_runs"
    path = os.path.join(root, f"{_safe_part(stamp)}-{_safe_part(module)}-{_safe_part(run_id)}")
    return DebugBundle(enabled=True, path=path, include_code=include_code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_debug_bundle -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add debug_bundle.py tests/test_debug_bundle.py
git commit -m "feat: add default debug bundle writer"
```

---

## Task 7: Main CLI Integration and Final JSON

**Files:**
- Modify: `main.py`
- Create: `tests/test_main_phase4.py`

**Dependencies:** Tasks 1-6

- [ ] **Step 1: Write failing main integration tests**

```python
# tests/test_main_phase4.py
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


def make_item():
    item = MagicMock()
    item.id = "5939"
    item.type = "requirement"
    item.title = "Test Title"
    item.description = "Desc"
    item.status = "active"
    item.priority = "1"
    item.project = ""
    item.product = "41"
    item.execution = ""
    item.assigned_to = "dev"
    item.created_by = "pm"
    item.created_date = "2026-05-20"
    item.keywords = ["test"]
    return item


def make_analysis():
    analysis = MagicMock()
    analysis.item_id = "5939"
    analysis.item_type = "requirement"
    analysis.item_title = "Test Title"
    analysis.conclusion = "完成"
    analysis.evidence = ["src/a.c"]
    analysis.gaps = []
    analysis.suspected_causes = []
    analysis.affected_scope = []
    analysis.recommendations = ["建议"]
    analysis.verification = ["验证"]
    analysis.priority = "高"
    analysis.confidence = "高"
    analysis.error = ""
    analysis.output_md = "LLM 理解"
    analysis.raw_response = '{"conclusion":"完成"}'
    analysis.is_insufficient_evidence.return_value = False
    return analysis


class TestMainPhase4(unittest.TestCase):
    def test_analyze_stdout_is_single_json_and_contains_debug_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            argv = [
                "main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--agent", "claude", "--agent-timeout", "5",
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("main.analyze", return_value=analysis) as mock_analyze:
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            code = main.main()
            self.assertEqual(code, 0)
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["debug_bundle_error"], "")
            self.assertTrue(parsed["debug_bundle"])
            self.assertTrue(os.path.exists(parsed["debug_bundle"]))
            self.assertEqual(parsed["log_file"], "")
            agent_config = mock_analyze.call_args.kwargs["agent_config"]
            self.assertEqual(agent_config.agent, "claude")
            self.assertEqual(agent_config.timeout, 5)

    def test_no_debug_bundle_disables_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            argv = [
                "main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--no-debug-bundle",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["debug_bundle"], "")

    def test_log_file_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            log_file = os.path.join(td, "run.jsonl")
            argv = [
                "main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--log-file", log_file,
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        with contextlib.redirect_stdout(io.StringIO()):
                            main.main()
            self.assertTrue(os.path.exists(log_file))
            with open(log_file, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertTrue(any(line["stage"] == "fetch_items" for line in lines))
            self.assertTrue(any(line["stage"] == "generate_docs" for line in lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_main_phase4 -v`

Expected: argparse failures for missing phase 4 flags or missing final JSON fields.

- [ ] **Step 3: Add CLI args to `main.py`**

Add imports:

```python
from agent_client import AgentConfig
from app_config import build_runtime_config
from debug_bundle import build_debug_bundle
from run_logger import RunLogger, redact_sensitive
```

Add parser arguments after existing `--agent`:

```python
    parser.add_argument("--model", help="LLM 模型名，OpenAI/Codex 使用")
    parser.add_argument("--agent-timeout", type=int, help="Agent 调用超时时间，单位秒")
    parser.add_argument("--claude-command", help="Claude CLI 命令，默认 claude")
    parser.add_argument("--claude-prompt-via", choices=["stdin", "arg"], help="Claude prompt 传递方式")
    parser.add_argument("--claude-extra-arg", action="append", help="额外 Claude CLI 参数，可重复")
    parser.add_argument("--verbose", action="store_true", help="输出详细运行日志到 stderr")
    parser.add_argument("--quiet", action="store_true", help="抑制进度日志，stdout 保持机器可读 JSON")
    parser.add_argument("--log-file", help="写入 JSONL 运行日志")
    parser.add_argument("--no-debug-bundle", action="store_true", help="关闭默认 debug bundle")
    parser.add_argument("--debug-bundle-dir", help="debug bundle 输出目录")
    parser.add_argument("--debug-include-code", action="store_true", help="debug bundle 保存代码上下文快照")
```

After `args = parser.parse_args()`:

```python
    runtime_config = build_runtime_config(args)
    logger = RunLogger(verbose=runtime_config.verbose, quiet=runtime_config.quiet, log_file=runtime_config.log_file)
```

- [ ] **Step 4: Wire logger and debug bundle**

Use the following integration pattern in `main.py`:

```python
    logger.info("fetch_items", "started", status="running", module=args.module, item_id=args.id or "")
    try:
        if args.id:
            items = [client.get_item(args.module, args.id)]
        else:
            items = client.list_items(
                module=args.module,
                project=args.project,
                product=args.product,
                execution=args.execution,
                status=args.status,
                limit=args.limit,
            )
        logger.info("fetch_items", "done", status="done", count=len(items))
    except ZentaoError as e:
        logger.error("fetch_items", "failed", status="failed", error=str(e))
        err_msg = str(e)
        if any(k in err_msg for k in ("Token 已失效", "token", "登录", "login", "认证", "auth")):
            print(f"[错误] 获取禅道数据失败: {err_msg}", file=sys.stderr)
            print("[提示] 这可能是由于 token 失效或未登录。请尝试添加 --login 参数，或提供 --server + --user + --password 重新登录。", file=sys.stderr)
        else:
            print(f"[错误] 获取禅道数据失败: {err_msg}", file=sys.stderr)
        return 1
```

Before the analyze loop:

```python
    run_id = args.id or args.project or args.product or "list"
    debug_bundle = build_debug_bundle(
        enabled=runtime_config.debug_bundle_enabled,
        base_dir=runtime_config.debug_bundle_dir,
        module=args.module,
        run_id=run_id,
        include_code=runtime_config.debug_include_code,
    )
    debug_bundle.write_config({
        "args": vars(args),
        "runtime_config": runtime_config.__dict__,
        "environment": {
            "LLM_AGENT": os.environ.get("LLM_AGENT", ""),
            "OPENAI_MODEL": os.environ.get("OPENAI_MODEL", ""),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            "CLAUDE_COMMAND": os.environ.get("CLAUDE_COMMAND", ""),
            "CLAUDE_PROMPT_VIA": os.environ.get("CLAUDE_PROMPT_VIA", ""),
            "ZENTAO_TOKEN": os.environ.get("ZENTAO_TOKEN", ""),
        },
    })
    debug_bundle.write_items(items)
```

Build AgentConfig:

```python
    agent_config = AgentConfig(**runtime_config.agent_config_dict())
```

Debug recorder:

```python
    def record_debug(kind, item, payload):
        if kind == "prompt":
            debug_bundle.write_prompt(item.id, payload)
        elif kind == "response":
            debug_bundle.write_response(item.id, payload)
```

Analyze call:

```python
        result = analyze(
            item,
            repo_path=repo_path,
            agent=runtime_config.agent,
            modified_files=modified_files,
            agent_config=agent_config,
            debug_recorder=record_debug,
        )
```

After summary:

```python
    debug_bundle.write_analysis_results(analysis_results)
    debug_bundle.write_documents(documents)
    debug_bundle.write_summary_path(summary_path)
```

Final output:

```python
    combined_output = {
        **base_result,
        "analysis": analysis_results,
        "documents": documents,
        "summary_report": summary_path,
        "debug_bundle": debug_bundle.path if debug_bundle.enabled and not debug_bundle.error else "",
        "debug_bundle_error": debug_bundle.error,
        "log_file": runtime_config.log_file,
    }
```

For non-analyze phase 1 output, keep current behavior and do not create debug bundle.

- [ ] **Step 5: Run focused tests**

Run: `python3 -m unittest tests.test_main_phase4 tests.test_main_phase3 -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add main.py tests/test_main_phase4.py
git commit -m "feat: wire phase4 cli logging and debug bundle"
```

---

## Task 8: Debug Bundle Scan Summary and Code Snapshot

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_phase4.py`

**Dependencies:** Task 7

- [ ] **Step 1: Add failing test for scan summary and include-code**

Append to `tests/test_main_phase4.py`:

```python
    def test_debug_bundle_writes_scan_summary_and_optional_code_context(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            debug_dir = os.path.join(td, "debug")
            argv = [
                "main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", debug_dir,
                "--debug-include-code",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()
            parsed = json.loads(stdout.getvalue())
            self.assertTrue(os.path.exists(os.path.join(parsed["debug_bundle"], "scan_summary.json")))
            self.assertTrue(os.path.exists(os.path.join(parsed["debug_bundle"], "code_context.json")))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_main_phase4 -v`

Expected: missing `scan_summary.json` or `code_context.json`.

- [ ] **Step 3: Add scan summary writing**

In `main.py`, after `modified_files` is calculated:

```python
    scan_summary = {
        "repo_path": repo_path,
        "incremental": incremental,
        "last_commit": last_commit or "",
        "modified_files": modified_files or [],
        "modified_file_count": len(modified_files or []),
        "max_files": 50,
        "max_lines_per_file": 200,
        "max_total_tokens": 8000,
    }
    debug_bundle.write_scan_summary(scan_summary)
    debug_bundle.write_code_context({
        "repo_path": repo_path,
        "items": [{"id": item.id, "keywords": item.keywords} for item in items],
        "modified_files": modified_files or [],
    })
```

This records scan boundaries without duplicating the full collector output. Full code snippets remain disabled unless `--debug-include-code` is set because `DebugBundle.write_code_context()` enforces that flag.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_main_phase4 -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add main.py tests/test_main_phase4.py
git commit -m "feat: record phase4 debug scan summary"
```

---

## Task 9: Documentation and SKILL.yaml

**Files:**
- Modify: `README.md`
- Modify: `SKILL.yaml`

**Dependencies:** Tasks 1-8

- [ ] **Step 1: Inspect current docs**

Run: `sed -n '1,260p' README.md`

Expected: current README content is visible so new sections can be added without deleting existing setup and phase 1-3 examples.

- [ ] **Step 2: Update README**

Add a section named `## 阶段四：Agent、日志与 Debug Bundle` with this content:

```markdown
## 阶段四：Agent、日志与 Debug Bundle

### Agent 选择

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent openai --model "$OPENAI_MODEL"
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent codex --model "$OPENAI_MODEL"
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent opencode
```

`openai` 和 `codex` 使用 OpenAI SDK 后端。需要设置：

```bash
export OPENAI_API_KEY="你的 OpenAI API Key"
export OPENAI_MODEL="模型名"
export OPENAI_BASE_URL="可选的兼容 OpenAI 接口地址"
```

`claude` 使用本机 Claude CLI。默认命令是 `claude`，默认通过 stdin 传入 prompt：

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --claude-command claude --claude-prompt-via arg
```

`opencode` 是预留接口，当前返回 `not_implemented`，不会伪造成功。

### 日志

运行日志默认写入 stderr，stdout 保持最终 JSON：

```bash
python3 main.py --module requirement --id 5939 --analyze --quiet
python3 main.py --module requirement --id 5939 --analyze --verbose
python3 main.py --module requirement --id 5939 --analyze --log-file logs/run.jsonl
```

日志会脱敏 token、password、API key、Authorization 和 Bearer token。

### Debug Bundle

`--analyze` 时 debug bundle 默认开启，默认写入：

```text
debug_runs/{timestamp}-{module}-{id_or_project}/
```

其中包含脱敏配置、禅道条目摘要、扫描摘要、prompt、Agent response、分析结果、文档路径、summary 路径和本次 JSONL 日志引用。默认不保存完整代码片段。

```bash
python3 main.py --module requirement --id 5939 --analyze --debug-bundle-dir debug_runs
python3 main.py --module requirement --id 5939 --analyze --no-debug-bundle
python3 main.py --module requirement --id 5939 --analyze --debug-include-code
```

Debug bundle 会默认脱敏，但仍可能包含业务上下文、prompt 和模型响应，应按项目敏感资料管理。
```

- [ ] **Step 3: Update `SKILL.yaml` inputs**

Add these inputs under existing `inputs`:

```yaml
  - name: agent
    description: Agent 类型（openai、codex、claude、opencode）
    type: string
    default: codex
  - name: model
    description: OpenAI/Codex 模型名
    type: string
  - name: agent_timeout
    description: Agent 调用超时时间，单位秒
    type: number
    default: 120
  - name: claude_command
    description: Claude CLI 命令
    type: string
    default: claude
  - name: claude_prompt_via
    description: Claude prompt 传递方式（stdin 或 arg）
    type: string
    default: stdin
  - name: verbose
    description: 输出详细 stderr 日志
    type: boolean
    default: false
  - name: quiet
    description: 抑制进度日志，stdout 保持最终 JSON
    type: boolean
    default: false
  - name: log_file
    description: JSONL 运行日志路径
    type: string
  - name: debug_bundle_dir
    description: Debug bundle 输出目录
    type: string
  - name: no_debug_bundle
    description: 关闭默认 debug bundle
    type: boolean
    default: false
  - name: debug_include_code
    description: 在 debug bundle 中保存代码上下文快照
    type: boolean
    default: false
```

- [ ] **Step 4: Check docs for required terms**

Run:

```bash
rg -n "openai|codex|claude|opencode|debug bundle|--quiet|--verbose|--log-file|SKILL.yaml" README.md SKILL.yaml
```

Expected: all phase 4 terms appear in README or `SKILL.yaml`.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md SKILL.yaml
git commit -m "docs: document phase4 agent options"
```

---

## Task 10: Full Regression and Acceptance Verification

**Files:**
- No source files expected unless verification exposes a concrete bug.

**Dependencies:** Tasks 1-9

- [ ] **Step 1: Run focused phase 4 tests**

Run:

```bash
python3 -m unittest tests.test_agent_client tests.test_run_logger tests.test_debug_bundle tests.test_app_config tests.test_main_phase4 tests.test_llm_client tests.test_analyzer -v
```

Expected: all tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python3 -m unittest discover -v tests
```

Expected: all tests pass. Existing ResourceWarning from older tests may remain as warnings only; failures must be fixed.

- [ ] **Step 3: Verify CLI help exposes phase 4 options**

Run:

```bash
python3 main.py --help
```

Expected output contains:

```text
--agent
--model
--agent-timeout
--claude-command
--claude-prompt-via
--claude-extra-arg
--verbose
--quiet
--log-file
--no-debug-bundle
--debug-bundle-dir
--debug-include-code
```

- [ ] **Step 4: Verify stdout remains JSON in quiet mode**

Run with mocked or available Zentao credentials only when local environment is configured:

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent opencode --quiet
```

Expected: stdout is a single JSON object. The `analysis[0].error` field reports OpenCode is not implemented, and `documents` still contains a diagnostic document path.

- [ ] **Step 5: Verify dirty worktree scope**

Run:

```bash
git status --short
```

Expected: only intentional phase 4 files are modified or staged. Ignore unrelated `__pycache__` changes and do not add them.

- [ ] **Step 6: Final commit if verification required fixes**

If verification required code fixes, commit only those files:

```bash
git add <fixed-files>
git commit -m "fix: complete phase4 verification"
```

If no fixes were needed, no extra commit is required.

---

## Self-Review Checklist

- [x] SPEC coverage: AgentClient, OpenAI/Codex, Claude CLI, OpenCode reserved, structured AgentResult fallback, JSON parse fallback, logs, JSONL, debug bundle default-on, CLI/env config, README, `SKILL.yaml`, and regression tests are mapped to tasks.
- [x] Placeholder scan: no task relies on missing behavior names without code or commands; OpenCode `not_implemented` is an intentional product behavior from the SPEC.
- [x] Type consistency: `RuntimeConfig.agent_config_dict()` maps directly into `AgentConfig`; `llm_client.call_llm()` preserves the legacy dict shape used by `analyzer.py`; debug recorder uses `(kind, item, payload)` consistently.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-21-phase4-agent-ux-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
