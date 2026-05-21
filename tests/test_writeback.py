import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from writeback import prepare_writeback_status, writeback_to_zentao


class TestWriteback(unittest.TestCase):
    def test_prepare_writeback_status_not_implemented(self):
        status = prepare_writeback_status()
        self.assertEqual(status["supported"], False)
        self.assertEqual(status["status"], "not_implemented")

    def test_writeback_to_zentao_does_not_write(self):
        result = writeback_to_zentao(item_id="1")
        self.assertEqual(result["supported"], False)
        self.assertEqual(result["status"], "not_implemented")
        self.assertIn("阶段三不实现", result["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
