import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_collector import collect

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

if __name__ == "__main__":
    unittest.main(verbosity=2)
