import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.repositories import (
    RoleWorkspace,
    RepositoryInputError,
    parse_repo_args,
    resolve_repo_relative_path,
)


class TestRepositorySet(unittest.TestCase):
    def test_single_anonymous_repo_is_normalized_to_main(self):
        with tempfile.TemporaryDirectory() as repo:
            repo_set = parse_repo_args([repo])
        self.assertEqual(repo_set.roles, ["main"])
        self.assertTrue(repo_set.is_single_repo)
        self.assertFalse(repo_set.show_roles)

    def test_multiple_role_qualified_repos_are_supported(self):
        with tempfile.TemporaryDirectory() as soc, tempfile.TemporaryDirectory() as mcu:
            repo_set = parse_repo_args([f"soc={soc}", f"mcu={mcu}"])
        self.assertEqual(repo_set.roles, ["soc", "mcu"])
        self.assertFalse(repo_set.is_single_repo)
        self.assertTrue(repo_set.show_roles)

    def test_multiple_anonymous_repos_are_rejected(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with self.assertRaisesRegex(RepositoryInputError, "多条匿名"):
                parse_repo_args([first, second])

    def test_mixed_anonymous_and_role_qualified_repos_are_rejected(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with self.assertRaisesRegex(RepositoryInputError, "混用"):
                parse_repo_args([f"soc={first}", second])

    def test_duplicate_and_invalid_roles_are_rejected(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with self.assertRaisesRegex(RepositoryInputError, "重复"):
                parse_repo_args([f"soc={first}", f"soc={second}"])
            with self.assertRaisesRegex(RepositoryInputError, "非法"):
                parse_repo_args([f"bad.role={first}"])

    def test_repo_path_and_repo_values_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as repo:
            with self.assertRaisesRegex(RepositoryInputError, "不能同时"):
                parse_repo_args([repo], repo_path=repo)

    def test_clue_file_repositories_are_used_as_default_and_resolve_relative_paths(self):
        with tempfile.TemporaryDirectory() as td:
            os.mkdir(os.path.join(td, "soc"))
            repo_set = parse_repo_args(
                clues_file_repositories={"soc": "../soc"},
                clues_file_dir=os.path.join(td, "clues"),
            )
        self.assertEqual(repo_set.roles, ["soc"])
        self.assertTrue(repo_set.show_roles)

    def test_cli_and_clue_file_repositories_must_match(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with self.assertRaisesRegex(RepositoryInputError, "不一致"):
                parse_repo_args([f"soc={first}"], clues_file_repositories={"soc": second})

    def test_resolve_repo_relative_path_uses_role_root(self):
        with tempfile.TemporaryDirectory() as soc:
            repo_set = parse_repo_args([f"soc={soc}"])
            resolved = resolve_repo_relative_path(repo_set, "soc", "src/send.c")
        self.assertEqual(resolved, os.path.realpath(os.path.join(soc, "src/send.c")))

    def test_multi_repo_workspace_exposes_role_symlinks_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as soc, tempfile.TemporaryDirectory() as mcu:
            repo_set = parse_repo_args([f"soc={soc}", f"mcu={mcu}"])
            with RoleWorkspace(repo_set) as workspace:
                if not workspace.available:
                    self.skipTest(f"symlink is not available: {workspace.error}")
                path = workspace.path
                self.assertTrue(os.path.islink(os.path.join(path, "soc")))
                self.assertTrue(os.path.islink(os.path.join(path, "mcu")))
            self.assertFalse(os.path.exists(path))

    def test_single_repo_workspace_uses_repository_directly(self):
        with tempfile.TemporaryDirectory() as repo:
            repo_set = parse_repo_args([repo])
            with RoleWorkspace(repo_set) as workspace:
                self.assertFalse(workspace.available)
                self.assertEqual(workspace.path, os.path.realpath(repo))


if __name__ == "__main__":
    unittest.main(verbosity=2)
