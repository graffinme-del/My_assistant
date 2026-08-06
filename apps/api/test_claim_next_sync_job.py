"""Regression: court-sync claim must lock the pending row (no double-claim)."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.court_sync_service import claim_next_sync_job


class ClaimNextSyncJobTests(unittest.TestCase):
    def test_claim_uses_for_update_skip_locked(self) -> None:
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.with_for_update.return_value = query
        query.first.return_value = None

        self.assertIsNone(claim_next_sync_job(db))
        query.with_for_update.assert_called_once_with(skip_locked=True)

    def test_claim_marks_pending_job_running(self) -> None:
        job = SimpleNamespace(
            id=7,
            status="pending",
            step="queued",
            started_at=None,
        )
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.with_for_update.return_value = query
        query.first.return_value = job

        claimed = claim_next_sync_job(db)

        self.assertIs(claimed, job)
        self.assertEqual(job.status, "running")
        self.assertEqual(job.step, "claimed")
        self.assertIsInstance(job.started_at, datetime)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(job)
        self.assertGreaterEqual(db.add.call_count, 2)

    def test_claim_refuses_non_pending_row_after_lock(self) -> None:
        job = SimpleNamespace(
            id=9,
            status="running",
            step="claimed",
            started_at=datetime.utcnow(),
        )
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.with_for_update.return_value = query
        query.first.return_value = job

        self.assertIsNone(claim_next_sync_job(db))
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
