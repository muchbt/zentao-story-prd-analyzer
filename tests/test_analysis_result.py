import dataclasses
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analysis_result import AnalysisResult, parse_requirement_interpretation, parse_code_impact, CodeImpactLocation, compute_item_confidence, RequirementPoint, RPStatus
from zentao_analyzer.zentao_client import ZentaoItem

class TestAnalysisResult(unittest.TestCase):
    def test_from_llm_json_full(self):
        item = ZentaoItem(id="1", type="story", title="T")
        data = {
            "conclusion": "完成",
            "evidence": ["file.c:foo()"],
            "gaps": [],
            "suspected_causes": [],
            "affected_scope": [],
            "recommendations": ["建议1"],
            "verification": ["验证1"],
            "priority": "高",
            "confidence": "高",
            "understanding_summary": "用户需要登录成功后进入首页。",
            "output_md": "# PRD",
        }
        result = AnalysisResult.from_llm_json(item, data, raw_response="raw")
        self.assertEqual(result.item_id, "1")
        self.assertEqual(result.conclusion, "完成")
        self.assertEqual(result.confidence, "高")
        self.assertEqual(result.evidence, ["file.c:foo()"])
        self.assertEqual(result.evidence_text, ["file.c:foo()"])
        self.assertEqual(result.understanding_summary, "用户需要登录成功后进入首页。")
        self.assertEqual(result.raw_response, "raw")
        self.assertFalse(hasattr(result, "output_md"))

    def test_from_llm_json_structured_evidence(self):
        item = ZentaoItem(id="6", type="story", title="T")
        data = {
            "conclusion": "完成",
            "confidence": "高",
            "evidence": [
                {
                    "path": "src/a.c",
                    "line_start": 12,
                    "line_end": 40,
                    "symbol": "Login",
                    "reason": "实现了登录",
                }
            ],
        }
        result = AnalysisResult.from_llm_json(item, data)
        self.assertEqual(result.evidence, ["src/a.c:12-40 Login 实现了登录"])
        self.assertEqual(result.evidence_text, ["src/a.c:12-40 Login 实现了登录"])
        self.assertEqual(len(result.cited_evidence_locations), 1)
        self.assertEqual(result.cited_evidence_locations[0].path, "src/a.c")
        self.assertEqual(result.cited_evidence_locations[0].line_start, 12)
        self.assertEqual(result.cited_evidence_locations[0].line_end, 40)

    def test_string_evidence_fallback_extracts_location_when_possible(self):
        item = ZentaoItem(id="7", type="bug", title="B")
        result = AnalysisResult.from_llm_json(item, {
            "conclusion": "已定位",
            "confidence": "中",
            "evidence": ["src/a.c:12-18 Login 出错"],
        })
        self.assertEqual(len(result.cited_evidence_locations), 1)
        self.assertEqual(result.cited_evidence_locations[0].path, "src/a.c")
        self.assertEqual(result.cited_evidence_locations[0].line_start, 12)
        self.assertEqual(result.cited_evidence_locations[0].line_end, 18)

    def test_string_evidence_without_line_does_not_fabricate_location(self):
        item = ZentaoItem(id="8", type="bug", title="B")
        result = AnalysisResult.from_llm_json(item, {
            "conclusion": "已定位",
            "confidence": "中",
            "evidence": ["src/a.c Login 出错"],
        })
        self.assertEqual(result.evidence, ["src/a.c Login 出错"])
        self.assertEqual(result.cited_evidence_locations, [])

    def test_from_llm_json_missing_fields(self):
        item = ZentaoItem(id="2", type="bug", title="B")
        data = {"conclusion": "已定位"}  # missing most fields
        result = AnalysisResult.from_llm_json(item, data)
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.gaps, [])
        self.assertEqual(result.confidence, "")

    def test_is_insufficient_evidence_empty_evidence(self):
        item = ZentaoItem(id="3", type="story", title="S")
        result = AnalysisResult.from_llm_json(item, {"conclusion": "完成", "evidence": []})
        self.assertTrue(result.is_insufficient_evidence())

    def test_is_insufficient_evidence_low_confidence(self):
        item = ZentaoItem(id="4", type="story", title="S")
        result = AnalysisResult.from_llm_json(item, {"conclusion": "无法判断", "confidence": "低", "evidence": []})
        self.assertTrue(result.is_insufficient_evidence())

    def test_from_error(self):
        item = ZentaoItem(id="5", type="story", title="S")
        result = AnalysisResult.from_error(item, "LLM timeout")
        self.assertEqual(result.error, "LLM timeout")
        self.assertTrue(result.is_insufficient_evidence())

    def test_from_error_preserves_provided_requirement_source(self):
        item = ZentaoItem(id="5", type="requirement", title="S", requirement_source="provided_requirement")
        result = AnalysisResult.from_error(item, "LLM timeout")
        self.assertEqual(result.requirement_source, "provided_requirement")

    def test_coerce_str_list_from_dict_items(self):
        item = ZentaoItem(id="10", type="requirement", title="R")
        data = {
            "conclusion": "部分完成",
            "confidence": "中",
            "gaps": [
                {"gap": "缺少导出功能", "module": "export"},
                "未实现批量操作",
            ],
            "suspected_causes": [{"cause": "配置缺失"}],
            "recommendations": [{"rec": "增加导出模块"}],
            "verification": [{"step": "检查导出按钮"}],
            "affected_scope": [{"scope": "用户模块"}],
        }
        result = AnalysisResult.from_llm_json(item, data)
        self.assertTrue(all(isinstance(g, str) for g in result.gaps))
        self.assertIn("缺少导出功能", result.gaps)
        self.assertIn("未实现批量操作", result.gaps)
        self.assertTrue(all(isinstance(s, str) for s in result.suspected_causes))
        self.assertTrue(all(isinstance(r, str) for r in result.recommendations))
        self.assertTrue(all(isinstance(v, str) for v in result.verification))
        self.assertTrue(all(isinstance(a, str) for a in result.affected_scope))


