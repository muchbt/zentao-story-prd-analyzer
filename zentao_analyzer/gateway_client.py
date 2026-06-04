import dataclasses
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

from .run_logger import redact_sensitive


GATEWAY_ERROR_MAP = {
    "adapter_not_found": "config",
    "unsupported_agent": "config",
    "unsupported_model": "config",
    "unsupported_permission_policy": "config",
    "sandbox_unavailable": "config",
    "invalid_request": "config",
    "timeout": "timeout",
    "idle_timeout": "timeout",
    "cancelled": "timeout",
    "protocol_error": "runtime",
    "adapter_spawn_failed": "runtime",
    "internal_error": "runtime",
    "unsupported_session_recovery": "runtime",
    "incompatible_session": "runtime",
    "session_cleanup_failed": "runtime",
    "invalid_session_state": "runtime",
    "agent_empty_response": "gateway_empty_response",
}


@dataclasses.dataclass
class GatewayConfig:
    gateway_agent: str = ""
    gateway_bin: str = ""
    permission_policy: str = "best-effort-read-only"
    idle_timeout: int = 300
    timeout: int = 900
    model: str = ""


@dataclasses.dataclass
class GatewayResult:
    ok: bool
    text: str = ""
    session_ref: str = ""
    error: str = ""
    error_kind: str = ""
    error_code: str = ""
    stop_reason: str = ""
    events: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    transport_error: str = ""
    duration_ms: int = 0


def resolve_gateway_command(config: GatewayConfig) -> Optional[str]:
    if config.gateway_bin:
        return config.gateway_bin
    env_bin = os.environ.get("ACP_AGENT_GATEWAY_BIN", "")
    if env_bin:
        return env_bin
    found = shutil.which("acp-agent-gateway")
    if found:
        return found
    return None


def _map_gateway_error(error_code: str) -> str:
    return GATEWAY_ERROR_MAP.get(error_code, "runtime")


GATEWAY_SUBPROCESS_TIMEOUT_GRACE = 30  # extra seconds for Gateway to flush its final JSON after timeoutMs expires
GATEWAY_EVENT_SAFE_FIELDS = {
    "type", "sessionRef", "session_ref", "agent", "turnId",
    "status", "errorCode", "error_code", "error", "message",
    "timestamp", "durationMs", "inputTokens", "outputTokens",
    "totalTokens", "model", "apiVersion", "version",
}


def _sanitize_gateway_event(event: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    safe: Dict[str, Any] = {}
    for key in event:
        if key in GATEWAY_EVENT_SAFE_FIELDS:
            safe[key] = event[key]
    if "_parse_error" in event:
        safe["_parse_error"] = True
        safe["raw"] = event.get("raw", "")
    return safe


def _sanitize_gateway_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_sanitize_gateway_event(e) for e in events]


