"""Season-scoped chat must not wipe a folder.

«удали все документы за лето в этой папке» used to match wants_all and hard-delete
every file in the open case because the season was ignored.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_season import (
    looks_like_season_scoped_document_request,
    season_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


class SeasonScopeTests(unittest.TestCase):
    def test_season_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_season_scoped_document_request(
                "удали все документы за лето в этой папке"
            )
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы за зиму")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы за весну")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы за осень")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы за это лето")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы этим летом")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы прошлой зимой")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все летние документы в этой папке")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request(
                "перенеси все документы за лето в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_season_scoped_document_request(
                "удали все документы за лето дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы за сезон")
        )
        self.assertTrue(
            looks_like_season_scoped_document_request("удали все документы летом")
        )

    def test_plain_wipe_or_id_commands_are_not_season_scoped(self) -> None:
        self.assertFalse(
            looks_like_season_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_season_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_season_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_season_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_season_scoped_document_request(
                "удали все документы за 2025 год в этой папке"
            )
        )
        self.assertFalse(
            looks_like_season_scoped_document_request(
                "удали все документы за последние 5 лет"
            )
        )
        self.assertFalse(
            looks_like_season_scoped_document_request(
                "удали все документы в папке Лето"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_season_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            season_blocks_bulk_document_mutation(
                "удали все документы за лето в этой папке"
            )
        )
        self.assertTrue(
            season_blocks_bulk_document_mutation("удали все документы за зиму")
        )
        self.assertTrue(
            season_blocks_bulk_document_mutation(
                "удали все документы за осень в этой папке"
            )
        )
        self.assertTrue(
            season_blocks_bulk_document_mutation("удали все летние документы в этой папке")
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за лето» was ignored."""
        text = "удали все документы за лето в этой папке"
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
        self.assertTrue(season_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_seasons(self) -> None:
        """#69–#72 cover dates, months, weeks, years — not лето/зима/весна/осень."""
        self.assertIsNone(parse_calendar_period_ru("удали все документы за лето в этой папке"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы за зиму"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы этим летом"))
        self.assertIsNone(parse_calendar_period_ru("удали все летние документы"))

    def test_explicit_id_still_allowed_even_if_season_is_mentioned(self) -> None:
        self.assertFalse(
            season_blocks_bulk_document_mutation(
                "удали документ 254 за лето",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            season_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            season_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            season_blocks_bulk_document_mutation("удали документ 254")
        )


if __name__ == "__main__":
    unittest.main()
