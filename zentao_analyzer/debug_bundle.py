import dataclasses
import datetime
import json
import os
import re
from typing import Any, Dict, Iterable, List

from .run_logger import redact_sensitive


def _safe_part(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fff]+", "_", str(value or "unknown"))
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


def _to_plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    return value


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
                json.dump(redact_sensitive(_to_plain(data)), f, ensure_ascii=False, indent=2)
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

    def write_code_evidence_locations(self, items: List[Dict[str, Any]]) -> None:
        self._write_json("code_evidence_locations.json", {"items": items})

    def write_rejected_clues(self, rejected_clues: List[Any]) -> None:
        self._write_json("rejected_clues.json", rejected_clues)


def build_debug_bundle(enabled: bool, base_dir: str = "", module: str = "", run_id: str = "", timestamp: str = "", include_code: bool = False) -> DebugBundle:
    if not enabled:
        return DebugBundle(enabled=False, include_code=include_code)
    stamp = timestamp or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = base_dir or "debug_runs"
    path = os.path.join(root, f"{_safe_part(stamp)}-{_safe_part(module)}-{_safe_part(run_id)}")
    return DebugBundle(enabled=True, path=path, include_code=include_code)
