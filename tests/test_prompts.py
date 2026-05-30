import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.prompts import build_defect_prompt, build_feature_prompt
from zentao_analyzer.protocol_hints import normalize_protocol_hints
from zentao_analyzer.repositories import RoleWorkspace, parse_repo_args
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
        self.assertIn("只有 analyzer 进程可以写入", prompt)
        self.assertIn("完成|部分完成|未完成|无法判断", prompt)
        self.assertIn('"understanding_summary"', prompt)
        self.assertIn("自然语言概述", prompt)
        self.assertIn('"path": "文件路径"', prompt)
        self.assertNotIn("output_md", prompt)
        self.assertNotIn("{{", prompt)
        self.assertNotIn("}}", prompt)
        self.assertIn("evidence 必须引用仓库中实际存在的文件和行号", prompt)

    def test_feature_prompt_contains_requirement_interpretation_schema(self):
        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("requirement_interpretation", prompt)
        self.assertIn('"summary"', prompt)
        self.assertIn('"scope"', prompt)
        self.assertIn('"terms"', prompt)
        self.assertIn('"rules"', prompt)
        self.assertIn('"scenarios"', prompt)
        self.assertIn('"matrix"', prompt)
        self.assertIn('"flow"', prompt)
        self.assertIn('"pending_confirmations"', prompt)
        self.assertIn("requirement|code_context|insufficient", prompt)
        self.assertIn("source 枚举值为 requirement", prompt)

    def test_feature_prompt_contains_code_impact_schema(self):
        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("code_impact", prompt)
        self.assertIn("related_locations", prompt)
        self.assertIn("impact_notes", prompt)
        self.assertIn("component", prompt)

    def test_feature_prompt_json_schema_example_is_valid_json(self):
        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        prompt = build_feature_prompt(item, repo_path="/repo")
        schema_text = prompt.split("【JSON Schema】\n", 1)[1]
        json.loads(schema_text)

    def test_feature_prompt_shows_requirement_source(self):
        item = ZentaoItem(id="1", type="requirement", title="T", description="D", status="active", requirement_source="provided_requirement")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("provided_requirement", prompt)

    def test_feature_prompt_shows_zentao_source_by_default(self):
        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("zentao", prompt)

    def test_feature_prompt_requires_source_boundary(self):
        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("related_locations 与 requirement_points.evidence 是独立的", prompt)
        self.assertIn("source 为 insufficient 时不可编造内容", prompt)
        self.assertIn("recommendations 为建议性内容", prompt)

    def test_feature_prompt_without_seed_still_instructs_search(self):
        item = ZentaoItem(id="1", type="story", title="T")
        prompt = build_feature_prompt(item, repo_path="/repo")
        self.assertIn("[未提供种子上下文]", prompt)
        self.assertIn("[未提供搜索建议]", prompt)
        self.assertIn("主动搜索代码仓库", prompt)

    def test_defect_prompt_unchanged(self):
        item = ZentaoItem(id="2", type="bug", title="Crash bug", description="Crashes", status="active")
        prompt = build_defect_prompt(item, repo_path="/repo", search_hints=["CrashHandler"])
        self.assertIn("Crash bug", prompt)
        self.assertIn("已定位|部分定位|无法定位", prompt)
        self.assertIn('"understanding_summary"', prompt)
        self.assertIn("可能根因", prompt)
        self.assertIn("CrashHandler", prompt)
        self.assertNotIn("requirement_interpretation", prompt)
        self.assertNotIn("code_impact", prompt)
        self.assertNotIn("requirement_points", prompt)

    def test_multi_repo_prompt_includes_roles_protocol_hints_and_role_schema(self):
        import tempfile

        item = ZentaoItem(id="1", type="story", title="T", description="D", status="active")
        with tempfile.TemporaryDirectory() as soc, tempfile.TemporaryDirectory() as mcu:
            repo_set = parse_repo_args([f"soc={soc}", f"mcu={mcu}"])
            hints = normalize_protocol_hints(["soc,mcu:cmd_id=0x1234"], repo_set)
            with RoleWorkspace(repo_set) as workspace:
                prompt = build_feature_prompt(
                    item,
                    repo_path=soc,
                    repo_set=repo_set,
                    workspace=workspace,
                    protocol_hints=hints,
                )
        self.assertIn("Target Repository Set", prompt)
        self.assertIn("soc", prompt)
        self.assertIn("mcu", prompt)
        self.assertIn("cmd_id=0x1234", prompt)
        self.assertIn('"role": "Repository Role', prompt)
        self.assertIn('"protocol_traces"', prompt)
        self.assertIn("不能由单侧", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
