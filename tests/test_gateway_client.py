import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.gateway_client import (
    GATEWAY_SUBPROCESS_TIMEOUT_GRACE,
    GatewayConfig,
    GatewayResult,
    _map_gateway_error,
    _parse_gateway_stderr,
    call_gateway_start_session,
    resolve_gateway_command,
)


FAKE_GATEWAY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "fake_gateway.py",
)


def _fake_gateway_cmd(mode="completed", text_output=None):
    return f"python3 {FAKE_GATEWAY} --fake"


class TestGatewayErrorMapping(unittest.TestCase):
    def test_known_error_codes_map_to_correct_kind(self):
        self.assertEqual(_map_gateway_error("adapter_not_found"), "config")
        self.assertEqual(_map_gateway_error("unsupported_agent"), "config")
        self.assertEqual(_map_gateway_error("unsupported_model"), "config")
        self.assertEqual(_map_gateway_error("timeout"), "timeout")
        self.assertEqual(_map_gateway_error("idle_timeout"), "timeout")
        self.assertEqual(_map_gateway_error("cancelled"), "timeout")
        self.assertEqual(_map_gateway_error("protocol_error"), "runtime")
        self.assertEqual(_map_gateway_error("adapter_spawn_failed"), "runtime")
        self.assertEqual(_map_gateway_error("internal_error"), "runtime")

    def test_unknown_error_code_maps_to_runtime(self):
        self.assertEqual(_map_gateway_error("some_unknown_code"), "runtime")


class TestGatewayStderrParsing(unittest.TestCase):
    def test_empty_stderr_returns_empty_list(self):
        self.assertEqual(_parse_gateway_stderr(""), [])
        self.assertEqual(_parse_gateway_stderr("  \n  "), [])

    def test_valid_jsonl_events_are_parsed(self):
        stderr = '\n'.join([
            '{"type": "session.created", "sessionRef": "abc"}',
            '{"type": "agent.connected", "agent": "opencode"}',
        ])
        events = _parse_gateway_stderr(stderr)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "session.created")
        self.assertEqual(events[0]["sessionRef"], "abc")

    def test_non_json_lines_are_preserved_as_raw(self):
        stderr = '\n'.join([
            '{"type": "valid"}',
            "some garbage line",
            '{"type": "also valid"}',
        ])
        events = _parse_gateway_stderr(stderr)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["type"], "valid")
        self.assertEqual(events[1]["raw"], "some garbage line")
        self.assertTrue(events[1]["_parse_error"])
        self.assertEqual(events[2]["type"], "also valid")


class TestGatewayCommandResolution(unittest.TestCase):
    def test_gateway_bin_from_config_takes_priority(self):
        config = GatewayConfig(gateway_bin="/custom/gateway")
        self.assertEqual(resolve_gateway_command(config), "/custom/gateway")

    def test_env_var_used_when_config_empty(self):
        config = GatewayConfig()
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": "/env/gateway"}, clear=True):
            self.assertEqual(resolve_gateway_command(config), "/env/gateway")

    def test_path_lookup_when_no_config_or_env(self):
        with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value="/usr/bin/acp-agent-gateway"):
            config = GatewayConfig()
            self.assertEqual(resolve_gateway_command(config), "/usr/bin/acp-agent-gateway")

    def test_returns_none_when_not_found(self):
        with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
            config = GatewayConfig()
            self.assertIsNone(resolve_gateway_command(config))


