import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.prompts import build_defect_prompt, build_feature_prompt
from zentao_analyzer.zentao_client import ZentaoItem


class TestPrompts(unittest.TestCase):
    def test_feature_prompt_contains_repo_seed_hints_and_write_boundary(self):
        item = ZentaoItem(id="1", type="story", title="Add feature", description="Desc", status="active")
        snippets = [{"path": "src/main.c", "content": "int foo() {}", "line_start": 1, "line_end": 1}]
        prompt = build_feature_prompt(item, repo_path="/repo", seed_snippets=snippets, search_hints=["foo", "callback"])
        self.assertIn("Add feature", prompt)
        self.assertIn("路径: /repo", prompt)
        self.assertIn("src/main.c", prompt)
        self.assertIn("foo, callback", prompt)
        self.assertIn("主动搜索代码仓库", prompt)
        self.assertIn("不得修改、创建、删除目标仓库源码", prompt)
        self.assertIn("完成|部分完成|未完成|无法判断", prompt)
        self.assertIn('"path": "文件路径"', prompt)
        self.assertIn('"output_md": ""', prompt)
        self.assertNotIn("{{", prompt)
        self.assertNotIn("}}", prompt)
        self.assertIn("evidence 必须引用仓库中实际存在的文件和行号", prompt)

    def test_feature_prompt_without_seed_still_instructs_search(self):
        item = ZentaoItem(id="1", type="story", title="T")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("[未提供种子上下文]", prompt)
        self.assertIn("[未提供搜索建议]", prompt)
        self.assertIn("主动搜索代码仓库", prompt)

    def test_defect_prompt_contains_defect_schema(self):
        item = ZentaoItem(id="2", type="bug", title="Crash bug", description="Crashes", status="active")
        prompt = build_defect_prompt(item, repo_path="/repo", search_hints=["CrashHandler"])
        self.assertIn("Crash bug", prompt)
        self.assertIn("已定位|部分定位|无法定位", prompt)
        self.assertIn("可能根因", prompt)
        self.assertIn("CrashHandler", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
