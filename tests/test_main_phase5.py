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
from zentao_analyzer.analysis_result import EvidenceLocation, EvidenceValidationIssue
from zentao_analyzer.code_clues import RejectedSeedPath
from zentao_analyzer.seed_loader import SeedLocation


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
    return item


def make_analysis(seed_path="src/a.c", rejected=None):
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
        EvidenceLocation(path="src/a.c", line_start=1, line_end=3, reason="ok", source="agent")
    ]
    analysis.seed_locations = [
        SeedLocation(path=seed_path, line_start=1, line_end=3)
    ]
    analysis.rejected_seed_paths = rejected or []
    analysis.evidence_validation_issues = []
    analysis.is_insufficient_evidence.return_value = False
    return analysis


class TestMainPhase5(unittest.TestCase):
    def test_cli_clues_and_seed_paths_are_passed_and_bundle_writes_seed_locations(self):
        with tempfile.TemporaryDirectory() as td:
            seed = os.path.join(td, "src", "a.c")
            os.makedirs(os.path.dirname(seed))
            with open(seed, "w", encoding="utf-8") as f:
                f.write("int a;\n")
            analysis = make_analysis(seed_path=seed)

            def fake_analyze(*args, **kwargs):
                self.assertEqual(kwargs["search_hints"], ["cli_kw", "Login"])
                self.assertEqual(kwargs["seed_paths"], [seed])
                return analysis

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--clues", "cli_kw,Login", "--paths", "src/a.c",
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
            self.assertEqual(evidence["items"][0]["seed_locations"][0]["path"], seed)
            self.assertEqual(evidence["items"][0]["cited_evidence_locations"][0]["path"], "src/a.c")

            with open(parsed["summary_report"], encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary["items"][0]["seed_location_count"], 1)
            self.assertEqual(summary["items"][0]["cited_evidence_location_count"], 1)

    def test_clues_file_and_rejected_seed_path_are_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            clues_path = os.path.join(td, "clues.json")
            rejected = [RejectedSeedPath(value="../outside.c", source="clues_file", item_id="5939", reason="outside_repo")]
            with open(clues_path, "w", encoding="utf-8") as f:
                json.dump({"5939": {"paths": ["../outside.c"], "clues": ["file_kw"]}}, f)

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--clues-file", clues_path,
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=make_item()):
                with patch("zentao_analyzer.main.analyze", return_value=make_analysis(rejected=rejected)) as mock_analyze:
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            self.assertEqual(mock_analyze.call_args.kwargs["search_hints"], ["file_kw"])
            parsed = json.loads(stdout.getvalue())
            with open(os.path.join(parsed["debug_bundle"], "rejected_seed_paths.json"), encoding="utf-8") as f:
                rejected_data = json.load(f)
            self.assertEqual(rejected_data[0]["reason"], "outside_repo")

    def test_evidence_validation_issues_are_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            analysis = make_analysis()
            analysis.evidence_validation_issues = [
                EvidenceValidationIssue(path="src/a.c", line_start=99, line_end=99, reason="line_out_of_range")
            ]
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=make_item()):
                with patch("zentao_analyzer.main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()
            parsed = json.loads(stdout.getvalue())
            with open(os.path.join(parsed["debug_bundle"], "code_evidence_locations.json"), encoding="utf-8") as f:
                evidence = json.load(f)
            self.assertEqual(evidence["items"][0]["evidence_validation_issues"][0]["reason"], "line_out_of_range")


if __name__ == "__main__":
    unittest.main(verbosity=2)
