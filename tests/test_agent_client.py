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
        self.assertEqual(extract_json_object('```json\n{"conclusion":"完成"}\n```'), {"conclusion": "完成"})
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
        with patch("agent_client.openai", MagicMock()):
            client = AgentClient(AgentConfig(agent="openai", model="gpt-test"))
            result = client.call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")
        self.assertIn("OPENAI_API_KEY", result.error)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_openai_missing_model_returns_config_error(self):
        with patch("agent_client.openai", MagicMock()):
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


def _subprocess_completed(stdout="", stderr="", returncode=0):
    completed = MagicMock()
    completed.stdout = stdout
    completed.stderr = stderr
    completed.returncode = returncode
    return completed


class TestAgentClientClaude(unittest.TestCase):
    def test_claude_stdin_success(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
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
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
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
        completed = _subprocess_completed(stdout="", stderr="unauthorized anthropic_api_key", returncode=1)
        with patch("agent_client.subprocess.run", return_value=completed):
            result = AgentClient(AgentConfig(agent="claude", command="claude")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "auth")


if __name__ == "__main__":
    unittest.main(verbosity=2)
