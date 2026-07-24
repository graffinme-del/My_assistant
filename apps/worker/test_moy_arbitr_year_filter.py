"""Focused tests: Moy Arbitr Parser-API fallback must honor date bounds."""

from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

import worker as worker_mod


class MoyArbitrParserDateFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_fallback = os.environ.get("MOY_ARBITR_PARSER_FALLBACK")
        self._prev_key = os.environ.get("PARSER_API_KEY")
        os.environ["MOY_ARBITR_PARSER_FALLBACK"] = "1"
        os.environ["PARSER_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        if self._prev_fallback is None:
            os.environ.pop("MOY_ARBITR_PARSER_FALLBACK", None)
        else:
            os.environ["MOY_ARBITR_PARSER_FALLBACK"] = self._prev_fallback
        if self._prev_key is None:
            os.environ.pop("PARSER_API_KEY", None)
        else:
            os.environ["PARSER_API_KEY"] = self._prev_key

    def test_fallback_keeps_only_in_range_dated_urls(self) -> None:
        entries = [
            ("https://kad.arbitr.ru/PdfDocument/old.pdf", date(2023, 5, 1)),
            ("https://kad.arbitr.ru/PdfDocument/in.pdf", date(2026, 2, 10)),
            ("https://kad.arbitr.ru/PdfDocument/nodate.pdf", None),
            ("https://kad.arbitr.ru/PdfDocument/late.pdf", date(2027, 1, 1)),
        ]
        with (
            patch.object(worker_mod, "MOY_ARBITR_PARSER_FALLBACK", True),
            patch.object(worker_mod, "_case_id_from_kad_card_url", return_value="cid-1"),
            patch.object(worker_mod, "parser_details_by_id", return_value={"Success": True, "Cases": [{}]}),
            patch.object(worker_mod, "extract_kad_pdf_url_entries_with_dates", return_value=entries),
        ):
            docs, diag = worker_mod.moy_arbitr_docs_from_parser_fallback(
                {"card_url": "https://kad.arbitr.ru/Card/cid-1"},
                "A40-1/2024",
                date_from=date(2026, 1, 1),
                date_to=date(2026, 12, 31),
            )
        urls = [d["file_url"] for d in docs]
        self.assertEqual(urls, ["https://kad.arbitr.ru/PdfDocument/in.pdf"])
        self.assertIn("kept=1", diag)
        self.assertIn("skipped_no_date=1", diag)

    def test_job_year_bounds_override_env(self) -> None:
        os.environ["PARSER_DOWNLOAD_YEAR_MIN"] = "2020"
        os.environ["PARSER_DOWNLOAD_YEAR_MAX"] = "2020"
        try:
            lo, hi = worker_mod._parser_pdf_date_bounds_for_job(
                {"parser_year_min": 2026, "parser_year_max": 2026}
            )
            self.assertEqual(lo, date(2026, 1, 1))
            self.assertEqual(hi, date(2026, 12, 31))
        finally:
            os.environ.pop("PARSER_DOWNLOAD_YEAR_MIN", None)
            os.environ.pop("PARSER_DOWNLOAD_YEAR_MAX", None)


if __name__ == "__main__":
    unittest.main()
