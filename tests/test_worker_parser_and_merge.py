import sys
import types
import unittest
from datetime import date

from parser_api_client import filter_pdf_urls_by_date_range


playwright_pkg = types.ModuleType("playwright")
sync_api = types.ModuleType("playwright.sync_api")
sync_api.TimeoutError = TimeoutError
sync_api.sync_playwright = lambda: None
sys.modules.setdefault("playwright", playwright_pkg)
sys.modules.setdefault("playwright.sync_api", sync_api)

from moy_arbitr_client import _merge_document_sources  # noqa: E402


class ParserApiDateFilterTests(unittest.TestCase):
    def test_undated_urls_are_kept_when_they_are_the_only_parser_results(self):
        urls, skipped = filter_pdf_urls_by_date_range(
            [
                ("https://kad.arbitr.ru/Document/PdfDocument/1", None),
                ("https://kad.arbitr.ru/Document/PdfDocument/2", None),
            ],
            date(2026, 1, 1),
            date(2026, 12, 31),
        )

        self.assertEqual(
            urls,
            [
                "https://kad.arbitr.ru/Document/PdfDocument/1",
                "https://kad.arbitr.ru/Document/PdfDocument/2",
            ],
        )
        self.assertEqual(skipped, 0)

    def test_dated_matches_win_over_undated_fallback_urls(self):
        urls, skipped = filter_pdf_urls_by_date_range(
            [
                ("https://kad.arbitr.ru/Document/PdfDocument/matching", date(2026, 2, 3)),
                ("https://kad.arbitr.ru/Document/PdfDocument/undated", None),
                ("https://kad.arbitr.ru/Document/PdfDocument/old", date(2025, 2, 3)),
            ],
            date(2026, 1, 1),
            date(2026, 12, 31),
        )

        self.assertEqual(urls, ["https://kad.arbitr.ru/Document/PdfDocument/matching"])
        self.assertEqual(skipped, 1)


class MoyArbitrMergeTests(unittest.TestCase):
    def test_merge_keeps_more_than_moy_arbitr_default_cap_and_deduplicates_urls(self):
        parser_docs = [
            {"title": f"parser-{idx}", "file_url": f"https://kad.arbitr.ru/Document/PdfDocument/{idx}"}
            for idx in range(85)
        ]
        browser_docs = [
            {"title": "duplicate", "file_url": "https://kad.arbitr.ru/Document/PdfDocument/5"},
            {"title": "browser-only", "file_url": "https://my.arbitr.ru/File/extra"},
        ]

        merged = _merge_document_sources(parser_docs, browser_docs)

        self.assertEqual(len(merged), 86)
        self.assertEqual(merged[-1]["title"], "browser-only")
        self.assertEqual(
            sum(1 for doc in merged if doc["file_url"] == "https://kad.arbitr.ru/Document/PdfDocument/5"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
