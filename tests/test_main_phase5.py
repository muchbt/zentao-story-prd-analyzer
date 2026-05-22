import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zentao_analyzer.main as main
from zentao_analyzer.code_clues import CodeLocation, CollectionResult


def make_item():
    item = MagicMock()
    item.id = "5939"
    item.type = "requirement"
    item.title = "Test Title"
    item.description = "Desc"
    item.status = "active"
    item.priority = "1"
    item.project = ""
    item.product = "41"
    item.execution = ""
    item.assigned_to = "dev"
    item.created_by = "pm"
    item.created_date = "2026-05-20"
    item.keywords = ["zentao"]
    return item


def make_analysis():
    analysis = MagicMock()
    analysis.item_id = "5939"
    analysis.item_type = "requirement"
    analysis.item_title = "Test Title"
    analysis.conclusion = "完成"
    analysis.evidence = ["src/a.c:1-3 ok"]
    analysis.gaps = []
    analysis.suspected_causes = []
    analysis.affected_scope = []
    analysis.recommendations = ["建议"]
    analysis.verification = ["验证"]
    analysis.priority = "高"
    analysis.confidence = "高"
    analysis.error = ""
    analysis.output_md = "LLM 理解"
    analysis.raw_response = '{"conclusion":"完成"}'
    analysis.cited_evidence_locations = [
        CodeLocation(path="src/a.c", line_start=1, line_end=3, reason="ok", source="agent")
    ]
    analysis.is_insufficient_evidence.return_value = False
    return analysis


class TestMainPhase5(unittest.TestCase):
    def test_cli_clues_are_passed_and_bundle_writes_locations(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "src"))
            analysis = make_analysis()

            def fake_analyze(*args, **kwargs):
                clues = kwargs["code_clues"]
                self.assertTrue(any(c.kind == "keyword" and c.value == "cli_kw" for c in clues))
                self.assertTrue(any(c.kind == "symbol" and c.value == "Login" for c in clues))
                kwargs["collection_recorder"](
                    args[0],
                    CollectionResult(
                        snippets=[],
                        collected_locations=[
                            CodeLocation(path="src/a.c", line_start=1, line_end=3, source="collector")
                        ],
                        rejected_clues=[],
                    ),
                )
                return analysis

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--keywords", "cli_kw", "--paths", "src", "--symbols", "Login",
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=make_item()):
                with patch("zentao_analyzer.main.analyze", side_effect=fake_analyze):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            parsed = json.loads(stdout.getvalue())
            with open(os.path.join(parsed["debug_bundle"], "code_evidence_locations.json"), encoding="utf-8") as f:
                evidence = json.load(f)
            self.assertEqual(evidence["items"][0]["collected_locations"][0]["path"], "src/a.c")
            self.assertEqual(evidence["items"][0]["cited_evidence_locations"][0]["path"], "src/a.c")

            with open(parsed["summary_report"], encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary["items"][0]["collected_location_count"], 1)
            self.assertEqual(summary["items"][0]["cited_evidence_location_count"], 1)

    def test_clues_file_and_rejected_path_are_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            clues_path = os.path.join(td, "clues.json")
            with open(clues_path, "w", encoding="utf-8") as f:
                json.dump({"5939": {"paths": ["../outside.c"], "keywords": ["file_kw"]}}, f)

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--clues-file", clues_path,
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=make_item()):
                with patch("zentao_analyzer.main.analyze", return_value=make_analysis()) as mock_analyze:
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            clues = mock_analyze.call_args.kwargs["code_clues"]
            self.assertTrue(any(c.kind == "keyword" and c.value == "file_kw" for c in clues))
            parsed = json.loads(stdout.getvalue())
            with open(os.path.join(parsed["debug_bundle"], "rejected_clues.json"), encoding="utf-8") as f:
                rejected = json.load(f)
            self.assertEqual(rejected[0]["reason"], "outside_repo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
