import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analysis_result import AnalysisResult
from zentao_analyzer.document_generator import DocumentResult
from zentao_analyzer.summary_report import build_summary_item, write_summary_report
from zentao_analyzer.zentao_client import ZentaoItem


class TestSummaryReport(unittest.TestCase):
    def test_build_summary_item(self):
        item = ZentaoItem(id="1", type="story", title="Title")
        analysis = AnalysisResult(
            item_id="1",
            item_type="story",
            item_title="Title",
            conclusion="完成",
            evidence=["a"],
            recommendations=["b"],
            verification=["c"],
            priority="高",
            confidence="高",
            raw_response="secret raw",
        )
        document = DocumentResult("1", "story", "Title", "PRD", "docs/prd/a.md", False)
        writeback = {"supported": False, "status": "not_implemented"}
        data = build_summary_item(item, analysis, document, writeback)
        self.assertEqual(data["item_id"], "1")
        self.assertEqual(data["title"], "Title")
        self.assertEqual(data["document_type"], "PRD")
        self.assertEqual(data["evidence_count"], 1)
        self.assertIn("has_error", data)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "")
        self.assertNotIn("raw_response", json.dumps(data, ensure_ascii=False))
        self.assertNotIn("secret raw", json.dumps(data, ensure_ascii=False))
        self.assertEqual(data["collected_location_count"], 0)
        self.assertEqual(data["cited_evidence_location_count"], 0)
        self.assertEqual(data["rejected_clue_count"], 0)

    def test_build_summary_item_with_evidence_counts(self):
        from zentao_analyzer.code_clues import CodeLocation

        item = ZentaoItem(id="2", type="bug", title="Bug")
        analysis = AnalysisResult(
            item_id="2",
            item_type="bug",
            item_title="Bug",
            conclusion="已定位",
            evidence=["src/a.c:1-2 bug"],
            confidence="高",
            cited_evidence_locations=[
                CodeLocation(path="src/a.c", line_start=1, line_end=2, source="agent")
            ],
        )
        document = DocumentResult("2", "bug", "Bug", "ISSUE", "docs/issue/a.md", False)
        data = build_summary_item(
            item,
            analysis,
            document,
            {"supported": False},
            collected_location_count=3,
            rejected_clue_count=1,
            debug_bundle="debug_runs/run",
        )
        self.assertEqual(data["collected_location_count"], 3)
        self.assertEqual(data["cited_evidence_location_count"], 1)
        self.assertEqual(data["rejected_clue_count"], 1)
        self.assertEqual(data["debug_bundle"], "debug_runs/run")

    def test_write_summary_report(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_summary_report(
                [{"item_id": "1"}],
                output_root=td,
                generated_at="2026-05-21T10:00:00+08:00",
            )
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["prd_dir"], os.path.join(td, "prd"))
            self.assertEqual(data["issue_dir"], os.path.join(td, "issue"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
