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
    value = re.sub(r"Bearer\s+[^\s,;]+", "Bearer ***", value, flags=re.IGNORECASE)
    value = re.sub(r"(password|token|api_key|authorization)=([^\s,;]+)", r"\1=***", value, flags=re.IGNORECASE)
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
        self._log_files: list = []
        if log_file:
            self.add_log_file(log_file)

    def add_log_file(self, path: str) -> None:
        try:
            parent = os.path.dirname(os.path.abspath(path))
            if parent:
                os.makedirs(parent, exist_ok=True)
        except OSError:
            print(f"[warning] 无法创建日志目录: {path}", file=sys.stderr)
            return
        if path not in self._log_files:
            self._log_files.append(path)

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
        failed = []
        for path in self._log_files:
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except OSError:
                print(f"[warning] 日志写入失败，已停用: {path}", file=sys.stderr)
                failed.append(path)
        for path in failed:
            self._log_files.remove(path)
