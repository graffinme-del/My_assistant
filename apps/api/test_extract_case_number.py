"""Regression tests for case-number extraction (no DB / httpx required)."""

from __future__ import annotations

import unittest

from app.case_number import extract_case_number


class ExtractCaseNumberTests(unittest.TestCase):
    def test_arbitr_and_magistrate_numbers(self) -> None:
        self.assertEqual(extract_case_number("А40-12345/2026 решение"), "A40-12345/2026")
        self.assertEqual(extract_case_number("дело 2-123/2026 иск"), "2-123/2026")
        self.assertEqual(
            extract_case_number("A40-19021-2025_дата_файла.pdf"),
            "A40-19021/2025",
        )

    def test_rejects_bare_slash_false_positives(self) -> None:
        # Former bare \\d+/\\d+ pattern treated these as case numbers and
        # auto-created / misfiled folders during document ingest.
        for text in (
            "Счет от 12/2024 на оплату",
            "Страница 3/15 документа",
            "Договор №45/2023",
            "Определение от 01/2025",
            "см. л.д. 12/34",
            "п. 12/345 ГК РФ",
            "Решение по делу; см. также письмо 7/2022",
            "текст без номера но есть дата 05/2024 в шапке",
        ):
            with self.subTest(text=text):
                self.assertIsNone(extract_case_number(text))

    def test_prefers_real_case_over_nearby_slash_noise(self) -> None:
        text = "К делу A40-999/2024 приложена страница 3/15 и счёт 12/2024"
        self.assertEqual(extract_case_number(text), "A40-999/2024")


if __name__ == "__main__":
    unittest.main()
