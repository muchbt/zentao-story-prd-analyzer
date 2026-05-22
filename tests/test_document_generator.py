import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analysis_result import AnalysisResult, EvidenceLocation
from zentao_analyzer.document_generator import generate_document, sanitize_title, DocumentResult, validate_document_consistency
from zentao_analyzer.zentao_client import ZentaoItem


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
            self.assertEqual(doc.title, "新增 登录")
            self.assertIn(os.path.join("prd", "PRD-story-1-新增_登录.md"), doc.document_path)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# PRD: 新增 登录", content)
            self.assertIn("## 来源信息", content)
            self.assertIn("条目类型: story", content)
            self.assertIn("## LLM 理解摘要", content)
            self.assertIn("部分完成", content)
            self.assertIn("## 关键代码证据", content)
            self.assertIn("## 追踪信息", content)
            self.assertIn("回写禅道: not_implemented", content)

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
            self.assertEqual(doc.title, "登录崩溃")
            self.assertIn(os.path.join("issue", "ISSUE-bug-2-登录崩溃.md"), doc.document_path)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# ISSUE: 登录崩溃", content)
            self.assertIn("## 来源信息", content)
            self.assertIn("## 可能根因", content)
            self.assertIn("## 关键代码证据", content)
            self.assertIn("## 追踪信息", content)
            self.assertIn("回写禅道: not_implemented", content)

    def test_document_renders_cited_evidence_locations_table(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="6", type="story", title="证据")
            analysis = AnalysisResult(
                item_id="6",
                item_type="story",
                item_title="证据",
                conclusion="完成",
                evidence=["src/a.c:12-40 Login 支持结论"],
                confidence="高",
                cited_evidence_locations=[
                    EvidenceLocation(path="src/a.c", line_start=12, line_end=40, symbol="Login", reason="支持结论", source="agent")
                ],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("| src/a.c | 12-40 | Login | 支持结论 |", content)
            self.assertEqual(validate_document_consistency(analysis, doc), [])

    def test_document_uses_understanding_summary_without_repeating_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="8", type="requirement", title="回拨", description="进入回拨模式")
            analysis = AnalysisResult(
                item_id="8",
                item_type="requirement",
                item_title="回拨",
                conclusion="部分完成",
                understanding_summary="TCAM 需要在通话结束后进入 25 分钟回拨模式。",
                evidence=["src/xcall.c:1-5 已实现定时器"],
                recommendations=["补充来电拒绝逻辑"],
                verification=["验证回拨超时"],
                confidence="中",
            )

            doc = generate_document(item, analysis, output_root=td)

            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            summary = content.split("## LLM 理解摘要", 1)[1].split("## 实现完成度", 1)[0]
            self.assertIn("TCAM 需要在通话结束后进入 25 分钟回拨模式。", summary)
            self.assertNotIn("src/xcall.c", summary)
            self.assertNotIn("补充来电拒绝逻辑", summary)

    def test_document_consistency_reports_diagnostic_banner_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="7", type="story", title="T")
            analysis = AnalysisResult(
                item_id="7",
                item_type="story",
                item_title="T",
                conclusion="完成",
                evidence=["src/a.c:1-1 ok"],
                confidence="高",
                cited_evidence_locations=[EvidenceLocation(path="src/a.c", line_start=1, line_end=1, reason="ok")],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, "w", encoding="utf-8") as f:
                f.write("> 诊断文档：当前条目未能生成完整 PRD。\n")

            issues = validate_document_consistency(analysis, doc)

        self.assertIn("unexpected_diagnostic_banner", issues)
        self.assertIn("missing_cited_evidence_path", issues)

    def test_diagnostic_document_still_in_prd(self):
        """诊断文档仍使用 PRD 目录和文件名，document_type 仍为 PRD"""
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="3", type="requirement", title="T")
            analysis = AnalysisResult.from_error(item, "LLM 调用失败")
            doc = generate_document(item, analysis, output_root=td)
            self.assertTrue(doc.is_diagnostic)
            self.assertEqual(doc.document_type, "PRD")
            self.assertIn(os.path.join("prd", "PRD-requirement-3-T.md"), doc.document_path)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# PRD: T", content)
            self.assertIn("> 诊断文档：当前条目未能生成完整 PRD。", content)
            self.assertIn("LLM 调用失败", content)
            self.assertIn("## 追踪信息", content)
            self.assertIn("回写禅道: not_implemented", content)

    def test_diagnostic_document_still_in_issue(self):
        """诊断文档仍使用 ISSUE 目录和文件名，document_type 仍为 ISSUE"""
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="4", type="bug", title="Bug")
            analysis = AnalysisResult.from_error(item, "超时")
            doc = generate_document(item, analysis, output_root=td)
            self.assertTrue(doc.is_diagnostic)
            self.assertEqual(doc.document_type, "ISSUE")
            self.assertIn(os.path.join("issue", "ISSUE-bug-4-Bug.md"), doc.document_path)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("# ISSUE: Bug", content)
            self.assertIn("> 诊断文档：当前条目未能生成完整 ISSUE。", content)

    def test_unknown_type_notice(self):
        """未知条目类型按 ISSUE 生成，并在文档中标记"""
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="5", type="custom_type", title="Custom")
            analysis = AnalysisResult(
                item_id="5",
                item_type="custom_type",
                item_title="Custom",
                conclusion="部分完成",
                evidence=["a.c"],
                recommendations=["建议"],
                verification=["验证"],
                priority="中",
                confidence="中",
            )
            doc = generate_document(item, analysis, output_root=td)
            self.assertEqual(doc.document_type, "ISSUE")
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("未知条目类型 `custom_type`，按问题类文档生成", content)

    def test_sanitize_title(self):
        self.assertEqual(sanitize_title("A/B C__中文!"), "A_B_C_中文")
        self.assertEqual(sanitize_title("!!!"), "untitled")


if __name__ == "__main__":
    unittest.main(verbosity=2)
