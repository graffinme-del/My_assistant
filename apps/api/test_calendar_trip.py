"""Business-trip / overtime-scoped chat must not wipe a folder or delete the wrong document.

«удали все документы за командировку в этой папке» used to match wants_all and hard-delete
every file in the open case because the trip phrase was ignored.
«удали документы 1-й командировки» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_trip import (
    looks_like_trip_scoped_document_request,
    mask_trip_ordinals,
    trip_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_trip_ordinals(raw)
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


class TripScopeTests(unittest.TestCase):
    def test_trip_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы за командировку в этой папке"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы за сверхурочные в этой папке"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы за переработку в этой папке"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы на командировке"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы по командировкам"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы по сверхурочным"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы во время командировки"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы за сверхурочную работу"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "перенеси все документы за командировку в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все документы за командировку дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали документы первой командировки"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали документы первых сверхурочных"
            )
        )

    def test_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все командировочные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request(
                "удали все сверхурочные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request("удали документы командировочные")
        )
        self.assertTrue(
            looks_like_trip_scoped_document_request("удали документы сверхурочные")
        )

    def test_plain_wipe_or_id_commands_are_not_trip_scoped(self) -> None:
        self.assertFalse(
            looks_like_trip_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_trip_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все документы за дежурство в этой папке"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все документы за смену в этой папке"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все документы за отпуск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все документы в папке Командировка"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все документы в папке Сверхурочные"
            )
        )
        self.assertFalse(
            looks_like_trip_scoped_document_request(
                "удали все ежедневные документы в этой папке"
            )
        )


class TripOrdinalIdTests(unittest.TestCase):
    def test_ordinal_trip_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й командировки"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-ю командировку"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-х сверхурочных"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й командировки"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 командировки"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-ю переработку"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за командировку"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-й командировки"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_trip_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            trip_blocks_bulk_document_mutation(
                "удали все документы за командировку в этой папке"
            )
        )
        self.assertTrue(
            trip_blocks_bulk_document_mutation(
                "удали все документы за сверхурочные в этой папке"
            )
        )
        self.assertTrue(
            trip_blocks_bulk_document_mutation("удали все документы по командировкам")
        )
        self.assertTrue(
            trip_blocks_bulk_document_mutation(
                "удали все документы во время командировки"
            )
        )
        self.assertTrue(
            trip_blocks_bulk_document_mutation("удали документы 1-й командировки")
        )

    def test_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            trip_blocks_bulk_document_mutation(
                "удали все командировочные документы в этой папке"
            )
        )
        self.assertTrue(
            trip_blocks_bulk_document_mutation(
                "удали все сверхурочные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за командировку» was ignored."""
        text = "удали все документы за командировку в этой папке"
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
        self.assertTrue(trip_blocks_bulk_document_mutation(text))

    def test_overtime_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за сверхурочные в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(trip_blocks_bulk_document_mutation(text))

    def test_current_trip_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущую командировку"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(trip_blocks_bulk_document_mutation(text))

    def test_current_overtime_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущие сверхурочные"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(trip_blocks_bulk_document_mutation(text))

    def test_ordinal_trip_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-й командировки» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-й командировки"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(trip_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_trip(self) -> None:
        """#69–#79 cover dates, months, weeks, years, seasons, holidays, отпуск, больничный, будни, смены, дежурство — not командировка/сверхурочные."""
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за командировку в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за сверхурочные в этой папке"
            )
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы по командировкам"))
        self.assertIsNone(parse_calendar_period_ru("удали все командировочные документы"))
        self.assertIsNone(parse_calendar_period_ru("удали все сверхурочные документы"))

    def test_explicit_id_still_allowed_even_if_trip_is_mentioned(self) -> None:
        self.assertFalse(
            trip_blocks_bulk_document_mutation(
                "удали документ 254 за командировку",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            trip_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            trip_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(trip_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            trip_blocks_bulk_document_mutation(
                "удали все документы в папке Командировка"
            )
        )
        self.assertFalse(
            trip_blocks_bulk_document_mutation(
                "удали все документы в папке Сверхурочные"
            )
        )
        self.assertFalse(
            trip_blocks_bulk_document_mutation(
                "удали все ежедневные документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
