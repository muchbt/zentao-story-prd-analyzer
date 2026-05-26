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
from zentao_analyzer.analysis_result import (
    AnalysisResult,
    EvidenceLocation,
    EvidenceValidationIssue,
    RequirementPoint,
    RPStatus,
    aggregate_evidence_from_rps,
    aggregate_evidence_text_from_rps,
    compute_item_conclusion,
    compute_item_confidence,
    compute_item_gaps,
    correct_invalidated_rps,
    parse_requirement_points,
    validate_requirement_points,
    validate_rp_evidence_locations,
)
from zentao_analyzer.document_generator import generate_document
from zentao_analyzer.summary_report import build_summary_item
from zentao_analyzer.zentao_client import ZentaoItem


def make_item(**overrides):
    item = MagicMock()
    defaults = dict(
        id="5939", type="requirement", title="Test Title",
        description="Desc", status="active", priority="1",
        project="", product="41", execution="",
        assigned_to="dev", created_by="pm", created_date="2026-05-20",
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def make_analysis_with_rps(rps, **overrides):
    analysis = AnalysisResult(
        item_id=overrides.pop("item_id", "5939"),
        item_type=overrides.pop("item_type", "requirement"),
        item_title=overrides.pop("item_title", "Test Title"),
        requirement_points=rps,
        analysis_status=overrides.pop("analysis_status", ""),
        **overrides,
    )
    return analysis


class TestRequirementPointModel(unittest.TestCase):
    def test_parse_requirement_points_basic(self):
        data = [
            {"description": "MCU 上报状态", "status": "完成", "reason": "已找到", "gaps": [], "evidence": [{"path": "src/a.c", "line_start": 1, "line_end": 3, "symbol": "report", "reason": "上报逻辑"}]},
            {"description": "SOC 接收状态", "status": "无法判断", "reason": "无代码证据", "gaps": [], "evidence": []},
        ]
        rps, has_malformed, rp_ids_with_invalid_evidence = parse_requirement_points(data)
        self.assertEqual(len(rps), 2)
        self.assertEqual(rps[0].id, "RP-001")
        self.assertEqual(rps[0].description, "MCU 上报状态")
        self.assertEqual(rps[0].status, "完成")
        self.assertEqual(rps[1].id, "RP-002")
        self.assertEqual(rps[1].status, "无法判断")
        self.assertFalse(has_malformed)
        self.assertEqual(rp_ids_with_invalid_evidence, set())

    def test_parse_requirement_points_empty_input(self):
        rps, has_malformed, rp_ids_with_invalid_evidence = parse_requirement_points([])
        self.assertEqual(rps, [])
        self.assertFalse(has_malformed)
        self.assertEqual(rp_ids_with_invalid_evidence, set())

    def test_parse_requirement_points_non_list(self):
        rps, has_malformed, rp_ids_with_invalid_evidence = parse_requirement_points("not a list")
        self.assertEqual(rps, [])
        self.assertTrue(has_malformed)
        self.assertEqual(rp_ids_with_invalid_evidence, set())

    def test_validate_requirement_points_valid(self):
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="完成", reason="ok", gaps=[], evidence=[]),
            RequirementPoint(id="RP-002", description="功能B", status="未完成", reason="缺失", gaps=["缺少实现"], evidence=[]),
        ]
        result = validate_requirement_points(rps)
        self.assertTrue(result.valid)
        self.assertEqual(len(result.requirement_points), 2)

    def test_validate_empty_requirement_points(self):
        result = validate_requirement_points([])
        self.assertFalse(result.valid)
        self.assertEqual(result.failure_reason, "empty_requirement_points")

    def test_validate_duplicate_description(self):
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="完成", reason="ok", gaps=[], evidence=[]),
            RequirementPoint(id="RP-002", description="功能A", status="未完成", reason="缺失", gaps=["缺口"], evidence=[]),
        ]
        result = validate_requirement_points(rps)
        self.assertFalse(result.valid)
        self.assertEqual(result.failure_reason, "invalid_requirement_point_schema")

    def test_validate_invalid_status(self):
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="invalid", reason="ok", gaps=[], evidence=[]),
        ]
        result = validate_requirement_points(rps)
        self.assertFalse(result.valid)
        self.assertEqual(result.failure_reason, "invalid_requirement_point_schema")

    def test_validate_gaps_contract_not_completed_without_gaps_is_invalid(self):
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="未完成", reason="缺失", gaps=[], evidence=[]),
        ]
        result = validate_requirement_points(rps)
        self.assertFalse(result.valid)
        self.assertEqual(result.failure_reason, "invalid_point_gap_state_combination")

    def test_validate_completed_with_gaps_is_invalid(self):
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="完成", reason="ok", gaps=["不应存在的缺口"], evidence=[]),
        ]
        result = validate_requirement_points(rps)
        self.assertFalse(result.valid)
        self.assertEqual(result.failure_reason, "invalid_point_gap_state_combination")

    def test_validate_empty_description(self):
        rps = [
            RequirementPoint(id="RP-001", description="", status="完成", reason="ok", gaps=[], evidence=[]),
        ]
        result = validate_requirement_points(rps)
        self.assertFalse(result.valid)
        self.assertEqual(result.failure_reason, "invalid_requirement_point_schema")


