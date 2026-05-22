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
    item.keywords = ["test"]
    return item


def make_analysis():
    analysis = MagicMock()
    analysis.item_id = "5939"
    analysis.item_type = "requirement"
    analysis.item_title = "Test Title"
    analysis.conclusion = "完成"
    analysis.evidence = ["src/a.c"]
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
    analysis.is_insufficient_evidence.return_value = False
    return analysis


class TestMainPhase4(unittest.TestCase):
    def test_analyze_stdout_is_single_json_and_contains_debug_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--agent", "claude", "--agent-timeout", "5",
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=analysis) as mock_analyze:
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            code = main.main()
            self.assertEqual(code, 0)
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["debug_bundle_error"], "")
            self.assertTrue(parsed["debug_bundle"])
            self.assertTrue(os.path.exists(parsed["debug_bundle"]))
            self.assertEqual(parsed["log_file"], "")
            agent_config = mock_analyze.call_args.kwargs["agent_config"]
            self.assertEqual(agent_config.agent, "claude")
            self.assertEqual(agent_config.timeout, 5)

    def test_no_debug_bundle_disables_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--no-debug-bundle",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["debug_bundle"], "")

    def test_phase1_without_analyze_does_not_create_debug_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch.object(sys, "argv", argv):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        main.main()
            parsed = json.loads(stdout.getvalue())
            self.assertNotIn("debug_bundle", parsed)
            self.assertFalse(os.path.exists(os.path.join(td, "debug_runs")))

    def test_log_file_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            log_file = os.path.join(td, "run.jsonl")
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--log-file", log_file,
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        with contextlib.redirect_stdout(io.StringIO()):
                            main.main()
            self.assertTrue(os.path.exists(log_file))
            with open(log_file, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertTrue(any(line["stage"] == "fetch_items" for line in lines))
            self.assertTrue(any(line["stage"] == "generate_docs" for line in lines))

    def test_debug_bundle_writes_scan_summary_and_optional_code_context(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            debug_dir = os.path.join(td, "debug")
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", debug_dir,
                "--debug-include-code",
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()
            parsed = json.loads(stdout.getvalue())
            self.assertTrue(os.path.exists(os.path.join(parsed["debug_bundle"], "scan_summary.json")))
            self.assertTrue(os.path.exists(os.path.join(parsed["debug_bundle"], "code_context.json")))

    def test_debug_bundle_contains_run_log_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()
            parsed = json.loads(stdout.getvalue())
            run_log = os.path.join(parsed["debug_bundle"], "run_log.jsonl")
            self.assertTrue(os.path.exists(run_log))
            with open(run_log, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertTrue(any(line["stage"] == "fetch_items" for line in lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
