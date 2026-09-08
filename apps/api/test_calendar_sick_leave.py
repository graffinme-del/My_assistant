"""Sick-leave / maternity-scoped chat must not wipe a folder.

«удали все документы за больничный в этой папке» used to match wants_all and hard-delete
every file in the open case because the sick-leave phrase was ignored.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_sick_leave import (
    looks_like_sick_leave_scoped_document_request,
    sick_leave_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


class SickLeaveScopeTests(unittest.TestCase):
    def test_sick_leave_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за больничный в этой папке"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы на больничном в этой папке"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы во время больничного"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за этот больничный"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все больничные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "перенеси все документы за больничный в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за больничный дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали документы этого больничного"
            )
        )

    def test_maternity_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы в декрете в этой папке"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за декрет"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы во время декрета"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все декретные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы в декретном отпуске"
            )
        )
        self.assertTrue(
            looks_like_sick_leave_scoped_document_request(
                "перенеси все документы в декрете в папку Банкротство"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_sick_leave_scoped(self) -> None:
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за отпуск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за будни в этой папке"
            )
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы за праздники в этой папке"
            )
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы в папке Больничный"
            )
        )
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы в папке Декрет"
            )
        )
        # Legal «декрет» (decree), not maternity leave.
        self.assertFalse(
            looks_like_sick_leave_scoped_document_request(
                "удали все документы по декрету"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_sick_leave_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы за больничный в этой папке"
            )
        )
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы на больничном в этой папке"
            )
        )
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все больничные документы в этой папке"
            )
        )
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы во время больничного"
            )
        )

    def test_maternity_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы в декрете в этой папке"
            )
        )
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все декретные документы в этой папке"
            )
        )
        self.assertTrue(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы во время декрета"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за больничный» was ignored."""
        text = "удали все документы за больничный в этой папке"
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
        self.assertTrue(sick_leave_blocks_bulk_document_mutation(text))

    def test_in_maternity_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы в декрете в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(sick_leave_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_sick_leave(self) -> None:
        """#69–#75 cover dates, months, weeks, years, seasons, holidays, отпуск — not больничный/декрет."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за больничный в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы на больничном"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы в декрете"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы во время декрета"))
        self.assertIsNone(parse_calendar_period_ru("удали все декретные документы"))

    def test_explicit_id_still_allowed_even_if_sick_leave_is_mentioned(self) -> None:
        self.assertFalse(
            sick_leave_blocks_bulk_document_mutation(
                "удали документ 254 за больничный",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            sick_leave_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            sick_leave_blocks_bulk_document_mutation("удали документ 254")
        )
        self.assertFalse(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы в папке Больничный"
            )
        )
        self.assertFalse(
            sick_leave_blocks_bulk_document_mutation(
                "удали все документы по декрету"
            )
        )


if __name__ == "__main__":
    unittest.main()
