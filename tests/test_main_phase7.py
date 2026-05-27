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
from zentao_analyzer.analysis_result import AnalysisResult, RequirementInterpretation, InterpretationEntry, CodeImpactAnalysis, CodeImpactLocation
from zentao_analyzer.summary_report import build_summary_item
from zentao_analyzer.zentao_client import ZentaoItem


def make_provided_item(**overrides):
    defaults = dict(
        id="5932",
        type="requirement",
        title="Ecall功能的优先级定义",
        description="Ecall优先级需求正文",
        status="provided",
        requirement_source="provided_requirement",
    )
    defaults.update(overrides)
    return ZentaoItem(**defaults)


def make_zentao_item(**overrides):
    item = MagicMock()
    defaults = dict(
        id="5939",
        type="requirement",
        title="Test Title",
        description="Desc",
        status="active",
        priority="1",
        project="",
        product="41",
        execution="",
        assigned_to="dev",
        created_by="pm",
        created_date="2026-05-20",
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def make_argv_provided_req(req_file, item_id="5932", title="Ecall标题", module="requirement", output_root=".", extra=None):
    base = [
        "zentao_analyzer.main.py",
        "--module", module,
        "--id", item_id,
        "--title", title,
        "--requirement-file", req_file,
        "--analyze",
        "--repo-path", ".",
        "--output-root", output_root,
        "--quiet",
    ]
    if extra:
        base.extend(extra)
    return base


class TestValidateProvidedRequirementArgs(unittest.TestCase):
    def test_no_requirement_file_is_ok(self):
        args = MagicMock(requirement_file=None, title=None, id="1", module="requirement", login=False, server=None, user=None, password=None, token=None, project=None, product=None, execution=None)
        self.assertIsNone(main._validate_provided_requirement_args(args))

    def test_title_without_requirement_file_rejected(self):
        args = MagicMock(requirement_file=None, title="标题", id="1", module="requirement", login=False, server=None, user=None, password=None, token=None, project=None, product=None, execution=None)
        result = main._validate_provided_requirement_args(args)
        self.assertIn("--title", result)

    def test_requirement_file_needs_id(self):
        args = MagicMock(requirement_file="/tmp/req.txt", title="标题", id=None, module="requirement", login=False, server=None, user=None, password=None, token=None, project=None, product=None, execution=None)
        result = main._validate_provided_requirement_args(args)
        self.assertIn("--id", result)

    def test_requirement_file_needs_title(self):
        args = MagicMock(requirement_file="/tmp/req.txt", title=None, id="5932", module="requirement", login=False, server=None, user=None, password=None, token=None, project=None, product=None, execution=None)
        result = main._validate_provided_requirement_args(args)
        self.assertIn("--title", result)

    def test_requirement_file_rejects_bug_module(self):
        args = MagicMock(requirement_file="/tmp/req.txt", title="标题", id="1", module="bug", login=False, server=None, user=None, password=None, token=None, project=None, product=None, execution=None)
        result = main._validate_provided_requirement_args(args)
        self.assertIn("story 或 requirement", result)

    def test_requirement_file_rejects_login(self):
        args = MagicMock(requirement_file="/tmp/req.txt", title="标题", id="1", module="requirement", login=True, server=None, user=None, password=None, token=None, project=None, product=None, execution=None)
        result = main._validate_provided_requirement_args(args)
        self.assertIn("--login", result)

    def test_requirement_file_rejects_zentao_auth_params(self):
        for param, value in [("server", "http://x"), ("user", "admin"), ("password", "pw"), ("token", "tok")]:
            kwargs = {param: value}
            args = MagicMock(requirement_file="/tmp/req.txt", title="标题", id="1", module="requirement", login=False, **kwargs)
            result = main._validate_provided_requirement_args(args)
            self.assertIn("禅道", result)

    def test_requirement_file_rejects_limit(self):
        args = MagicMock(requirement_file="/tmp/req.txt", title="标题", id="1", module="requirement", login=False, server=None, user=None, password=None, token=None, product=None, execution=None, limit=10)
        result = main._validate_provided_requirement_args(args)
        self.assertIn("--limit", result)

    def test_requirement_file_rejects_list_filter_params(self):
        args = MagicMock(
            requirement_file="/tmp/req.txt", title="标题", id="1",
            module="requirement", login=False, server=None, user=None,
            password=None, token=None, product="9", execution=None, limit=None,
        )
        self.assertIn("--product", main._validate_provided_requirement_args(args))
        args.product = None
        args.execution = "10"
        self.assertIn("--execution", main._validate_provided_requirement_args(args))
        args.execution = None
        self.assertIn("--project", main._validate_provided_requirement_args(args, ["--project", "1"]))
        self.assertIn("--status", main._validate_provided_requirement_args(args, ["--status=open"]))


class TestLoadProvidedRequirement(unittest.TestCase):
    def test_loads_file_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("  需求正文内容  \n\n")
            f.flush()
            args = MagicMock(requirement_file=f.name, id="5932", module="requirement", title="标题")
            item, error = main._load_provided_requirement(args)
            os.unlink(f.name)
        self.assertIsNone(error)
        self.assertIsNotNone(item)
        self.assertEqual(item.id, "5932")
        self.assertEqual(item.type, "requirement")
        self.assertEqual(item.title, "标题")
        self.assertEqual(item.description, "需求正文内容")
        self.assertEqual(item.requirement_source, "provided_requirement")
        self.assertEqual(item.status, "provided")

    def test_empty_file_rejected(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("   \n  \n  ")
            f.flush()
            args = MagicMock(requirement_file=f.name, id="5932", module="requirement", title="标题")
            item, error = main._load_provided_requirement(args)
            os.unlink(f.name)
        self.assertIsNone(item)
        self.assertIn("内容为空", error)

    def test_nonexistent_file_rejected(self):
        args = MagicMock(requirement_file="/nonexistent/file.txt", id="5932", module="requirement", title="标题")
        item, error = main._load_provided_requirement(args)
        self.assertIsNone(item)
        self.assertIn("无法读取", error)


class TestProvidedRequirementMainFlow(unittest.TestCase):
    def test_provided_requirement_skips_zentao_fetch(self):
        with tempfile.TemporaryDirectory() as td:
            req_file = os.path.join(td, "requirement.txt")
            with open(req_file, "w", encoding="utf-8") as f:
                f.write("Ecall优先级需求正文")

            mock_analysis = AnalysisResult(
                item_id="5932",
                item_type="requirement",
                item_title="Ecall标题",
                conclusion="完成",
                evidence=[],
                gaps=[],
                recommendations=[],
                verification=[],
                priority="高",
                confidence="高",
                requirement_source="provided_requirement",
            )

            argv = [
                "zentao_analyzer.main.py",
                "--module", "requirement",
                "--id", "5932",
                "--title", "Ecall标题",
                "--requirement-file", req_file,
                "--analyze",
                "--repo-path", td,
                "--output-root", td,
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item") as mock_get, \
                 patch.object(main.ZentaoClient, "list_items") as mock_list, \
                 patch("zentao_analyzer.main.analyze", return_value=mock_analysis), \
                 patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    main.main()

            mock_get.assert_not_called()
            mock_list.assert_not_called()
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["analysis"][0]["requirement_source"], "provided_requirement")

    def test_provided_requirement_log_records_only_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            sensitive_body = "机密需求正文-不得进入运行日志"
            req_file = os.path.join(td, "requirement.txt")
            log_file = os.path.join(td, "run.jsonl")
            with open(req_file, "w", encoding="utf-8") as f:
                f.write(sensitive_body)
            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5932",
                "--title", "Ecall标题", "--requirement-file", req_file,
                "--log-file", log_file, "--quiet",
            ]
            with patch.object(sys, "argv", argv):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main.main(), 0)
            with open(log_file, encoding="utf-8") as f:
                logs = f.read()
            self.assertNotIn(sensitive_body, logs)
            self.assertNotIn(sensitive_body[:10], logs)
            self.assertIn('"desc_length"', logs)

    def test_timeout_retry_preserves_provided_requirement_options(self):
        with tempfile.TemporaryDirectory() as td:
            req_file = os.path.join(td, "requirement.txt")
            with open(req_file, "w", encoding="utf-8") as f:
                f.write("需求正文")
            failed = AnalysisResult.from_error(
                make_provided_item(), "timeout", error_kind="timeout",
            )
            argv = make_argv_provided_req(req_file, output_root=td, extra=["--no-debug-bundle"])
            with patch("zentao_analyzer.main.analyze", return_value=failed), \
                 patch.object(sys, "argv", argv):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                    main.main()
            retry_output = stderr.getvalue()
            self.assertIn("--requirement-file", retry_output)
            self.assertIn(req_file, retry_output)
            self.assertIn("--title", retry_output)
    def test_provided_requirement_no_id_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            req_file = os.path.join(td, "req.txt")
            with open(req_file, "w") as f:
                f.write("content")
            argv = [
                "zentao_analyzer.main.py",
                "--module", "requirement",
                "--title", "标题",
                "--requirement-file", req_file,
                "--analyze",
                "--repo-path", td,
                "--output-root", td,
            ]
            with patch.object(sys, "argv", argv):
                code = main.main()
            self.assertEqual(code, 4)

    def test_existing_zentao_id_mode_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="5939", type="requirement", title="Test Title", description="Desc", status="active", priority="1")
            mock_analysis = AnalysisResult(
                item_id="5939",
                item_type="requirement",
                item_title="Test Title",
                conclusion="完成",
                evidence=["src/a.c:1-1 ok"],
                priority="高",
                confidence="高",
            )

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item) as mock_get, \
                 patch("zentao_analyzer.main.analyze", return_value=mock_analysis), \
                 patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    main.main()

            mock_get.assert_called_once()
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["analysis"][0]["requirement_source"], "zentao")


