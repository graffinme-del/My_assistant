"""«Пояснение» / «лицензия» / «свидетельство» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го пояснения» as document id 1. The calendar-period parser does not
recognize these phrases, and the требование guard does not match them.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_explanation import (
    explanation_blocks_bulk_document_mutation,
    looks_like_explanation_scoped_document_request,
    mask_explanation_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_explanation_ordinals(raw)
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


class ExplanationScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за пояснение в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(explanation_blocks_bulk_document_mutation(text))

    def test_with_explanations_phrase_wipes_pre_fix(self) -> None:
        text = "удали все документы с пояснениями в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("этой папк", low)
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(explanation_blocks_bulk_document_mutation(text))

    def test_explanatory_note_wipes_pre_fix(self) -> None:
        text = "удали все документы за пояснительную записку в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(explanation_blocks_bulk_document_mutation(text))
        self.assertTrue(
            explanation_blocks_bulk_document_mutation(
                "удали все документы с пояснительной запиской в этой папке"
            )
        )

    def test_license_and_certificate_wipes_pre_fix(self) -> None:
        for text in (
            "удали все документы за лицензию в этой папке",
            "удали все документы по лицензии в этой папке",
            "удали все документы с лицензией в этой папке",
            "удали все документы за свидетельство в этой папке",
            "удали все документы со свидетельством в этой папке",
            "удали все документы по свидетельству в этой папке",
        ):
            low = text.lower()
            self.assertIn("все документ", low, text)
            self.assertTrue(any(p in low for p in ("этой папк", "в этой")), text)
            self.assertEqual(_pre_fix_parse_ids(text), [], text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(explanation_blocks_bulk_document_mutation(text), text)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        current = "удали все документы за текущее пояснение"
        opened = "удали все документы за открытые лицензии"
        for text in (current, opened):
            low = text.lower()
            self.assertIn("все документ", low)
            self.assertTrue("текущ" in low or "открыт" in low)
            self.assertIsNone(parse_calendar_period_ru(text))
            self.assertTrue(explanation_blocks_bulk_document_mutation(text))

    def test_case_number_scope_would_wipe_that_case(self) -> None:
        text = "удали все документы за пояснение дела А53-13969/2026"
        self.assertIn("все документ", text.lower())
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertTrue(explanation_blocks_bulk_document_mutation(text))
        self.assertTrue(
            explanation_blocks_bulk_document_mutation(
                "удали все документы за свидетельство дела А40-12345/2025"
            )
        )

    def test_ordinal_wrong_id_trigger(self) -> None:
        """Pre-fix: the leading ordinal digit was document id 1 and that file was hard-deleted."""
        samples = (
            "удали документы 1-го пояснения",
            "удали документы 1-й лицензии",
            "удали документы 1-го свидетельства",
            "удали документы 1-й пояснительной записки",
            "удали документы 2-е свидетельство",
        )
        for text in samples:
            self.assertEqual(_pre_fix_parse_ids(text), [1] if text.startswith("удали документы 1") else [2], text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(explanation_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за пояснение в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(explanation_blocks_bulk_document_mutation(text))
        self.assertTrue(
            explanation_blocks_bulk_document_mutation(
                "перенеси все документы с пояснениями в папку Архив"
            )
        )
        self.assertTrue(
            explanation_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за лицензию в папку Архив"
            )
        )
        self.assertTrue(
            explanation_blocks_bulk_document_mutation(
                "перенеси документ 1-го свидетельства в дело Архив"
            )
        )

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            explanation_blocks_bulk_document_mutation(
                "удали документ 254 за пояснение",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за пояснение"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за лицензию"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за свидетельство"), [214])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за пояснение в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за лицензию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за лицензию"), [214])
        self.assertNotIn("214", mask_explanation_ordinals("удали документ 214 за свидетельство"))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без пояснений",
            "удали все документы в этой папке и дай пояснение",
            "удали все документы в папке Пояснение",
            "удали все документы в папке Лицензия",
            "удали все документы в папке Свидетельство",
            "перенеси все документы в папку Пояснение",
            "удали все документы дела А53-13969/2026",
            "удали все документы за требование в этой папке",
            "удали документы 1-го требования",
        ):
            self.assertFalse(looks_like_explanation_scoped_document_request(text), text)
            self.assertFalse(explanation_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все документы пояснительные в этой папке",
            "удали все пояснительные документы в этой папке",
            "удали все лицензионные документы в этой папке",
            "удали все документы за письменные пояснения в этой папке",
        ):
            self.assertTrue(explanation_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("explanation_blocks_bulk_document_mutation", source)
        self.assertIn("mask_explanation_ordinals", source)
        self.assertIn("DELETE_REFUSED_EXPLANATION", source)
        self.assertIn("MOVE_REFUSED_EXPLANATION", source)


if __name__ == "__main__":
    unittest.main()
