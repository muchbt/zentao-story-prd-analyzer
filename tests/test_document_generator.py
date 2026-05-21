import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis_result import AnalysisResult
from document_generator import generate_document, sanitize_title
from zentao_client import ZentaoItem


class TestDocumentGenerator(unittest.TestCase):
    def test_story_generates_prd(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="1", type="story", title="新增 登录", description="用户可以登录", status="active")
            analysis = AnalysisResult(
                item_id="1",
                item_type="story",
                item_title="新增 登录",
                conclusion="部分完成",
                evidence=["src/auth.py: login exists"],
                gaps=["缺少异常提示"],
                recommendations=["补充错误提示"],
                verification=["验证错误密码"],
                priority="高",
                confidence="中",
            )
            doc = generate_document(item, analysis, output_root=td, generated_at="2026-05-21T10:00:00+08:00")
            self.assertEqual(doc.document_type, "PRD")
            self.assertIn(os.path.join("prd", "PRD-story-1-新增_登录.md"), doc.document_path)
            content = open(doc.document_path, encoding="utf-8").read()
            self.assertIn("# PRD: 新增 登录", content)
            self.assertIn("## LLM 理解摘要", content)
            self.assertIn("部分完成", content)

    def test_bug_generates_issue(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="2", type="bug", title="登录崩溃", description="点击登录崩溃")
            analysis = AnalysisResult(
                item_id="2",
                item_type="bug",
                item_title="登录崩溃",
                conclusion="部分定位",
                evidence=["src/auth.py"],
                suspected_causes=["空指针"],
                affected_scope=["登录模块"],
                recommendations=["增加空值检查"],
                verification=["复现登录"],
                priority="中",
                confidence="中",
            )
            doc = generate_document(item, analysis, output_root=td)
            self.assertEqual(doc.document_type, "ISSUE")
            content = open(doc.document_path, encoding="utf-8").read()
            self.assertIn("# ISSUE: 登录崩溃", content)
            self.assertIn("## 可能根因", content)

    def test_diagnostic_document_for_error(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="3", type="requirement", title="T")
            analysis = AnalysisResult.from_error(item, "LLM 调用失败")
            doc = generate_document(item, analysis, output_root=td)
            self.assertTrue(doc.is_diagnostic)
            content = open(doc.document_path, encoding="utf-8").read()
            self.assertIn("诊断文档", content)
            self.assertIn("LLM 调用失败", content)

    def test_sanitize_title(self):
        self.assertEqual(sanitize_title("A/B C__中文!"), "A_B_C_中文")
        self.assertEqual(sanitize_title("!!!"), "untitled")

if __name__ == "__main__":
    unittest.main(verbosity=2)
