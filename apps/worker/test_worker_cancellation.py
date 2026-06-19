import unittest
from unittest.mock import Mock, patch

import worker


class _FakeBrowser:
    def __init__(self):
        self.context = Mock()
        self.page = Mock()
        self.context.new_page.return_value = self.page
        self.close = Mock()

    def new_context(self, **_kwargs):
        return self.context


class _FakePlaywright:
    def __init__(self, browser):
        self.chromium = Mock()
        self.chromium.launch.return_value = browser


class _FakeSyncPlaywright:
    def __init__(self, browser):
        self._playwright = _FakePlaywright(browser)

    def __enter__(self):
        return self._playwright

    def __exit__(self, *_args):
        return False


class WorkerCancellationTests(unittest.TestCase):
    def test_kad_browser_job_stops_after_document_discovery_without_completing(self):
        browser = _FakeBrowser()
        stop_checks = iter([False, False, True])
        job = {
            "id": 42,
            "query_type": "case_number",
            "query_value": "A40-1/2026",
            "run_mode": "download",
        }
        cases = [{"card_url": "https://kad.arbitr.ru/Card/case-id", "case_number": "A40-1/2026"}]
        docs = [{"title": "doc", "file_url": "https://kad.arbitr.ru/Document/Pdf/1"}]

        with (
            patch.object(worker, "COURT_SYNC_USE_PARSER_API", False),
            patch.object(worker, "court_sync_job_stopped_remotely", side_effect=lambda _job_id: next(stop_checks)),
            patch.object(worker, "search_cases_for_job", return_value=cases),
            patch.object(worker, "ensure_case_id", return_value=7),
            patch.object(worker, "register_case_source", return_value=10),
            patch.object(worker, "report_progress"),
            patch.object(worker, "sync_playwright", return_value=_FakeSyncPlaywright(browser)),
            patch.object(worker, "extract_case_number_from_page", return_value=None),
            patch.object(worker, "open_kad_card_and_collect_docs", return_value=docs) as collect_docs,
            patch.object(worker, "download_document_via_context") as download_doc,
            patch.object(worker, "complete_job") as complete_job,
        ):
            worker.process_job(job)

        collect_docs.assert_called_once_with(
            browser.page,
            cases[0]["card_url"],
            max(60_000, worker.COURT_SYNC_TIMEOUT_SEC * 1000),
            progress=worker.report_progress,
            job_id=42,
        )
        download_doc.assert_not_called()
        complete_job.assert_not_called()
        browser.close.assert_called_once()

    def test_moy_arbitr_job_stops_between_documents_without_completing(self):
        browser = Mock()
        playwright_driver = Mock()
        stop_checks = iter([False, False, True])
        job = {
            "id": 99,
            "query_type": "moy_arbitr_case_number",
            "query_value": "A40-2/2026",
            "run_mode": "download",
        }
        cases = [{"card_url": "https://my.arbitr.ru/#case", "case_number": "A40-2/2026"}]
        docs = [{"title": "doc", "file_url": "https://kad.arbitr.ru/Document/Pdf/2"}]

        with (
            patch.object(worker, "court_sync_job_stopped_remotely", side_effect=lambda _job_id: next(stop_checks)),
            patch.object(worker, "search_moy_arbitr_cases", return_value=cases),
            patch.object(worker, "ensure_case_id", return_value=8),
            patch.object(worker, "register_case_source", return_value=11),
            patch.object(worker, "moy_arbitr_docs_from_parser_fallback", return_value=([], "no parser docs")),
            patch.object(
                worker,
                "open_case_and_download_documents",
                return_value=(Mock(), browser, playwright_driver, docs),
            ),
            patch.object(worker, "download_moy_arbitr_document") as download_doc,
            patch.object(worker, "complete_job") as complete_job,
            patch.object(worker, "report_progress"),
        ):
            worker.process_moy_arbitr_job(job)

        download_doc.assert_not_called()
        complete_job.assert_not_called()
        browser.close.assert_called_once()
        playwright_driver.stop.assert_called_once()

    def test_kad_tab_collection_does_not_navigate_when_job_was_cancelled(self):
        page = Mock()
        page.remove_listener = Mock()

        with (
            patch.object(worker, "KAD_TAB_LABELS", ("Картотека",)),
            patch.object(worker, "court_sync_job_stopped_remotely", return_value=True),
        ):
            docs = worker.open_kad_card_and_collect_docs(
                page,
                "https://kad.arbitr.ru/Card/case-id",
                60_000,
                job_id=123,
            )

        self.assertEqual(docs, [])
        page.goto.assert_not_called()


if __name__ == "__main__":
    unittest.main()