def _parse_gateway_stderr(stderr_text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not stderr_text:
        return events
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append({"raw": line, "_parse_error": True})
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def call_gateway_start_session(
    prompt: str,
    cwd: str,
    config: GatewayConfig,
    extra_env: Optional[Dict[str, str]] = None,
) -> GatewayResult:
    started = _now_ms()
    gateway_exe = resolve_gateway_command(config)
    if not gateway_exe:
        return GatewayResult(
            ok=False,
            error="acp-agent-gateway 命令未找到。请设置 ACP_AGENT_GATEWAY_BIN 环境变量或将其放入 PATH。",
            error_kind="config",
            duration_ms=_now_ms() - started,
        )
    cmd_parts = shlex.split(gateway_exe)
    cmd = cmd_parts + [
        "start-session",
        "--agent", config.gateway_agent,
        "--cwd", cwd,
    ]
    request_data = {
        "apiVersion": "v1",
        "prompt": prompt,
        "permissionPolicy": config.permission_policy,
        "timeoutMs": config.timeout * 1000,
        "idleTimeoutMs": config.idle_timeout * 1000,
    }
    if config.model:
        request_data["model"] = config.model
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="gateway-request-",
            encoding="utf-8",
            delete=False,
        ) as f:
            json.dump(request_data, f)
            request_path = f.name
        cmd.extend(["--input", request_path])
        merge_env = os.environ.copy()
        if extra_env:
            merge_env.update(extra_env)
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout + GATEWAY_SUBPROCESS_TIMEOUT_GRACE,
            cwd=cwd,
            shell=False,
            env=merge_env,
        )
    except FileNotFoundError as exc:
        return GatewayResult(
            ok=False,
            error=f"acp-agent-gateway 命令不存在: {exc}",
            error_kind="config",
            duration_ms=_now_ms() - started,
        )
    except subprocess.TimeoutExpired as exc:
        return GatewayResult(
            ok=False,
            error=f"acp-agent-gateway start-session 超时: {exc}",
            error_kind="timeout",
            duration_ms=_now_ms() - started,
        )
    except Exception as exc:
        return GatewayResult(
            ok=False,
            error=redact_sensitive(str(exc)),
            error_kind="runtime",
            duration_ms=_now_ms() - started,
        )
    finally:
        if "request_path" in dir():
            try:
                os.unlink(request_path)
            except OSError:
                pass

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    raw_events = _parse_gateway_stderr(stderr)
    events = _sanitize_gateway_events(raw_events)
    session_ref = ""
    for event in events:
        ref = event.get("sessionRef", "") or event.get("session_ref", "")
        if ref and not session_ref:
            session_ref = ref

    if not stdout.strip():
        return GatewayResult(
            ok=False,
            error="acp-agent-gateway 返回空 stdout",
            error_kind="runtime",
            transport_error="gateway_empty_stdout",
            session_ref=session_ref,
            events=events,
            duration_ms=_now_ms() - started,
        )

    try:
        result_json = json.loads(stdout.strip())
    except json.JSONDecodeError:
        return GatewayResult(
            ok=False,
            error="acp-agent-gateway stdout 不是有效 JSON",
            error_kind="runtime",
            transport_error="gateway_invalid_stdout_json",
            session_ref=session_ref,
            events=events,
            duration_ms=_now_ms() - started,
        )

    if not isinstance(result_json, dict):
        return GatewayResult(
            ok=False,
            error="acp-agent-gateway stdout 不是 JSON 对象",
            error_kind="runtime",
            transport_error="gateway_invalid_stdout_json",
            session_ref=session_ref,
            events=events,
            duration_ms=_now_ms() - started,
        )

    if session_ref:
        pass
    if not session_ref:
        session_ref = result_json.get("sessionRef", "") or result_json.get("session_ref", "") or ""

    status = result_json.get("status", "")
    if status == "completed":
        text = result_json.get("text", "")
        stop_reason = result_json.get("stopReason", "") or result_json.get("stop_reason", "")
        if stop_reason == "empty_response" or not text:
            error_code = "agent_empty_response"
            return GatewayResult(
                ok=False,
                text="",
                stop_reason=stop_reason or "empty_response",
                error_code=error_code,
                error="Agent completed but returned no final text via ACP",
                error_kind=_map_gateway_error(error_code),
                session_ref=session_ref,
                events=events,
                duration_ms=_now_ms() - started,
            )
        return GatewayResult(
            ok=True,
            text=text,
            session_ref=session_ref,
            stop_reason=stop_reason,
            events=events,
            duration_ms=_now_ms() - started,
        )

    error_code = result_json.get("errorCode", "") or result_json.get("error_code", "")
    error_message = result_json.get("error", "") or "网关返回未完成状态"
    return GatewayResult(
        ok=False,
        error=error_message,
        error_kind=_map_gateway_error(error_code),
        error_code=error_code,
        session_ref=session_ref,
        events=events,
        duration_ms=_now_ms() - started,
    )
