import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.agent_client import AgentClient, AgentConfig, extract_json_object


class TestAgentClientCore(unittest.TestCase):
    def test_extract_json_direct_markdown_and_embedded(self):
        self.assertEqual(extract_json_object('{"conclusion":"完成"}'), {"conclusion": "完成"})
        self.assertEqual(extract_json_object('```json\n{"conclusion":"完成"}\n```'), {"conclusion": "完成"})
        self.assertEqual(extract_json_object('prefix {"conclusion":"完成"} suffix'), {"conclusion": "完成"})

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
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(mock_run.call_args.kwargs["input"], "prompt")
        self.assertEqual(mock_run.call_args.kwargs["cwd"], "/repo")

    def test_claude_arg_success(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="claude", prompt_via="arg", extra_args=["--foo"], timeout=5)).call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertIn("--foo", cmd)
        self.assertIn("-p", cmd)
        self.assertEqual(cmd[-1], "prompt")


class TestAgentClientCodex(unittest.TestCase):
    def test_codex_exec_success_uses_stdin_model_and_cwd(self):
        completed = _subprocess_completed(stdout='{"conclusion":"完成"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="codex", command="codex", model="gpt-5", timeout=5, cwd="/repo")).call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[:4], ["codex", "exec", "-C", "/repo"])
        self.assertIn("-m", cmd)
        self.assertIn("gpt-5", cmd)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertEqual(mock_run.call_args.kwargs["input"], "prompt")
        self.assertEqual(mock_run.call_args.kwargs["cwd"], "/repo")

    def test_codex_missing_command_is_config_error(self):
        with patch("zentao_analyzer.agent_client.subprocess.run", side_effect=FileNotFoundError("missing")):
            result = AgentClient(AgentConfig(agent="codex", command="missing")).call("prompt")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "config")


class TestAgentClientOpenCode(unittest.TestCase):
    def test_opencode_success_passes_model(self):
        completed = _subprocess_completed(stdout='{"conclusion":"已定位"}', stderr="", returncode=0)
        with patch("zentao_analyzer.agent_client.subprocess.run", return_value=completed) as mock_run:
            result = AgentClient(AgentConfig(agent="opencode", command="opencode", model="model-a", timeout=5, cwd="/repo")).call("prompt")
        self.assertTrue(result.ok)
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[:2], ["opencode", "run"])
        self.assertIn("--model", cmd)
        self.assertIn("model-a", cmd)
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(cmd[-1], "prompt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
