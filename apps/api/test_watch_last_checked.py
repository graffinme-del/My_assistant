"""Regression: watch last_checked_at must not advance on failed/cancelled syncs."""

from __future__ import annotations

import unittest

from app.watch_last_checked import should_update_watch_last_checked


class WatchLastCheckedTests(unittest.TestCase):
    def test_only_done_bumps_last_checked(self) -> None:
        self.assertTrue(should_update_watch_last_checked("done"))
        self.assertTrue(should_update_watch_last_checked(" done "))

    def test_non_success_statuses_do_not_bump(self) -> None:
        for status in (
            "failed",
            "cancelled",
            "needs_manual_step",
            "running",
            "pending",
            "",
        ):
            with self.subTest(status=status):
                self.assertFalse(should_update_watch_last_checked(status))


if __name__ == "__main__":
    unittest.main()
