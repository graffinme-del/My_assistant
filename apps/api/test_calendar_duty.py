"""Duty/rotation-scoped chat must not wipe a folder or delete the wrong document.

«удали все документы за дежурство в этой папке» used to match wants_all and hard-delete
every file in the open case because the duty phrase was ignored.
«удали документы 1-го дежурства» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_duty import (
    duty_blocks_bulk_document_mutation,
    looks_like_duty_scoped_document_request,
    mask_duty_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_duty_ordinals(raw)
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        safe,
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", safe, flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


class DutyScopeTests(unittest.TestCase):
    def test_duty_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы за дежурство в этой папке"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы за вахту в этой папке"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы на дежурстве"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request("удали все документы на вахте")
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы по дежурствам"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request("удали все документы по вахтам")
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы во время дежурства"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы во время вахты"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "перенеси все документы за дежурство в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все документы за дежурство дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request("удали документы первого дежурства")
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request("удали документы первой вахты")
        )

    def test_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все дежурные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request(
                "удали все вахтовые документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request("удали документы дежурные")
        )
        self.assertTrue(
            looks_like_duty_scoped_document_request("удали документы вахтовые")
        )

    def test_plain_wipe_or_id_commands_are_not_duty_scoped(self) -> None:
        self.assertFalse(
            looks_like_duty_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_duty_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "удали все документы за смену в этой папке"
            )
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "удали все документы за будни в этой папке"
            )
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "удали все документы за отпуск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "удали все документы в папке Дежурство"
            )
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request("удали все документы в папке Вахта")
        )
        self.assertFalse(
            looks_like_duty_scoped_document_request(
                "удали все ежедневные документы в этой папке"
            )
        )


class DutyOrdinalIdTests(unittest.TestCase):
    def test_ordinal_duty_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го дежурства"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-е дежурство"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-й вахты"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й вахты"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 вахты"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-ю вахту"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за дежурство"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го дежурства"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_duty_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            duty_blocks_bulk_document_mutation(
                "удали все документы за дежурство в этой папке"
            )
        )
        self.assertTrue(
            duty_blocks_bulk_document_mutation(
                "удали все документы за вахту в этой папке"
            )
        )
        self.assertTrue(
            duty_blocks_bulk_document_mutation("удали все документы по дежурствам")
        )
        self.assertTrue(
            duty_blocks_bulk_document_mutation("удали все документы во время вахты")
        )
        self.assertTrue(
            duty_blocks_bulk_document_mutation("удали документы 1-го дежурства")
        )

    def test_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            duty_blocks_bulk_document_mutation(
                "удали все дежурные документы в этой папке"
            )
        )
        self.assertTrue(
            duty_blocks_bulk_document_mutation(
                "удали все вахтовые документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за дежурство» was ignored."""
        text = "удали все документы за дежурство в этой папке"
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
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(duty_blocks_bulk_document_mutation(text))

    def test_watch_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за вахту в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(duty_blocks_bulk_document_mutation(text))

    def test_current_duty_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущее дежурство"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(duty_blocks_bulk_document_mutation(text))

    def test_current_watch_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущую вахту"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(duty_blocks_bulk_document_mutation(text))

    def test_ordinal_duty_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го дежурства» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го дежурства"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(duty_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_duty(self) -> None:
        """#69–#78 cover dates, months, weeks, years, seasons, holidays, отпуск, больничный, будни, смены — not дежурство/вахта."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за дежурство в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за вахту в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы по дежурствам"))
        self.assertIsNone(parse_calendar_period_ru("удали все дежурные документы"))
        self.assertIsNone(parse_calendar_period_ru("удали все вахтовые документы"))

    def test_explicit_id_still_allowed_even_if_duty_is_mentioned(self) -> None:
        self.assertFalse(
            duty_blocks_bulk_document_mutation(
                "удали документ 254 за дежурство",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            duty_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            duty_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(duty_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            duty_blocks_bulk_document_mutation("удали все документы в папке Дежурство")
        )
        self.assertFalse(
            duty_blocks_bulk_document_mutation("удали все документы в папке Вахта")
        )
        self.assertFalse(
            duty_blocks_bulk_document_mutation(
                "удали все ежедневные документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
