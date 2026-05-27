import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.agent_client import AgentClient, AgentConfig, extract_json_object, _extract_markdown_json, _repair_json_quotes


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
        self.assertIn("--sandbox", cmd)
        self.assertIn("read-only", cmd)
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
        self.assertNotIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(cmd[-1], "prompt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
