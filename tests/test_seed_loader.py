import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.code_clues import RejectedSeedPath, RoleSeedPath
from zentao_analyzer.seed_loader import SeedLocation, load_seed_context


class TestSeedLoader(unittest.TestCase):
    def _file(self, root, relative_path, content):
        path = os.path.join(root, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_loads_seed_files_and_records_seed_locations(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._file(td, "src/a.c", "int a;\nint b;\n")
            result = load_seed_context([path], max_lines_per_seed=50, max_seed_tokens=2000)
        self.assertEqual(len(result.snippets), 1)
        self.assertEqual(result.snippets[0]["path"], path)
        self.assertEqual(result.snippets[0]["line_start"], 1)
        self.assertEqual(result.snippets[0]["line_end"], 2)
        self.assertEqual(result.seed_locations, [SeedLocation(path=path, line_start=1, line_end=2)])

    def test_limits_files_lines_and_total_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            paths = [self._file(td, f"src/f{i}.c", "line\n" * 100) for i in range(5)]
            result = load_seed_context(paths, max_seed_files=3, max_lines_per_seed=10, max_seed_tokens=20)
        self.assertLessEqual(len(result.snippets), 3)
        self.assertLessEqual(result.snippets[0]["line_end"], 10)
        self.assertIn("截断", result.snippets[-1]["content"])

    def test_clamps_token_budget_to_hard_limit(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._file(td, "src/big.c", "x" * 40000)
            result = load_seed_context([path], max_lines_per_seed=1000, max_seed_tokens=9000, max_seed_tokens_limit=8000)
        self.assertLessEqual(len(result.snippets[0]["content"]), 8000 * 4 + 40)

    def test_read_failures_are_rejected_seed_paths(self):
        result = load_seed_context(
            ["/missing.c"],
            rejected_seed_paths=[RejectedSeedPath(value="../outside.c", source="cli", item_id="1", reason="outside_repo")],
        )
        self.assertEqual(result.snippets, [])
        self.assertEqual([item.reason for item in result.rejected_seed_paths], ["outside_repo", "read_failed"])

    def test_role_seed_path_uses_role_relative_display_path(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._file(td, "src/a.c", "int a;\n")
            result = load_seed_context([RoleSeedPath(role="soc", path=path, relative_path="src/a.c")])
        self.assertEqual(result.snippets[0]["path"], "soc:src/a.c")
        self.assertEqual(result.seed_locations[0].role, "soc")


if __name__ == "__main__":
    unittest.main(verbosity=2)