class TestGatewayStartSession(unittest.TestCase):
    def test_completed_result_returns_text_and_session_ref(self):
        config = GatewayConfig(gateway_agent="opencode", timeout=5, idle_timeout=60)
        env = {
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": '{"conclusion":"完成","evidence":[]}',
            "FAKE_GATEWAY_SESSION_REF": "sess-test-1",
            "FAKE_GATEWAY_STDERR_EVENTS": "true",
        }
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": _fake_gateway_cmd()}, clear=False):
            with tempfile.TemporaryDirectory() as td:
                result = call_gateway_start_session("test prompt", td, config, extra_env=env)
        self.assertTrue(result.ok)
        self.assertIn("完成", result.text)
        self.assertEqual(result.session_ref, "sess-test-1")
        self.assertTrue(len(result.events) > 0)
        self.assertEqual(result.error_kind, "")
        self.assertEqual(result.error_code, "")

    def test_failed_result_maps_error_code_and_preserves_session_ref(self):
        config = GatewayConfig(gateway_agent="opencode", timeout=5)
        env = {
            "FAKE_GATEWAY_MODE": "failed",
            "FAKE_GATEWAY_ERROR_CODE": "adapter_not_found",
            "FAKE_GATEWAY_ERROR_MESSAGE": "adapter not found",
            "FAKE_GATEWAY_SESSION_REF": "sess-fail-1",
        }
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": _fake_gateway_cmd()}, clear=False):
            with tempfile.TemporaryDirectory() as td:
                result = call_gateway_start_session("prompt", td, config, extra_env=env)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertEqual(result.error_code, "adapter_not_found")
        self.assertEqual(result.session_ref, "sess-fail-1")
        self.assertIn("adapter", result.error.lower())

    def test_completed_empty_response_maps_to_retryable_gateway_kind(self):
        config = GatewayConfig(gateway_bin="acp-agent-gateway", gateway_agent="opencode", timeout=5)
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({
                "status": "completed",
                "text": "",
                "stopReason": "empty_response",
                "sessionRef": "sess-empty-1",
            }),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as td:
            with patch("zentao_analyzer.gateway_client.subprocess.run", return_value=completed):
                result = call_gateway_start_session("prompt", td, config)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "agent_empty_response")
        self.assertEqual(result.error_kind, "gateway_empty_response")
        self.assertEqual(result.stop_reason, "empty_response")
        self.assertEqual(result.session_ref, "sess-empty-1")

    def test_invalid_stdout_returns_transport_error(self):
        config = GatewayConfig(gateway_agent="opencode", timeout=5)
        env = {
            "FAKE_GATEWAY_MODE": "invalid_stdout",
            "FAKE_GATEWAY_SESSION_REF": "sess-invalid-1",
        }
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": _fake_gateway_cmd()}, clear=False):
            with tempfile.TemporaryDirectory() as td:
                result = call_gateway_start_session("prompt", td, config, extra_env=env)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "runtime")
        self.assertEqual(result.transport_error, "gateway_invalid_stdout_json")
        self.assertEqual(result.session_ref, "sess-invalid-1")

    def test_missing_command_returns_config_error(self):
        with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
            config = GatewayConfig(gateway_agent="opencode")
            result = call_gateway_start_session("prompt", ".", config)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")

    def test_timeout_error_code_maps_to_timeout_kind(self):
        config = GatewayConfig(gateway_agent="opencode", timeout=5)
        env = {
            "FAKE_GATEWAY_MODE": "timeout",
            "FAKE_GATEWAY_ERROR_CODE": "timeout",
            "FAKE_GATEWAY_ERROR_MESSAGE": "request timed out",
            "FAKE_GATEWAY_SESSION_REF": "sess-timeout-1",
        }
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": _fake_gateway_cmd()}, clear=False):
            with tempfile.TemporaryDirectory() as td:
                result = call_gateway_start_session("prompt", td, config, extra_env=env)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "timeout")
        self.assertEqual(result.error_code, "timeout")

    def test_subprocess_timeout_allows_gateway_to_report_timeout(self):
        config = GatewayConfig(gateway_bin="acp-agent-gateway", gateway_agent="opencode", timeout=5)
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"status":"completed","text":"{}","sessionRef":"sess-timeout-grace"}',
            stderr="",
        )
        with tempfile.TemporaryDirectory() as td:
            with patch("zentao_analyzer.gateway_client.subprocess.run", return_value=completed) as mock_run:
                result = call_gateway_start_session("prompt", td, config)
        self.assertTrue(result.ok)
        self.assertEqual(
            mock_run.call_args.kwargs["timeout"],
            config.timeout + GATEWAY_SUBPROCESS_TIMEOUT_GRACE,
        )

    def test_events_parsed_from_stderr(self):
        config = GatewayConfig(gateway_agent="opencode", timeout=5)
        env = {
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": '{"conclusion":"ok"}',
            "FAKE_GATEWAY_SESSION_REF": "sess-events-1",
        }
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": _fake_gateway_cmd()}, clear=False):
            with tempfile.TemporaryDirectory() as td:
                result = call_gateway_start_session("prompt", td, config, extra_env=env)
        self.assertTrue(result.ok)
        event_types = [e.get("type", "") for e in result.events if isinstance(e, dict) and "type" in e]
        self.assertIn("session.created", event_types)
        self.assertIn("turn.completed", event_types)

    def test_model_and_permission_policy_in_request(self):
        config = GatewayConfig(
            gateway_agent="opencode",
            timeout=5,
            model="test-model",
            permission_policy="best-effort-read-only",
            idle_timeout=120,
        )
        env = {
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": '{"conclusion":"ok"}',
            "FAKE_GATEWAY_SESSION_REF": "sess-model-1",
        }
        with patch.dict(os.environ, {"ACP_AGENT_GATEWAY_BIN": _fake_gateway_cmd()}, clear=False):
            with tempfile.TemporaryDirectory() as td:
                result = call_gateway_start_session("prompt", td, config, extra_env=env)
        self.assertTrue(result.ok)

    def test_shlex_split_handles_extra_args_in_command(self):
        config = GatewayConfig(gateway_bin=f"python3 {FAKE_GATEWAY} --fake", gateway_agent="opencode", timeout=5)
        env = {
            "FAKE_GATEWAY_MODE": "completed",
            "FAKE_GATEWAY_TEXT_OUTPUT": '{"conclusion":"ok"}',
            "FAKE_GATEWAY_SESSION_REF": "sess-shlex-1",
        }
        with tempfile.TemporaryDirectory() as td:
            result = call_gateway_start_session("prompt", td, config, extra_env=env)
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
