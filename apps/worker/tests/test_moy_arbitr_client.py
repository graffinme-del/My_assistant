import sys
import types
from pathlib import Path


playwright_pkg = types.ModuleType("playwright")
playwright_sync_api = types.ModuleType("playwright.sync_api")
playwright_sync_api.TimeoutError = TimeoutError
playwright_sync_api.sync_playwright = lambda: None
sys.modules.setdefault("playwright", playwright_pkg)
sys.modules.setdefault("playwright.sync_api", playwright_sync_api)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import moy_arbitr_client  # noqa: E402


class _FakePage:
    url = "https://my.arbitr.ru/#/case/test"

    def goto(self, *args, **kwargs) -> None:
        pass

    def wait_for_timeout(self, *args, **kwargs) -> None:
        pass


class _FakeContext:
    def __init__(self) -> None:
        self.page = _FakePage()

    def new_page(self) -> _FakePage:
        return self.page


class _FakeBrowser:
    def close(self) -> None:
        pass


class _FakePlaywright:
    def __init__(self) -> None:
        self.chromium = types.SimpleNamespace(launch=lambda *args, **kwargs: _FakeBrowser())

    def stop(self) -> None:
        pass


class _FakePlaywrightStarter:
    def start(self) -> _FakePlaywright:
        return _FakePlaywright()


def test_open_case_merges_prebuilt_parser_documents_with_browser_discovery() -> None:
    old_sync_playwright = moy_arbitr_client.sync_playwright
    old_new_context = moy_arbitr_client._new_context
    old_ensure_authorized = moy_arbitr_client.ensure_authorized
    old_collect_moy = moy_arbitr_client.collect_moy_arbitr_documents
    old_worker = sys.modules.get("worker")
    try:
        moy_arbitr_client.sync_playwright = lambda: _FakePlaywrightStarter()
        moy_arbitr_client._new_context = lambda browser: _FakeContext()
        moy_arbitr_client.ensure_authorized = lambda page: None
        moy_arbitr_client.collect_moy_arbitr_documents = lambda page, card_url: [
            {"title": "browser duplicate", "file_url": "https://kad.arbitr.ru/doc/parser.pdf"},
            {"title": "browser new", "file_url": "https://kad.arbitr.ru/doc/browser.pdf"},
        ]
        sys.modules["worker"] = types.SimpleNamespace(
            collect_kad_documents_from_linked_cards=lambda page, text, nav_ms: [
                {"title": "linked new", "file_url": "https://kad.arbitr.ru/doc/linked.pdf"}
            ],
            open_kad_card_and_collect_docs=lambda *args, **kwargs: [],
        )

        context, browser, playwright_driver, docs = moy_arbitr_client.open_case_and_download_documents(
            {"card_url": "https://my.arbitr.ru/#/case/test", "case_number": "A40-1/2026"},
            prebuilt_documents=[
                {"title": "parser seed", "file_url": "https://kad.arbitr.ru/doc/parser.pdf"}
            ],
        )
    finally:
        moy_arbitr_client.sync_playwright = old_sync_playwright
        moy_arbitr_client._new_context = old_new_context
        moy_arbitr_client.ensure_authorized = old_ensure_authorized
        moy_arbitr_client.collect_moy_arbitr_documents = old_collect_moy
        if old_worker is None:
            sys.modules.pop("worker", None)
        else:
            sys.modules["worker"] = old_worker

    assert context is not None
    assert browser is not None
    assert playwright_driver is not None
    assert [doc["file_url"] for doc in docs] == [
        "https://kad.arbitr.ru/doc/parser.pdf",
        "https://kad.arbitr.ru/doc/browser.pdf",
        "https://kad.arbitr.ru/doc/linked.pdf",
    ]
