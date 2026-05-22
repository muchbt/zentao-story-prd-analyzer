import argparse
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.app_config import RuntimeConfig, build_runtime_config


class TestAppConfig(unittest.TestCase):
    def test_defaults_match_phase4_spec(self):
        args = argparse.Namespace(
            agent=None,
            model=None,
            agent_timeout=None,
            claude_command=None,
            codex_command=None,
            opencode_command=None,
            claude_prompt_via=None,
            claude_extra_arg=None,
            verbose=False,
            quiet=False,
            log_file=None,
            no_debug_bundle=False,
            debug_bundle_dir=None,
            debug_include_code=False,
            repo_path=".",
        )
        with patch.dict(os.environ, {}, clear=True), patch("zentao_analyzer.app_config.shutil.which", side_effect=lambda name: name if name == "claude" else None):
            config = build_runtime_config(args)
        self.assertEqual(config.agent, "claude")
        self.assertEqual(config.agent_timeout, 900)
        self.assertEqual(config.claude_command, "claude")
        self.assertEqual(config.codex_command, "codex")
        self.assertEqual(config.opencode_command, "opencode")
        self.assertEqual(config.claude_prompt_via, "stdin")
        self.assertTrue(config.debug_bundle_enabled)
        self.assertFalse(config.debug_include_code)

    def test_env_values_are_used_when_cli_missing(self):
        args = argparse.Namespace(
            agent=None,
            model=None,
            agent_timeout=None,
            claude_command=None,
            codex_command=None,
            opencode_command=None,
            claude_prompt_via=None,
            claude_extra_arg=None,
            verbose=False,
            quiet=False,
            log_file=None,
            no_debug_bundle=False,
            debug_bundle_dir=None,
            debug_include_code=False,
            repo_path="/repo",
        )
        env = {
            "LLM_AGENT": "claude",
            "AGENT_TIMEOUT": "9",
            "CLAUDE_COMMAND": "claude-dev",
            "CODEX_COMMAND": "codex-dev",
            "OPENCODE_COMMAND": "opencode-dev",
            "CLAUDE_PROMPT_VIA": "arg",
            "DEBUG_BUNDLE_DIR": "/tmp/debugs",
        }
        with patch.dict(os.environ, env, clear=True):
            config = build_runtime_config(args)
        self.assertEqual(config.agent, "claude")
        self.assertEqual(config.model, "")
        self.assertEqual(config.agent_timeout, 9)
        self.assertEqual(config.claude_command, "claude-dev")
        self.assertEqual(config.codex_command, "codex-dev")
        self.assertEqual(config.opencode_command, "opencode-dev")
        self.assertEqual(config.claude_prompt_via, "arg")
        self.assertEqual(config.debug_bundle_dir, "/tmp/debugs")

    def test_cli_values_override_env(self):
        args = argparse.Namespace(
            agent="codex",
            model="cli-model",
            agent_timeout=30,
            claude_command="claude-cli",
            codex_command="codex-cli",
            opencode_command="opencode-cli",
            claude_prompt_via="stdin",
            claude_extra_arg=["--foo", "bar"],
            verbose=True,
            quiet=False,
            log_file="run.jsonl",
            no_debug_bundle=True,
            debug_bundle_dir="debug",
            debug_include_code=True,
            repo_path="/repo",
        )
        with patch.dict(os.environ, {"LLM_AGENT": "claude", "AGENT_TIMEOUT": "9"}, clear=True):
            config = build_runtime_config(args)
        self.assertEqual(config.agent, "codex")
        self.assertEqual(config.model, "cli-model")
        self.assertEqual(config.agent_timeout, 30)
        self.assertEqual(config.claude_extra_args, ["--foo", "bar"])
        self.assertTrue(config.verbose)
        self.assertEqual(config.log_file, "run.jsonl")
        self.assertFalse(config.debug_bundle_enabled)
        self.assertTrue(config.debug_include_code)

    def test_agent_config_dict_uses_agent_specific_command(self):
        config = RuntimeConfig(agent="codex", codex_command="codex-dev", repo_path="/repo")
        self.assertEqual(config.agent_config_dict()["command"], "codex-dev")
        self.assertEqual(config.agent_config_dict()["cwd"], "/repo")

    def test_default_agent_detection_falls_back_to_codex_then_opencode(self):
        args = argparse.Namespace(
            agent=None,
            model=None,
            agent_timeout=None,
            claude_command=None,
            codex_command=None,
            opencode_command=None,
            claude_prompt_via=None,
            claude_extra_arg=None,
            verbose=False,
            quiet=False,
            log_file=None,
            no_debug_bundle=False,
            debug_bundle_dir=None,
            debug_include_code=False,
            repo_path=".",
        )
        with patch.dict(os.environ, {}, clear=True), patch("zentao_analyzer.app_config.shutil.which", side_effect=lambda name: name if name == "codex" else None):
            self.assertEqual(build_runtime_config(args).agent, "codex")
        with patch.dict(os.environ, {}, clear=True), patch("zentao_analyzer.app_config.shutil.which", side_effect=lambda name: name if name == "opencode" else None):
            self.assertEqual(build_runtime_config(args).agent, "opencode")


if __name__ == "__main__":
    unittest.main(verbosity=2)
