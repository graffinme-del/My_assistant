from datetime import date
import sys
import types
import unittest

if "playwright.sync_api" not in sys.modules:
    playwright_mod = types.ModuleType("playwright")
    sync_api_mod = types.ModuleType("playwright.sync_api")
    sync_api_mod.TimeoutError = TimeoutError
    sync_api_mod.sync_playwright = lambda: None
    sys.modules.setdefault("playwright", playwright_mod)
    sys.modules.setdefault("playwright.sync_api", sync_api_mod)

if "httpx" not in sys.modules:
    httpx_mod = types.ModuleType("httpx")
    httpx_mod.HTTPStatusError = RuntimeError
    sys.modules["httpx"] = httpx_mod

from moy_arbitr_client import _merge_prebuilt_documents
from parser_api_client import filter_pdf_urls_by_date_range


class DocumentDiscoveryRegressionTests(unittest.TestCase):
    def test_date_filter_keeps_undated_urls_to_avoid_document_loss(self) -> None:
        urls, included_no_date = filter_pdf_urls_by_date_range(
            [
                ("https://kad.arbitr.ru/Document/Pdf/in-range", date(2026, 2, 1)),
                ("https://kad.arbitr.ru/Document/Pdf/out-of-range", date(2025, 12, 31)),
                ("https://kad.arbitr.ru/Document/Pdf/no-date", None),
            ],
            date(2026, 1, 1),
            date(2026, 12, 31),
        )

        self.assertEqual(
            urls,
            [
                "https://kad.arbitr.ru/Document/Pdf/in-range",
                "https://kad.arbitr.ru/Document/Pdf/no-date",
            ],
        )
        self.assertEqual(included_no_date, 1)

    def test_parser_documents_are_merged_with_browser_documents(self) -> None:
        merged = _merge_prebuilt_documents(
            [
                {"title": "browser", "file_url": "https://kad.arbitr.ru/Document/Pdf/browser"},
            ],
            [
                {"title": "duplicate", "file_url": "https://kad.arbitr.ru/Document/Pdf/browser"},
                {"title": "parser", "file_url": "https://kad.arbitr.ru/Document/Pdf/parser"},
            ],
            cap=10,
        )

        self.assertEqual(
            [x["file_url"] for x in merged],
            [
                "https://kad.arbitr.ru/Document/Pdf/browser",
                "https://kad.arbitr.ru/Document/Pdf/parser",
            ],
        )

    def test_parser_merge_respects_document_cap(self) -> None:
        merged = _merge_prebuilt_documents(
            [
                {"title": "browser", "file_url": "https://kad.arbitr.ru/Document/Pdf/browser"},
            ],
            [
                {"title": "parser", "file_url": "https://kad.arbitr.ru/Document/Pdf/parser"},
            ],
            cap=1,
        )

        self.assertEqual([x["title"] for x in merged], ["browser"])


if __name__ == "__main__":
    unittest.main()
