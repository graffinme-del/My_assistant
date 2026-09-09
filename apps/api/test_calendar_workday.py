"""Workday-scoped chat must not wipe a folder.

«удали все документы за будни в этой папке» used to match wants_all and hard-delete
every file in the open case because the weekday phrase was ignored.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_workday import (
    looks_like_workday_scoped_document_request,
    workday_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


class WorkdayScopeTests(unittest.TestCase):
    def test_weekday_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за будни в этой папке"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы в будни в этой папке"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы по будням"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы на буднях"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за эти будни"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все будние документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "перенеси все документы за будни в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за будни дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали документы этих будней"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы во время будней"
            )
        )

    def test_workday_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за рабочие дни в этой папке"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы в рабочие дни"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за рабочий день"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за будний день"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы во время рабочих дней"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы в рабочее время"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за рабочие часы"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "перенеси все документы за рабочие дни в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_workday_scoped_document_request(
                "удали все документы за текущие рабочие дни"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_workday_scoped(self) -> None:
        self.assertFalse(
            looks_like_workday_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы за отпуск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы за больничный в этой папке"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы за праздники в этой папке"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы за выходные в этой папке"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы в папке Будни"
            )
        )
        # Working files, not weekday-scoped.
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все рабочие документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_workday_scoped_document_request(
                "удали все документы на рабочем столе"
            )
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_weekday_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы за будни в этой папке"
            )
        )
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы по будням"
            )
        )
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все будние документы в этой папке"
            )
        )
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы во время будней"
            )
        )

    def test_workday_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы за рабочие дни в этой папке"
            )
        )
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы за рабочий день"
            )
        )
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы в рабочее время"
            )
        )
        self.assertTrue(
            workday_blocks_bulk_document_mutation(
                "удали все документы во время рабочих дней"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за будни» was ignored."""
        text = "удали все документы за будни в этой папке"
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
        self.assertTrue(workday_blocks_bulk_document_mutation(text))

    def test_workdays_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за рабочие дни в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(workday_blocks_bulk_document_mutation(text))

    def test_current_workdays_use_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущие рабочие дни"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(workday_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_workdays(self) -> None:
        """#69–#76 cover dates, months, weeks, years, seasons, holidays, отпуск, больничный — not будни."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за будни в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы за рабочие дни"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы по будням"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы в рабочее время"))
        self.assertIsNone(parse_calendar_period_ru("удали все будние документы"))

    def test_explicit_id_still_allowed_even_if_workday_is_mentioned(self) -> None:
        self.assertFalse(
            workday_blocks_bulk_document_mutation(
                "удали документ 254 за будни",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            workday_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            workday_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            workday_blocks_bulk_document_mutation("удали документ 254")
        )
        self.assertFalse(
            workday_blocks_bulk_document_mutation(
                "удали все документы в папке Будни"
            )
        )
        self.assertFalse(
            workday_blocks_bulk_document_mutation(
                "удали все рабочие документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
