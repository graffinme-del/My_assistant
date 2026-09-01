"""Calendar-scoped chat must not wipe or dump a whole folder.

«удали все документы за вчера в этой папке» used to match wants_all and hard-delete
every file in the open case because the date was ignored.
"""

from __future__ import annotations

import unittest

from app.ru_date_range import (
    calendar_period_blocks_bulk_document_mutation,
    looks_like_calendar_period_scoped_document_request,
    parse_calendar_period_ru,
)


class CalendarPeriodScopeTests(unittest.TestCase):
    def test_yesterday_today_and_relative_periods_are_detected(self) -> None:
        self.assertTrue(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы за вчера в этой папке"
            )
        )
        self.assertTrue(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы дела А40-12345/2025 за вчера"
            )
        )
        self.assertTrue(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы за сегодня"
            )
        )
        self.assertTrue(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы за последние 10 дней в этой папке"
            )
        )
        self.assertTrue(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы за 3 дня"
            )
        )
        self.assertTrue(
            looks_like_calendar_period_scoped_document_request(
                "перенеси все документы за вчера в папку Банкротство"
            )
        )
        self.assertIsNotNone(parse_calendar_period_ru("удали все документы позавчера"))

    def test_plain_wipe_or_id_commands_are_not_date_scoped(self) -> None:
        self.assertFalse(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_calendar_period_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_calendar_period_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_calendar_period_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_date_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            calendar_period_blocks_bulk_document_mutation(
                "удали все документы за вчера в этой папке"
            )
        )
        self.assertTrue(
            calendar_period_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025 за сегодня"
            )
        )
        self.assertTrue(
            calendar_period_blocks_bulk_document_mutation(
                "удали все документы за последние 10 дней в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + «в этой папке» hard-deleted every file because the date was ignored."""
        text = "удали все документы за вчера в этой папке"
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
        self.assertTrue(calendar_period_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_date_is_mentioned(self) -> None:
        self.assertFalse(
            calendar_period_blocks_bulk_document_mutation(
                "удали документ 254 за вчера",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            calendar_period_blocks_bulk_document_mutation(
                "удали все документы в этой папке"
            )
        )
        self.assertFalse(
            calendar_period_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )


if __name__ == "__main__":
    unittest.main()
