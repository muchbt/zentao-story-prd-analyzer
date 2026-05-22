import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.prompts import build_feature_prompt, build_defect_prompt
from zentao_analyzer.zentao_client import ZentaoItem

class TestPrompts(unittest.TestCase):
    def test_feature_prompt_contains_fields(self):
        item = ZentaoItem(id="1", type="story", title="Add feature", description="Desc", status="active")
        snippets = [{"path": "src/main.c", "content": "int foo() {}", "line_start": 1, "line_end": 1}]
        prompt = build_feature_prompt(item, snippets)
        self.assertIn("Add feature", prompt)
        self.assertIn("Desc", prompt)
        self.assertIn("src/main.c", prompt)
        self.assertIn("完成|部分完成|未完成|无法判断", prompt)
        self.assertIn('"path": "文件路径"', prompt)
        self.assertIn('"line_start": 1', prompt)
        self.assertIn('"reason": "该证据如何支持结论"', prompt)
        self.assertIn("只能引用代码上下文中出现过的位置", prompt)
        self.assertIn("禁止编造", prompt)

    def test_defect_prompt_contains_fields(self):
        item = ZentaoItem(id="2", type="bug", title="Crash bug", description="Crashes", status="active")
        snippets = [{"path": "src/bug.c", "content": "void bad() {}", "line_start": 1, "line_end": 1}]
        prompt = build_defect_prompt(item, snippets)
        self.assertIn("Crash bug", prompt)
        self.assertIn("Crashes", prompt)
        self.assertIn("src/bug.c", prompt)
        self.assertIn("已定位|部分定位|无法定位", prompt)
        self.assertIn('"path": "文件路径"', prompt)
        self.assertIn('"line_end": 20', prompt)
        self.assertIn("禁止编造", prompt)

    def test_feature_vs_defect_distinct(self):
        item = ZentaoItem(id="1", type="story", title="T")
        snippets = [{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]
        p1 = build_feature_prompt(item, snippets)
        p2 = build_defect_prompt(item, snippets)
        self.assertNotEqual(p1, p2)
        self.assertIn("功能实现完成度", p1)
        self.assertIn("可能根因", p2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
