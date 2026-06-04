import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.agent_client import AgentClient, AgentConfig, extract_json_object, _extract_markdown_json, _repair_json_quotes, _parse_opencode_events

FAKE_GATEWAY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "fake_gateway.py",
)


class TestAgentClientCore(unittest.TestCase):
    def test_extract_json_direct_markdown_and_embedded(self):
        self.assertEqual(extract_json_object('{"conclusion":"完成"}'), {"conclusion": "完成"})
        self.assertEqual(extract_json_object('```json\n{"conclusion":"完成"}\n```'), {"conclusion": "完成"})
        self.assertEqual(extract_json_object('prefix {"conclusion":"完成"} suffix'), {"conclusion": "完成"})

    def test_extract_markdown_json_nested_braces(self):
        text = '```json\n{"key": {"nested": true}, "list": [1, 2]}\n```'
        result = extract_json_object(text)
        self.assertEqual(result, {"key": {"nested": True}, "list": [1, 2]})

    def test_extract_markdown_json_with_prefix_text(self):
        text = 'Based on my analysis:\n\n```json\n{"conclusion":"完成","evidence":[]}\n```'
        result = extract_json_object(text)
        self.assertEqual(result["conclusion"], "完成")

    def test_extract_markdown_json_incomplete_code_fence(self):
        text = '```json\n{"key": "value"}\n'
        result = extract_json_object(text)
        self.assertEqual(result, {"key": "value"})

    def test_repair_json_quotes_in_string_values(self):
        broken = '{"reason": "覆盖了"对地短路"故障场景"}'
        result = extract_json_object(broken)
        self.assertEqual(result["reason"], '覆盖了"对地短路"故障场景')

    def test_repair_json_quotes_multiple_embedded(self):
        broken = '{"a": "他说"你好"然后离开", "b": "正常值"}'
        result = extract_json_object(broken)
        self.assertIn("你好", result["a"])
        self.assertEqual(result["b"], "正常值")

    def test_repair_json_quotes_in_markdown_response(self):
        broken = 'Based on analysis:\n\n```json\n{"requirement_points": [{"description": "TCAM 应记录"备份电池"的 DTC", "status": "完成"}]}\n```'
        result = extract_json_object(broken)
        self.assertEqual(len(result["requirement_points"]), 1)
        self.assertIn("备份电池", result["requirement_points"][0]["description"])

    def test_valid_json_not_modified_by_repair(self):
        valid = '{"key": "value without issues", "num": 42}'
        result = extract_json_object(valid)
        self.assertEqual(result, {"key": "value without issues", "num": 42})

    def test_openai_agent_is_not_supported(self):
        result = AgentClient(AgentConfig(agent="openai")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertIn("未识别 agent", result.error)


def _subprocess_completed(stdout="", stderr="", returncode=0):
    completed = MagicMock()
    completed.stdout = stdout
    completed.stderr = stderr
    completed.returncode = returncode
    return completed


class TestAgentClientClaude(unittest.TestCase):
    def test_claude_stdin_success_passes_model(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            client = AgentClient(AgentConfig(agent="claude", command="claude", model="sonnet", prompt_via="stdin", timeout=5, cwd="/repo"))
            result = client.call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertIn("--model", cmd)
        self.assertIn("sonnet", cmd)
        self.assertIn("-p", cmd)
        self.assertIn("--output-format", cmd)
        self.assertIn("json", cmd)
        self.assertIn("--tools", cmd)
        self.assertIn("Read,Grep,Glob", cmd)
        self.assertNotIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(mock_run.call_args.kwargs["input"], "prompt")
        self.assertEqual(mock_run.call_args.kwargs["cwd"], "/repo")

    def test_claude_arg_success(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="claude", prompt_via="arg", extra_args=["--foo"], timeout=5)).call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertIn("--output-format", cmd)
        self.assertIn("json", cmd)
        self.assertIn("--foo", cmd)
        self.assertIn("-p", cmd)
        self.assertEqual(cmd[-1], "prompt")

    def test_claude_json_envelope_success_extracts_result(self):
        inner = json.dumps({"conclusion": "完成", "evidence": [], "recommendations": []})
        envelope = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": inner})
        completed = _subprocess_completed(stdout=envelope, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "完成")

    def test_claude_json_envelope_error_returns_runtime(self):
        envelope = json.dumps({"type": "result", "subtype": "error", "is_error": True, "result": "Something went wrong"})
        completed = _subprocess_completed(stdout=envelope, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "runtime")
        self.assertIn("Something went wrong", result.error)

    def test_claude_envelope_result_empty_text_returns_parse_empty(self):
        envelope = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "All key aspects have been investigated."})
        completed = _subprocess_completed(stdout=envelope, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse_empty")

    def test_parse_empty_text_without_braces(self):
        completed = _subprocess_completed(stdout="All key aspects have been investigated. Here is the comprehensive analysis.", stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse_empty")

    def test_claude_non_envelope_json_falls_back_to_direct_parse(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成","evidence":[]}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "完成")


class TestAgentClientCodex(unittest.TestCase):
    def test_codex_exec_success_uses_stdin_model_and_cwd(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="codex", command="codex", model="gpt-5", timeout=5, cwd="/repo")).call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[:4], ["codex", "exec", "-C", "/repo"])
        self.assertIn("--sandbox", cmd)
        self.assertIn("read-only", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("-m", cmd)
        self.assertIn("gpt-5", cmd)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertEqual(mock_run.call_args.kwargs["input"], "prompt")
        self.assertEqual(mock_run.call_args.kwargs["cwd"], "/repo")

    def test_codex_missing_command_is_config_error(self):
        with patch("zentao_analyzer.agent_client.subprocess.run", side_effect=FileNotFoundError("missing")):
            result = AgentClient(AgentConfig(agent="codex", command="missing")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")

    def test_codex_jsonl_extracts_agent_message(self):
        inner = json.dumps({"conclusion": "完成", "evidence": []})
        events = [
            '{"type":"thread.started","thread_id":"1"}',
            '{"type":"item.in_progress","item":{"type":"agent_message","text":"thinking"}}',
            '{"type":"item.completed","item":{"type":"agent_message","text":' + json.dumps(inner) + '}}',
        ]
        completed = _subprocess_completed(stdout="\n".join(events), stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="codex")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "完成")

    def test_codex_jsonl_no_agent_message_returns_failure(self):
        events = [
            '{"type":"thread.started","thread_id":"1"}',
            '{"type":"item.completed","item":{"type":"tool_call","text":"running tool"}}',
        ]
        completed = _subprocess_completed(stdout="\n".join(events), stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="codex")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse_empty")

    def test_codex_single_line_jsonl_event_extracts_agent_message(self):
        inner = json.dumps({"conclusion": "完成", "evidence": []})
        event = '{"type":"item.completed","item":{"type":"agent_message","text":' + json.dumps(inner) + '}}'
        completed = _subprocess_completed(stdout=event, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="codex")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "完成")

    def test_codex_single_line_json_falls_back_to_direct_parse(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="codex")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "完成")