class TestComputeConclusion(unittest.TestCase):
    def test_all_completed(self):
        rps = [RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[], evidence=[])]
        self.assertEqual(compute_item_conclusion(rps), "完成")

    def test_partial_completion(self):
        rps = [
            RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[], evidence=[]),
            RequirementPoint(id="RP-002", description="B", status="未完成", reason="", gaps=["缺口1"], evidence=[]),
        ]
        self.assertEqual(compute_item_conclusion(rps), "部分完成")

    def test_all_not_completed(self):
        rps = [
            RequirementPoint(id="RP-001", description="A", status="未完成", reason="", gaps=["缺口1"], evidence=[]),
        ]
        self.assertEqual(compute_item_conclusion(rps), "未完成")

    def test_indeterminate(self):
        rps = [
            RequirementPoint(id="RP-001", description="A", status="无法判断", reason="", gaps=[], evidence=[]),
        ]
        self.assertEqual(compute_item_conclusion(rps), "无法判断")

    def test_mixed_confirmed_gaps_and_indeterminate(self):
        rps = [
            RequirementPoint(id="RP-001", description="A", status="部分完成", reason="", gaps=["缺口1"], evidence=[]),
            RequirementPoint(id="RP-002", description="B", status="无法判断", reason="", gaps=[], evidence=[]),
        ]
        self.assertEqual(compute_item_conclusion(rps), "部分完成")

    def test_empty_rps(self):
        self.assertEqual(compute_item_conclusion([]), "无法判断")


class TestComputeConfidence(unittest.TestCase):
    def test_high_confidence(self):
        rps = [RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[])]
        self.assertEqual(compute_item_confidence(rps), "高")

    def test_low_confidence_indeterminate(self):
        rps = [RequirementPoint(id="RP-001", description="A", status="无法判断", reason="", gaps=[])]
        self.assertEqual(compute_item_confidence(rps), "低")

    def test_low_confidence_invalid_evidence(self):
        rps = [RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[])]
        self.assertEqual(compute_item_confidence(rps, has_invalid_evidence=True), "低")

    def test_medium_confidence_fallback(self):
        rps = [RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[])]
        self.assertEqual(compute_item_confidence(rps, has_fallback_evidence=True), "中")


class TestComputeGaps(unittest.TestCase):
    def test_gaps_with_rp_id(self):
        rps = [
            RequirementPoint(id="RP-001", description="A", status="未完成", reason="", gaps=["缺少实现", "接口不匹配"]),
            RequirementPoint(id="RP-002", description="B", status="完成", reason="", gaps=[]),
        ]
        gaps = compute_item_gaps(rps)
        self.assertEqual(gaps, ["RP-001: 缺少实现", "RP-001: 接口不匹配"])


