import importlib
import sys
import types
import unittest


class _FakePage:
    url = "https://kad.arbitr.ru/Card/00000000-0000-0000-0000-000000000000"

    def goto(self, *_args, **_kwargs) -> None:
        return None

    def wait_for_timeout(self, *_args, **_kwargs) -> None:
        return None


class _FakeContext:
    def __init__(self) -> None:
        self.page = _FakePage()

    def new_page(self) -> _FakePage:
        return self.page


class _FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self) -> None:
        self.browser = _FakeBrowser()

    def launch(self, *_args, **_kwargs) -> _FakeBrowser:
        return self.browser


class _FakePlaywright:
    def __init__(self) -> None:
        self.chromium = _FakeChromium()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakeSyncPlaywright:
    def __init__(self) -> None:
        self.driver = _FakePlaywright()

    def start(self) -> _FakePlaywright:
        return self.driver


class MoyArbitrDocumentCollectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.TimeoutError = TimeoutError
        sync_api.sync_playwright = lambda: _FakeSyncPlaywright()
        sys.modules.setdefault("playwright", types.ModuleType("playwright"))
        sys.modules["playwright.sync_api"] = sync_api
        cls.client = importlib.import_module("moy_arbitr_client")

    def setUp(self) -> None:
        self.fake_context = _FakeContext()
        self.client._new_context = lambda _browser: self.fake_context
        self.client.ensure_authorized = lambda _page: None
        self.client.sync_playwright = lambda: _FakeSyncPlaywright()

    def test_parser_documents_are_seeded_and_browser_sources_still_merge(self) -> None:
        parser_url = "https://kad.arbitr.ru/PdfDocument/parser.pdf"
        browser_url = "https://kad.arbitr.ru/PdfDocument/browser.pdf"
        hub_url = "https://kad.arbitr.ru/PdfDocument/hub.pdf"
        worker_mod = types.ModuleType("worker")
        worker_mod.open_kad_card_and_collect_docs = lambda *_args, **_kwargs: [
            {"file_url": parser_url, "title": "duplicate parser"},
            {"file_url": browser_url, "title": "browser"},
        ]
        sys.modules["worker"] = worker_mod
        self.client._collect_documents_via_my_arbitr_hub = lambda *_args, **_kwargs: [
            {"file_url": browser_url, "title": "duplicate browser"},
            {"file_url": hub_url, "title": "hub"},
        ]

        _context, browser, playwright_driver, docs = self.client.open_case_and_download_documents(
            {
                "card_url": "https://kad.arbitr.ru/Card/00000000-0000-0000-0000-000000000000",
                "case_number": "А40-1/2026",
            },
            prebuilt_documents=[{"file_url": parser_url, "title": "parser"}],
        )

        self.addCleanup(browser.close)
        self.addCleanup(playwright_driver.stop)
        self.assertEqual([doc["file_url"] for doc in docs], [parser_url, browser_url, hub_url])


if __name__ == "__main__":
    unittest.main()