class TestOpenCodeEventParsing(unittest.TestCase):
    def test_single_text_event(self):
        events = '{"type":"text","part":{"text":"Hello world"}}'
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "Hello world")
        self.assertEqual(error, "")

    def test_multiple_text_events_concatenated(self):
        events = '\n'.join([
            '{"type":"text","part":{"text":"Part 1"}}',
            '{"type":"text","part":{"text":"Part 2"}}',
        ])
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "Part 1Part 2")
        self.assertEqual(error, "")

    def test_error_event_detected(self):
        events = '{"type":"error","error":{"data":{"message":"something went wrong"}}}'
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "")
        self.assertIn("something went wrong", error)

    def test_error_event_flat_message(self):
        events = '{"type":"error","error":{"message":"flat error"}}'
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "")
        self.assertEqual(error, "flat error")

    def test_mixed_events_skip_non_text(self):
        events = '\n'.join([
            '{"type":"step_start","step":{"name":"search"}}',
            '{"type":"text","part":{"text":"analysis result"}}',
            '{"type":"step_finish","step":{"name":"search"}}',
            '{"type":"tool_use","tool":{"name":"Read"}}',
            '{"type":"reasoning","content":"thinking..."}',
        ])
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "analysis result")
        self.assertEqual(error, "")

    def test_empty_output_not_event_stream(self):
        text, error, is_stream = _parse_opencode_events("")
        self.assertFalse(is_stream)
        self.assertEqual(text, "")
        self.assertEqual(error, "")

    def test_plain_text_not_event_stream(self):
        text, error, is_stream = _parse_opencode_events("just some plain text output")
        self.assertFalse(is_stream)
        self.assertEqual(text, "")
        self.assertEqual(error, "")

    def test_non_json_lines_skipped(self):
        events = '\n'.join([
            "some garbage line",
            '{"type":"text","part":{"text":"valid"}}',
            "",
            "more garbage",
        ])
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "valid")

    def test_no_text_events_in_stream(self):
        events = '\n'.join([
            '{"type":"step_start","step":{"name":"search"}}',
            '{"type":"tool_use","tool":{"name":"Read"}}',
            '{"type":"step_finish","step":{"name":"search"}}',
        ])
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "")
        self.assertEqual(error, "")

    def test_error_and_text_both_present(self):
        events = '\n'.join([
            '{"type":"text","part":{"text":"partial result"}}',
            '{"type":"error","error":{"data":{"message":"fatal error"}}}',
        ])
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "partial result")
        self.assertIn("fatal error", error)

    def test_multiple_error_events_concatenated(self):
        events = '\n'.join([
            '{"type":"error","error":{"data":{"message":"first error"}}}',
            '{"type":"error","error":{"data":{"message":"second error"}}}',
        ])
        text, error, is_stream = _parse_opencode_events(events)
        self.assertTrue(is_stream)
        self.assertEqual(text, "")
        self.assertIn("first error", error)
        self.assertIn("second error", error)