class TestAggregateEvidence(unittest.TestCase):
    def test_deduplication(self):
        loc = EvidenceLocation(path="src/a.c", line_start=1, line_end=10, symbol="foo", reason="bar")
        rps = [
            RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[], evidence=[loc]),
            RequirementPoint(id="RP-002", description="B", status="完成", reason="", gaps=[], evidence=[loc]),
        ]
        aggregated = aggregate_evidence_from_rps(rps)
        self.assertEqual(len(aggregated), 1)

    def test_same_location_supports_multiple_rps(self):
        loc1 = EvidenceLocation(path="src/a.c", line_start=1, line_end=10, symbol="foo", reason="supports A")
        loc2 = EvidenceLocation(path="src/a.c", line_start=1, line_end=10, symbol="foo", reason="supports B")
        rps = [
            RequirementPoint(id="RP-001", description="A", status="完成", reason="", gaps=[], evidence=[loc1]),
            RequirementPoint(id="RP-002", description="B", status="完成", reason="", gaps=[], evidence=[loc2]),
        ]
        aggregated = aggregate_evidence_from_rps(rps)
        self.assertEqual(len(aggregated), 1)


class TestCorrectInvalidatedRps(unittest.TestCase):
    def test_invalid_evidence_corrects_rp_and_clears_evidence(self):
        rps = [
            RequirementPoint(id="RP-001", description="A", status="完成", reason="找到了", gaps=[], evidence=[
                EvidenceLocation(path="/outside/a.c", line_start=1, line_end=1, symbol="x", reason="test"),
            ]),
        ]
        issues = [("RP-001", [EvidenceValidationIssue(path="/outside/a.c", line_start=1, line_end=1, reason="outside_repo")])]
        corrected, unique_issues, invalid_count = correct_invalidated_rps(rps, issues)
        self.assertEqual(corrected[0].status, "无法判断")
        self.assertEqual(corrected[0]._original_status, "完成")
        self.assertEqual(corrected[0]._correction_reason, "evidence_location_validation_failed")
        self.assertEqual(corrected[0].gaps, [])
        self.assertEqual(corrected[0].evidence, [])
        self.assertEqual(invalid_count, 1)


class TestCorrectRpsWithoutValidEvidence(unittest.TestCase):
    def test_completed_without_evidence_is_corrected(self):
        from zentao_analyzer.analysis_result import correct_rps_without_valid_evidence
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="完成", reason="已实现", gaps=[], evidence=[]),
        ]
        rps = correct_rps_without_valid_evidence(rps)
        self.assertEqual(rps[0].status, "无法判断")
        self.assertEqual(rps[0].gaps, [])

    def test_completed_with_evidence_is_kept(self):
        from zentao_analyzer.analysis_result import correct_rps_without_valid_evidence
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="完成", reason="已实现", gaps=[], evidence=[
                EvidenceLocation(path="src/a.c", line_start=1, line_end=10, symbol="foo", reason="bar"),
            ]),
        ]
        rps = correct_rps_without_valid_evidence(rps)
        self.assertEqual(rps[0].status, "完成")

    def test_indeterminate_without_evidence_is_unchanged(self):
        from zentao_analyzer.analysis_result import correct_rps_without_valid_evidence
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="无法判断", reason="无代码证据", gaps=[], evidence=[]),
        ]
        rps = correct_rps_without_valid_evidence(rps)
        self.assertEqual(rps[0].status, "无法判断")

    def test_not_completed_without_evidence_is_corrected(self):
        from zentao_analyzer.analysis_result import correct_rps_without_valid_evidence
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="未完成", reason="缺失", gaps=["缺口1"], evidence=[]),
        ]
        rps = correct_rps_without_valid_evidence(rps)
        self.assertEqual(rps[0].status, "无法判断")
        self.assertEqual(rps[0].gaps, [])


