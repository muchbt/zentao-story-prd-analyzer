import json
import os
import sys


MODE = os.environ.get("FAKE_GATEWAY_MODE", "completed")
ERROR_CODE = os.environ.get("FAKE_GATEWAY_ERROR_CODE", "internal_error")
ERROR_MESSAGE = os.environ.get("FAKE_GATEWAY_ERROR_MESSAGE", "simulated gateway failure")
STDERR_EVENTS = os.environ.get("FAKE_GATEWAY_STDERR_EVENTS", "true")
SESSION_REF = os.environ.get("FAKE_GATEWAY_SESSION_REF", "session-abc123")
TEXT_OUTPUT = os.environ.get("FAKE_GATEWAY_TEXT_OUTPUT", '{"conclusion":"已完成","evidence":["src/a.c"],"recommendations":["建议1"],"verification":["验证1"],"priority":"高","confidence":"中"}')


def _emit_stderr_events():
    events = [
        {"type": "session.created", "sessionRef": SESSION_REF, "timestamp": "2026-06-03T10:00:00Z"},
        {"type": "agent.connected", "agent": "opencode", "timestamp": "2026-06-03T10:00:01Z"},
        {"type": "turn.started", "turnId": "turn-1", "timestamp": "2026-06-03T10:00:02Z"},
        {"type": "tool.used", "tool": "Read", "args": {"path": "src/a.c"}, "timestamp": "2026-06-03T10:00:05Z"},
        {"type": "turn.completed", "turnId": "turn-1", "timestamp": "2026-06-03T10:00:10Z"},
    ]
    for event in events:
        print(json.dumps(event), file=sys.stderr)


def main():
    if not sys.argv[1:]:
        print(json.dumps({"error": "Missing arguments"}), file=sys.stderr)
        sys.exit(1)

    if MODE == "completed":
        _emit_stderr_events()
        result = {
            "apiVersion": "v1",
            "sessionRef": SESSION_REF,
            "status": "completed",
            "text": TEXT_OUTPUT,
            "usage": {"inputTokens": 500, "outputTokens": 300},
        }
        print(json.dumps(result))
        return

    if MODE == "failed":
        _emit_stderr_events()
        result = {
            "apiVersion": "v1",
            "sessionRef": SESSION_REF,
            "status": "failed",
            "errorCode": ERROR_CODE,
            "error": ERROR_MESSAGE,
        }
        print(json.dumps(result))
        sys.exit(1)

    if MODE == "invalid_stdout":
        _emit_stderr_events()
        print("not json at all -- some broken output")
        return

    if MODE == "completed_no_events":
        result = {
            "apiVersion": "v1",
            "sessionRef": SESSION_REF,
            "status": "completed",
            "text": TEXT_OUTPUT,
        }
        print(json.dumps(result))
        return

    if MODE == "completed_bad_json":
        _emit_stderr_events()
        result = {
            "apiVersion": "v1",
            "sessionRef": SESSION_REF,
            "status": "completed",
            "text": '{"key": "unclosed',
        }
        print(json.dumps(result))
        return

    if MODE == "timeout":
        _emit_stderr_events()
        result = {
            "apiVersion": "v1",
            "sessionRef": SESSION_REF,
            "status": "failed",
            "errorCode": "timeout",
            "error": "request timed out",
        }
        print(json.dumps(result))
        return

    if MODE == "completed_with_rich_text":
        _emit_stderr_events()
        text = json.dumps({
            "conclusion": "已完成",
            "evidence": ["src/a.c"],
            "recommendations": ["建议1"],
            "verification": ["验证1"],
            "priority": "高",
            "confidence": "中",
            "requirement_interpretation": {
                "summary": "需求总结",
                "scope": [{"text": "适用范围", "source": "requirement"}],
                "terms": [],
                "rules": [],
                "scenarios": [],
                "pending_confirmations": [],
            },
            "code_impact": {
                "related_locations": [
                    {"component": "auth", "path": "src/a.c", "line_start": 1, "line_end": 10, "symbol": "login", "reason": "核心逻辑", "role": "main"}
                ],
                "impact_notes": ["影响认证流程"],
            },
            "requirement_points": [
                {"id": "RP-001", "description": "用户登录", "status": "完成", "reason": "已实现", "gaps": [], "evidence": [{"path": "src/a.c", "line_start": 1, "line_end": 10, "symbol": "login"}]}
            ],
            "role_evidence_statuses": [
                {"role": "main", "status": "found", "searched_for": ["login"], "explanation": "找到login函数"}
            ],
            "protocol_traces": [],
        })
        result = {
            "apiVersion": "v1",
            "sessionRef": SESSION_REF,
            "status": "completed",
            "text": text,
        }
        print(json.dumps(result))
        return

    print(json.dumps({"error": f"unknown mode: {MODE}"}), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
