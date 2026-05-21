import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_logger import RunLogger, redact_sensitive


class TestRunLogger(unittest.TestCase):
    def test_redact_sensitive_values(self):
        data = {
            "token": "abc123",
            "password": "secret",
            "api_key": "key",
            "authorization": "Bearer xyz",
            "nested": {"OPENAI_API_KEY": "sk-test", "safe": "value"},
            "text": "Authorization: Bearer live-token and password=abc",
        }
        redacted = redact_sensitive(data)
        self.assertEqual(redacted["token"], "***")
        self.assertEqual(redacted["password"], "***")
        self.assertEqual(redacted["api_key"], "***")
        self.assertEqual(redacted["authorization"], "***")
        self.assertEqual(redacted["nested"]["OPENAI_API_KEY"], "***")
        self.assertIn("Bearer ***", redacted["text"])
        self.assertNotIn("live-token", redacted["text"])
        self.assertNotIn("password=abc", redacted["text"])

    def test_quiet_suppresses_progress_stderr(self):
        stream = io.StringIO()
        logger = RunLogger(quiet=True)
        with redirect_stderr(stream):
            logger.info("fetch_items", "started", status="running")
        self.assertEqual(stream.getvalue(), "")

    def test_verbose_writes_more_fields_to_stderr(self):
        stream = io.StringIO()
        logger = RunLogger(verbose=True)
        with redirect_stderr(stream):
            logger.info("analyze", "agent_call", status="done", item_id="5939", agent="claude", duration_ms=12)
        text = stream.getvalue()
        self.assertIn("analyze", text)
        self.assertIn("agent_call", text)
        self.assertIn("5939", text)
        self.assertIn("claude", text)

    def test_jsonl_log_file_is_redacted(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "run.jsonl")
            logger = RunLogger(log_file=path)
            logger.info("analyze", "agent_call", token="abc123", error="Authorization: Bearer abc123")
            with open(path, "r", encoding="utf-8") as f:
                line = f.readline()
            event = json.loads(line)
            self.assertEqual(event["token"], "***")
            self.assertEqual(event["error"], "Authorization: Bearer ***")


if __name__ == "__main__":
    unittest.main(verbosity=2)
