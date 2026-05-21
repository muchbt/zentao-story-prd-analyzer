import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_client import AgentConfig, AgentResult
from llm_client import call_llm


class TestLLMClient(unittest.TestCase):
    def test_call_llm_returns_json_data_and_raw(self):
        result_obj = AgentResult(ok=True, json_data={"conclusion": "完成"}, raw_response='{"conclusion":"完成"}')
        with patch("llm_client.AgentClient") as mock_client:
            mock_client.return_value.call.return_value = result_obj
            result = call_llm("prompt", agent="codex", agent_config=AgentConfig(agent="codex", model="gpt-test"))
        self.assertEqual(result["conclusion"], "完成")
        self.assertEqual(result["raw"], '{"conclusion":"完成"}')

    def test_call_llm_failure_returns_legacy_error_shape(self):
        result_obj = AgentResult(ok=False, error="LLM 返回非 JSON", error_kind="parse", raw_response="bad")
        with patch("llm_client.AgentClient") as mock_client:
            mock_client.return_value.call.return_value = result_obj
            result = call_llm("prompt", agent="claude", agent_config=AgentConfig(agent="claude"))
        self.assertEqual(result["error"], "LLM 返回非 JSON")
        self.assertEqual(result["error_kind"], "parse")
        self.assertEqual(result["raw"], "bad")

    def test_call_llm_builds_config_from_agent_name(self):
        with patch("llm_client.AgentClient") as mock_client:
            mock_client.return_value.call.return_value = AgentResult(ok=False, error="OpenCode 适配尚未实现", error_kind="not_implemented")
            result = call_llm("prompt", agent="opencode")
        created_config = mock_client.call_args[0][0]
        self.assertEqual(created_config.agent, "opencode")
        self.assertEqual(result["error_kind"], "not_implemented")


if __name__ == "__main__":
    unittest.main(verbosity=2)
