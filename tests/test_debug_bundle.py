import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from debug_bundle import DebugBundle, build_debug_bundle


class TestDebugBundle(unittest.TestCase):
    def test_build_default_path_and_write_config(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = build_debug_bundle(
                enabled=True,
                base_dir=td,
                module="requirement",
                run_id="5939",
                timestamp="20260521-100000",
            )
            self.assertTrue(bundle.enabled)
            self.assertTrue(bundle.path.endswith("20260521-100000-requirement-5939"))
            bundle.write_config({"OPENAI_API_KEY": "sk-test", "safe": "value"})
            with open(os.path.join(bundle.path, "run_config.redacted.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["OPENAI_API_KEY"], "***")
            self.assertEqual(data["safe"], "value")

    def test_disabled_bundle_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = build_debug_bundle(enabled=False, base_dir=td, module="story", run_id="1")
            bundle.write_items([])
            self.assertFalse(os.listdir(td))

    def test_prompt_response_analysis_documents_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle"))
            item = MagicMock()
            item.id = "1"
            item.type = "story"
            item.title = "T"
            item.status = "active"
            item.priority = "1"
            item.keywords = ["test"]
            bundle.write_items([item])
            bundle.write_scan_summary({"files": ["a.py"], "matched_count": 1})
            bundle.write_prompt("1", "password=abc")
            bundle.write_response("1", "Authorization: Bearer token")
            bundle.write_analysis_results([{"item_id": "1", "raw_response": "token=abc"}])
            bundle.write_documents([{"document_path": "docs/prd/a.md"}])
            bundle.write_summary_path("docs/summary_report.json")
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "items.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "scan_summary.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "prompts", "1.txt")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "responses", "1.txt")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "analysis_results.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "documents.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "summary_report_path.txt")))
            with open(os.path.join(bundle.path, "prompts", "1.txt"), encoding="utf-8") as f:
                self.assertIn("password=***", f.read())

    def test_code_context_only_written_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle"), include_code=False)
            bundle.write_code_context({"snippets": [{"content": "secret"}]})
            self.assertFalse(os.path.exists(os.path.join(bundle.path, "code_context.json")))
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle2"), include_code=True)
            bundle.write_code_context({"snippets": [{"content": "password=abc"}]})
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "code_context.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
