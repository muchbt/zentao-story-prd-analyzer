import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import analyze
from zentao_client import ZentaoItem

class TestAnalyzer(unittest.TestCase):
    def test_empty_code_returns_insufficient(self):
        item = ZentaoItem(id="1", type="story", title="T")
        with patch("analyzer.collect", return_value=[]):
            result = analyze(item, ".", agent="codex")
        self.assertTrue(result.is_insufficient_evidence())
        self.assertEqual(result.conclusion, "无法判断")

    def test_feature_type_uses_feature_prompt(self):
        item = ZentaoItem(id="2", type="story", title="Feature")
        with patch("analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="codex")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("功能实现完成度", prompt)

    def test_bug_type_uses_defect_prompt(self):
        item = ZentaoItem(id="3", type="bug", title="Bug")
        with patch("analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("analyzer.call_llm", return_value={"conclusion": "已定位", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="codex")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("可能根因", prompt)

    def test_llm_error_returns_error_result(self):
        item = ZentaoItem(id="4", type="story", title="S")
        with patch("analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("analyzer.call_llm", return_value={"error": "timeout", "raw": ""}):
                result = analyze(item, ".", agent="codex")
        self.assertEqual(result.error, "timeout")
        self.assertTrue(result.is_insufficient_evidence())

    def test_force_insufficient_when_evidence_empty(self):
        item = ZentaoItem(id="5", type="story", title="S")
        with patch("analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("analyzer.call_llm", return_value={"conclusion": "完成", "evidence": [], "confidence": "高"}):
                result = analyze(item, ".", agent="codex")
        self.assertTrue(result.is_insufficient_evidence())
        self.assertEqual(result.conclusion, "无法判断")

if __name__ == "__main__":
    unittest.main(verbosity=2)
