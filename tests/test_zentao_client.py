import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.zentao_client import (
    ZentaoClient,
    ZentaoItem,
    ZentaoAuthError,
    ZentaoNotFoundError,
    ZentaoTimeoutError,
    ZentaoFormatError,
    ZentaoCommandError,
)


class TestZentaoItem(unittest.TestCase):
    def test_from_dict_basic(self):
        data = {
            "id": 123,
            "title": "测试需求",
            "desc": "这是一个描述",
            "status": "active",
            "pri": 1,
            "project": 5,
            "product": 2,
            "assignedTo": "dev1",
            "openedBy": "pm1",
            "openedDate": "2024-01-01",
        }
        item = ZentaoItem.from_dict(data, item_type="story")
        self.assertEqual(item.id, "123")
        self.assertEqual(item.title, "测试需求")
        self.assertEqual(item.type, "story")
        self.assertEqual(item.priority, "1")
        self.assertFalse(hasattr(item, "keywords"))

    def test_from_dict_invalid(self):
        with self.assertRaises(ZentaoFormatError):
            ZentaoItem.from_dict("not a dict")


class TestZentaoClient(unittest.TestCase):
    def _mock_run(self, returncode=0, stdout="{}", stderr="", side_effect=None):
        mock = MagicMock()
        mock.returncode = returncode
        mock.stdout = stdout
        mock.stderr = stderr
        if side_effect:
            return patch("subprocess.run", side_effect=side_effect)
        return patch("subprocess.run", return_value=mock)

    def test_get_item_success(self):
        data = {"id": 1, "title": "需求A", "status": "draft"}
        with self._mock_run(stdout=json.dumps(data)):
            client = ZentaoClient()
            item = client.get_item("story", "1")
        self.assertEqual(item.id, "1")
        self.assertEqual(item.title, "需求A")

    def test_list_items_success(self):
        data = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
        with self._mock_run(stdout=json.dumps(data)):
            client = ZentaoClient()
            items = client.list_items("bug", project="10", status="active", limit=5)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].id, "1")

    def test_list_items_wrapped_dict(self):
        data = {"data": [{"id": 3, "title": "C"}]}
        with self._mock_run(stdout=json.dumps(data)):
            client = ZentaoClient()
            items = client.list_items("story")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, "3")

    def test_login_missing_server(self):
        client = ZentaoClient()
        with self.assertRaises(ZentaoAuthError):
            client.login(user="admin", password="123456")

    def test_login_success(self):
        with self._mock_run(stdout='{"status":"ok"}'):
            client = ZentaoClient()
            result = client.login(server="https://z.example.com", user="u", password="p")
        self.assertEqual(result["status"], "ok")

    def test_auth_error_from_response(self):
        data = {"error": "unauthorized: 请先登录"}
        with self._mock_run(stdout=json.dumps(data)):
            client = ZentaoClient()
            with self.assertRaises(ZentaoAuthError):
                client.get_item("story", "1")

    def test_not_found_error_from_response(self):
        data = {"message": "对象不存在"}
        with self._mock_run(stdout=json.dumps(data)):
            client = ZentaoClient()
            with self.assertRaises(ZentaoNotFoundError):
                client.get_item("bug", "999")

    def test_timeout(self):
        with self._mock_run(side_effect=subprocess.TimeoutExpired("zentao", 1)):
            client = ZentaoClient()
            with self.assertRaises(ZentaoTimeoutError):
                client.get_item("story", "1")

    def test_command_not_found(self):
        with self._mock_run(side_effect=FileNotFoundError()):
            client = ZentaoClient()
            with self.assertRaises(ZentaoCommandError):
                client.get_item("story", "1")

    def test_json_decode_error(self):
        with self._mock_run(stdout="not json"):
            client = ZentaoClient()
            with self.assertRaises(ZentaoFormatError):
                client.get_item("story", "1")

    def test_sanitize_cmd(self):
        cmd = ["zentao", "login", "-s", "url", "-u", "admin", "-p", "secret", "--token", "tok123"]
        sanitized = ZentaoClient._sanitize_cmd(cmd)
        self.assertNotIn("secret", sanitized)
        self.assertNotIn("tok123", sanitized)
        self.assertIn("***", sanitized)

    def test_command_failure_does_not_leak_password_in_stderr(self):
        with self._mock_run(returncode=1, stdout="", stderr="password: secret123"):
            client = ZentaoClient()
            with self.assertRaises(ZentaoCommandError) as ctx:
                client.login(server="s", user="u", password="secret123")
            err_msg = str(ctx.exception)
            self.assertNotIn("secret123", err_msg)

    def test_login_password_from_env(self):
        env = {"ZENTAO_PASSWORD": "envpass"}
        with patch.dict(os.environ, env, clear=False):
            with self._mock_run(stdout='{"status":"ok"}'):
                client = ZentaoClient()
                result = client.login(server="https://z.example.com", user="u")
        self.assertEqual(result["status"], "ok")

    def test_profile_switch_on_get_item(self):
        responses = iter([
            # First call: profile switch
            MagicMock(returncode=0, stdout="Switched to admin@z.com", stderr=""),
            # Second call: get item
            MagicMock(returncode=0, stdout='{"id":1,"title":"A"}', stderr=""),
        ])
        with patch("subprocess.run", side_effect=lambda *a, **k: next(responses)):
            client = ZentaoClient(profile="admin@z.com")
            item = client.get_item("story", "1")
        self.assertEqual(item.id, "1")
        self.assertEqual(item.title, "A")

    def test_profile_switch_on_list_items(self):
        responses = iter([
            MagicMock(returncode=0, stdout="Switched to admin@z.com", stderr=""),
            MagicMock(returncode=0, stdout='[{"id":2}]', stderr=""),
        ])
        with patch("subprocess.run", side_effect=lambda *a, **k: next(responses)):
            client = ZentaoClient(profile="admin@z.com")
            items = client.list_items("bug")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, "2")

    def test_profile_text_response_treated_as_success(self):
        with self._mock_run(stdout="Switched to admin@z.com"):
            client = ZentaoClient()
            result = client._run(["profile", "admin@z.com"])
        self.assertTrue(result.get("success"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
