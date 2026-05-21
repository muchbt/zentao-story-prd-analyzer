import dataclasses
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis_result import AnalysisResult
from zentao_client import ZentaoItem

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
            "output_md": "# PRD",
        }
        result = AnalysisResult.from_llm_json(item, data, raw_response="raw")
        self.assertEqual(result.item_id, "1")
        self.assertEqual(result.conclusion, "完成")
        self.assertEqual(result.confidence, "高")
        self.assertEqual(result.evidence, ["file.c:foo()"])
        self.assertEqual(result.raw_response, "raw")

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

if __name__ == "__main__":
    unittest.main(verbosity=2)
