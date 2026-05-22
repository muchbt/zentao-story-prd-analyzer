import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.analysis_result import EvidenceLocation, EvidenceValidationIssue
from zentao_analyzer.code_clues import RejectedSeedPath
from zentao_analyzer.debug_bundle import DebugBundle, build_debug_bundle
from zentao_analyzer.seed_loader import SeedLocation


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
            bundle.write_config({"ZENTAO_TOKEN": "tok-test", "safe": "value"})
            with open(os.path.join(bundle.path, "run_config.redacted.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["ZENTAO_TOKEN"], "***")
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
            bundle.write_items([item])
            bundle.write_scan_summary({"seed_path_count": 1})
            bundle.write_prompt("1", "password=abc")
            bundle.write_response("1", "Authorization: Bearer token")
            bundle.write_analysis_results([{"item_id": "1", "raw_response": "token=abc"}])
            bundle.write_documents([{"document_path": "docs/prd/a.md"}])
            bundle.write_summary_path("docs/summary_report.json")
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "items.json")))
            self.assertTrue(os.path.exists(os.path.join(bundle.path, "scan_summary.json")))
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

    def test_seed_locations_rejected_seed_paths_and_validation_issues_are_written(self):
        with tempfile.TemporaryDirectory() as td:
            bundle = DebugBundle(enabled=True, path=os.path.join(td, "bundle"), include_code=False)
            bundle.write_code_evidence_locations([
                {
                    "item_id": "1",
                    "seed_locations": [
                        SeedLocation(path="src/a.c", line_start=1, line_end=10)
                    ],
                    "cited_evidence_locations": [
                        EvidenceLocation(path="src/a.c", line_start=2, line_end=4, symbol="Login", reason="支持结论", source="agent")
                    ],
                    "evidence_validation_issues": [
                        EvidenceValidationIssue(path="src/a.c", line_start=99, line_end=99, reason="line_out_of_range")
                    ],
                }
            ])
            bundle.write_rejected_seed_paths([RejectedSeedPath(value="../secret.c", source="cli", item_id="1", reason="outside_repo")])

            with open(os.path.join(bundle.path, "code_evidence_locations.json"), encoding="utf-8") as f:
                locations = json.load(f)
            self.assertEqual(locations["items"][0]["seed_locations"][0]["path"], "src/a.c")
            self.assertEqual(locations["items"][0]["cited_evidence_locations"][0]["symbol"], "Login")
            self.assertEqual(locations["items"][0]["evidence_validation_issues"][0]["reason"], "line_out_of_range")

            with open(os.path.join(bundle.path, "rejected_seed_paths.json"), encoding="utf-8") as f:
                rejected = json.load(f)
            self.assertEqual(rejected[0]["reason"], "outside_repo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
