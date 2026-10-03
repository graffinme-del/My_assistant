"""«Запрос» / «адвокатский запрос» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го запроса» as document id 1. The calendar-period parser does
not recognize these phrases, and the разъяснение guard does not match «запрос».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_inquiry import (
    inquiry_blocks_bulk_document_mutation,
    looks_like_inquiry_scoped_document_request,
    mask_inquiry_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_inquiry_ordinals(raw)
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


class InquiryScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за запрос в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(inquiry_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за запросы в этой папке",
            "удали все документы по запросу в этой папке",
            "удали все документы с запросом в этой папке",
            "удали все документы с запросами в этой папке",
            "удали все документы на запрос в этой папке",
            "удали все документы из запроса в этой папке",
            "удали все документы за адвокатский запрос в этой папке",
            "удали все документы по адвокатскому запросу в этой папке",
            "удали все документы с адвокатским запросом в этой папке",
            "удали все документы за судебный запрос в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertEqual(_pre_fix_parse_ids(synonym), [])
            self.assertIsNone(parse_calendar_period_ru(synonym))
            self.assertTrue(inquiry_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        current = "удали все документы за текущий запрос"
        opened = "удали все документы за открытые запросы"
        for text in (current, opened):
            low = text.lower()
            self.assertIn("все документ", low)
            self.assertTrue("текущ" in low or "открыт" in low)
            self.assertIsNone(parse_calendar_period_ru(text))
            self.assertTrue(inquiry_blocks_bulk_document_mutation(text))

    def test_case_number_scope_would_wipe_that_case(self) -> None:
        text = "удали все документы за запрос дела А53-13969/2026"
        self.assertIn("все документ", text.lower())
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertTrue(inquiry_blocks_bulk_document_mutation(text))
        self.assertTrue(
            inquiry_blocks_bulk_document_mutation(
                "удали все документы за адвокатский запрос дела А40-12345/2025"
            )
        )

    def test_ordinal_wrong_id_trigger(self) -> None:
        """Pre-fix: the leading ordinal digit was document id 1 and that file was hard-deleted."""
        samples = (
            "удали документы 1-го запроса",
            "удали документы 1-й запрос",
            "удали документы 1-го адвокатского запроса",
            "удали документы 2-й запрос",
        )
        for text in samples:
            expected = [2] if "2-й" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(inquiry_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за запрос в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(inquiry_blocks_bulk_document_mutation(text))
        self.assertTrue(
            inquiry_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за адвокатский запрос в папку Архив"
            )
        )
        self.assertTrue(
            inquiry_blocks_bulk_document_mutation(
                "перенеси все документы с запросами в папку Архив"
            )
        )
        self.assertTrue(
            inquiry_blocks_bulk_document_mutation(
                "перенеси документ 1-го запроса в дело Архив"
            )
        )

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        text = "перенеси документ 1-го запроса в дело Архив"
        pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
        safe = mask_inquiry_ordinals(text)
        post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
        self.assertEqual(pre, [1])
        self.assertEqual(post, [])
        kept = "перенеси документ 214 за запрос в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_inquiry_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            inquiry_blocks_bulk_document_mutation(
                "удали документ 254 за запрос",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за запрос"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за адвокатский запрос"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за запрос"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за запрос в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за запрос"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за запрос"), [214])
        self.assertIn("214", mask_inquiry_ordinals("удали документ 214 за запрос"))
        self.assertIn("12345", mask_inquiry_ordinals(text))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без запросов",
            "удали все документы в этой папке и дай запрос",
            "удали все документы в папке Запрос",
            "перенеси все документы в папку Запрос",
            "удали все документы из папки Запрос",
            "удали все документы дела А53-13969/2026",
            "удали все документы за разъяснение в этой папке",
            "удали все документы за пояснение в этой папке",
            "удали все документы за требование в этой папке",
            "удали документы 1-го разъяснения",
            "удали документы 1-го пояснения",
            "запросить документы в этой папке",
            "запросите документы в этой папке",
        ):
            self.assertFalse(looks_like_inquiry_scoped_document_request(text), text)
            self.assertFalse(inquiry_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все запросные документы в этой папке",
            "удали все документы запросные в этой папке",
            "удали все документы за письменный запрос в этой папке",
            "удали все документы во время запроса в этой папке",
            "удали все документы с запросным письмом в этой папке",
            "удали все документы за адвокатские запросы в этой папке",
        ):
            self.assertTrue(inquiry_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("inquiry_blocks_bulk_document_mutation", source)
        self.assertIn("mask_inquiry_ordinals", source)
        self.assertIn("DELETE_REFUSED_INQUIRY", source)
        self.assertIn("MOVE_REFUSED_INQUIRY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("inquiry_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_inquiry_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_inquiry_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("inquiry_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
