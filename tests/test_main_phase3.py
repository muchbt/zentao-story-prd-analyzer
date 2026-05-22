import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zentao_analyzer.main as main

class TestMainPhase3(unittest.TestCase):
    def test_analyze_generates_document_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            mock_item = MagicMock()
            mock_item.id = "5939"
            mock_item.type = "requirement"
            mock_item.title = "Test Title"
            mock_item.description = "Desc"
            mock_item.status = "active"
            mock_item.priority = "1"
            mock_item.project = ""
            mock_item.product = "41"
            mock_item.execution = ""
            mock_item.assigned_to = "dev"
            mock_item.created_by = "pm"
            mock_item.created_date = "2026-05-20"

            mock_analysis = MagicMock()
            mock_analysis.item_id = "5939"
            mock_analysis.item_type = "requirement"
            mock_analysis.item_title = "Test Title"
            mock_analysis.conclusion = "完成"
            mock_analysis.evidence = ["src/a.c"]
            mock_analysis.gaps = []
            mock_analysis.suspected_causes = []
            mock_analysis.affected_scope = []
            mock_analysis.recommendations = ["建议"]
            mock_analysis.verification = ["验证"]
            mock_analysis.priority = "高"
            mock_analysis.confidence = "高"
            mock_analysis.error = ""
            mock_analysis.is_insufficient_evidence.return_value = False
            mock_analysis.output_md = ""
            mock_analysis.raw_response = "secret"
            mock_analysis.cited_evidence_locations = []
            mock_analysis.seed_locations = []
            mock_analysis.rejected_seed_paths = []
            mock_analysis.evidence_validation_issues = []

            with patch.object(main.ZentaoClient, "get_item", return_value=mock_item):
                with patch("zentao_analyzer.main.analyze", return_value=mock_analysis):
                    with patch.object(sys, "argv", [
                        "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                        "--analyze", "--repo-path", td, "--output-root", td,
                        "--quiet",
                    ]):
                        with contextlib.redirect_stdout(io.StringIO()):
                            main.main()

            # Check generated document exists
            prd_files = [f for f in os.listdir(os.path.join(td, "prd")) if f.endswith(".md")]
            self.assertTrue(len(prd_files) > 0, "PRD document should be generated")

            # Check summary report exists
            summary_path = os.path.join(td, "summary_report.json")
            self.assertTrue(os.path.exists(summary_path), "Summary report should be generated")

            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary["count"], 1)

    def test_without_analyze_no_phase3_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            mock_item = MagicMock()
            mock_item.id = "1"
            mock_item.type = "story"
            mock_item.title = "T"
            mock_item.description = "D"
            mock_item.status = "active"
            mock_item.priority = ""
            mock_item.project = ""
            mock_item.product = ""
            mock_item.execution = ""
            mock_item.assigned_to = ""
            mock_item.created_by = ""
            mock_item.created_date = ""

            with patch.object(main.ZentaoClient, "get_item", return_value=mock_item):
                with patch.object(sys, "argv", [
                    "zentao_analyzer.main.py", "--module", "story", "--id", "1",
                    "--quiet",
                ]):
                    with contextlib.redirect_stdout(io.StringIO()):
                        main.main()

            # No docs directory should be created
            self.assertFalse(os.path.exists(os.path.join(td, "prd")))
            self.assertFalse(os.path.exists(os.path.join(td, "issue")))

if __name__ == "__main__":
    unittest.main(verbosity=2)
