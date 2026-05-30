import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analysis_result import (
    AnalysisResult,
    CodeImpactAnalysis,
    CodeImpactLocation,
    EvidenceLocation,
    InterpretationEntry,
    InterpretationRule,
    InterpretationTerm,
    RequirementInterpretation,
    RequirementMatrix,
    RequirementScenario,
    RequirementFlow,
    RequirementPoint,
    ProtocolTrace,
    RPStatus,
)
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
            self.assertIn("## 1. 概述", content)
            self.assertIn("### 1.1 需求摘要", content)
            self.assertIn("### 1.2 范围", content)
            self.assertIn("### 1.3 术语定义", content)
            self.assertIn("### 1.4 来源信息", content)
            self.assertIn("条目类型: story", content)
            self.assertIn("需求来源: 禅道", content)
            self.assertIn("## 2. 需求解读", content)
            self.assertIn("### 2.1 业务规则", content)
            self.assertIn("### 2.2 场景与流程", content)
            self.assertIn("### 2.3 关系或并发矩阵", content)
            self.assertIn("### 2.4 待确认事项", content)
            self.assertIn("部分完成", content)
            self.assertIn("## 3. 代码依据", content)
            self.assertIn("### 3.1 代码位置总览", content)
            self.assertIn("### 3.2 影响说明", content)
            self.assertIn("### 3.3 实现完成度", content)
            self.assertIn("- src/auth.py: login exists", content)
            self.assertIn("## 4. 完成度评估", content)
            self.assertIn("### 4.1 需求点完成情况", content)
            self.assertIn("## 5. 实现建议", content)
            self.assertIn("以下建议为参考性质", content)
            self.assertIn("### 5.1 代码变更建议", content)
            self.assertIn("### 5.2 测试要点", content)
            self.assertIn("## 6. 参考信息", content)
            self.assertIn("### 6.1 追踪信息", content)
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
            self.assertEqual(content.count("src/auth.py"), 1)
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
                evidence=["src/a.c:12-40 Login 支持结论", "src/b.c:2-3 Logout 支持退出"],
                confidence="高",
                cited_evidence_locations=[
                    EvidenceLocation(path="src/a.c", line_start=12, line_end=40, symbol="Login", reason="支持结论", source="agent"),
                    EvidenceLocation(path="src/b.c", line_start=2, line_end=3, symbol="Logout", reason="支持退出", source="agent"),
                ],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("| 关联模块 | 文件 | 行号 | 符号 | 影响说明 | 证据说明 |", content)
            self.assertIn("| src/a.c | 12-40 | Login | — | 支持结论 |", content)
            self.assertIn("| src/b.c | 2-3 | Logout | — | 支持退出 |", content)
            self.assertNotIn("补充说明：", content)
            self.assertNotIn("## 实现证据", content)
            self.assertNotIn("## 已实现的核心功能", content)
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
            section_1_1 = content.split("### 1.1 需求摘要", 1)[1].split("###", 1)[0]
            self.assertIn("TCAM 需要在通话结束后进入 25 分钟回拨模式。", section_1_1)
            self.assertNotIn("src/xcall.c", section_1_1)
            self.assertNotIn("补充来电拒绝逻辑", section_1_1)

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
            self.assertIn("分析结果未提供有效内容", content)
            self.assertIn("无法确定是否存在缺口", content)
            self.assertIn("## 6. 参考信息", content)
            self.assertIn("### 6.1 追踪信息", content)
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

    def test_prd_contains_all_six_chapters(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="10", type="requirement", title="完整章节", description="需求描述")
            analysis = AnalysisResult(
                item_id="10", item_type="requirement", item_title="完整章节",
                conclusion="完成", evidence=["src/a.c:1-10 ok"], confidence="高",
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            for heading in [
                "## 1. 概述", "### 1.1 需求摘要", "### 1.2 范围",
                "### 1.3 术语定义", "### 1.4 来源信息",
                "## 2. 需求解读", "### 2.1 业务规则", "### 2.2 场景与流程",
                "### 2.3 关系或并发矩阵", "### 2.4 待确认事项",
                "## 3. 代码依据", "### 3.1 代码位置总览",
                "### 3.2 影响说明", "### 3.3 实现完成度",
                "## 4. 完成度评估", "### 4.1 需求点完成情况", "### 4.2 差异与缺口",
                "## 5. 实现建议", "### 5.1 代码变更建议", "### 5.2 测试要点",
                "## 6. 参考信息", "### 6.1 追踪信息",
            ]:
                self.assertIn(heading, content, f"Missing heading: {heading}")

    def test_prd_renders_interpretation_fields(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="11", type="story", title="解释字段", description="用户登录功能")
            interp = RequirementInterpretation(
                summary="用户可在登录页面输入凭据并认证",
                scope=[
                    InterpretationEntry(text="支持手机号登录", source="requirement"),
                    InterpretationEntry(text="支持邮箱登录", source="code_context"),
                ],
                terms=[
                    InterpretationTerm(term="SSO", definition="单点登录", source="requirement"),
                    InterpretationTerm(term="Token", definition="认证令牌", source="code_context"),
                ],
                rules=[
                    InterpretationRule(title="密码强度", description="至少8位", source="requirement"),
                    InterpretationRule(title="重试限制", description="5次后锁定", source="code_context"),
                ],
                scenarios=[
                    RequirementScenario(
                        title="正常登录", precondition="用户在登录页", trigger="点击登录",
                        expected_behavior=["跳转首页", "显示欢迎信息"], source="requirement",
                    ),
                ],
                matrix=RequirementMatrix(
                    title="角色权限矩阵", columns=["角色", "查看", "编辑"],
                    rows=[["管理员", "是", "是"], ["用户", "是", "否"]],
                    source="requirement",
                ),
                flow=RequirementFlow(title="登录流程", content="输入凭据→提交→验证→跳转", source="requirement"),
                pending_confirmations=["是否需要二次验证", "超时时间具体值"],
            )
            analysis = AnalysisResult(
                item_id="11", item_type="story", item_title="解释字段",
                conclusion="部分完成", evidence=["src/auth.c:1-10"], confidence="中",
                requirement_interpretation=interp,
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("支持手机号登录", content)
            self.assertIn("支持邮箱登录 *（代码侧候选上下文，不构成需求定义）*", content)
            self.assertIn("SSO", content)
            self.assertIn("单点登录", content)
            self.assertIn("Token", content)
            self.assertIn("代码侧候选上下文，不构成需求定义", content)
            self.assertIn("密码强度", content)
            self.assertIn("至少8位", content)
            self.assertIn("重试限制", content)
            self.assertIn("5次后锁定", content)
            self.assertIn("正常登录", content)
            self.assertIn("前置条件: 用户在登录页", content)
            self.assertIn("触发条件: 点击登录", content)
            self.assertIn("跳转首页", content)
            self.assertIn("角色权限矩阵", content)
            self.assertIn("管理员", content)
            self.assertIn("登录流程", content)
            self.assertIn("输入凭据→提交→验证→跳转", content)
            self.assertIn("是否需要二次验证", content)
            self.assertIn("超时时间具体值", content)
            self.assertIn("用户可在登录页面输入凭据并认证", content)

    def test_prd_missing_insufficient_sections_show_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="12", type="story", title="缺省", description="空需求")
            interp = RequirementInterpretation(
                scope=[InterpretationEntry(text="有范围", source="requirement")],
                terms=[InterpretationTerm(term="T", definition="", source="insufficient")],
            )
            analysis = AnalysisResult(
                item_id="12", item_type="story", item_title="缺省",
                conclusion="无法判断", evidence=[], confidence="低",
                requirement_interpretation=interp,
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("有范围", content)
            self.assertIn("原始需求未提供足够信息", content)

    def test_prd_no_interpretation_shows_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="13", type="story", title="无解释", description="仅描述")
            analysis = AnalysisResult(
                item_id="13", item_type="story", item_title="无解释",
                conclusion="无法判断", evidence=[], confidence="低",
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            scope_section = content.split("### 1.2 范围", 1)[1].split("### 1.3", 1)[0]
            self.assertIn("分析结果未提供有效内容", scope_section)
            terms_section = content.split("### 1.3 术语定义", 1)[1].split("### 1.4", 1)[0]
            self.assertIn("分析结果未提供有效内容", terms_section)
            rules_section = content.split("### 2.1 业务规则", 1)[1].split("### 2.2", 1)[0]
            self.assertIn("分析结果未提供有效内容", rules_section)
            pending_section = content.split("### 2.4 待确认事项", 1)[1].split("## 3.", 1)[0]
            self.assertIn("分析结果未提供有效内容", pending_section)

    def test_prd_invalid_interpretation_field_shows_analysis_degradation(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="131", type="story", title="畸形分析", description="原始正文")
            analysis = AnalysisResult(
                item_id="131", item_type="story", item_title="畸形分析",
                conclusion="无法判断", evidence=[], confidence="低",
                requirement_interpretation=RequirementInterpretation(),
                rich_content_issues=["requirement_interpretation_invalid_scope"],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            scope_section = content.split("### 1.2 范围", 1)[1].split("### 1.3", 1)[0]
            self.assertIn("分析结果未提供有效内容", scope_section)

    def test_prd_code_context_items_show_source_label(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="14", type="story", title="代码侧", description="需求描述")
            interp = RequirementInterpretation(
                scope=[
                    InterpretationEntry(text="需求侧范围", source="requirement"),
                    InterpretationEntry(text="代码侧范围", source="code_context"),
                ],
                terms=[
                    InterpretationTerm(term="需求术语", definition="定义A", source="requirement"),
                    InterpretationTerm(term="代码术语", definition="定义B", source="code_context"),
                ],
                rules=[
                    InterpretationRule(title="需求规则", description="描述A", source="requirement"),
                    InterpretationRule(title="代码规则", description="描述B", source="code_context"),
                ],
            )
            analysis = AnalysisResult(
                item_id="14", item_type="story", item_title="代码侧",
                conclusion="完成", evidence=["src/a.c:1-5 ok"], confidence="高",
                requirement_interpretation=interp,
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("需求侧范围", content)
            self.assertIn("代码侧范围 *（代码侧候选上下文，不构成需求定义）*", content)
            self.assertIn("需求术语", content)
            self.assertIn("代码术语", content)
            self.assertIn("代码侧候选上下文，不构成需求定义", content)
            self.assertIn("需求规则", content)
            self.assertIn("代码规则", content)
            code_context_count = content.count("代码侧候选上下文，不构成需求定义")
            self.assertGreaterEqual(code_context_count, 3)

    def test_prd_uses_interpretation_summary_and_labels_raw_description_detail(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="21", type="requirement", title="长需求", description="原始需求正文内容")
            analysis = AnalysisResult(
                item_id="21", item_type="requirement", item_title="长需求",
                conclusion="无法判断", confidence="低",
                requirement_interpretation=RequirementInterpretation(summary="提炼后的摘要"),
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            summary_section = content.split("### 1.1 需求摘要", 1)[1].split("### 1.2", 1)[0]
            detail_section = content.split("## 2. 需求解读", 1)[1].split("### 2.1", 1)[0]
            self.assertIn("提炼后的摘要", summary_section)
            self.assertNotIn("原始需求正文内容", summary_section)
            self.assertIn("原始需求正文：", detail_section)
            self.assertIn("原始需求正文内容", detail_section)
            self.assertNotIn("提炼后的摘要", detail_section)

    def test_prd_code_impact_table_shows_validated_locations(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="15", type="story", title="代码关联", description="需求")
            impact = CodeImpactAnalysis(
                related_locations=[
                    CodeImpactLocation(component="Auth", path="src/auth.c", line_start=10, line_end=20, symbol="login", reason="登录入口"),
                    CodeImpactLocation(component="", path="src/invalid.c", line_start=0, line_end=0, symbol="", reason="无效位置"),
                    CodeImpactLocation(component="DB", path="src/db.c", line_start=5, line_end=15, symbol="connect", reason="数据库连接"),
                ],
                impact_notes=["注意并发安全", "需要事务处理"],
            )
            analysis = AnalysisResult(
                item_id="15", item_type="story", item_title="代码关联",
                conclusion="部分完成", evidence=["src/auth.c"], confidence="中",
                code_impact=impact,
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            table_section = content.split("### 3.1 代码位置总览", 1)[1].split("### 3.2", 1)[0]
            notes_section = content.split("### 3.2 影响说明", 1)[1].split("### 3.3", 1)[0]
            self.assertIn("Auth", table_section)
            self.assertIn("src/auth.c | 10-20 | login | 登录入口", table_section)
            self.assertIn("DB", table_section)
            self.assertIn("src/db.c", table_section)
            self.assertNotIn("src/invalid.c", table_section)
            self.assertNotIn("无效位置", table_section)
            self.assertIn("注意并发安全", notes_section)
            self.assertIn("需要事务处理", notes_section)

    def test_prd_code_impact_no_locations_shows_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="16", type="story", title="无关联", description="需求")
            analysis = AnalysisResult(
                item_id="16", item_type="story", item_title="无关联",
                conclusion="无法判断", evidence=[], confidence="低",
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            table_section = content.split("### 3.1 代码位置总览", 1)[1].split("### 3.2", 1)[0]
            self.assertIn("分析结果未提供有效内容", table_section)

    def test_prd_recommendations_marked_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="17", type="story", title="建议标记", description="需求")
            analysis = AnalysisResult(
                item_id="17", item_type="story", item_title="建议标记",
                conclusion="未完成", evidence=["src/a.c:1-5 part"],
                recommendations=["新增模块X", "修改接口Y"],
                verification=["验证登录流程"],
                confidence="中",
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("以下建议为参考性质，不构成现有实现描述", content)
            self.assertIn("### 5.1 代码变更建议", content)
            self.assertIn("新增模块X", content)

    def test_prd_issue_filename_assertions_still_pass(self):
        with tempfile.TemporaryDirectory() as td:
            story_item = ZentaoItem(id="20", type="story", title="文件名测试", description="d")
            story_analysis = AnalysisResult(item_id="20", item_type="story", item_title="文件名测试", conclusion="完成", confidence="高")
            story_doc = generate_document(story_item, story_analysis, output_root=td)
            self.assertIn(os.path.join("prd", "PRD-story-20-文件名测试.md"), story_doc.document_path)

            bug_item = ZentaoItem(id="21", type="bug", title="Bug名", description="d")
            bug_analysis = AnalysisResult(item_id="21", item_type="bug", item_title="Bug名", conclusion="已定位", confidence="高")
            bug_doc = generate_document(bug_item, bug_analysis, output_root=td)
            self.assertEqual(bug_doc.document_type, "ISSUE")
            self.assertIn(os.path.join("issue", "ISSUE-bug-21-Bug名.md"), bug_doc.document_path)

    def test_prd_provided_requirement_source_label(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="22", type="story", title="用户提交", description="用户需求", requirement_source="provided")
            analysis = AnalysisResult(
                item_id="22", item_type="story", item_title="用户提交",
                conclusion="完成", confidence="高",
                requirement_source="provided",
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("需求来源: 用户提交", content)

    def test_prd_shows_completion_ratio(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="23", type="story", title="比例测试")
            analysis = AnalysisResult(
                item_id="23", item_type="story", item_title="比例测试",
                conclusion="部分完成", confidence="中",
                requirement_points=[
                    RequirementPoint(id="RP-001", description="A", status="完成"),
                    RequirementPoint(id="RP-002", description="B", status="无法判断"),
                    RequirementPoint(id="RP-003", description="C", status="完成"),
                ],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path) as f:
                content = f.read()
            section = content.split("### 3.3 实现完成度", 1)[1].split("## 4.", 1)[0]
            self.assertIn("需求点统计", section)
            self.assertIn("2 完成", section)
            self.assertIn("1 无法判断", section)
            self.assertIn("共 3", section)

    def test_evidence_deduplication_against_code_impact(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="24", type="story", title="去重测试")
            impact = CodeImpactAnalysis(
                related_locations=[
                    CodeImpactLocation(component="A", path="src/a.c", line_start=10, line_end=20, symbol="f1", reason="关联1"),
                ]
            )
            analysis = AnalysisResult(
                item_id="24", item_type="story", item_title="去重测试",
                conclusion="部分完成", confidence="中",
                code_impact=impact,
                cited_evidence_locations=[
                    EvidenceLocation(path="src/a.c", line_start=10, line_end=20, symbol="f1", reason="关联1"),
                    EvidenceLocation(path="src/b.c", line_start=5, line_end=10, symbol="f2", reason="独有"),
                ],
                evidence=["src/a.c:10-20 f1 关联1", "src/b.c:5-10 f2 独有"],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path) as f:
                content = f.read()
            table_section = content.split("### 3.1 代码位置总览", 1)[1].split("### 3.2", 1)[0]
            self.assertIn("src/a.c", table_section)
            self.assertIn("src/b.c", table_section)
            self.assertEqual(table_section.count("src/a.c"), 1)
            self.assertEqual(table_section.count("src/b.c"), 1)

    def test_prd_low_confidence_with_evidence_no_diagnostic_banner(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="25", type="story", title="T")
            analysis = AnalysisResult(
                item_id="25", item_type="story", item_title="T",
                conclusion="部分完成", confidence="低",
                evidence=["src/a.c:1-5 已实现"],
                requirement_points=[
                    RequirementPoint(id="RP-001", description="A", status="完成"),
                    RequirementPoint(id="RP-002", description="B", status="无法判断"),
                ],
            )
            doc = generate_document(item, analysis, output_root=td)
            self.assertFalse(doc.is_diagnostic)
            with open(doc.document_path) as f:
                content = f.read()
            self.assertNotIn("诊断文档：当前条目未能生成完整", content)

    def test_multi_repo_document_shows_role_paths_and_protocol_trace(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="26", type="story", title="T")
            location = EvidenceLocation(role="soc", path="src/send.c", line_start=1, line_end=2, reason="sender")
            analysis = AnalysisResult(
                item_id="26",
                item_type="story",
                item_title="T",
                conclusion="无法判断",
                evidence=["soc:src/send.c:1-2 sender"],
                cited_evidence_locations=[location],
                requirement_points=[RequirementPoint(id="RP-001", description="A", status="无法判断", evidence=[location])],
                protocol_traces=[ProtocolTrace(roles=["soc", "mcu"], hint_type="cmd_id", value="0x1234", status="partial", evidence=[location])],
            )
            doc = generate_document(item, analysis, output_root=td)
            with open(doc.document_path, encoding="utf-8") as f:
                content = f.read()
        self.assertIn("soc:src/send.c", content)
        self.assertIn("协议线索闭环", content)
        self.assertIn("partial", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
