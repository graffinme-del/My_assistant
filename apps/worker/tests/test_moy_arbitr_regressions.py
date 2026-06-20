from datetime import date
import unittest

import moy_arbitr_client
import worker


class MoyArbitrParserRegressionTest(unittest.TestCase):
    def test_parser_fallback_applies_date_filter(self) -> None:
        def fake_details_by_id(_case_id: str) -> dict:
            return {
                "Success": 1,
                "Cases": [
                    {
                        "CaseInstances": [
                            {
                                "InstanceEvents": [
                                    {
                                        "Date": "2025-12-31",
                                        "File": "https://kad.arbitr.ru/Document/PdfDocument/old.pdf",
                                    },
                                    {
                                        "Date": "2026-01-10",
                                        "File": "https://kad.arbitr.ru/Document/PdfDocument/new.pdf",
                                    },
                                    {
                                        "File": "https://kad.arbitr.ru/Document/PdfDocument/no-date.pdf",
                                    },
                                ]
                            }
                        ]
                    }
                ],
            }

        old_key = worker.os.environ.get("PARSER_API_KEY")
        old_fallback = worker.MOY_ARBITR_PARSER_FALLBACK
        old_details_by_id = worker.parser_details_by_id
        try:
            worker.os.environ["PARSER_API_KEY"] = "test-key"
            worker.MOY_ARBITR_PARSER_FALLBACK = True
            worker.parser_details_by_id = fake_details_by_id

            docs, diag = worker.moy_arbitr_docs_from_parser_fallback(
                {
                    "card_url": "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111",
                },
                "A00-1/2026",
                date_from=date(2026, 1, 1),
                date_to=date(2026, 12, 31),
            )
        finally:
            if old_key is None:
                worker.os.environ.pop("PARSER_API_KEY", None)
            else:
                worker.os.environ["PARSER_API_KEY"] = old_key
            worker.MOY_ARBITR_PARSER_FALLBACK = old_fallback
            worker.parser_details_by_id = old_details_by_id

        self.assertEqual([doc["file_url"] for doc in docs], ["https://kad.arbitr.ru/Document/PdfDocument/new.pdf"])
        self.assertIn("kept=1", diag)
        self.assertIn("skipped_no_date=1", diag)


class _FakePage:
    url = "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111"

    def goto(self, *_args, **_kwargs) -> None:
        return None

    def wait_for_timeout(self, *_args, **_kwargs) -> None:
        return None


class _FakeContext:
    def new_page(self) -> _FakePage:
        return _FakePage()


class _FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def new_context(self, **_kwargs) -> _FakeContext:
        return _FakeContext()

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.browser = browser

    def launch(self, **_kwargs) -> _FakeBrowser:
        return self.browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.chromium = _FakeChromium(browser)
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakePlaywrightStarter:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self.playwright = playwright

    def start(self) -> _FakePlaywright:
        return self.playwright


class MoyArbitrBrowserMergeRegressionTest(unittest.TestCase):
    def test_prebuilt_documents_are_merged_with_browser_documents(self) -> None:
        fake_browser = _FakeBrowser()
        fake_playwright = _FakePlaywright(fake_browser)
        old_sync_playwright = moy_arbitr_client.sync_playwright
        old_ensure_authorized = moy_arbitr_client.ensure_authorized
        old_kad_collect = worker.open_kad_card_and_collect_docs
        old_hub_collect = moy_arbitr_client._collect_documents_via_my_arbitr_hub
        try:
            moy_arbitr_client.sync_playwright = lambda: _FakePlaywrightStarter(fake_playwright)
            moy_arbitr_client.ensure_authorized = lambda _page: None
            worker.open_kad_card_and_collect_docs = lambda *_args, **_kwargs: [
                {"file_url": "https://kad.arbitr.ru/Document/PdfDocument/parser.pdf", "title": "duplicate"},
                {"file_url": "https://kad.arbitr.ru/Document/PdfDocument/browser.pdf", "title": "browser"},
            ]
            moy_arbitr_client._collect_documents_via_my_arbitr_hub = lambda *_args, **_kwargs: [
                {"file_url": "https://kad.arbitr.ru/Document/PdfDocument/hub.pdf", "title": "hub"}
            ]

            _context, _browser, _pw, docs = moy_arbitr_client.open_case_and_download_documents(
                {
                    "card_url": "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111",
                    "case_number": "A00-1/2026",
                },
                prebuilt_documents=[
                    {"file_url": "https://kad.arbitr.ru/Document/PdfDocument/parser.pdf", "title": "parser"}
                ],
            )
        finally:
            moy_arbitr_client.sync_playwright = old_sync_playwright
            moy_arbitr_client.ensure_authorized = old_ensure_authorized
            worker.open_kad_card_and_collect_docs = old_kad_collect
            moy_arbitr_client._collect_documents_via_my_arbitr_hub = old_hub_collect

        self.assertEqual(
            [doc["file_url"] for doc in docs],
            [
                "https://kad.arbitr.ru/Document/PdfDocument/parser.pdf",
                "https://kad.arbitr.ru/Document/PdfDocument/browser.pdf",
                "https://kad.arbitr.ru/Document/PdfDocument/hub.pdf",
            ],
        )


if __name__ == "__main__":
    unittest.main()
