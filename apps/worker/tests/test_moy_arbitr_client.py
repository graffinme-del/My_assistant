import sys
import types


playwright_module = types.ModuleType("playwright")
sync_api_module = types.ModuleType("playwright.sync_api")
sync_api_module.TimeoutError = TimeoutError
sync_api_module.sync_playwright = lambda: None
sys.modules.setdefault("playwright", playwright_module)
sys.modules.setdefault("playwright.sync_api", sync_api_module)

from moy_arbitr_client import _merge_prebuilt_documents


def test_merge_prebuilt_documents_keeps_browser_docs_and_deduplicates() -> None:
    docs = [{"file_url": "https://kad.arbitr.ru/doc/browser.pdf", "title": "browser"}]
    seen = {"https://kad.arbitr.ru/doc/browser.pdf"}
    prebuilt = [
        {"file_url": "https://kad.arbitr.ru/doc/browser.pdf", "title": "duplicate"},
        {"file_url": "https://kad.arbitr.ru/doc/parser.pdf", "title": "parser"},
    ]

    _merge_prebuilt_documents(docs, seen, prebuilt, cap=5)

    assert docs == [
        {"file_url": "https://kad.arbitr.ru/doc/browser.pdf", "title": "browser"},
        {"file_url": "https://kad.arbitr.ru/doc/parser.pdf", "title": "parser"},
    ]
    assert seen == {
        "https://kad.arbitr.ru/doc/browser.pdf",
        "https://kad.arbitr.ru/doc/parser.pdf",
    }


def test_merge_prebuilt_documents_respects_existing_cap() -> None:
    docs = [{"file_url": "browser-1"}]
    seen = {"browser-1"}
    prebuilt = [{"file_url": "parser-1"}, {"file_url": "parser-2"}]

    _merge_prebuilt_documents(docs, seen, prebuilt, cap=2)

    assert docs == [{"file_url": "browser-1"}, {"file_url": "parser-1"}]
