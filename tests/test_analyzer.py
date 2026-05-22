import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analyzer import analyze
from zentao_analyzer.zentao_client import ZentaoItem

class TestAnalyzer(unittest.TestCase):
    def test_empty_code_returns_insufficient(self):
        item = ZentaoItem(id="1", type="story", title="T")
        with patch("zentao_analyzer.analyzer.collect", return_value=[]):
            result = analyze(item, ".", agent="codex")
        self.assertTrue(result.is_insufficient_evidence())
        self.assertEqual(result.conclusion, "无法判断")

    def test_feature_type_uses_feature_prompt(self):
        item = ZentaoItem(id="2", type="story", title="Feature")
        with patch("zentao_analyzer.analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="codex")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("功能实现完成度", prompt)

    def test_bug_type_uses_defect_prompt(self):
        item = ZentaoItem(id="3", type="bug", title="Bug")
        with patch("zentao_analyzer.analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "已定位", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="codex")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("可能根因", prompt)

    def test_llm_error_returns_error_result(self):
        item = ZentaoItem(id="4", type="story", title="S")
        with patch("zentao_analyzer.analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"error": "timeout", "raw": ""}):
                result = analyze(item, ".", agent="codex")
        self.assertEqual(result.error, "timeout")
        self.assertTrue(result.is_insufficient_evidence())

    def test_force_insufficient_when_evidence_empty(self):
        item = ZentaoItem(id="5", type="story", title="S")
        with patch("zentao_analyzer.analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "完成", "evidence": [], "confidence": "高"}):
                result = analyze(item, ".", agent="codex")
        self.assertTrue(result.is_insufficient_evidence())
        self.assertEqual(result.conclusion, "无法判断")

    def test_analyzer_passes_agent_config_to_llm_client(self):
        item = ZentaoItem(id="6", type="story", title="S")
        agent_config = MagicMock()
        with patch("zentao_analyzer.analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="claude", agent_config=agent_config)
        self.assertEqual(mock_llm.call_args.kwargs["agent_config"], agent_config)

    def test_analyzer_records_prompt_and_response_with_debug_recorder(self):
        item = ZentaoItem(id="7", type="story", title="S")
        records = []
        def recorder(kind, item_obj, payload):
            records.append((kind, item_obj.id, payload))
        with patch("zentao_analyzer.analyzer.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高", "raw": '{"ok":true}'}):
                analyze(item, ".", agent="codex", debug_recorder=recorder)
        self.assertEqual(records[0][0], "prompt")
        self.assertEqual(records[0][1], "7")
        self.assertIn("功能实现完成度", records[0][2])
        self.assertEqual(records[1], ("response", "7", '{"ok":true}'))

    def test_analyzer_uses_collect_with_clues_and_records_collection(self):
        from zentao_analyzer.code_clues import CodeClue, CodeLocation, CollectionResult

        item = ZentaoItem(id="8", type="story", title="S")
        collection = CollectionResult(
            snippets=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 2}],
            collected_locations=[CodeLocation(path="a.c", line_start=1, line_end=2, source="collector")],
            rejected_clues=[],
        )
        collected = []

        def collection_recorder(item_obj, result):
            collected.append((item_obj.id, result))

        with patch("zentao_analyzer.analyzer.collect_with_clues", return_value=collection) as mock_collect:
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c:1-2 ok"], "confidence": "高"}):
                result = analyze(
                    item,
                    ".",
                    agent="codex",
                    code_clues=[CodeClue("keyword", "S", "cli", "8")],
                    collection_recorder=collection_recorder,
                )

        self.assertEqual(result.conclusion, "完成")
        mock_collect.assert_called_once()
        self.assertEqual(collected[0][0], "8")
        self.assertEqual(collected[0][1].collected_locations[0].path, "a.c")

if __name__ == "__main__":
    unittest.main(verbosity=2)
