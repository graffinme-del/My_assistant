"""«Доказательство» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го доказательства» as document id 1. Evidence is its own category
in classify_document; the calendar-period parser does not recognize these phrases.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_evidence import (
    looks_like_evidence_scoped_document_request,
    mask_evidence_ordinals,
    evidence_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_evidence_ordinals(raw)
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
    """Parser on main before evidence ordinals are masked."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", raw, flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


class EvidenceScopeTests(unittest.TestCase):
    def test_folder_wipe_phrases_are_evidence_scoped(self) -> None:
        for phrase in (
            "удали все документы за доказательства в этой папке",
            "удали все документы за доказательство в этой папке",
            "удали все документы с доказательствами в этой папке",
            "удали все документы по доказательствам в этой папке",
            "удали все файлы за письменные доказательства в этой папке",
            "удали все документы за вещественные доказательства в этой папке",
            "удали все документы за электронные доказательства в этой папке",
        ):
            self.assertTrue(looks_like_evidence_scoped_document_request(phrase), phrase)

    def test_demonstrative_and_current_evidence_are_detected(self) -> None:
        self.assertTrue(
            looks_like_evidence_scoped_document_request(
                "удали все документы за текущие доказательства"
            )
        )
        self.assertTrue(
            looks_like_evidence_scoped_document_request(
                "удали все документы за открытые доказательства"
            )
        )
        self.assertTrue(
            looks_like_evidence_scoped_document_request("удали документы этого доказательства")
        )
        self.assertTrue(
            looks_like_evidence_scoped_document_request("удали файлы этих доказательств")
        )

    def test_ordinals_and_adjective_documents_are_detected(self) -> None:
        for phrase in (
            "удали документы 1-го доказательства",
            "удали документы 1-е доказательство",
            "удали документы 2-х доказательств",
            "удали документы первого доказательства",
            "удали все документы доказательственные в этой папке",
            "удали все доказательственные документы в этой папке",
        ):
            self.assertTrue(looks_like_evidence_scoped_document_request(phrase), phrase)

    def test_unscoped_and_lookalikes_do_not_match(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы в папке «Доказательства»",
            "удали все документы в папке Доказательства",
            "удали документ «доказательство.pdf»",
            "удали все документы за контракт в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за поручение в этой папке",
            "удали все документы за приложение в этой папке",
            "удали все документы за расчет в этой папке",
            "удали все документы за человека в этой папке",
            "удали документы 1-го человека",
            "это доказательный аргумент, удали все документы в этой папке",
        ):
            self.assertFalse(looks_like_evidence_scoped_document_request(phrase), phrase)

    def test_human_ordinal_is_not_masked(self) -> None:
        self.assertFalse(looks_like_evidence_scoped_document_request("удали документы 1-го человека"))
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])

    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за доказательства в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(evidence_blocks_bulk_document_mutation(text))

    def test_with_evidence_phrase_wipes_pre_fix(self) -> None:
        """«с доказательствами» is the idiomatic scope and still matched wants_all."""
        text = "удали все документы с доказательствами в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("этой папк", low)
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(evidence_blocks_bulk_document_mutation(text))

    def test_current_evidence_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущие доказательства"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(evidence_blocks_bulk_document_mutation(text))

    def test_open_evidence_uses_active_folder_via_открыт(self) -> None:
        text = "удали все документы за открытые доказательства"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("открыт", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(evidence_blocks_bulk_document_mutation(text))

    def test_ordinal_evidence_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го доказательства» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го доказательства"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(evidence_blocks_bulk_document_mutation(text))

    def test_move_all_with_evidence_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за доказательства в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(evidence_blocks_bulk_document_mutation(text))
        with_evidence = "перенеси все документы с доказательствами в папку Архив"
        self.assertTrue(evidence_blocks_bulk_document_mutation(with_evidence))

    def test_explicit_id_still_allowed_even_if_evidence_is_mentioned(self) -> None:
        self.assertFalse(
            evidence_blocks_bulk_document_mutation(
                "удали документ 254 за доказательства",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за доказательства"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за доказательства"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_main_wires_the_guard(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("evidence_blocks_bulk_document_mutation", source)
        self.assertIn("mask_evidence_ordinals", source)
        self.assertIn("DELETE_REFUSED_EVIDENCE", source)
        self.assertIn("MOVE_REFUSED_EVIDENCE", source)


if __name__ == "__main__":
    unittest.main()
