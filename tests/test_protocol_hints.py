import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zentao_analyzer.protocol_hints import ProtocolHintInputError, normalize_protocol_hints
from zentao_analyzer.repositories import parse_repo_args


class TestProtocolHints(unittest.TestCase):
    def setUp(self):
        self.soc_dir = tempfile.TemporaryDirectory()
        self.mcu_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.soc_dir.cleanup)
        self.addCleanup(self.mcu_dir.cleanup)
        self.repo_set = parse_repo_args([f"soc={self.soc_dir.name}", f"mcu={self.mcu_dir.name}"])

    def test_cli_hint_parses_roles_type_and_value(self):
        hints = normalize_protocol_hints(["soc,mcu:cmd_id=0x1234"], self.repo_set)
        self.assertEqual(hints[0].roles, ["soc", "mcu"])
        self.assertEqual(hints[0].type, "cmd_id")
        self.assertEqual(hints[0].value, "0x1234")

    def test_plain_text_defaults_to_all_roles(self):
        hints = normalize_protocol_hints(["CALLBACK_STATUS"], self.repo_set)
        self.assertEqual(hints[0].roles, ["soc", "mcu"])
        self.assertEqual(hints[0].type, "text")
        self.assertEqual(hints[0].value, "CALLBACK_STATUS")

    def test_mapping_hint_is_supported(self):
        hints = normalize_protocol_hints(
            [{"roles": ["mcu", "soc", "mcu"], "type": "field", "value": "CallBackSts"}],
            self.repo_set,
        )
        self.assertEqual(hints[0].roles, ["mcu", "soc"])
        self.assertEqual(hints[0].type, "field")

    def test_unknown_role_invalid_type_and_empty_value_are_rejected(self):
        with self.assertRaisesRegex(ProtocolHintInputError, "未知"):
            normalize_protocol_hints(["app:msg=CALLBACK_STATUS"], self.repo_set)
        with self.assertRaisesRegex(ProtocolHintInputError, "类型"):
            normalize_protocol_hints(["soc:opcode=1"], self.repo_set)
        with self.assertRaisesRegex(ProtocolHintInputError, "不能为空"):
            normalize_protocol_hints(["soc:msg="], self.repo_set)


if __name__ == "__main__":
    unittest.main(verbosity=2)
