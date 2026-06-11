import importlib
import sys
import types
import unittest


def _load_client():
    if "playwright.sync_api" not in sys.modules:
        playwright = types.ModuleType("playwright")
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.TimeoutError = TimeoutError
        sync_api.sync_playwright = lambda: None
        sys.modules["playwright"] = playwright
        sys.modules["playwright.sync_api"] = sync_api
    return importlib.import_module("moy_arbitr_client")


class FakePage:
    url = "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111"

    def goto(self, *_args, **_kwargs) -> None:
        return None

    def wait_for_timeout(self, *_args, **_kwargs) -> None:
        return None


class FakeContext:
    def new_page(self) -> FakePage:
        return FakePage()


class FakeBrowser:
    def close(self) -> None:
        return None


class FakeChromium:
    def launch(self, *_args, **_kwargs) -> FakeBrowser:
        return FakeBrowser()


class FakePlaywright:
    chromium = FakeChromium()

    def start(self) -> "FakePlaywright":
        return self

    def stop(self) -> None:
        return None


class MoyArbitrDocumentMergeTest(unittest.TestCase):
    def test_prebuilt_parser_documents_are_merged_with_browser_discovery(self) -> None:
        client = _load_client()
        old_sync_playwright = client.sync_playwright
        old_new_context = client._new_context
        old_ensure_authorized = client.ensure_authorized
        old_hub = client._collect_documents_via_my_arbitr_hub
        old_worker = sys.modules.get("worker")
        fake_worker = types.ModuleType("worker")
        fake_worker.open_kad_card_and_collect_docs = lambda *_args, **_kwargs: [
            {"title": "from browser", "file_url": "https://kad.arbitr.ru/doc/browser.pdf"},
            {"title": "duplicate parser", "file_url": "https://kad.arbitr.ru/doc/parser.pdf"},
        ]
        fake_worker.collect_kad_documents_from_linked_cards = lambda *_args, **_kwargs: []

        try:
            client.sync_playwright = lambda: FakePlaywright()
            client._new_context = lambda _browser: FakeContext()
            client.ensure_authorized = lambda _page: None
            client._collect_documents_via_my_arbitr_hub = lambda *_args, **_kwargs: [
                {"title": "from hub", "file_url": "https://kad.arbitr.ru/doc/hub.pdf"}
            ]
            sys.modules["worker"] = fake_worker

            _context, _browser, _pw, docs = client.open_case_and_download_documents(
                {
                    "card_url": "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111",
                    "case_number": "A40-1/2026",
                },
                prebuilt_documents=[
                    {"title": "from parser", "file_url": "https://kad.arbitr.ru/doc/parser.pdf"}
                ],
            )

            self.assertEqual(
                [d["file_url"] for d in docs],
                [
                    "https://kad.arbitr.ru/doc/parser.pdf",
                    "https://kad.arbitr.ru/doc/browser.pdf",
                    "https://kad.arbitr.ru/doc/hub.pdf",
                ],
            )
        finally:
            client.sync_playwright = old_sync_playwright
            client._new_context = old_new_context
            client.ensure_authorized = old_ensure_authorized
            client._collect_documents_via_my_arbitr_hub = old_hub
            if old_worker is None:
                sys.modules.pop("worker", None)
            else:
                sys.modules["worker"] = old_worker


if __name__ == "__main__":
    unittest.main()
