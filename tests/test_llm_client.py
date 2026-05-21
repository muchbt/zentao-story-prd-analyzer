import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_client import call_llm

class TestLLMClient(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_codex_returns_json(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"conclusion":"完成"}'

        with patch("llm_client.openai") as mock_openai:
            mock_openai.ChatCompletion.create.return_value = mock_response
            result = call_llm("test prompt", agent="codex")
        self.assertEqual(result["conclusion"], "完成")

    def test_claude_placeholder(self):
        result = call_llm("test", agent="claude")
        self.assertIn("error", result)
        self.assertIn("未实现", result["error"])

    def test_opencode_placeholder(self):
        result = call_llm("test", agent="opencode")
        self.assertIn("error", result)
        self.assertIn("未实现", result["error"])

    def test_unknown_agent(self):
        result = call_llm("test", agent="unknown")
        self.assertIn("error", result)
        self.assertIn("未识别", result["error"])

    def test_non_json_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json"

        with patch("llm_client.openai") as mock_openai:
            mock_openai.ChatCompletion.create.return_value = mock_response
            result = call_llm("test", agent="codex")
        self.assertIn("error", result)
        self.assertEqual(result["raw"], "not json")

if __name__ == "__main__":
    unittest.main(verbosity=2)
