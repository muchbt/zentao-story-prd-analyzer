import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.code_clues import (
    RejectedSeedPath,
    build_search_hints,
    build_seed_paths,
    load_clues_file,
    parse_csv_values,
)


class TestCodeClues(unittest.TestCase):
    def test_parse_csv_values(self):
        self.assertEqual(parse_csv_values("a,b, c"), ["a", "b", "c"])
        self.assertEqual(parse_csv_values(["a,b", "c"]), ["a", "b", "c"])
        self.assertEqual(parse_csv_values(None), [])

    def test_load_clues_file_uses_new_format_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "clues.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "5939": {
                            "clues": ["callback", "ecall"],
                            "paths": ["src/a.c"],
                            "keywords": ["legacy"],
                            "symbols": ["LegacySymbol"],
                        }
                    },
                    f,
                )
            data = load_clues_file(path)
        self.assertEqual(data["5939"]["clues"], ["callback", "ecall"])
        self.assertEqual(data["5939"]["paths"], ["src/a.c"])
        self.assertNotIn("keywords", data["5939"])
        self.assertNotIn("symbols", data["5939"])

    def test_build_search_hints_merges_cli_and_file(self):
        hints = build_search_hints(
            "5939",
            cli_clues="cli_kw, Login",
            clues_by_item={"5939": {"clues": ["file_kw", "Login"]}},
        )
        self.assertEqual(hints, ["cli_kw", "Login", "file_kw"])

    def test_build_seed_paths_accepts_repo_files_only(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src")
            os.makedirs(src)
            file_path = os.path.join(src, "a.c")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("int a;\n")

            paths, rejected = build_seed_paths(
                "5939",
                repo_path=td,
                cli_paths=["src/a.c", "src", "missing.c", os.path.join(td, "..", "outside.c")],
            )

        self.assertEqual(paths, [file_path])
        self.assertEqual(
            [(item.value, item.reason) for item in rejected],
            [("src", "not_file"), ("missing.c", "not_found"), (os.path.join(td, "..", "outside.c"), "outside_repo")],
        )
        self.assertTrue(all(isinstance(item, RejectedSeedPath) for item in rejected))

    def test_build_seed_paths_rejects_symlink_to_outside_repo(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside_dir:
            outside_file = os.path.join(outside_dir, "secret.txt")
            with open(outside_file, "w", encoding="utf-8") as f:
                f.write("secret\n")
            link_path = os.path.join(td, "linked.txt")
            try:
                os.symlink(outside_file, link_path)
            except (AttributeError, NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink is not available: {exc}")

            paths, rejected = build_seed_paths("5939", repo_path=td, cli_paths=["linked.txt"])

        self.assertEqual(paths, [])
        self.assertEqual([(item.value, item.reason) for item in rejected], [("linked.txt", "outside_repo")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
