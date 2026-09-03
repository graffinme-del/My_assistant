"""Week-scoped chat must not wipe a folder or hard-delete the wrong document id.

«удали все документы за эту неделю в этой папке» used to match wants_all and
hard-delete every file in the open case because the week phrase was ignored.

«удали документы 1-й недели» used to take the first digit as a document id.

#65–#68 mask digit tokens mistaken as ids. #69 uses parse_calendar_period_ru
(вчера / «за последние N дней» / bare «за неделю»). #70 covers named months and
quarters. None of those match «эту неделю», weekday names, or hyphen ordinals
like «1-й недели».
"""

from __future__ import annotations

import unittest

from app.calendar_week import (
    looks_like_week_scoped_document_request,
    parse_document_ids_for_delete_command,
    parse_document_ids_for_move_command,
    week_blocks_bulk_document_mutation,
)


class WeekOrdinalIsNotDocumentIdTests(unittest.TestCase):
    def test_hyphen_week_ordinal_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1-й недели"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 1-я неделя"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файлы 2-ю неделю"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 1-й недели"), [])

    def test_explicit_id_still_parsed(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 254"), [254])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1 и 2"), [1, 2])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 за эту неделю"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ [18] 1-й недели"),
            [18],
        )

    def test_week_ordinal_is_not_a_move_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command(
                "перенеси документ 1-й недели в дело Банкротство"
            ),
            [],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 254 в дело Банкротство"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_move_command(
                "перемести документ [12] за эту неделю в дело Банкротство"
            ),
            [12],
        )


class WeekScopeTests(unittest.TestCase):
    def test_this_last_and_current_week_are_detected(self) -> None:
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы за эту неделю в этой папке"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы этой недели в этой папке"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы на этой неделе"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы за прошлую неделю в этой папке"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы за текущую неделю"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы дела А40-12345/2025 за эту неделю"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "перенеси все документы за эту неделю в папку Банкротство"
            )
        )

    def test_ordinal_week_weekday_and_weekend_are_detected(self) -> None:
        self.assertTrue(
            looks_like_week_scoped_document_request("удали документы 1-й недели")
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы первой недели в этой папке"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы за понедельник в этой папке"
            )
        )
        self.assertTrue(
            looks_like_week_scoped_document_request(
                "удали все документы за выходные в этой папке"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_week_scoped(self) -> None:
        self.assertFalse(
            looks_like_week_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_week_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_week_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_week_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_week_scoped_document_request(
                "удали все документы за вчера в этой папке"
            )
        )
        self.assertFalse(
            looks_like_week_scoped_document_request(
                "удали все документы за март в этой папке"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_week_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            week_blocks_bulk_document_mutation(
                "удали все документы за эту неделю в этой папке"
            )
        )
        self.assertTrue(
            week_blocks_bulk_document_mutation(
                "удали все документы за прошлую неделю в этой папке"
            )
        )
        self.assertTrue(week_blocks_bulk_document_mutation("удали документы 1-й недели"))

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because the week was ignored."""
        text = "удали все документы за эту неделю в этой папке"
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
        self.assertTrue(week_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_week_is_mentioned(self) -> None:
        self.assertFalse(
            week_blocks_bulk_document_mutation(
                "удали документ 254 за эту неделю",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            week_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            week_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )


if __name__ == "__main__":
    unittest.main()
