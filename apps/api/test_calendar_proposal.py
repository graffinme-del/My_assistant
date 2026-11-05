"""Bare proposal chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-е предложение», «12,5% предложения», and «214-е предложение» as document ids.
The calendar period parser does not recognize these phrases.

«публичное предложение» is the auction guard. «оферта» is the payment guard.
A folder titled «Предложение» is not this guard. «без предложения» is not this
guard. «предложенный» and «предложить» are not this stem.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_proposal import (
    looks_like_proposal_scoped_document_request,
    mask_proposal_ordinals,
    proposal_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_proposal_ordinals(raw)
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


def _wants_all(text: str) -> bool:
    low = (text or "").lower()
    return any(
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


def _pre_fix_selects_active_folder(text: str) -> bool:
    """Current main treats these substrings as the open folder once wants_all is true."""
    low = (text or "").lower()
    return _wants_all(text) and any(
        p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело")
    )


class ProposalScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за предложение в этой папке",
            "удали все документы по предложению в этой папке",
            "удали все документы на предложении в этой папке",
            "удали все документы о предложении в этой папке",
            "удали все документы за коммерческое предложение в этой папке",
            "удали все документы по коммерческому предложению в этой папке",
            "удали все документы за встречное предложение в этой папке",
            "удали все документы за ценовое предложение в этой папке",
            "удали все документы за служебное предложение в этой папке",
            "удали все документы за текущее предложение",
            "удали все документы за открытое предложение",
            "удали все документы за некоммерческое предложение в этой папке",
            "удали все документы по условиям предложения в этой папке",
            "удали все документы в рамках предложения в этой папке",
            "удали все документы до предложения в этой папке",
            "удали все документы после предложения в этой папке",
            "удали все документы во время предложения в этой папке",
            "удали все документы за «предложение» в этой папке",
            "удали все документы за «коммерческое предложение» в этой папке",
            "удали каждый документ за предложение в этой папке",
            "удали все файлы за предложение в этой папке",
            "удали все документы дела А40-12345/2025 за предложение",
            "удали все документы дела А40-12345/2025 за коммерческое предложение",
            "удали все документы за первое предложение в этой папке",
            "удали все документы за моё предложение в этой папке",
            "удали все документы за наше предложение в этой папке",
            "удали все документы по твоему предложению в этой папке",
            "удали все документы с предложения в этой папке",
            "удали все документы об предложении в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(proposal_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за предложение в этой папке",
            "удали все документы за коммерческое предложение в этой папке",
            "удали все документы за текущее предложение",
            "удали все документы за открытое предложение",
            "удали все документы за встречное предложение в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е предложение", [1]),
            ("удали документы 1 предложение", [1]),
            ("удали документы 2-го предложения", [2]),
            ("удали документы 1-му коммерческому предложению", [1]),
            ("удали документы 1-го договора предложения", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(proposal_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 предложений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 предложений"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оферт"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оферт"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% предложения"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% предложения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% предложения"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% предложения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е предложение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е предложение"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го предложения"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го предложения"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за предложение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за коммерческое предложение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за предложение"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-е публичное предложение"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й оферты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й продажи"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за предложение в папку Архив",
            "перенеси все документы дела А40-12345/2025 за коммерческое предложение в папку Архив",
            "перенеси все документы дела А40-12345/2025 за встречное предложение в папку Архив",
            "перенеси документ 1-е предложение в дело Архив",
            "перемести документ 1-е коммерческое предложение в дело Архив",
        )
        for text in phrases:
            self.assertTrue(proposal_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за предложение в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_proposal_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 предложений в папку Архив"
        masked = mask_proposal_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        public = mask_proposal_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 публичных предложений в папку Архив"
        )
        self.assertIn("100", public)
        oferta = mask_proposal_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 оферт в папку Архив"
        )
        self.assertIn("100", oferta)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            proposal_blocks_bulk_document_mutation(
                "удали документ 214 за предложение",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за предложение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за коммерческое предложение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по предложению"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за предложение"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за предложение"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Предложение",
            "удали все документы в папке «Предложение»",
            "удали все документы по делу Предложение",
            "удали все документы по делу Коммерческое предложение",
            "удали все документы без предложения в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за публичное предложение в этой папке",
            "удали все документы за публичного предложения в этой папке",
            "удали все документы за оферту в этой папке",
            "удали все документы за публичную оферту в этой папке",
            "удали все документы за коммерческую оферту в этой папке",
            "удали все документы за продажу в этой папке",
            "удали все документы за реализацию плана в этой папке",
            "удали все документы за реализацию имущества в этой папке",
            "удали все документы за предложенный договор в этой папке",
            "удали все документы за предложить правки в этой папке",
            "удали все документы за торги в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Предложение",
            "собери все документы в папку Предложение по Гримме",
            "удали документ 214",
            "удали все документы по делу Публичное предложение",
        ):
            self.assertFalse(looks_like_proposal_scoped_document_request(text), text)
            self.assertFalse(proposal_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за предложение",
            "по предложению",
            "на предложении",
            "о предложении",
            "за предложения",
            "за предложением",
            "за предложений",
            "по предложениям",
            "о предложениях",
            "за предложениями",
            "за коммерческое предложение",
            "по коммерческому предложению",
            "за встречное предложение",
            "за текущее предложение",
            "за открытое предложение",
            "в рамках предложения",
            "по условиям предложения",
            "до предложения",
            "за первое предложение",
            "за ценовое предложение",
            "за моё предложение",
            "за наше предложение",
            "по твоему предложению",
            "за ваше предложение",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_proposal_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("proposal_blocks_bulk_document_mutation", source)
        self.assertIn("mask_proposal_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("proposal_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_proposal_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_proposal_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("proposal_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