class TestParseRequirementInterpretation(unittest.TestCase):
    def test_valid_interpretation(self):
        data = {
            "summary": "需求摘要",
            "scope": [{"text": "范围1", "source": "requirement"}],
            "terms": [{"term": "MSD", "definition": "最小数据集", "source": "requirement"}],
            "rules": [{"title": "规则1", "description": "描述", "source": "insufficient"}],
            "scenarios": [{"title": "场景1", "precondition": "", "trigger": "触发", "expected_behavior": ["行为1"], "source": "requirement"}],
            "matrix": {"title": "矩阵", "columns": ["A", "B"], "rows": [["1", "2"]], "source": "insufficient"},
            "flow": {"title": "流程", "content": "描述", "source": "requirement"},
            "pending_confirmations": ["待确认1"],
        }
        interp, issues = parse_requirement_interpretation(data)
        self.assertIsNotNone(interp)
        self.assertEqual(interp.summary, "需求摘要")
        self.assertEqual(len(interp.scope), 1)
        self.assertEqual(interp.scope[0].source, "requirement")
        self.assertEqual(interp.terms[0].term, "MSD")
        self.assertEqual(interp.rules[0].source, "insufficient")
        self.assertEqual(len(interp.scenarios), 1)
        self.assertEqual(interp.scenarios[0].expected_behavior, ["行为1"])
        self.assertIsNotNone(interp.matrix)
        self.assertEqual(interp.matrix.columns, ["A", "B"])
        self.assertIsNotNone(interp.flow)
        self.assertEqual(interp.flow.content, "描述")
        self.assertEqual(interp.pending_confirmations, ["待确认1"])
        self.assertEqual(issues, [])

    def test_missing_interpretation(self):
        interp, issues = parse_requirement_interpretation(None)
        self.assertIsNone(interp)
        self.assertIn("requirement_interpretation_missing", issues)

    def test_partial_interpretation(self):
        data = {"summary": "部分摘要"}
        interp, issues = parse_requirement_interpretation(data)
        self.assertIsNotNone(interp)
        self.assertEqual(interp.summary, "部分摘要")
        self.assertEqual(len(interp.scope), 0)
        self.assertIsNone(interp.matrix)

    def test_source_enum_filtering(self):
        data = {
            "scope": [{"text": "范围", "source": "invalid_source"}],
            "rules": [{"title": "不可采信规则", "description": "描述", "source": "invalid_source"}],
        }
        interp, issues = parse_requirement_interpretation(data)
        self.assertEqual(interp.scope[0].source, "insufficient")
        self.assertEqual(interp.rules[0].title, "")
        self.assertIn("requirement_interpretation_invalid_source", issues)

    def test_invalid_list_field_is_reported_as_rich_content_issue(self):
        interp, issues = parse_requirement_interpretation({"scope": "bad"})
        self.assertIsNotNone(interp)
        self.assertEqual(interp.scope, [])
        self.assertIn("requirement_interpretation_invalid_scope", issues)


