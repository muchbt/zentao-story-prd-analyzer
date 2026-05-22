import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analyzer import analyze, validate_evidence_locations
from zentao_analyzer.analysis_result import AnalysisResult, EvidenceLocation
from zentao_analyzer.zentao_client import ZentaoItem


class TestAnalyzer(unittest.TestCase):
    def test_no_seed_still_calls_agent(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="1", type="story", title="T")
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "无法判断", "evidence": [], "confidence": "低"}) as mock_llm:
                result = analyze(item, td, agent="claude", agent_config=MagicMock(), seed_paths=[], search_hints=["hint"])
        self.assertEqual(result.conclusion, "无法判断")
        self.assertTrue(mock_llm.called)
        self.assertIn("hint", mock_llm.call_args[0][0])

    def test_seed_paths_are_loaded_and_metadata_is_attached(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.c")
            with open(path, "w", encoding="utf-8") as f:
                f.write("int a;\n")
            item = ZentaoItem(id="2", type="story", title="Feature")
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "完成", "evidence": [{"path": path, "line_start": 1, "line_end": 1}], "confidence": "高"}):
                result = analyze(item, td, agent="claude", agent_config=MagicMock(), seed_paths=[path])
        self.assertEqual(result.seed_locations[0].path, path)
        self.assertEqual(result.evidence_validation_issues, [])

    def test_invalid_repo_path_returns_error(self):
        item = ZentaoItem(id="3", type="story", title="Feature")
        result = analyze(item, "/missing/repo", agent="claude", agent_config=MagicMock())
        self.assertEqual(result.error_kind, "config")

    def test_debug_recorder_receives_prompt_and_response(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="4", type="story", title="S")
            records = []
            def recorder(kind, item_obj, payload):
                records.append((kind, item_obj.id, payload))
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "无法判断", "evidence": [], "confidence": "低", "raw": '{"ok":true}'}):
                analyze(item, td, agent="codex", agent_config=MagicMock(), debug_recorder=recorder)
        self.assertEqual(records[0][0], "prompt")
        self.assertEqual(records[1], ("response", "4", '{"ok":true}'))


class TestEvidenceValidation(unittest.TestCase):
    def test_validate_evidence_locations_accepts_existing_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.c")
            with open(path, "w", encoding="utf-8") as f:
                f.write("1\n2\n")
            result = AnalysisResult(item_id="1", item_type="story", item_title="T", cited_evidence_locations=[
                EvidenceLocation(path=path, line_start=1, line_end=2, source="agent")
            ])
            self.assertEqual(validate_evidence_locations(td, result), [])

    def test_validate_evidence_locations_resolves_relative_paths_from_repo(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src")
            os.makedirs(src)
            with open(os.path.join(src, "a.c"), "w", encoding="utf-8") as f:
                f.write("1\n2\n")
            result = AnalysisResult(item_id="1", item_type="story", item_title="T", cited_evidence_locations=[
                EvidenceLocation(path="src/a.c", line_start=1, line_end=2, source="agent")
            ])
            self.assertEqual(validate_evidence_locations(td, result), [])

    def test_validate_evidence_locations_reports_out_of_range_and_outside_repo(self):
        with tempfile.TemporaryDirectory() as td:
            inside = os.path.join(td, "a.c")
            outside = os.path.join(os.path.dirname(td), "outside.c")
            with open(inside, "w", encoding="utf-8") as f:
                f.write("1\n")
            with open(outside, "w", encoding="utf-8") as f:
                f.write("1\n")
            result = AnalysisResult(item_id="1", item_type="story", item_title="T", cited_evidence_locations=[
                EvidenceLocation(path=inside, line_start=2, line_end=2, source="agent"),
                EvidenceLocation(path=outside, line_start=1, line_end=1, source="agent"),
            ])
            issues = validate_evidence_locations(td, result)
        self.assertEqual([issue.reason for issue in issues], ["line_out_of_range", "outside_repo"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
