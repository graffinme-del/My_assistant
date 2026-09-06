"""Holiday/vacation-scoped chat must not wipe a folder.

«удали все документы за праздники в этой папке» used to match wants_all and hard-delete
every file in the open case because the holiday/vacation phrase was ignored.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_holiday import (
    looks_like_holiday_scoped_document_request,
    holiday_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


class HolidayScopeTests(unittest.TestCase):
    def test_holiday_and_vacation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все документы за праздники в этой папке"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request("удали все документы за каникулы")
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все документы на каникулах в этой папке"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request("удали все документы в праздники")
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все документы во время праздников"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все документы за эти каникулы"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все праздничные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все каникулярные документы"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все новогодние документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все документы за новый год в этой папке"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "перенеси все документы за праздники в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request(
                "удали все документы за каникулы дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_holiday_scoped_document_request("удали документы этих праздников")
        )

    def test_plain_wipe_or_id_commands_are_not_holiday_scoped(self) -> None:
        self.assertFalse(
            looks_like_holiday_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "удали все документы за 2025 год в этой папке"
            )
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "удали все документы за прошлый год"
            )
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "удали все документы за лето в этой папке"
            )
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "удали все документы в папке Праздники"
            )
        )
        self.assertFalse(
            looks_like_holiday_scoped_document_request(
                "удали все документы в папке Каникулы"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_holiday_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            holiday_blocks_bulk_document_mutation(
                "удали все документы за праздники в этой папке"
            )
        )
        self.assertTrue(
            holiday_blocks_bulk_document_mutation("удали все документы за каникулы")
        )
        self.assertTrue(
            holiday_blocks_bulk_document_mutation(
                "удали все документы на каникулах в этой папке"
            )
        )
        self.assertTrue(
            holiday_blocks_bulk_document_mutation(
                "удали все праздничные документы в этой папке"
            )
        )
        self.assertTrue(
            holiday_blocks_bulk_document_mutation(
                "удали все документы за новый год в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за праздники» was ignored."""
        text = "удали все документы за праздники в этой папке"
        low = text.lower()
        wants_all = any(
            w in low
            for w in (
                "все документ",
                "все файлы",
                "всех документ",
                "всех файлов",
                "каждый документ",
                "каждый файл",
            )
        )
        uses_open_folder = any(
            p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело")
        )
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertFalse(re.search(r"\[(\d+)\]", text))
        self.assertFalse(re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", text, flags=re.I))
        self.assertTrue(holiday_blocks_bulk_document_mutation(text))

    def test_vacation_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за каникулы в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(holiday_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_holidays(self) -> None:
        """#69–#73 cover dates, months, weeks, years, seasons — not праздники/каникулы."""
        self.assertIsNone(parse_calendar_period_ru("удали все документы за праздники в этой папке"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы за каникулы"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы на каникулах"))
        self.assertIsNone(parse_calendar_period_ru("удали все праздничные документы"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы за новый год"))

    def test_explicit_id_still_allowed_even_if_holiday_is_mentioned(self) -> None:
        self.assertFalse(
            holiday_blocks_bulk_document_mutation(
                "удали документ 254 за праздники",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            holiday_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            holiday_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            holiday_blocks_bulk_document_mutation("удали документ 254")
        )


if __name__ == "__main__":
    unittest.main()
