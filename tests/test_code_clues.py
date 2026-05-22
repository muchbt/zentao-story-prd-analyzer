import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.code_clues import (
    CodeClue,
    load_clues_file,
    parse_csv_values,
    build_item_clues,
)
from zentao_analyzer.zentao_client import ZentaoItem


class TestCodeClues(unittest.TestCase):
    def test_parse_csv_values(self):
        self.assertEqual(parse_csv_values("a,b, c"), ["a", "b", "c"])
        self.assertEqual(parse_csv_values(["a,b", "c"]), ["a", "b", "c"])
        self.assertEqual(parse_csv_values(None), [])

    def test_load_clues_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "clues.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"5939": {"keywords": ["login"], "paths": ["src"], "symbols": ["Auth"]}}, f)
            data = load_clues_file(path)
        self.assertEqual(data["5939"]["keywords"], ["login"])

    def test_build_item_clues_merges_sources(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "src"))
            item = ZentaoItem(id="5939", type="story", title="T", keywords=["zentao_kw"])
            clues, rejected = build_item_clues(
                item,
                repo_path=td,
                cli_keywords=["cli_kw"],
                cli_paths=["src"],
                cli_symbols=["CliSymbol"],
                clues_by_item={"5939": {"keywords": ["file_kw"], "symbols": ["FileSymbol"]}},
            )
        self.assertEqual(rejected, [])
        triples = {(c.kind, c.value, c.source) for c in clues}
        self.assertIn(("keyword", "zentao_kw", "zentao"), triples)
        self.assertIn(("keyword", "cli_kw", "cli"), triples)
        self.assertIn(("symbol", "CliSymbol", "cli"), triples)
        self.assertIn(("keyword", "file_kw", "clues_file"), triples)
        self.assertIn(("symbol", "FileSymbol", "clues_file"), triples)
        self.assertTrue(any(c.kind == "path" and c.source == "cli" for c in clues))

    def test_path_outside_repo_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            outside = os.path.abspath(os.path.join(td, "..", "outside.c"))
            item = ZentaoItem(id="1", type="bug", title="B")
            clues, rejected = build_item_clues(item, repo_path=td, cli_paths=[outside])
        self.assertFalse([c for c in clues if c.kind == "path"])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].reason, "outside_repo")

    def test_limits_drop_extra_values(self):
        item = ZentaoItem(id="1", type="story", title="T", keywords=["x" * 200])
        clues, rejected = build_item_clues(item, repo_path=".", cli_keywords=["a"] * 101)
        self.assertLessEqual(len([c for c in clues if c.kind == "keyword"]), 100)
        self.assertFalse(any(c.value == "x" * 200 for c in clues))


if __name__ == "__main__":
    unittest.main(verbosity=2)
