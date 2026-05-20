from __future__ import annotations

import unittest


class CompatibilityImportTests(unittest.TestCase):
    def test_public_import_paths_survive_package_refactor(self) -> None:
        """
        用途與流程：確認深度拆包後仍保留既有 public import path，避免外部腳本與舊測試被迫改寫。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；任一 import 或 callable assertion 失敗時由 unittest 回報。
        """
        from signal_forge import PhaseRunner
        from signal_forge.cli import main
        from signal_forge.phase import SignalDigest
        from signal_forge.reporting import write_phase_outputs

        self.assertTrue(callable(main))
        self.assertTrue(callable(write_phase_outputs))
        self.assertEqual(PhaseRunner.__name__, "PhaseRunner")
        self.assertEqual(SignalDigest.__name__, "SignalDigest")


if __name__ == "__main__":
    unittest.main()