class TestAgentClientOpenCode(unittest.TestCase):
    def test_opencode_success_with_event_stream(self):
        events = '\n'.join([
            '{"type":"step_start","step":{"name":"search"}}',
            '{"type":"text","part":{"text":"{\\"conclusion\\":\\"已定位\\"}"}}',
            '{"type":"step_finish","step":{"name":"search"}}',
        ])
        completed = _subprocess_completed(stdout=events, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="opencode", command="opencode", model="model-a", timeout=5, cwd="/repo")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "已定位")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[:2], ["opencode", "run"])
        self.assertIn("--format", cmd)
        self.assertIn("json", cmd)
        self.assertIn("--dir", cmd)
        self.assertIn("/repo", cmd)
        self.assertIn("--model", cmd)
        self.assertIn("model-a", cmd)
        self.assertNotIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(cmd[-1], "prompt")

    def test_opencode_error_event_returns_failure(self):
        events = '{"type":"error","error":{"data":{"message":"API key invalid"}}}'
        completed = _subprocess_completed(stdout=events, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="opencode")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "runtime")
        self.assertIn("API key invalid", result.error)

    def test_opencode_event_stream_no_text_returns_parse_empty(self):
        events = '\n'.join([
            '{"type":"step_start","step":{"name":"search"}}',
            '{"type":"tool_use","tool":{"name":"Read"}}',
            '{"type":"step_finish","step":{"name":"search"}}',
        ])
        completed = _subprocess_completed(stdout=events, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="opencode")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse_empty")

    def test_opencode_error_priority_over_text(self):
        events = '\n'.join([
            '{"type":"text","part":{"text":"partial"}}',
            '{"type":"error","error":{"data":{"message":"crash"}}}',
        ])
        completed = _subprocess_completed(stdout=events, stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="opencode")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "runtime")
        self.assertIn("crash", result.error)

    def test_opencode_fallback_raw_text_when_not_event_stream(self):
        completed = _subprocess_completed(stdout='{"conclusion":"已定位"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="opencode", command="opencode", model="model-a", timeout=5, cwd="/repo")).call("prompt")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "已定位")

    def test_opencode_preserves_extra_args(self):
        completed = _subprocess_completed(stdout='{"conclusion":"done"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            AgentClient(AgentConfig(agent="opencode", extra_args=["--verbose"])).call("prompt")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--verbose", cmd)

    def test_opencode_non_zero_returncode_with_error_event(self):
        events = '{"type":"error","error":{"data":{"message":"connection refused"}}}'
        completed = _subprocess_completed(stdout=events, stderr="", returncode=1)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="opencode")).call("prompt")
        self.assertFalse(result.ok)
        self.assertIn("connection refused", result.error)


