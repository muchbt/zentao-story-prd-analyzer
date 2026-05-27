import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analyzer import analyze, validate_evidence_locations, validate_code_impact_locations
from zentao_analyzer.analysis_result import AnalysisResult, EvidenceLocation, CodeImpactLocation
from zentao_analyzer.zentao_client import ZentaoItem


class TestAnalyzer(unittest.TestCase):
    def test_no_seed_still_calls_agent(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="1", type="story", title="T")
            with patch("zentao_analyzer.analyzer.call_llm", return_value={"conclusion": "无法判断", "evidence": [], "confidence": "低"}) as mock_llm:
                result = analyze(item, td, agent="claude", agent_config=MagicMock(), seed_paths=[], search_hints=["hint"])
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")
        self.assertEqual(result.conclusion, "")
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
                result = analyze(item, td, agent="codex", agent_config=MagicMock(), debug_recorder=recorder)
        self.assertEqual(records[0][0], "prompt")
        self.assertEqual(records[1], ("response", "4", '{"ok":true}'))
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")


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


class TestCodeImpactLocationValidation(unittest.TestCase):
    def test_validate_valid_code_impact_location(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            locations = [CodeImpactLocation(component="模块A", path=src, line_start=1, line_end=1, symbol="a", reason="相关")]
            issues = validate_code_impact_locations(td, locations)
        self.assertEqual(issues, [])

    def test_validate_outside_repo_code_impact_location(self):
        locations = [CodeImpactLocation(component="模块A", path="/outside/a.c", line_start=1, line_end=1)]
        issues = validate_code_impact_locations("/repo", locations)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].reason, "code_impact_outside_repo")

    def test_validate_nonexistent_code_impact_location(self):
        with tempfile.TemporaryDirectory() as td:
            locations = [CodeImpactLocation(component="模块A", path=os.path.join(td, "missing.c"), line_start=1, line_end=1)]
            issues = validate_code_impact_locations(td, locations)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].reason, "code_impact_not_found")

    def test_validate_code_impact_location_without_path(self):
        issues = validate_code_impact_locations("/repo", [
            CodeImpactLocation(component="模块A", path="", line_start=1, line_end=1),
        ])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].reason, "code_impact_missing_path")

    def test_validate_code_impact_directory_is_reported_not_opened(self):
        with tempfile.TemporaryDirectory() as td:
            locations = [CodeImpactLocation(component="模块A", path=td, line_start=1, line_end=1)]
            issues = validate_code_impact_locations(td, locations)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].reason, "code_impact_is_directory")

    def test_validate_code_impact_does_not_affect_completion(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            missing = os.path.join(td, "missing.c")
            from zentao_analyzer.analyzer import _analyze_feature
            item = ZentaoItem(id="1", type="story", title="T")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已实现", "gaps": [], "evidence": [{"path": src, "line_start": 1, "line_end": 1, "symbol": "a", "reason": "实现"}]},
                ],
                "understanding_summary": "",
                "code_impact": {
                    "related_locations": [
                        {"component": "模块X", "path": missing, "line_start": 1, "line_end": 1},
                    ],
                    "impact_notes": ["影响说明"],
                },
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(result.conclusion, "完成")
        self.assertEqual(result.confidence, "高")
        self.assertIsNotNone(result.code_impact)
        self.assertEqual(len(result.code_impact.related_locations), 0)
        self.assertTrue(any("code_impact_location_invalid" in issue for issue in result.rich_content_issues))
        self.assertEqual(result.code_impact_validation_issues[0].reason, "code_impact_not_found")

    def test_invalid_rich_content_schema_is_preserved_for_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            from zentao_analyzer.analyzer import _analyze_feature
            item = ZentaoItem(id="1", type="story", title="T")
            result = _analyze_feature(item, {
                "requirement_interpretation": {"scope": "bad"},
                "code_impact": {"related_locations": "bad"},
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已实现", "gaps": [], "evidence": [{"path": src, "line_start": 1, "line_end": 1}]},
                ],
            }, "", td, [], [])
        self.assertIn("requirement_interpretation_invalid_scope", result.rich_content_issues)
        self.assertIn("code_impact_invalid_related_locations", result.rich_content_issues)


if __name__ == "__main__":
    unittest.main(verbosity=2)
