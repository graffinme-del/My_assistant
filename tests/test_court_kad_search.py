import unittest

from app.court_kad_search import looks_like_cancel_court_sync_jobs, looks_like_court_search_command


class CourtKadSearchIntentTests(unittest.TestCase):
    def test_hypothetical_or_negated_cancel_phrases_do_not_cancel_jobs(self):
        for text in (
            "не останови все процессы",
            "как останови фоновую загрузку из кад?",
            "что будет, если останови все задачи?",
            "отчет по задаче",
        ):
            with self.subTest(text=text):
                self.assertFalse(looks_like_cancel_court_sync_jobs(text))

    def test_explicit_cancel_commands_still_match(self):
        for text in (
            "останови все задачи",
            "отмени задачи кад",
            "сбрось очередь",
            "пожалуйста останови фоновую загрузку из кад",
        ):
            with self.subTest(text=text):
                self.assertTrue(looks_like_cancel_court_sync_jobs(text))
                self.assertTrue(looks_like_court_search_command(text))


if __name__ == "__main__":
    unittest.main()
