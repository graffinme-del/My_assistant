"""Focused tests: Moy Arbitr chat must capture year range for PDF filtering."""

from __future__ import annotations

import unittest

from app.moy_arbitr import (
    format_moy_arbitr_search_queued_reply,
    format_parser_year_period,
    parse_moy_arbitr_search_request,
)


class MoyArbitrYearFilterTests(unittest.TestCase):
    def test_case_download_captures_single_year(self) -> None:
        req = parse_moy_arbitr_search_request(
            "скачай из мой арбитр дело А40-12345/2024 за 2026 год"
        )
        self.assertIsNotNone(req)
        assert req is not None
        self.assertEqual(req.query_type, "moy_arbitr_case_number")
        self.assertEqual(req.query_value, "A40-12345/2024")
        self.assertEqual(req.parser_year_min, 2026)
        self.assertEqual(req.parser_year_max, 2026)
        self.assertEqual(req.run_mode, "download")

    def test_case_download_captures_year_range(self) -> None:
        req = parse_moy_arbitr_search_request(
            "скачай документы из мой арбитр по делу А40-999/2023 с 2024 по 2026"
        )
        self.assertIsNotNone(req)
        assert req is not None
        self.assertEqual(req.parser_year_min, 2024)
        self.assertEqual(req.parser_year_max, 2026)

    def test_case_number_year_alone_does_not_set_filter(self) -> None:
        """«А40-12345/2024» must not be treated as «за 2024 год»."""
        req = parse_moy_arbitr_search_request("скачай из мой арбитр дело А40-12345/2024")
        self.assertIsNotNone(req)
        assert req is not None
        self.assertIsNone(req.parser_year_min)
        self.assertIsNone(req.parser_year_max)

    def test_queued_reply_mentions_period(self) -> None:
        req = parse_moy_arbitr_search_request(
            "скачай из мой арбитр дело А40-1/2024 за 2025 год"
        )
        assert req is not None
        text = format_moy_arbitr_search_queued_reply(req, job_id=7, created=True)
        self.assertIn("только документы за 2025 г.", text)
        self.assertEqual(format_parser_year_period(2024, 2026), " (только документы за 2024–2026 г.)")


if __name__ == "__main__":
    unittest.main()
