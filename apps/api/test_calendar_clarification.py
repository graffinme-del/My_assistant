"""«Разъяснение» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го разъяснения» as document id 1. The calendar-period parser does
not recognize these phrases, and the пояснение guard does not match «разъяснение».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_clarification import (
    clarification_blocks_bulk_document_mutation,
    looks_like_clarification_scoped_document_request,
    mask_clarification_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_clarification_ordinals(raw)
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


class ClarificationScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за разъяснение в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(clarification_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за разъяснения в этой папке",
            "удали все документы по разъяснению в этой папке",
            "удали все документы с разъяснениями в этой папке",
            "удали все документы за разъяснительное письмо в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertEqual(_pre_fix_parse_ids(synonym), [])
            self.assertIsNone(parse_calendar_period_ru(synonym))
            self.assertTrue(clarification_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        current = "удали все документы за текущее разъяснение"
        opened = "удали все документы за открытые разъяснения"
        for text in (current, opened):
            low = text.lower()
            self.assertIn("все документ", low)
            self.assertTrue("текущ" in low or "открыт" in low)
            self.assertIsNone(parse_calendar_period_ru(text))
            self.assertTrue(clarification_blocks_bulk_document_mutation(text))

    def test_case_number_scope_would_wipe_that_case(self) -> None:
        text = "удали все документы за разъяснение дела А53-13969/2026"
        self.assertIn("все документ", text.lower())
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertTrue(clarification_blocks_bulk_document_mutation(text))
        self.assertTrue(
            clarification_blocks_bulk_document_mutation(
                "удали все документы за разъяснительное письмо дела А40-12345/2025"
            )
        )

    def test_ordinal_wrong_id_trigger(self) -> None:
        """Pre-fix: the leading ordinal digit was document id 1 and that file was hard-deleted."""
        samples = (
            "удали документы 1-го разъяснения",
            "удали документы 1-е разъяснение",
            "удали документы 1-го разъяснительного письма",
            "удали документы 2-е разъяснение",
        )
        for text in samples:
            expected = [1] if " 1-" in text or text.startswith("удали документы 1") else [2]
            if "2-е" in text:
                expected = [2]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(clarification_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за разъяснение в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(clarification_blocks_bulk_document_mutation(text))
        self.assertTrue(
            clarification_blocks_bulk_document_mutation(
                "перенеси все документы с разъяснениями в папку Архив"
            )
        )
        self.assertTrue(
            clarification_blocks_bulk_document_mutation(
                "перенеси документ 1-го разъяснения в дело Архив"
            )
        )

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            clarification_blocks_bulk_document_mutation(
                "удали документ 254 за разъяснение",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за разъяснение"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за разъяснение"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за разъяснение в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за разъяснение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за разъяснение"), [214])
        self.assertIn("214", mask_clarification_ordinals("удали документ 214 за разъяснение"))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без разъяснений",
            "удали все документы в этой папке и дай разъяснение",
            "удали все документы в папке Разъяснение",
            "перенеси все документы в папку Разъяснение",
            "удали все документы дела А53-13969/2026",
            "удали все документы за пояснение в этой папке",
            "удали все документы за объяснение в этой папке",
            "удали все документы за требование в этой папке",
            "удали документы 1-го пояснения",
            "удали документы 1-го требования",
            "разъяснить документы в этой папке",
        ):
            self.assertFalse(looks_like_clarification_scoped_document_request(text), text)
            self.assertFalse(clarification_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все разъяснительные документы в этой папке",
            "удали все документы разъяснительные в этой папке",
            "удали все документы за письменное разъяснение в этой папке",
            "удали все документы во время разъяснения в этой папке",
            "удали все документы с разъяснительной запиской в этой папке",
        ):
            self.assertTrue(clarification_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("clarification_blocks_bulk_document_mutation", source)
        self.assertIn("mask_clarification_ordinals", source)
        self.assertIn("DELETE_REFUSED_CLARIFICATION", source)
        self.assertIn("MOVE_REFUSED_CLARIFICATION", source)


if __name__ == "__main__":
    unittest.main()
