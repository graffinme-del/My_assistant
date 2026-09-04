"""Year-scoped chat must not wipe a folder or hard-delete the wrong document id.

«удали все документы за 2025 год в этой папке» used to match wants_all and hard-delete
every file in the open case because the year was ignored.

«удали документы 2025 года» used to take 2025 as a document id.
"""

from __future__ import annotations

import unittest

from app.calendar_year import (
    looks_like_year_scoped_document_request,
    parse_document_ids_for_delete_command,
    parse_document_ids_for_move_command,
    year_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


class YearIsNotDocumentIdTests(unittest.TestCase):
    def test_calendar_year_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 2025 года"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 2025 года"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 2025 года"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 2024 года"), [])
        self.assertEqual(parse_document_ids_for_delete_command("убери файл 2025 г."), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 25 года"), [])

    def test_explicit_id_still_parsed(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 254"), [254])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1 и 2"), [1, 2])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 за 2025 год"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ [18] 2025 года"),
            [18],
        )

    def test_year_is_not_a_move_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 2025 года в дело Банкротство"),
            [],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 254 в дело Банкротство"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перемести документ [12] за 2025 год в дело Банкротство"),
            [12],
        )


class YearScopeTests(unittest.TestCase):
    def test_year_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_year_scoped_document_request(
                "удали все документы за 2025 год в этой папке"
            )
        )
        self.assertTrue(
            looks_like_year_scoped_document_request("удали все документы за 2024 год")
        )
        self.assertTrue(
            looks_like_year_scoped_document_request("удали документы 2025 года")
        )
        self.assertTrue(
            looks_like_year_scoped_document_request(
                "удали все документы с 2024 по 2026 в этой папке"
            )
        )
        self.assertTrue(
            looks_like_year_scoped_document_request(
                "перенеси все документы за 2025 год в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_year_scoped_document_request("удали документы 25 года")
        )
        self.assertTrue(
            looks_like_year_scoped_document_request(
                "удали все документы за 2024 год дела А40-12345/2025"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_year_scoped(self) -> None:
        self.assertFalse(
            looks_like_year_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_year_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_year_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_year_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_year_scoped_document_request(
                "удали все документы дела А40-19021/25"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_year_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            year_blocks_bulk_document_mutation(
                "удали все документы за 2025 год в этой папке"
            )
        )
        self.assertTrue(
            year_blocks_bulk_document_mutation("удали документы 2025 года")
        )
        self.assertTrue(
            year_blocks_bulk_document_mutation(
                "удали все документы с 2024 по 2026 в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «2025 год» was ignored."""
        text = "удали все документы за 2025 год в этой папке"
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
        self.assertEqual(parse_document_ids_for_delete_command(text), [])
        self.assertTrue(year_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_numeric_years(self) -> None:
        """#69 only covers parse_calendar_period_ru (вчера / последние N дней / прошлый год)."""
        self.assertIsNone(parse_calendar_period_ru("удали все документы за 2025 год в этой папке"))
        self.assertIsNone(parse_calendar_period_ru("удали документы 2025 года"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы с 2024 по 2026"))

    def test_explicit_id_still_allowed_even_if_year_is_mentioned(self) -> None:
        self.assertFalse(
            year_blocks_bulk_document_mutation(
                "удали документ 254 за 2025 год",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            year_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            year_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )


if __name__ == "__main__":
    unittest.main()
