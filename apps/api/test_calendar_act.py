"""Court-act-scoped chat must not wipe a folder or delete the wrong document.

«удали все документы за ходатайство в этой папке» used to match wants_all and hard-delete
every file in the open case because the act phrase was ignored.
«удали документы 1-го ходатайства» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_act import (
    act_blocks_bulk_document_mutation,
    looks_like_act_scoped_document_request,
    mask_act_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_act_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го ходатайства» become an id."""
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


class ActScopeTests(unittest.TestCase):
    def test_act_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за ходатайство в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за определение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за решение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за постановление в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за судебное решение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за частное определение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы на ходатайстве"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы по постановлению"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы во время ходатайства"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "перенеси все документы за ходатайство в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы за ходатайство дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали документы первого ходатайства"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали документы первого определения"
            )
        )

    def test_genitive_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали все документы ходатайства в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали документы судебного решения"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request("удали документы определения")
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали ходатайственные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_act_scoped_document_request(
                "удали документы постановления"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_act_scoped(self) -> None:
        self.assertFalse(
            looks_like_act_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_act_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы за заседание в этой папке"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы за апелляцию в этой папке"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы за надзор в этой папке"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы в папке Ходатайство"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы в папке Определение"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы в папке Решение"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы в папке Постановление"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все судебные документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "принял решение удалить все документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_act_scoped_document_request(
                "удали все документы за жалобу в этой папке"
            )
        )


class ActOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го ходатайства"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го определения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-го решения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-го постановления"), [1])

    def test_ordinal_act_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го ходатайства"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-е ходатайство"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-го определения"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-го решения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 ходатайства"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-е постановление"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за ходатайство"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го определения"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_act_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали все документы за ходатайство в этой папке"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали все документы за определение в этой папке"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали все документы за решение в этой папке"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали все документы за постановление в этой папке"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation("удали все документы на ходатайстве")
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали все документы во время определения"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation("удали документы 1-го ходатайства")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали все документы ходатайства в этой папке"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали документы судебного решения"
            )
        )
        self.assertTrue(
            act_blocks_bulk_document_mutation(
                "удали ходатайственные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за ходатайство» was ignored."""
        text = "удали все документы за ходатайство в этой папке"
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
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_ruling_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за определение в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_decision_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за решение в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_order_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за постановление в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_current_motion_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущее ходатайство"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_current_decision_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущее решение"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_ordinal_act_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го ходатайства» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го ходатайства"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(act_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_act(self) -> None:
        """#69–#83 cover dates through supervisory/instance — not ходатайство/определение/решение/постановление."""
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за ходатайство в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за определение в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за решение в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за постановление"
            )
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы на ходатайстве"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы ходатайства"))

    def test_explicit_id_still_allowed_even_if_act_is_mentioned(self) -> None:
        self.assertFalse(
            act_blocks_bulk_document_mutation(
                "удали документ 254 за ходатайство",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            act_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            act_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(act_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            act_blocks_bulk_document_mutation(
                "удали все документы в папке Ходатайство"
            )
        )
        self.assertFalse(
            act_blocks_bulk_document_mutation(
                "удали все документы в папке Решение"
            )
        )
        self.assertFalse(
            act_blocks_bulk_document_mutation(
                "удали все судебные документы в этой папке"
            )
        )
        self.assertFalse(
            act_blocks_bulk_document_mutation(
                "принял решение удалить все документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