class TestParseCodeImpact(unittest.TestCase):
    def test_valid_code_impact(self):
        data = {
            "related_locations": [
                {"component": "模块A", "path": "src/a.c", "line_start": 10, "line_end": 20, "symbol": "foo", "reason": "相关"},
            ],
            "impact_notes": ["模块A可能受影响"],
        }
        impact, issues = parse_code_impact(data)
        self.assertIsNotNone(impact)
        self.assertEqual(len(impact.related_locations), 1)
        self.assertEqual(impact.related_locations[0].component, "模块A")
        self.assertEqual(impact.impact_notes, ["模块A可能受影响"])
        self.assertEqual(issues, [])

    def test_missing_code_impact(self):
        impact, issues = parse_code_impact(None)
        self.assertIsNone(impact)
        self.assertIn("code_impact_missing", issues)

    def test_empty_locations(self):
        data = {"related_locations": [], "impact_notes": []}
        impact, issues = parse_code_impact(data)
        self.assertIsNotNone(impact)
        self.assertEqual(len(impact.related_locations), 0)

    def test_invalid_location_list_field_is_reported(self):
        impact, issues = parse_code_impact({"related_locations": "bad", "impact_notes": []})
        self.assertIsNotNone(impact)
        self.assertEqual(impact.related_locations, [])
        self.assertIn("code_impact_invalid_related_locations", issues)

    def test_location_without_path_is_preserved_for_location_validation(self):
        impact, issues = parse_code_impact({
            "related_locations": [{"component": "模块A", "path": "", "line_start": 1, "line_end": 1}],
            "impact_notes": [],
        })
        self.assertEqual(issues, [])
        self.assertEqual(len(impact.related_locations), 1)
        self.assertEqual(impact.related_locations[0].path, "")


class TestAnalysisResultRichContent(unittest.TestCase):
    def test_default_rich_content_fields(self):
        result = AnalysisResult(item_id="1", item_type="story", item_title="T")
        self.assertEqual(result.requirement_source, "zentao")
        self.assertIsNone(result.requirement_interpretation)
        self.assertIsNone(result.code_impact)
        self.assertEqual(result.rich_content_issues, [])


class TestIsInsufficientEvidence(unittest.TestCase):
    def test_has_evidence_not_insufficient_despite_low_confidence(self):
        result = AnalysisResult(
            item_id="1", item_type="story", item_title="T",
            conclusion="部分完成", confidence="低",
            evidence=["src/a.c:1-5 实现了核心功能"],
            requirement_points=[
                RequirementPoint(id="RP-001", description="功能A", status="完成"),
                RequirementPoint(id="RP-002", description="功能B", status="无法判断"),
            ],
        )
        self.assertFalse(result.is_insufficient_evidence())

    def test_no_evidence_returns_insufficient(self):
        result = AnalysisResult(
            item_id="2", item_type="story", item_title="T",
            conclusion="无法判断", confidence="中", evidence=[],
        )
        self.assertTrue(result.is_insufficient_evidence())

    def test_error_returns_insufficient(self):
        result = AnalysisResult.from_error(
            ZentaoItem(id="3", type="story", title="T"), "LLM timeout",
        )
        self.assertTrue(result.is_insufficient_evidence())


class TestComputeConfidence(unittest.TestCase):
    def setUp(self):
        self.rp_completed = RequirementPoint(id="RP-001", description="A", status="完成")
        self.rp_indeterminate = RequirementPoint(id="RP-002", description="B", status="无法判断")
        self.rp_partial = RequirementPoint(id="RP-003", description="C", status="部分完成")

    def test_all_completed_returns_high(self):
        rps = [self.rp_completed, self.rp_completed]
        self.assertEqual(compute_item_confidence(rps), "高")

    def test_mix_completed_and_indeterminate_returns_medium(self):
        rps = [self.rp_completed, self.rp_indeterminate]
        self.assertEqual(compute_item_confidence(rps), "中")

    def test_mix_completed_partial_indeterminate_returns_medium(self):
        rps = [self.rp_completed, self.rp_partial, self.rp_indeterminate]
        self.assertEqual(compute_item_confidence(rps), "中")

    def test_mostly_completed_one_indeterminate_returns_medium(self):
        rps = [self.rp_completed for _ in range(8)] + [self.rp_indeterminate]
        self.assertEqual(compute_item_confidence(rps), "中")

    def test_no_confirmed_returns_low(self):
        rps = [self.rp_indeterminate, self.rp_indeterminate]
        self.assertEqual(compute_item_confidence(rps), "低")

    def test_invalid_evidence_returns_low(self):
        rps = [self.rp_completed]
        self.assertEqual(compute_item_confidence(rps, has_invalid_evidence=True), "低")

    def test_fallback_evidence_returns_medium(self):
        rps = [self.rp_completed, self.rp_indeterminate]
        self.assertEqual(compute_item_confidence(rps, has_fallback_evidence=True), "中")

    def test_empty_rps_returns_low(self):
        self.assertEqual(compute_item_confidence([]), "低")


if __name__ == "__main__":
    unittest.main(verbosity=2)