class TestZentaoItemRequirementSource(unittest.TestCase):
    def test_default_source_is_zentao(self):
        item = ZentaoItem(id="1", type="story", title="T")
        self.assertEqual(item.requirement_source, "zentao")

    def test_provided_requirement_source(self):
        item = ZentaoItem(id="1", type="requirement", title="T", requirement_source="provided_requirement")
        self.assertEqual(item.requirement_source, "provided_requirement")


class TestRichContentInOutput(unittest.TestCase):
    def test_feature_analysis_includes_rich_content_fields(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="100", type="requirement", title="RT", description="desc", requirement_source="provided_requirement")
            interp = RequirementInterpretation(
                summary="摘要",
                scope=[InterpretationEntry(text="范围1", source="requirement")],
                pending_confirmations=["待确认项"],
            )
            code_impact = CodeImpactAnalysis(
                related_locations=[CodeImpactLocation(component="模块A", path=os.path.join(td, "a.c"), line_start=1, line_end=1, symbol="a", reason="相关")],
                impact_notes=["影响说明"],
            )
            analysis = AnalysisResult(
                item_id="100", item_type="requirement", item_title="RT",
                conclusion="完成", evidence=[], confidence="高",
                requirement_source="provided_requirement",
                requirement_interpretation=interp,
                code_impact=code_impact,
            )
            doc_mock = MagicMock()
            doc_mock.document_type = "PRD"
            doc_mock.document_path = "docs/prd/a.md"
            doc_mock.is_diagnostic = False
            doc_mock.error = ""
            summary = build_summary_item(item, analysis, doc_mock, {"supported": False})
            self.assertEqual(summary["requirement_source"], "provided_requirement")
            self.assertEqual(summary["code_impact_location_count"], 1)
            self.assertTrue(summary["has_pending_requirement_confirmation"])

    def test_defect_analysis_omits_rich_content_fields(self):
        item = ZentaoItem(id="200", type="bug", title="Bug")
        analysis = AnalysisResult(item_id="200", item_type="bug", item_title="Bug", conclusion="已定位")
        doc_mock = MagicMock()
        doc_mock.document_type = "ISSUE"
        doc_mock.document_path = "docs/issue/b.md"
        doc_mock.is_diagnostic = False
        doc_mock.error = ""
        summary = build_summary_item(item, analysis, doc_mock, {"supported": False})
        self.assertEqual(summary["requirement_source"], "zentao")
        self.assertNotIn("code_impact_location_count", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
