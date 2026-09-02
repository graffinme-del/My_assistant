"""Month/quarter chat must not wipe a folder or hard-delete the wrong document id.

«удали все документы за март в этой папке» used to match wants_all and hard-delete
every file in the open case because the month was ignored.

«удали документы 1 квартала» used to take the first digit as a document id.
"""

from __future__ import annotations

import unittest

from app.calendar_month_quarter import (
    looks_like_month_or_quarter_scoped_document_request,
    month_or_quarter_blocks_bulk_document_mutation,
    parse_document_ids_for_delete_command,
    parse_document_ids_for_move_command,
)


class QuarterIsNotDocumentIdTests(unittest.TestCase):
    def test_quarter_ordinal_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1 квартала"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 1 квартала"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файлы 2 квартал"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 1 квартала"), [])
        self.assertEqual(parse_document_ids_for_delete_command("убери файл 3 квартала"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1 полугодия"), [])

    def test_explicit_id_still_parsed(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 254"), [254])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1 и 2"), [1, 2])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 за 1 квартал"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ [18] 1 квартала"),
            [18],
        )

    def test_quarter_is_not_a_move_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 1 квартала в дело Банкротство"),
            [],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 254 в дело Банкротство"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перемести документ [12] за март в дело Банкротство"),
            [12],
        )


class MonthQuarterScopeTests(unittest.TestCase):
    def test_month_and_quarter_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы за март в этой папке"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы за январь"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы за май 2025 в этой папке"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы за этот месяц в этой папке"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы в этом квартале"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали документы 1 квартала"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "перенеси все документы за март в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы за первый квартал"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы этого месяца в этой папке"
            )
        )
        self.assertTrue(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы за месяц в этой папке"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_month_scoped(self) -> None:
        self.assertFalse(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_month_or_quarter_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_month_or_quarter_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_month_or_quarter_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_month_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            month_or_quarter_blocks_bulk_document_mutation(
                "удали все документы за март в этой папке"
            )
        )
        self.assertTrue(
            month_or_quarter_blocks_bulk_document_mutation(
                "удали все документы за этот месяц в этой папке"
            )
        )
        self.assertTrue(
            month_or_quarter_blocks_bulk_document_mutation("удали документы 1 квартала")
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «март» was ignored."""
        text = "удали все документы за март в этой папке"
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
        self.assertEqual(parse_document_ids_for_delete_command(text), [])
        self.assertTrue(month_or_quarter_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_month_is_mentioned(self) -> None:
        self.assertFalse(
            month_or_quarter_blocks_bulk_document_mutation(
                "удали документ 254 за март",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            month_or_quarter_blocks_bulk_document_mutation(
                "удали все документы в этой папке"
            )
        )
        self.assertFalse(
            month_or_quarter_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )


if __name__ == "__main__":
    unittest.main()
