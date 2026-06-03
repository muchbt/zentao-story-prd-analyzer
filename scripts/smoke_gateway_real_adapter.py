#!/usr/bin/env python3
"""Manual smoke test for the real ACP Agent Gateway backend.

This script intentionally calls a real Gateway adapter/model. It avoids Zentao
dependencies by using Provided Requirement mode and a temporary target repo.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(cmd: List[str], env: Dict[str, str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=None,
        shell=False,
    )


def _write_fixture_repo(path: pathlib.Path) -> None:
    src = path / "src"
    tests = path / "tests"
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    (src / "seatbelt_status.py").write_text(
        "\n".join(
            [
                "from dataclasses import dataclass",
                "",
                "",
                "@dataclass(frozen=True)",
                "class SeatbeltStatus:",
                "    locked: bool",
                "    occupant_present: bool",
                "",
                "",
                "def should_warn(status: SeatbeltStatus) -> bool:",
                "    if not status.occupant_present:",
                "        return False",
                "    return not status.locked",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tests / "test_seatbelt_status.py").write_text(
        "\n".join(
            [
                "from src.seatbelt_status import SeatbeltStatus, should_warn",
                "",
                "",
                "def test_warns_when_occupied_and_unlocked():",
                "    assert should_warn(SeatbeltStatus(locked=False, occupant_present=True))",
                "",
                "",
                "def test_no_warning_when_empty():",
                "    assert not should_warn(SeatbeltStatus(locked=False, occupant_present=False))",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_requirement(path: pathlib.Path) -> None:
    path.write_text(
        "\n".join(
            [
                "车辆座椅安全带提醒功能：",
                "1. 当座椅有乘员且安全带未锁止时，应触发提醒。",
                "2. 当座椅无乘员时，不应触发提醒。",
                "3. 当座椅有乘员且安全带已锁止时，不应触发提醒。",
                "请分析当前代码是否已有对应实现，并引用代码证据。",
            ]
        ),
        encoding="utf-8",
    )


def _load_json(path: pathlib.Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_one(root: pathlib.Path, pattern: str) -> pathlib.Path:
    matches = list(root.glob(pattern))
    if not matches:
        raise AssertionError(f"missing expected file matching {pattern} under {root}")
    if len(matches) > 1:
        print(f"[warn] multiple matches for {pattern}; using {matches[0]}", file=sys.stderr)
    return matches[0]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _validate_outputs(workdir: pathlib.Path, stdout_path: pathlib.Path) -> Dict[str, Any]:
    stdout_json = _load_json(stdout_path)
    analyses = stdout_json.get("analysis") or []
    _assert(analyses, "stdout JSON has no analysis items")
    analysis = analyses[0]
    _assert(not analysis.get("error"), f"analysis failed: {analysis.get('error')}")

    summary_path = pathlib.Path(stdout_json.get("summary_report", ""))
    _assert(summary_path.is_file(), f"summary_report not found: {summary_path}")
    summary = _load_json(summary_path)
    items = summary.get("items") if isinstance(summary, dict) else summary
    _assert(isinstance(items, list) and items, "summary has no items")
    item = items[0]

    session_ref = item.get("gateway_session_ref", "")
    _assert(session_ref, "summary item has no gateway_session_ref")
    _assert(item.get("gateway_backend_agent"), "summary item has no gateway_backend_agent")

    document_path = pathlib.Path(item.get("document_path", ""))
    _assert(document_path.is_file(), f"document_path not found: {document_path}")
    document_text = document_path.read_text(encoding="utf-8")
    _assert(session_ref not in document_text, "PRD document leaked gateway_session_ref")

    debug_bundle = pathlib.Path(item.get("debug_bundle", ""))
    _assert(debug_bundle.is_dir(), f"debug_bundle not found: {debug_bundle}")
    events_path = _find_one(debug_bundle, "gateway_events/*.json")
    events = _load_json(events_path)
    events_text = json.dumps(events, ensure_ascii=False)
    _assert("src/seatbelt_status.py" not in events_text, "gateway events leaked tool path")
    _assert('"args"' not in events_text, "gateway events leaked tool args")

    diagnostics_path = _find_one(debug_bundle, "gateway_diagnostics/*.json")
    diagnostics = _load_json(diagnostics_path)
    _assert(
        diagnostics.get("gateway_session_ref") == session_ref,
        "gateway diagnostics session ref does not match summary",
    )

    return {
        "summary_report": str(summary_path),
        "document_path": str(document_path),
        "debug_bundle": str(debug_bundle),
        "gateway_session_ref": session_ref,
        "analysis_conclusion": analysis.get("conclusion", ""),
        "analysis_confidence": analysis.get("confidence", ""),
        "workdir": str(workdir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real Gateway adapter smoke for zentao-story-prd-analyzer.")
    parser.add_argument("--gateway-agent", required=True, choices=["opencode", "claude", "codex"])
    parser.add_argument("--gateway-bin", help="Gateway CLI command. Defaults to ACP_AGENT_GATEWAY_BIN or PATH.")
    parser.add_argument("--model", help="Model passed to ACP Agent Gateway.")
    parser.add_argument("--agent-timeout", type=int, default=900, help="Analyzer/Gateway timeout in seconds.")
    parser.add_argument("--gateway-idle-timeout", type=int, default=300, help="Gateway idle timeout in seconds.")
    parser.add_argument(
        "--gateway-permission-policy",
        default="best-effort-read-only",
        choices=["best-effort-read-only", "strict-read-only"],
    )
    parser.add_argument("--workdir", help="Use an existing work directory instead of a temp dir.")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary work directory after the smoke.")
    args = parser.parse_args()

    gateway_cmd = args.gateway_bin or os.environ.get("ACP_AGENT_GATEWAY_BIN") or shutil.which("acp-agent-gateway")
    if not gateway_cmd:
        print("[error] acp-agent-gateway not found. Set --gateway-bin or ACP_AGENT_GATEWAY_BIN.", file=sys.stderr)
        return 2

    temp_dir = None
    if args.workdir:
        workdir = pathlib.Path(args.workdir).resolve()
        workdir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="zentao-gateway-smoke-")
        workdir = pathlib.Path(temp_dir.name)

    target_repo = workdir / "target-repo"
    output_root = workdir / "out"
    debug_root = workdir / "debug"
    requirement_file = workdir / "requirement.txt"
    stdout_path = workdir / "stdout.json"
    stderr_path = workdir / "stderr.log"

    try:
        if target_repo.exists():
            shutil.rmtree(target_repo)
        target_repo.mkdir(parents=True)
        _write_fixture_repo(target_repo)
        _write_requirement(requirement_file)

        env = os.environ.copy()
        env["ACP_AGENT_GATEWAY_BIN"] = gateway_cmd

        cmd = [
            sys.executable,
            "-m",
            "zentao_analyzer.main",
            "--module",
            "requirement",
            "--id",
            "gateway-smoke-001",
            "--title",
            "Gateway real adapter smoke",
            "--requirement-file",
            str(requirement_file),
            "--analyze",
            "--repo-path",
            str(target_repo),
            "--agent",
            "gateway",
            "--gateway-agent",
            args.gateway_agent,
            "--gateway-permission-policy",
            args.gateway_permission_policy,
            "--gateway-idle-timeout",
            str(args.gateway_idle_timeout),
            "--agent-timeout",
            str(args.agent_timeout),
            "--output-root",
            str(output_root),
            "--debug-bundle-dir",
            str(debug_root),
            "--quiet",
        ]
        if args.model:
            cmd.extend(["--model", args.model])

        completed = _run(cmd, env=env, cwd=REPO_ROOT)
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr)
            print(f"[error] analyzer exited with {completed.returncode}", file=sys.stderr)
            print(f"[info] workdir: {workdir}", file=sys.stderr)
            return completed.returncode

        result = _validate_outputs(workdir, stdout_path)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[error] smoke failed: {exc}", file=sys.stderr)
        print(f"[info] workdir: {workdir}", file=sys.stderr)
        return 1
    finally:
        if temp_dir is not None and not args.keep:
            temp_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
