"""Supervisory-review / instance-scoped chat must not wipe a folder or delete the wrong document.

«удали все документы за надзор в этой папке» used to match wants_all and hard-delete
every file in the open case because the instance phrase was ignored.
«удали документы 1-й инстанции» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_instance import (
    instance_blocks_bulk_document_mutation,
    looks_like_instance_scoped_document_request,
    mask_instance_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_instance_ordinals(raw)
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


def _pre_fix_parse_ids(text: str) -> list[int]:
    """Document-id parser on main before this fix — digits of «1-й инстанции» become an id."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", text or "", flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


class InstanceScopeTests(unittest.TestCase):
    def test_instance_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за надзор в этой папке"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за надзорную жалобу в этой папке"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за первую инстанцию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за вторую инстанцию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы на надзоре"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы на первой инстанции"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы по надзору"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы во время надзора"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы во время первой инстанции"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "перенеси все документы за надзор в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за надзор дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали документы первой инстанции"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали документы второй инстанции"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за апелляционную инстанцию"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы за кассационную инстанцию"
            )
        )

    def test_genitive_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали все документы надзора в этой папке"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали документы первой инстанции"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request("удали документы надзора")
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали надзорные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_instance_scoped_document_request(
                "удали документы надзорной жалобы"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_instance_scoped(self) -> None:
        self.assertFalse(
            looks_like_instance_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_instance_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы за заседание в этой папке"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы за апелляцию в этой папке"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы за командировку в этой папке"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы в папке Надзор"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы в папке Инстанция"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все ежедневные документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все судебные документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_instance_scoped_document_request(
                "удали все документы за жалобу в этой папке"
            )
        )


class InstanceOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й инстанции"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й надзорной жалобы"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-го надзора"), [1])

    def test_ordinal_instance_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й инстанции"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-я инстанция"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-го надзора"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й надзорной жалобы"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 инстанции"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-я инстанция"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за надзор"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-й инстанции"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_instance_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали все документы за надзор в этой папке"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали все документы за надзорную жалобу в этой папке"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали все документы за первую инстанцию в этой папке"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали все документы за вторую инстанцию в этой папке"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation("удали все документы на надзоре")
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали все документы во время надзора"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation("удали документы 1-й инстанции")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали все документы надзора в этой папке"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали документы первой инстанции"
            )
        )
        self.assertTrue(
            instance_blocks_bulk_document_mutation(
                "удали надзорные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за надзор» was ignored."""
        text = "удали все документы за надзор в этой папке"
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
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_supervisory_complaint_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за надзорную жалобу в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_first_instance_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за первую инстанцию в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_second_instance_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за вторую инстанцию в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_current_supervisory_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущий надзор"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_current_instance_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущую инстанцию"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_ordinal_instance_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-й инстанции» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-й инстанции"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(instance_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_instance(self) -> None:
        """#69–#82 cover dates through appeal/cassation/review — not надзор/инстанция."""
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за надзор в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за надзорную жалобу в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за первую инстанцию в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за вторую инстанцию"
            )
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы на надзоре"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы надзора"))

    def test_explicit_id_still_allowed_even_if_instance_is_mentioned(self) -> None:
        self.assertFalse(
            instance_blocks_bulk_document_mutation(
                "удали документ 254 за надзор",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            instance_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            instance_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(instance_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            instance_blocks_bulk_document_mutation(
                "удали все документы в папке Надзор"
            )
        )
        self.assertFalse(
            instance_blocks_bulk_document_mutation(
                "удали все документы в папке Инстанция"
            )
        )
        self.assertFalse(
            instance_blocks_bulk_document_mutation(
                "удали все ежедневные документы в этой папке"
            )
        )
        self.assertFalse(
            instance_blocks_bulk_document_mutation(
                "удали все судебные документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
