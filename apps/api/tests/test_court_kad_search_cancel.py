import unittest

from app.court_kad_search import looks_like_cancel_court_sync_jobs


class CourtSyncCancelIntentTest(unittest.TestCase):
    def test_positive_cancel_phrases_still_match(self) -> None:
        self.assertTrue(looks_like_cancel_court_sync_jobs("останови все задачи КАД"))
        self.assertTrue(looks_like_cancel_court_sync_jobs("отмени все задачи"))
        self.assertTrue(looks_like_cancel_court_sync_jobs("сбрось очередь"))

    def test_negated_cancel_phrases_do_not_cancel_jobs(self) -> None:
        self.assertFalse(looks_like_cancel_court_sync_jobs("не останови все задачи"))
        self.assertFalse(looks_like_cancel_court_sync_jobs("не отмени все задачи"))
        self.assertFalse(looks_like_cancel_court_sync_jobs("не надо остановить все задачи"))
        self.assertFalse(looks_like_cancel_court_sync_jobs("нельзя сбрось очередь"))

    def test_task_report_is_not_cancel(self) -> None:
        self.assertFalse(looks_like_cancel_court_sync_jobs("отчет по задаче 58"))


if __name__ == "__main__":
    unittest.main()
