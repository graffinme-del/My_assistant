import unittest

from app.court_kad_search import looks_like_cancel_court_sync_jobs


class CancelCourtSyncIntentTest(unittest.TestCase):
    def test_explicit_cancel_commands_match(self) -> None:
        positives = [
            "останови все задачи",
            "пожалуйста останови загрузку",
            "отмени задачи КАД",
            "сбрось очередь",
            "очисти очередь кад",
        ]
        for text in positives:
            with self.subTest(text=text):
                self.assertTrue(looks_like_cancel_court_sync_jobs(text))

    def test_conversational_or_negated_text_does_not_cancel(self) -> None:
        negatives = [
            "Не останови все задачи сразу",
            "Что будет, если останови все загрузки?",
            "Расскажи, можно ли останови всё без потери файлов",
            "отчёт по задаче 58",
        ]
        for text in negatives:
            with self.subTest(text=text):
                self.assertFalse(looks_like_cancel_court_sync_jobs(text))


if __name__ == "__main__":
    unittest.main()
