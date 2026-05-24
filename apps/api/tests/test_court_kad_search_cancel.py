import unittest

from app.court_kad_search import looks_like_cancel_court_sync_jobs


class CourtSyncCancelIntentTest(unittest.TestCase):
    def test_explicit_download_cancel_commands_still_match(self) -> None:
        self.assertTrue(looks_like_cancel_court_sync_jobs("останови все задачи"))
        self.assertTrue(looks_like_cancel_court_sync_jobs("отмени задачи кад"))
        self.assertTrue(looks_like_cancel_court_sync_jobs("останови процесс скачивания"))

    def test_generic_or_negated_stop_phrases_do_not_cancel_jobs(self) -> None:
        self.assertFalse(looks_like_cancel_court_sync_jobs("не останови всё, давайте разберём претензию"))
        self.assertFalse(looks_like_cancel_court_sync_jobs("нужно остановить все процессы обжалования по сути"))
        self.assertFalse(looks_like_cancel_court_sync_jobs("останови все процессы по делу, но фоновые задачи не трогай"))


if __name__ == "__main__":
    unittest.main()
