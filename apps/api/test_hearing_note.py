"""Hearing-note parser must not treat clause numbers as next_hearing_date."""

from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from app.hearing_note import (
    apply_hearing_date_to_case,
    extract_hearing_date,
    looks_like_hearing_note,
)


class LooksLikeHearingNoteTests(unittest.TestCase):
    def test_clause_or_version_alone_is_not_a_hearing_note(self) -> None:
        self.assertFalse(looks_like_hearing_note("Что в п. 3.2 определения?"))
        self.assertFalse(looks_like_hearing_note("файл v1.2.pdf"))
        self.assertFalse(looks_like_hearing_note("кто судья по делу?"))
        self.assertFalse(looks_like_hearing_note("Найди доказательства в папке"))
        self.assertFalse(looks_like_hearing_note("перенеси документ 4 в дело Банкротство"))

    def test_explicit_hearing_language_matches(self) -> None:
        self.assertTrue(looks_like_hearing_note("Заседание отложено на 20.09.2026"))
        self.assertTrue(looks_like_hearing_note("Отложили рассмотрение, нужно приобщить документы"))


class ExtractHearingDateTests(unittest.TestCase):
    def test_prefers_full_date_over_preceding_clause_number(self) -> None:
        text = "Рассмотрели п. 1.2. Заседание отложено на 20.09.2026."
        self.assertEqual(extract_hearing_date(text), date(2026, 9, 20))

    def test_prefers_full_date_when_clause_number_follows(self) -> None:
        text = "Заседание 20.09.2026. Рассмотрели п. 1.2 иска."
        self.assertEqual(extract_hearing_date(text), date(2026, 9, 20))

    def test_ignores_clause_number_without_hearing_date(self) -> None:
        self.assertIsNone(extract_hearing_date("См. п. 3.2 и п. 4.1 договора."))

    def test_yearless_date_only_near_hearing_marker(self) -> None:
        self.assertEqual(extract_hearing_date("Отложили на 15.03"), date(date.today().year, 3, 15))
        self.assertIsNone(extract_hearing_date("сумма 10.5 млн, см. расчёт"))

    def test_two_digit_year(self) -> None:
        self.assertEqual(extract_hearing_date("Заседание назначено на 01.11.26"), date(2026, 11, 1))


class ApplyHearingDateToCaseTests(unittest.TestCase):
    def test_clause_then_real_date_updates_next_hearing_date(self) -> None:
        case = SimpleNamespace(next_hearing_date=date(2026, 12, 1))
        extracted = apply_hearing_date_to_case(
            case, "Рассмотрели п. 1.2. Заседание отложено на 20.09.2026."
        )
        self.assertEqual(extracted, date(2026, 9, 20))
        self.assertEqual(case.next_hearing_date, date(2026, 9, 20))

    def test_clause_only_does_not_overwrite_existing_hearing_date(self) -> None:
        case = SimpleNamespace(next_hearing_date=date(2026, 12, 1))
        extracted = apply_hearing_date_to_case(case, "См. п. 1.2 определения.")
        self.assertIsNone(extracted)
        self.assertEqual(case.next_hearing_date, date(2026, 12, 1))


if __name__ == "__main__":
    unittest.main()