class TestAgentClientGateway(unittest.TestCase):
    def test_gateway_completed_parses_text_and_session_ref(self):
        env = {
            "ACP_AGENT_GATEWAY_BIN": f"python3 {FAKE_GATEWAY}",
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": '{"conclusion":"完成","evidence":["src/a.c"]}',
            "FAKE_GATEWAY_SESSION_REF": "sess-agt-1",
            "FAKE_GATEWAY_STDERR_EVENTS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as td:
                config = AgentConfig(
                    agent="gateway",
                    gateway_agent="opencode",
                    timeout=5,
                    cwd=td,
                )
                result = AgentClient(config).call("分析这个需求")
        self.assertTrue(result.ok)
        self.assertEqual(result.json_data["conclusion"], "完成")
        self.assertEqual(result.gateway_session_ref, "sess-agt-1")
        self.assertTrue(len(result.gateway_events) > 0)

    def test_gateway_failed_maps_error_kind_and_records_diagnostics(self):
        env = {
            "ACP_AGENT_GATEWAY_BIN": f"python3 {FAKE_GATEWAY}",
            "FAKE_GATEWAY_MODE": "failed",
            "FAKE_GATEWAY_ERROR_CODE": "adapter_not_found",
            "FAKE_GATEWAY_ERROR_MESSAGE": "adapter not found",
            "FAKE_GATEWAY_SESSION_REF": "sess-fail-agt-1",
            "FAKE_GATEWAY_STDERR_EVENTS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as td:
                config = AgentConfig(
                    agent="gateway",
                    gateway_agent="opencode",
                    timeout=5,
                    cwd=td,
                )
                result = AgentClient(config).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertEqual(result.gateway_error_code, "adapter_not_found")
        self.assertEqual(result.gateway_session_ref, "sess-fail-agt-1")
        self.assertTrue(len(result.gateway_events) > 0)

    def test_gateway_empty_completed_response_maps_to_retryable_kind(self):
        env = {
            "ACP_AGENT_GATEWAY_BIN": f"python3 {FAKE_GATEWAY}",
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": "",
            "FAKE_GATEWAY_SESSION_REF": "sess-empty-agt-1",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as td:
                config = AgentConfig(
                    agent="gateway",
                    gateway_agent="opencode",
                    timeout=5,
                    cwd=td,
                )
                result = AgentClient(config).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "gateway_empty_response")
        self.assertEqual(result.gateway_error_code, "agent_empty_response")
        self.assertEqual(result.gateway_stop_reason, "empty_response")
        self.assertEqual(result.gateway_session_ref, "sess-empty-agt-1")

    def test_gateway_stderr_events_not_in_raw_response(self):
        env = {
            "ACP_AGENT_GATEWAY_BIN": f"python3 {FAKE_GATEWAY}",
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": '{"conclusion":"完成"}',
            "FAKE_GATEWAY_SESSION_REF": "sess-events-2",
            "FAKE_GATEWAY_STDERR_EVENTS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as td:
                config = AgentConfig(
                    agent="gateway",
                    gateway_agent="opencode",
                    timeout=5,
                    cwd=td,
                )
                result = AgentClient(config).call("prompt")
        self.assertTrue(result.ok)
        self.assertNotIn("session.created", result.raw_response)
        self.assertNotIn("turn.completed", result.raw_response)
        self.assertNotIn("tool.used", result.raw_response)

    def test_gateway_invalid_stdout_becomes_transport_error(self):
        env = {
            "ACP_AGENT_GATEWAY_BIN": f"python3 {FAKE_GATEWAY}",
            "FAKE_GATEWAY_MODE": "invalid_stdout",
            "FAKE_GATEWAY_SESSION_REF": "sess-tport-1",
            "FAKE_GATEWAY_STDERR_EVENTS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as td:
                config = AgentConfig(
                    agent="gateway",
                    gateway_agent="opencode",
                    timeout=5,
                    cwd=td,
                )
                result = AgentClient(config).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "runtime")
        self.assertEqual(result.gateway_transport_error, "gateway_invalid_stdout_json")
        self.assertEqual(result.gateway_session_ref, "sess-tport-1")

    def test_gateway_missing_gateway_agent_returns_config_error(self):
        config = AgentConfig(agent="gateway", gateway_agent="", timeout=5)
        result = AgentClient(config).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertIn("gateway-agent", result.error)

    def test_gateway_timeout_error_maps_correctly(self):
        env = {
            "ACP_AGENT_GATEWAY_BIN": f"python3 {FAKE_GATEWAY}",
            "FAKE_GATEWAY_MODE": "timeout",
            "FAKE_GATEWAY_ERROR_CODE": "timeout",
            "FAKE_GATEWAY_ERROR_MESSAGE": "request timed out",
            "FAKE_GATEWAY_SESSION_REF": "sess-timeout-2",
            "FAKE_GATEWAY_STDERR_EVENTS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as td:
                config = AgentConfig(
                    agent="gateway",
                    gateway_agent="opencode",
                    timeout=5,
                    cwd=td,
                )
                result = AgentClient(config).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "timeout")
        self.assertEqual(result.gateway_error_code, "timeout")


if __name__ == "__main__":
    unittest.main(verbosity=2)