class TestBuildSummaryItemWithRPs(unittest.TestCase):
    def test_feature_item_with_rps(self):
        item = ZentaoItem(id="1", type="story", title="T")
        rps = [
            RequirementPoint(id="RP-001", description="功能A", status="完成", reason="已实现", gaps=[], evidence=[]),
            RequirementPoint(id="RP-002", description="功能B", status="无法判断", reason="无代码证据", gaps=[], evidence=[]),
        ]
        analysis = AnalysisResult(
            item_id="1", item_type="story", item_title="T",
            conclusion="部分完成", confidence="低", requirement_points=rps,
        )
        doc = MagicMock()
        doc.document_type = "PRD"
        doc.document_path = "docs/prd/a.md"
        doc.is_diagnostic = False
        doc.error = ""
        data = build_summary_item(item, analysis, doc, {"supported": False})
        self.assertEqual(data["requirement_point_count"], 2)
        self.assertEqual(data["requirement_point_status_counts"]["完成"], 1)
        self.assertEqual(data["requirement_point_status_counts"]["无法判断"], 1)
        self.assertTrue(data["has_unconfirmed_requirement_points"])

    def test_feature_item_unavailable(self):
        item = ZentaoItem(id="1", type="story", title="T")
        analysis = AnalysisResult(
            item_id="1", item_type="story", item_title="T",
            conclusion="无法判断", confidence="低", analysis_status="requirement_points_unavailable",
            analysis_status_detail="empty_requirement_points",
        )
        doc = MagicMock()
        doc.document_type = "PRD"
        doc.document_path = "docs/prd/a.md"
        doc.is_diagnostic = True
        doc.error = ""
        data = build_summary_item(item, analysis, doc, {"supported": False})
        self.assertNotIn("requirement_point_count", data)
        self.assertNotIn("requirement_point_status_counts", data)
        self.assertTrue(data["has_unconfirmed_requirement_points"])
        self.assertEqual(data["analysis_status"], "requirement_points_unavailable")

    def test_defect_item_no_rp_fields(self):
        item = ZentaoItem(id="2", type="bug", title="B")
        analysis = AnalysisResult(
            item_id="2", item_type="bug", item_title="B",
            conclusion="已定位", confidence="高",
        )
        doc = MagicMock()
        doc.document_type = "ISSUE"
        doc.document_path = "docs/issue/a.md"
        doc.is_diagnostic = False
        doc.error = ""
        data = build_summary_item(item, analysis, doc, {"supported": False})
        self.assertNotIn("requirement_point_count", data)
        self.assertNotIn("analysis_status", data)


