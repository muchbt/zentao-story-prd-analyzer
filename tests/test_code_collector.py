import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.code_clues import CodeClue
from zentao_analyzer.code_collector import collect, collect_with_clues

class TestCodeCollector(unittest.TestCase):
    def _create_repo(self, files_content):
        td = tempfile.mkdtemp()
        for path, content in files_content.items():
            full = os.path.join(td, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return td

    def test_os_walk_fallback_collects_files(self):
        td = self._create_repo({
            "src/main.c": "int main() { return 0; }\n",
            "README.md": "# readme\n",
        })
        snippets = collect(td, keywords=["main"], max_files=10, max_lines_per_file=100)
        paths = [s["path"] for s in snippets]
        self.assertTrue(any("main.c" in p for p in paths))
        self.assertFalse(any("README" in p for p in paths))

    def test_os_walk_no_match_returns_empty(self):
        td = self._create_repo({"src/foo.c": "void bar() {}\n"})
        snippets = collect(td, keywords=["nonexistent"])
        self.assertEqual(snippets, [])

    def test_max_files_limit(self):
        td = self._create_repo({f"src/f{i}.c": f"int x{i};\n" for i in range(10)})
        snippets = collect(td, keywords=["int"], max_files=3)
        self.assertLessEqual(len(snippets), 3)

    def test_max_lines_per_file(self):
        td = self._create_repo({"src/big.c": "line\n" * 500})
        snippets = collect(td, keywords=["line"], max_lines_per_file=10)
        self.assertLessEqual(len(snippets[0]["content"].splitlines()), 10)

    def test_modified_files_restricts_search(self):
        td = self._create_repo({
            "src/a.c": "int alpha;\n",
            "src/b.c": "int beta;\n",
        })
        snippets = collect(td, keywords=["int"], modified_files=[os.path.join(td, "src", "a.c")])
        paths = [s["path"] for s in snippets]
        self.assertTrue(any("a.c" in p for p in paths))
        self.assertFalse(any("b.c" in p for p in paths))

    def test_modified_files_relative_paths(self):
        """Verify relative paths from git diff are resolved against repo_path"""
        td = self._create_repo({
            "src/a.c": "int alpha;\n",
            "src/b.c": "int beta;\n",
        })
        # Pass relative paths (like git diff --name-only returns)
        snippets = collect(td, keywords=["int"], modified_files=["src/a.c"])
        paths = [s["path"] for s in snippets]
        self.assertTrue(any("a.c" in p for p in paths))
        self.assertFalse(any("b.c" in p for p in paths))

    def test_os_walk_matches_filename(self):
        """Verify keyword matching also works against filenames, not just content"""
        td = self._create_repo({
            "src/delta_v.c": "void func() {}\n",  # content does NOT contain "delta"
            "src/other.c": "int main() {}\n",
        })
        snippets = collect(td, keywords=["delta"], max_files=10)
        paths = [s["path"] for s in snippets]
        self.assertTrue(any("delta_v.c" in p for p in paths))
        self.assertFalse(any("other.c" in p for p in paths))

    def test_collect_with_path_clue_records_locations(self):
        td = self._create_repo({
            "src/auth.c": "int login(void) {\n  return 1;\n}\n",
            "src/other.c": "int other;\n",
        })
        path = os.path.join(td, "src", "auth.c")
        result = collect_with_clues(td, [CodeClue("path", path, "cli", "1")])
        self.assertEqual(len(result.snippets), 1)
        self.assertEqual(result.snippets[0]["matched_clues"], [path])
        self.assertEqual(result.collected_locations[0].path, path)
        self.assertEqual(result.collected_locations[0].line_start, 1)
        self.assertEqual(result.collected_locations[0].line_end, 3)

    def test_collect_with_symbol_and_keyword_clues(self):
        td = self._create_repo({
            "src/auth.c": "int LoginUser(void) {\n  return 1;\n}\n",
            "src/config.c": "int config;\n",
        })
        result = collect_with_clues(td, [
            CodeClue("symbol", "LoginUser", "cli", "1"),
            CodeClue("keyword", "config", "zentao", "1"),
        ])
        paths = [s["path"] for s in result.snippets]
        self.assertTrue(any("auth.c" in p for p in paths))
        self.assertTrue(any("config.c" in p for p in paths))
        self.assertGreaterEqual(len(result.collected_locations), 2)

    def test_collect_with_modified_files_intersection(self):
        td = self._create_repo({
            "src/a.c": "int alpha;\n",
            "src/b.c": "int beta;\n",
        })
        result = collect_with_clues(
            td,
            [CodeClue("keyword", "int", "cli", "1")],
            modified_files=["src/a.c"],
        )
        paths = [s["path"] for s in result.snippets]
        self.assertTrue(any("a.c" in p for p in paths))
        self.assertFalse(any("b.c" in p for p in paths))

if __name__ == "__main__":
    unittest.main(verbosity=2)
