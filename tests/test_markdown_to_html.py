import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.markdown_to_html import markdown_to_html


class TestMarkdownToHtml(unittest.TestCase):
    def test_headings(self):
        html = markdown_to_html("# H1\n## H2\n### H3")
        self.assertIn("<h1>H1</h1>", html)
        self.assertIn("<h2>H2</h2>", html)
        self.assertIn("<h3>H3</h3>", html)

    def test_bold_and_italic(self):
        html = markdown_to_html("**bold** *italic*")
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)

    def test_bold_italic_nested(self):
        html = markdown_to_html("***both***")
        self.assertIn("<strong><em>both</em></strong>", html)

    def test_inline_code(self):
        html = markdown_to_html("`code`")
        self.assertIn("<code>code</code>", html)

    def test_links(self):
        html = markdown_to_html("[text](https://example.com)")
        self.assertIn('<a href="https://example.com">text</a>', html)

    def test_code_block(self):
        md = "```python\nprint('hello')\n```"
        html = markdown_to_html(md)
        self.assertIn("<pre><code", html)
        self.assertIn("print(", html)
        self.assertIn("language-python", html)

    def test_code_block_without_language(self):
        md = "```\nplain\n```"
        html = markdown_to_html(md)
        self.assertIn("<pre><code>plain</code></pre>", html)

    def test_horizontal_rule(self):
        for hr in ("---", "***", "___"):
            with self.subTest(hr=hr):
                html = markdown_to_html(hr)
                self.assertIn("<hr>", html)

    def test_unordered_list(self):
        md = "- item1\n- item2\n- item3"
        html = markdown_to_html(md)
        self.assertIn("<ul>", html)
        self.assertIn("<li>item1</li>", html)
        self.assertIn("<li>item2</li>", html)
        self.assertIn("<li>item3</li>", html)

    def test_ordered_list(self):
        md = "1. first\n2. second"
        html = markdown_to_html(md)
        self.assertIn("<ol>", html)
        self.assertIn("<li>first</li>", html)
        self.assertIn("<li>second</li>", html)

    def test_blockquote(self):
        md = "> quoted text"
        html = markdown_to_html(md)
        self.assertIn("<blockquote>", html)
        self.assertIn("quoted text", html)

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = markdown_to_html(md)
        self.assertIn("<table>", html)
        self.assertIn("<thead>", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<th>B</th>", html)
        self.assertIn("<tbody>", html)
        self.assertIn("<td>1</td>", html)
        self.assertIn("<td>2</td>", html)

    def test_table_with_inline_elements(self):
        md = "| **Key** | `value` |\n|---------|---------|\n| a | b |"
        html = markdown_to_html(md)
        self.assertIn("<strong>Key</strong>", html)
        self.assertIn("<code>value</code>", html)

    def test_paragraphs(self):
        md = "Para 1\n\nPara 2"
        html = markdown_to_html(md)
        self.assertIn("<p>Para 1</p>", html)
        self.assertIn("<p>Para 2</p>", html)

    def test_paragraph_with_inline(self):
        md = "Text with **bold** and `code`."
        html = markdown_to_html(md)
        body = _extract_body(html)
        self.assertIn("<strong>bold</strong>", body)
        self.assertIn("<code>code</code>", body)

    def test_html_escaping(self):
        html = markdown_to_html("<script>alert('xss')</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_document_structure(self):
        html = markdown_to_html("# Title", title="My PRD")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<title>My PRD</title>", html)
        self.assertIn("<meta charset=\"UTF-8\">", html)
        self.assertIn("<style>", html)
        self.assertIn("</html>", html)

    def test_empty_input(self):
        html = markdown_to_html("")
        self.assertIn("<body>", html)
        self.assertIn("</body>", html)

    def test_table_without_separator(self):
        md = "| A | B |\n| 1 | 2 |"
        html = markdown_to_html(md)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td>1</td>", html)

    def test_list_items_with_inline(self):
        md = "- **bold** item\n- `code` item"
        html = markdown_to_html(md)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)

    def test_mixed_content(self):
        md = """# Title

## Section

Some **text** with `code`.

- item 1
- item 2

| A | B |
|---|---|
| x | y |"""
        html = markdown_to_html(md)
        self.assertIn("<h1>Title</h1>", html)
        self.assertIn("<h2>Section</h2>", html)
        self.assertIn("<strong>text</strong>", html)
        self.assertIn("<code>code</code>", html)
        self.assertIn("<ul>", html)
        self.assertIn("<table>", html)

    def test_code_block_marker_not_confused_with_inline(self):
        md = "This is `a` and not ```code block```"
        html = markdown_to_html(md)
        self.assertIn("<code>a</code>", html)

    def test_multiple_code_blocks(self):
        md = "```a\none\n```\n\n```b\ntwo\n```"
        html = markdown_to_html(md)
        self.assertIn("one", html)
        self.assertIn("two", html)


def _extract_body(html: str) -> str:
    import re
    m = re.search(r"<body>(.*?)</body>", html, re.DOTALL)
    return m.group(1) if m else html


class TestDocumentGeneratorHtml(unittest.TestCase):
    def setUp(self):
        from zentao_analyzer.zentao_client import ZentaoItem
        from zentao_analyzer.analysis_result import AnalysisResult
        self.item = ZentaoItem(
            id="5939", type="requirement", title="Test Title",
            description="Test description", status="active", priority="1",
        )
        self.analysis = AnalysisResult(
            item_id="5939", item_type="requirement", item_title="Test Title",
            conclusion="完成", evidence=["src/a.c"], gaps=[],
            recommendations=[], verification=[], priority="高",
            confidence="高",
        )

    def test_generate_document_produces_html_path(self):
        from zentao_analyzer.document_generator import generate_document
        with tempfile.TemporaryDirectory() as td:
            doc = generate_document(self.item, self.analysis, output_root=td)
            self.assertTrue(doc.html_path)
            self.assertTrue(os.path.exists(doc.html_path))
            self.assertTrue(doc.html_path.endswith(".html"))
            self.assertEqual(
                os.path.splitext(doc.html_path)[0],
                os.path.splitext(doc.document_path)[0],
            )

    def test_html_content_is_valid(self):
        from zentao_analyzer.document_generator import generate_document
        with tempfile.TemporaryDirectory() as td:
            doc = generate_document(self.item, self.analysis, output_root=td)
            with open(doc.html_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("<html", content)
            self.assertIn("Test Title", content)
            self.assertIn("完成", content)

    def test_documentresult_has_html_path_default(self):
        from zentao_analyzer.document_generator import DocumentResult
        dr = DocumentResult(
            item_id="1", item_type="story", title="T",
            document_type="PRD", document_path="docs/prd/test.md",
        )
        self.assertEqual(dr.html_path, "")


class TestSummaryReportHtml(unittest.TestCase):
    def test_summary_includes_html_path(self):
        from zentao_analyzer.zentao_client import ZentaoItem
        from zentao_analyzer.analysis_result import AnalysisResult
        from zentao_analyzer.document_generator import DocumentResult
        from zentao_analyzer.summary_report import build_summary_item

        item = ZentaoItem(
            id="5939", type="requirement", title="T",
            description="D", status="active", priority="1",
        )
        analysis = AnalysisResult(
            item_id="5939", item_type="requirement", item_title="T",
            conclusion="完成", evidence=[], gaps=[],
            recommendations=[], verification=[], priority="高",
            confidence="高",
        )
        doc = DocumentResult(
            item_id="5939", item_type="requirement", title="T",
            document_type="PRD", document_path="docs/prd/test.md",
            html_path="docs/prd/test.html",
        )
        summary = build_summary_item(item, analysis, doc, {})
        self.assertEqual(summary["html_path"], "docs/prd/test.html")

    def test_summary_html_path_empty_when_not_set(self):
        from zentao_analyzer.zentao_client import ZentaoItem
        from zentao_analyzer.analysis_result import AnalysisResult
        from zentao_analyzer.document_generator import DocumentResult
        from zentao_analyzer.summary_report import build_summary_item

        item = ZentaoItem(
            id="5939", type="requirement", title="T",
            description="D", status="active", priority="1",
        )
        analysis = AnalysisResult(
            item_id="5939", item_type="requirement", item_title="T",
            conclusion="完成", evidence=[], gaps=[],
            recommendations=[], verification=[], priority="高",
            confidence="高",
        )
        doc = DocumentResult(
            item_id="5939", item_type="requirement", title="T",
            document_type="PRD", document_path="docs/prd/test.md",
        )
        summary = build_summary_item(item, analysis, doc, {})
        self.assertEqual(summary["html_path"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
