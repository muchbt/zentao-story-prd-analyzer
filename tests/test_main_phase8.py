import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zentao_analyzer.main as main
from zentao_analyzer.analysis_result import AnalysisResult, EvidenceLocation, ProtocolTrace
from zentao_analyzer.zentao_client import ZentaoItem


class TestMainPhase8(unittest.TestCase):
    def test_multi_repo_cli_passes_repository_set_protocol_hints_and_role_seed_paths(self):
        with tempfile.TemporaryDirectory() as td:
            soc = os.path.join(td, "soc")
            mcu = os.path.join(td, "mcu")
            os.makedirs(os.path.join(soc, "src"))
            os.makedirs(os.path.join(mcu, "src"))
            with open(os.path.join(soc, "src", "send.c"), "w", encoding="utf-8") as f:
                f.write("int send;\n")
            item = ZentaoItem(id="1", type="bug", title="Bug", description="D")
            analysis = AnalysisResult(
                item_id="1",
                item_type="bug",
                item_title="Bug",
                conclusion="部分定位",
                evidence=["soc:src/send.c:1-1 sender"],
                cited_evidence_locations=[EvidenceLocation(role="soc", path="src/send.c", line_start=1, line_end=1)],
                protocol_traces=[ProtocolTrace(roles=["soc", "mcu"], hint_type="cmd_id", value="0x1234", status="partial")],
            )

            def fake_analyze(*args, **kwargs):
                self.assertEqual(kwargs["repo_set"].roles, ["soc", "mcu"])
                self.assertEqual(kwargs["protocol_hints"][0].value, "0x1234")
                self.assertEqual(kwargs["seed_paths"][0].role, "soc")
                return analysis

            argv = [
                "zentao_analyzer.main.py", "--module", "bug", "--id", "1", "--analyze",
                "--repo", f"soc={soc}", "--repo", f"mcu={mcu}",
                "--protocol-hint", "soc,mcu:cmd_id=0x1234",
                "--paths", "soc=src/send.c",
                "--output-root", os.path.join(td, "docs"),
                "--debug-bundle-dir", os.path.join(td, "debug"),
                "--quiet",
            ]
            with patch.object(main.ZentaoClient, "get_item", return_value=item):
                with patch("zentao_analyzer.main.analyze", side_effect=fake_analyze):
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            self.assertEqual(main.main(), 0)
            output = json.loads(stdout.getvalue())
            with open(os.path.join(output["debug_bundle"], "normalized_clues.json"), encoding="utf-8") as f:
                clues = json.load(f)
            with open(os.path.join(output["debug_bundle"], "repositories.json"), encoding="utf-8") as f:
                repositories = json.load(f)
        self.assertEqual(clues["items"]["1"]["protocol_hints"][0]["value"], "0x1234")
        self.assertEqual(repositories["repositories"][0]["role"], "soc")

    def test_item_specific_protocol_hint_error_does_not_block_other_batch_items(self):
        with tempfile.TemporaryDirectory() as td:
            soc = os.path.join(td, "soc")
            mcu = os.path.join(td, "mcu")
            os.makedirs(soc)
            os.makedirs(mcu)
            clues_path = os.path.join(td, "clues.json")
            with open(clues_path, "w", encoding="utf-8") as f:
                json.dump({
                    "items": {
                        "1": {"protocol_hints": [{"roles": ["app"], "type": "msg", "value": "BAD"}]},
                        "2": {"protocol_hints": [{"roles": ["soc", "mcu"], "type": "msg", "value": "OK"}]},
                    }
                }, f)
            items = [
                ZentaoItem(id="1", type="bug", title="Bad", description="D"),
                ZentaoItem(id="2", type="bug", title="Good", description="D"),
            ]
            good_analysis = AnalysisResult(item_id="2", item_type="bug", item_title="Good", conclusion="无法定位")
            argv = [
                "zentao_analyzer.main.py", "--module", "bug", "--project", "1", "--analyze",
                "--repo", f"soc={soc}", "--repo", f"mcu={mcu}",
                "--clues-file", clues_path, "--output-root", os.path.join(td, "docs"),
                "--no-debug-bundle", "--quiet",
            ]
            with patch.object(main.ZentaoClient, "list_items", return_value=items):
                with patch("zentao_analyzer.main.analyze", return_value=good_analysis) as mock_analyze:
                    with patch.object(sys, "argv", argv):
                        stdout = io.StringIO()
                        with contextlib.redirect_stdout(stdout):
                            self.assertEqual(main.main(), 0)
            output = json.loads(stdout.getvalue())
        self.assertEqual(mock_analyze.call_count, 1)
        self.assertIn("未知 Repository Role", output["analysis"][0]["error"])
        self.assertEqual(output["analysis"][1]["item_id"], "2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
