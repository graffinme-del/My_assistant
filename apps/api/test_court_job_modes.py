"""Unit tests for court sync job run_mode helpers."""

from __future__ import annotations

import unittest

from app.court_job_modes import is_document_ingest_run_mode


class CourtJobModesTests(unittest.TestCase):
    def test_download_and_sync_are_ingest(self) -> None:
        self.assertTrue(is_document_ingest_run_mode("download"))
        self.assertTrue(is_document_ingest_run_mode("sync"))
        self.assertTrue(is_document_ingest_run_mode(" SYNC "))

    def test_preview_is_not_ingest(self) -> None:
        self.assertFalse(is_document_ingest_run_mode("preview"))
        self.assertFalse(is_document_ingest_run_mode(""))
        self.assertFalse(is_document_ingest_run_mode(None))


if __name__ == "__main__":
    unittest.main()
