"""Unit tests for Parser-API download gate (sync vs download vs preview)."""

from __future__ import annotations

import unittest

from parser_download_gate import should_download_via_parser


class ParserDownloadGateTests(unittest.TestCase):
    def test_sync_uses_parser_when_enabled(self) -> None:
        self.assertTrue(
            should_download_via_parser(use_parser_api=True, run_mode="sync")
        )

    def test_download_uses_parser_when_enabled(self) -> None:
        self.assertTrue(
            should_download_via_parser(use_parser_api=True, run_mode="download")
        )

    def test_preview_never_uses_parser_download(self) -> None:
        self.assertFalse(
            should_download_via_parser(use_parser_api=True, run_mode="preview")
        )

    def test_disabled_flag_skips_parser(self) -> None:
        self.assertFalse(
            should_download_via_parser(use_parser_api=False, run_mode="sync")
        )
        self.assertFalse(
            should_download_via_parser(use_parser_api=False, run_mode="download")
        )

    def test_mode_normalization(self) -> None:
        self.assertTrue(
            should_download_via_parser(use_parser_api=True, run_mode=" SYNC ")
        )
        self.assertFalse(
            should_download_via_parser(use_parser_api=True, run_mode="")
        )


if __name__ == "__main__":
    unittest.main()
