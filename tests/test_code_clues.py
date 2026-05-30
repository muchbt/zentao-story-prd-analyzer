import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.code_clues import (
    RejectedSeedPath,
    build_role_seed_paths,
    build_search_hints,
    build_seed_paths,
    load_clues_file,
    parse_csv_values,
)
from zentao_analyzer.repositories import parse_repo_args


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

    def test_load_structured_clues_file_with_repositories_items_and_protocol_hints(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "clues.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "repositories": {"soc": "../soc", "mcu": "../mcu"},
                        "items": {
                            "5939": {
                                "primary_role": "soc",
                                "clues": ["callback"],
                                "protocol_hints": [{"roles": ["soc", "mcu"], "type": "cmd_id", "value": "0x1234"}],
                                "paths": {"soc": ["src/send.c"], "mcu": ["src/recv.c"]},
                            }
                        },
                    },
                    f,
                )
            data = load_clues_file(path)
        self.assertEqual(data.repositories, {"soc": "../soc", "mcu": "../mcu"})
        self.assertEqual(data["5939"]["primary_role"], "soc")
        self.assertEqual(data["5939"]["paths"]["soc"], ["src/send.c"])
        self.assertEqual(data["5939"]["protocol_hints"][0]["type"], "cmd_id")

    def test_build_role_seed_paths_resolves_each_role_root(self):
        with tempfile.TemporaryDirectory() as soc, tempfile.TemporaryDirectory() as mcu:
            os.makedirs(os.path.join(soc, "src"))
            os.makedirs(os.path.join(mcu, "src"))
            soc_path = os.path.join(soc, "src", "send.c")
            mcu_path = os.path.join(mcu, "src", "recv.c")
            for path in (soc_path, mcu_path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("int x;\n")
            repo_set = parse_repo_args([f"soc={soc}", f"mcu={mcu}"])
            paths, rejected = build_role_seed_paths(
                "5939",
                repo_set=repo_set,
                clues_by_item={"5939": {"paths": {"soc": ["src/send.c"], "mcu": ["src/recv.c"]}}},
            )
        self.assertEqual([(item.role, item.relative_path) for item in paths], [("soc", "src/send.c"), ("mcu", "src/recv.c")])
        self.assertEqual(rejected, [])

    def test_build_role_seed_paths_requires_role_for_multi_repo_cli_path(self):
        with tempfile.TemporaryDirectory() as soc, tempfile.TemporaryDirectory() as mcu:
            repo_set = parse_repo_args([f"soc={soc}", f"mcu={mcu}"])
            paths, rejected = build_role_seed_paths("5939", repo_set=repo_set, cli_paths=["src/send.c"])
        self.assertEqual(paths, [])
        self.assertEqual([(item.value, item.reason) for item in rejected], [("src/send.c", "missing_role")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
