import sys
import types
import unittest


fake_playwright_api = types.ModuleType("playwright.sync_api")


class FakePlaywrightTimeoutError(Exception):
    pass


fake_playwright_api.TimeoutError = FakePlaywrightTimeoutError
fake_playwright_api.sync_playwright = lambda: None
sys.modules.setdefault("playwright", types.ModuleType("playwright"))
sys.modules["playwright.sync_api"] = fake_playwright_api

import moy_arbitr_client as client


class FakePage:
    url = "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111"

    def goto(self, *args, **kwargs):
        return None

    def wait_for_timeout(self, *args, **kwargs):
        return None


class FakeContext:
    def new_page(self):
        return FakePage()


class FakeBrowser:
    def close(self):
        return None


class FakeChromium:
    def launch(self, **kwargs):
        return FakeBrowser()


class FakePlaywright:
    chromium = FakeChromium()

    def stop(self):
        return None


class FakePlaywrightStarter:
    def start(self):
        return FakePlaywright()


class MoyArbitrClientTests(unittest.TestCase):
    def test_prebuilt_parser_documents_are_merged_with_browser_discovery(self):
        calls = {"kad": 0, "hub": 0}
        old_sync_playwright = client.sync_playwright
        old_new_context = client._new_context
        old_ensure_authorized = client.ensure_authorized
        old_hub_collect = client._collect_documents_via_my_arbitr_hub
        old_worker = sys.modules.get("worker")
        fake_worker = types.ModuleType("worker")

        def collect_kad_docs(*args, **kwargs):
            calls["kad"] += 1
            return [
                {"title": "duplicate parser doc", "file_url": "https://kad.arbitr.ru/parser.pdf"},
                {"title": "browser-only doc", "file_url": "https://kad.arbitr.ru/browser.pdf"},
            ]

        def collect_hub_docs(*args, **kwargs):
            calls["hub"] += 1
            return [{"title": "hub-only doc", "file_url": "https://my.arbitr.ru/hub.pdf"}]

        fake_worker.open_kad_card_and_collect_docs = collect_kad_docs
        sys.modules["worker"] = fake_worker
        client.sync_playwright = lambda: FakePlaywrightStarter()
        client._new_context = lambda browser: FakeContext()
        client.ensure_authorized = lambda page: None
        client._collect_documents_via_my_arbitr_hub = collect_hub_docs
        try:
            _context, _browser, _pw, docs = client.open_case_and_download_documents(
                {
                    "card_url": "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111",
                    "case_number": "A00-1/2026",
                },
                prebuilt_documents=[
                    {"title": "parser doc", "file_url": "https://kad.arbitr.ru/parser.pdf"},
                ],
            )
        finally:
            client.sync_playwright = old_sync_playwright
            client._new_context = old_new_context
            client.ensure_authorized = old_ensure_authorized
            client._collect_documents_via_my_arbitr_hub = old_hub_collect
            if old_worker is None:
                sys.modules.pop("worker", None)
            else:
                sys.modules["worker"] = old_worker

        self.assertEqual(calls, {"kad": 1, "hub": 1})
        self.assertEqual(
            [d["file_url"] for d in docs],
            [
                "https://kad.arbitr.ru/parser.pdf",
                "https://kad.arbitr.ru/browser.pdf",
                "https://my.arbitr.ru/hub.pdf",
            ],
        )


if __name__ == "__main__":
    unittest.main()
