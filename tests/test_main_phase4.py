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
    analysis.error_kind = ""
    analysis.raw_response = '{"conclusion":"完成"}'
    analysis.cited_evidence_locations = []
    analysis.seed_locations = []
    analysis.rejected_seed_paths = []
    analysis.evidence_validation_issues = []
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

    def test_parse_failure_is_retryable_and_prints_safe_item_retry_command(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            analysis = make_analysis()
            analysis.conclusion = "无法判断"
            analysis.error = "LLM 返回非 JSON"
            analysis.error_kind = "parse"
            analysis.confidence = ""
            output_path = os.path.join(td, "combined.json")
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td,
                "--output", output_path,
                "--agent", "claude", "--agent-timeout", "5", "--quiet",
                "--token", "private-token", "--user", "private-user", "--password", "private-password",
                "--clues", "callback,token=clue-secret", "--paths", "src/ecall.c",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=analysis):
                    with patch.object(sys, "argv", argv):
                        stderr = io.StringIO()
                        with contextlib.redirect_stderr(stderr):
                            code = main.main()
            self.assertEqual(code, 0)
            with open(output_path, encoding="utf-8") as f:
                parsed = json.load(f)
            self.assertTrue(parsed["analysis"][0]["retryable"])
            self.assertEqual(parsed["analysis"][0]["retry_reason"], "agent_response_parse_failed")
            self.assertTrue(parsed["has_retryable_failure"])
            message = stderr.getvalue()
            self.assertIn("条目 5939", message)
            self.assertIn("python3 zentao_analyzer.main.py", message)
            self.assertIn("--id 5939", message)
            self.assertIn("--output-root", message)
            self.assertIn("--clues", message)
            self.assertIn("--paths", message)
            self.assertNotIn("--output", message.replace("--output-root", ""))
            self.assertNotIn("--token", message)
            self.assertNotIn("private-token", message)
            self.assertNotIn("--user", message)
            self.assertNotIn("private-user", message)
            self.assertNotIn("--password", message)
            self.assertNotIn("private-password", message)
            self.assertNotIn("clue-secret", message)

    def test_batch_parse_failure_marks_only_failed_item_as_retryable(self):
        with tempfile.TemporaryDirectory() as td:
            succeeded_item = make_item()
            failed_item = make_item()
            failed_item.id = "5940"
            succeeded_analysis = make_analysis()
            failed_analysis = make_analysis()
            failed_analysis.item_id = "5940"
            failed_analysis.error = "LLM 返回非 JSON"
            failed_analysis.error_kind = "parse"
            failed_analysis.conclusion = "无法判断"
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--project", "3",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "list_items", return_value=[succeeded_item, failed_item]):
                with patch("zentao_analyzer.main.analyze", side_effect=[succeeded_analysis, failed_analysis]):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        stderr = io.StringIO()
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            code = main.main()
            self.assertEqual(code, 0)
            parsed = json.loads(stdout.getvalue())
            self.assertFalse(parsed["analysis"][0]["retryable"])
            self.assertEqual(parsed["analysis"][0]["retry_reason"], "")
            self.assertTrue(parsed["analysis"][1]["retryable"])
            self.assertEqual(parsed["analysis"][1]["retry_reason"], "agent_response_parse_failed")
            self.assertTrue(parsed["has_retryable_failure"])
            self.assertIn("--id 5940", stderr.getvalue())
            self.assertNotIn("--id 5939", stderr.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