class TestDocumentGeneratorWithRPs(unittest.TestCase):
    def test_prd_includes_requirement_points_table(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="1", type="story", title="状态上报", description="MCU 上报状态", status="active")
            rps = [
                RequirementPoint(id="RP-001", description="MCU 上报指定状态", status="完成", reason="已找到对应上报逻辑", gaps=[], evidence=[]),
                RequirementPoint(id="RP-002", description="SOC 接收并更新状态", status="无法判断", reason="无代码证据", gaps=[], evidence=[]),
            ]
            analysis = AnalysisResult(
                item_id="1", item_type="story", item_title="状态上报",
                conclusion="部分完成", confidence="低",
                evidence=["相关代码证据不足"],
                gaps=["RP-002: 无代码证据"],
                requirement_points=rps,
            )
            doc = generate_document(item, analysis, output_root=td, generated_at="2026-05-26T10:00:00+08:00")
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("## 需求点完成情况", content)
            self.assertIn("RP-001", content)
            self.assertIn("MCU 上报指定状态", content)
            self.assertIn("RP-002", content)
            self.assertIn("无法判断", content)

    def test_prd_no_rp_table_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="2", type="story", title="简单需求", description="Desc", status="active")
            analysis = AnalysisResult(
                item_id="2", item_type="story", item_title="简单需求",
                conclusion="完成", confidence="高", requirement_points=[],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("## 需求点完成情况", content)

    def test_prd_gaps_with_rp_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="3", type="story", title="需求3", description="Desc", status="active")
            rps = [
                RequirementPoint(id="RP-001", description="功能A", status="未完成", reason="", gaps=["缺少实现"], evidence=[]),
            ]
            analysis = AnalysisResult(
                item_id="3", item_type="story", item_title="需求3",
                conclusion="未完成", confidence="高",
                gaps=["RP-001: 缺少实现"],
                requirement_points=rps,
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("RP-001: 缺少实现", content)


class TestAnalyzerFeatureIntegration(unittest.TestCase):
    def test_feature_with_rps_in_main_flow(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            rps = [
                RequirementPoint(id="RP-001", description="功能A", status="完成", reason="已实现", gaps=[], evidence=[]),
                RequirementPoint(id="RP-002", description="功能B", status="无法判断", reason="无代码证据", gaps=[], evidence=[]),
            ]
            mock_analysis = MagicMock()
            mock_analysis.item_id = "5939"
            mock_analysis.item_type = "requirement"
            mock_analysis.item_title = "Test Title"
            mock_analysis.conclusion = "部分完成"
            mock_analysis.evidence = ["相关代码证据不足"]
            mock_analysis.gaps = ["RP-002: 无代码证据"]
            mock_analysis.suspected_causes = []
            mock_analysis.affected_scope = []
            mock_analysis.recommendations = []
            mock_analysis.verification = []
            mock_analysis.priority = "高"
            mock_analysis.confidence = "低"
            mock_analysis.understanding_summary = "测试需求理解"
            mock_analysis.error = ""
            mock_analysis.error_kind = ""
            mock_analysis.raw_response = "{}"
            mock_analysis.cited_evidence_locations = []
            mock_analysis.seed_locations = []
            mock_analysis.rejected_seed_paths = []
            mock_analysis.evidence_validation_issues = []
            mock_analysis.is_insufficient_evidence.return_value = False
            mock_analysis.requirement_points = rps
            mock_analysis.analysis_status = ""

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=mock_analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            parsed = json.loads(stdout.getvalue())
            rp_data = parsed["analysis"][0]["requirement_points"]
            self.assertEqual(len(rp_data), 2)
            self.assertEqual(rp_data[0]["id"], "RP-001")
            self.assertEqual(rp_data[0]["status"], "完成")
            self.assertNotIn("analysis_status", parsed["analysis"][0])

    def test_feature_rp_unavailable_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            mock_analysis = MagicMock()
            mock_analysis.item_id = "5939"
            mock_analysis.item_type = "requirement"
            mock_analysis.item_title = "Test Title"
            mock_analysis.conclusion = "无法判断"
            mock_analysis.evidence = []
            mock_analysis.gaps = []
            mock_analysis.suspected_causes = []
            mock_analysis.affected_scope = []
            mock_analysis.recommendations = []
            mock_analysis.verification = []
            mock_analysis.priority = ""
            mock_analysis.confidence = "低"
            mock_analysis.understanding_summary = ""
            mock_analysis.error = ""
            mock_analysis.error_kind = ""
            mock_analysis.raw_response = "{}"
            mock_analysis.cited_evidence_locations = []
            mock_analysis.seed_locations = []
            mock_analysis.rejected_seed_paths = []
            mock_analysis.evidence_validation_issues = []
            mock_analysis.is_insufficient_evidence.return_value = False
            mock_analysis.requirement_points = []
            mock_analysis.analysis_status = "requirement_points_unavailable"
            mock_analysis.analysis_status_detail = "empty_requirement_points"

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=mock_analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            code = main.main()
            self.assertEqual(code, 1)
            parsed = json.loads(stdout.getvalue())
            self.assertNotIn("requirement_points", parsed["analysis"][0])
            self.assertNotIn("conclusion", parsed["analysis"][0])
            self.assertNotIn("gaps", parsed["analysis"][0])
            self.assertEqual(parsed["analysis"][0]["analysis_status"], "requirement_points_unavailable")
            self.assertEqual(parsed["analysis"][0]["analysis_status_detail"], "empty_requirement_points")
            self.assertEqual(parsed["analysis"][0]["recommended_action"], "update_zentao_requirement")

    def test_feature_parse_error_does_not_output_empty_requirement_points(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            mock_analysis = AnalysisResult.from_error(
                item,
                "LLM 返回非 JSON",
                error_kind="parse",
            )

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=mock_analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            parsed = json.loads(stdout.getvalue())
            self.assertNotIn("requirement_points", parsed["analysis"][0])

    def test_feature_schema_failure_recommends_manual_retry(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item()
            mock_analysis = AnalysisResult(
                item_id="5939",
                item_type="requirement",
                item_title="Test Title",
                analysis_status="requirement_points_unavailable",
                analysis_status_detail="invalid_requirement_point_schema",
            )

            argv = [
                "zentao_analyzer.main.py", "--module", "requirement", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=mock_analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["analysis"][0]["recommended_action"], "manual_retry")

    def test_defect_item_no_rp_in_output(self):
        with tempfile.TemporaryDirectory() as td:
            item = make_item(type="bug")
            mock_analysis = MagicMock()
            mock_analysis.item_id = "5939"
            mock_analysis.item_type = "bug"
            mock_analysis.item_title = "Test Bug"
            mock_analysis.conclusion = "已定位"
            mock_analysis.evidence = ["src/a.c:1-3"]
            mock_analysis.gaps = []
            mock_analysis.suspected_causes = ["空指针"]
            mock_analysis.affected_scope = []
            mock_analysis.recommendations = []
            mock_analysis.verification = []
            mock_analysis.priority = "中"
            mock_analysis.confidence = "高"
            mock_analysis.understanding_summary = ""
            mock_analysis.error = ""
            mock_analysis.error_kind = ""
            mock_analysis.raw_response = "{}"
            mock_analysis.cited_evidence_locations = []
            mock_analysis.seed_locations = []
            mock_analysis.rejected_seed_paths = []
            mock_analysis.evidence_validation_issues = []
            mock_analysis.is_insufficient_evidence.return_value = False
            mock_analysis.requirement_points = []
            mock_analysis.analysis_status = ""

            argv = [
                "zentao_analyzer.main.py", "--module", "bug", "--id", "5939",
                "--analyze", "--repo-path", td, "--output-root", td, "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", return_value=mock_analysis):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            main.main()

            parsed = json.loads(stdout.getvalue())
            self.assertNotIn("requirement_points", parsed["analysis"][0])
            self.assertNotIn("analysis_status", parsed["analysis"][0])
            self.assertIn("conclusion", parsed["analysis"][0])


class TestFeaturePromptPhase6(unittest.TestCase):
    def test_feature_prompt_contains_requirement_points_schema(self):
        from zentao_analyzer.prompts import build_feature_prompt
        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("requirement_points", prompt)
        self.assertIn("description", prompt)
        self.assertIn("可独立验证的需求点描述", prompt)
        self.assertNotIn('"conclusion": "完成', prompt)

    def test_defect_prompt_unchanged(self):
        from zentao_analyzer.prompts import build_defect_prompt
        item = ZentaoItem(id="2", type="bug", title="B", description="D", status="active")
        prompt = build_defect_prompt(item, repo_path="/repo")
        self.assertIn("conclusion", prompt)
        self.assertIn("已定位|部分定位|无法定位", prompt)
        self.assertNotIn("requirement_points", prompt)


class TestAnalyzerFeatureCorrection(unittest.TestCase):
    def test_completed_rp_without_evidence_corrected_to_indeterminate(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="1", type="story", title="T")
        data = {
            "requirement_points": [
                {"description": "功能A", "status": "完成", "reason": "已实现", "gaps": [], "evidence": []},
            ],
            "understanding_summary": "理解需求",
            "priority": "高",
        }
        result = _analyze_feature(item, data, "", ".", [], [])
        self.assertEqual(result.requirement_points[0].status, "无法判断")
        self.assertEqual(result.analysis_status, "")
        self.assertEqual(result.confidence, "低")

    def test_gap_state_conflict_marks_unavailable(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="2", type="story", title="T")
        data = {
            "requirement_points": [
                {"description": "功能A", "status": "未完成", "reason": "缺失", "gaps": [], "evidence": []},
            ],
            "understanding_summary": "",
        }
        result = _analyze_feature(item, data, "", ".", [], [])
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")
        self.assertEqual(result.analysis_status_detail, "invalid_point_gap_state_combination")

    def test_completed_with_gaps_marks_unavailable(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="3", type="story", title="T")
        data = {
            "requirement_points": [
                {"description": "功能A", "status": "完成", "reason": "ok", "gaps":["不应有的缺口"], "evidence": [{"path":"a.c","line_start":1,"line_end":1}]},
            ],
            "understanding_summary": "",
        }
        result = _analyze_feature(item, data, "", ".", [], [])
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")
        self.assertEqual(result.analysis_status_detail, "invalid_point_gap_state_combination")

    def test_malformed_items_in_requirement_points_marks_unavailable(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="6", type="story", title="T")
        data = {
            "requirement_points": [
                {"description": "功能A", "status": "完成", "reason": "ok", "gaps": [], "evidence": []},
                "不是一个对象",
            ],
            "understanding_summary": "",
        }
        result = _analyze_feature(item, data, "", ".", [], [])
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")
        self.assertEqual(result.analysis_status_detail, "invalid_requirement_point_schema")

    def test_non_string_description_marks_unavailable(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="10", type="story", title="T")
        data = {
            "requirement_points": [
                {"description": None, "status": "完成", "reason": "ok", "gaps": [], "evidence": []},
            ],
        }
        result = _analyze_feature(item, data, "", ".", [], [])
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")
        self.assertEqual(result.analysis_status_detail, "invalid_requirement_point_schema")

    def test_invalid_evidence_object_downgrades_rp(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="7", type="story", title="T")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已找到", "gaps": [], "evidence": [
                        {"path": src, "line_start": 1, "line_end": 1},
                        {"path": "", "line_start": 0, "line_end": 0},
                    ]},
                ],
                "understanding_summary": "",
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(result.analysis_status, "")
        self.assertEqual(result.requirement_points[0].status, "无法判断")
        self.assertEqual(result.requirement_points[0].evidence, [])
        self.assertEqual(result.confidence, "低")
        self.assertEqual(len(result.evidence_validation_issues), 1)
        self.assertEqual(result.evidence_validation_issues[0].reason, "invalid_evidence_object")
        self.assertEqual(result.evidence_validation_issues[0].requirement_point_ids, ["RP-001"])

    def test_shared_invalid_evidence_location_keeps_affected_point_ids(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="11", type="story", title="T")
        with tempfile.TemporaryDirectory() as td:
            missing = os.path.join(td, "missing.c")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已找到", "gaps": [], "evidence": [{"path": missing, "line_start": 1, "line_end": 1}]},
                    {"description": "功能B", "status": "完成", "reason": "已找到", "gaps": [], "evidence": [{"path": missing, "line_start": 1, "line_end": 1}]},
                ],
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(len(result.evidence_validation_issues), 1)
        self.assertEqual(
            result.evidence_validation_issues[0].requirement_point_ids,
            ["RP-001", "RP-002"],
        )

    def test_optional_null_text_fields_are_not_rendered_as_none(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="12", type="story", title="T")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已实现", "gaps": [], "evidence": [{"path": src, "line_start": 1, "line_end": 1}]},
                ],
                "priority": None,
                "understanding_summary": None,
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(result.priority, "")
        self.assertEqual(result.understanding_summary, "")

    def test_string_evidence_parsed_as_fallback(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="9", type="story", title="T")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已实现", "gaps": [], "evidence": [
                        f"{src}:1-1 支持该结论",
                    ]},
                ],
                "understanding_summary": "",
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(result.analysis_status, "")
        self.assertEqual(result.requirement_points[0].status, "完成")
        self.assertEqual(len(result.requirement_points[0].evidence), 1)
        self.assertEqual(result.requirement_points[0].evidence[0].source, "fallback")
        self.assertEqual(result.confidence, "中")

    def test_mixed_not_completed_and_indeterminate_is_partially_completed(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="8", type="story", title="T")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "未完成", "reason": "缺失", "gaps": ["缺少实现"], "evidence": [{"path": src, "line_start": 1, "line_end": 1}]},
                    {"description": "功能B", "status": "无法判断", "reason": "无证据", "gaps": [], "evidence": []},
                ],
                "understanding_summary": "",
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(result.conclusion, "部分完成")

    def test_old_format_response_marks_unavailable(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="4", type="story", title="T")
        data = {"conclusion": "完成", "evidence": [], "confidence": "高"}
        result = _analyze_feature(item, data, "", ".", [], [])
        self.assertEqual(result.analysis_status, "requirement_points_unavailable")
        self.assertEqual(result.conclusion, "")
        self.assertEqual(result.gaps, [])

    def test_valid_rps_with_evidence_produce_conclusion(self):
        from zentao_analyzer.analyzer import _analyze_feature
        item = ZentaoItem(id="5", type="story", title="T")
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.c")
            with open(src, "w") as f:
                f.write("int a;\n")
            data = {
                "requirement_points": [
                    {"description": "功能A", "status": "完成", "reason": "已实现", "gaps": [], "evidence": [{"path": src, "line_start": 1, "line_end": 1, "symbol": "a", "reason": "实现"}]},
                ],
                "understanding_summary": "理解",
                "priority": "高",
            }
            result = _analyze_feature(item, data, "", td, [], [])
        self.assertEqual(result.conclusion, "完成")
        self.assertEqual(result.analysis_status, "")
        self.assertEqual(len(result.requirement_points), 1)
        self.assertEqual(result.requirement_points[0].status, "完成")


if __name__ == "__main__":
    unittest.main(verbosity=2)
