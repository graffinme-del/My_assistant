"""Bare implementation chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-я реализация», «12,5% реализации», and «214-я реализация» as document ids.
The calendar period parser does not recognize these phrases.

«реализация имущества» is the trustee guard. A folder titled «Реализация» is
not this guard. «без реализации» is not this guard. «реализованный»,
«реализовать», and «реализационный» are not this stem.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_realization import (
    looks_like_realization_scoped_document_request,
    mask_realization_ordinals,
    realization_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_realization_ordinals(raw)
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


class RealizationScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за реализацию в этой папке",
            "удали все документы за реализацию плана в этой папке",
            "удали все документы по реализации в этой папке",
            "удали все документы по реализации плана в этой папке",
            "удали все документы по плану реализации в этой папке",
            "удали все документы на реализации в этой папке",
            "удали все документы о реализации в этой папке",
            "удали все документы за реализацию проекта в этой папке",
            "удали все документы по проекту реализации в этой папке",
            "удали все документы за программу реализации в этой папке",
            "удали все документы в процессе реализации в этой папке",
            "удали все документы в планировании реализации в этой папке",
            "удали все документы за не реализацию в этой папке",
            "удали все документы за не полную реализацию в этой папке",
            "удали все документы за счет реализации в этой папке",
            "удали все документы за счёт реализации в этой папке",
            "удали все документы в ходе реализации в этой папке",
            "удали все документы в рамках реализации в этой папке",
            "удали все документы за полную реализацию в этой папке",
            "удали все документы за поэтапную реализацию в этой папке",
            "удали все документы за неполную реализацию в этой папке",
            "удали все документы за текущую реализацию",
            "удали все документы за открытую реализацию",
            "удали все документы за нереализацию плана в этой папке",
            "удали все документы до реализации в этой папке",
            "удали все документы после реализации в этой папке",
            "удали все документы во время реализации в этой папке",
            "удали все документы за «реализацию» в этой папке",
            "удали все документы за «реализацию плана» в этой папке",
            "удали каждый документ за реализацию в этой папке",
            "удали все файлы за реализацию в этой папке",
            "удали все документы дела А40-12345/2025 за реализацию",
            "удали все документы дела А40-12345/2025 за реализацию плана",
            "удали все документы за первую реализацию в этой папке",
            "удали все документы за мою реализацию в этой папке",
            "удали все документы за нашу реализацию в этой папке",
            "удали все документы по твоей реализации в этой папке",
            "удали все документы с реализации в этой папке",
            "удали все документы об реализации в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(realization_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за реализацию в этой папке",
            "удали все документы за реализацию плана в этой папке",
            "удали все документы за текущую реализацию",
            "удали все документы за открытую реализацию",
            "удали все документы по плану реализации в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я реализация", [1]),
            ("удали документы 1 реализация", [1]),
            ("удали документы 2-й реализации", [2]),
            ("удали документы 1-ю реализацию", [1]),
            ("удали документы 1-й реализации плана", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(realization_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 реализаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 реализаций"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 предложений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 предложений"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% реализации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% реализации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% реализации"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% реализации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я реализация"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я реализация"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й реализации"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й реализации"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реализацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реализацию плана"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за реализацию"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 100 реализации имущества"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 1-я реализация имущества"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й продажи"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е предложение"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за реализацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за реализацию плана в папку Архив",
            "перенеси все документы дела А40-12345/2025 по плану реализации в папку Архив",
            "перенеси документ 1-я реализация в дело Архив",
            "перемести документ 1-ю реализацию плана в дело Архив",
        )
        for text in phrases:
            self.assertTrue(realization_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за реализацию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_realization_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 реализаций в папку Архив"
        masked = mask_realization_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        asset = mask_realization_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 реализации имущества в папку Архив"
        )
        self.assertIn("100", asset)
        proposal = mask_realization_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 предложений в папку Архив"
        )
        self.assertIn("100", proposal)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            realization_blocks_bulk_document_mutation(
                "удали документ 214 за реализацию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реализацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реализацию плана"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по реализации"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за реализацию"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за реализацию"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Реализация",
            "удали все документы в папке «Реализация»",
            "удали все документы по делу Реализация",
            "удали все документы по делу Реализация плана",
            "удали все документы без реализации в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за реализацию имущества в этой папке",
            "удали все документы по реализации имущества в этой папке",
            "удали все документы за процедуру реализации имущества в этой папке",
            "удали все документы в планировании реализации имущества в этой папке",
            "удали все документы за счет реализации имущества в этой папке",
            "удали все документы за реализованный план в этой папке",
            "удали все документы за реализовать план в этой папке",
            "удали все документы за реализационную схему в этой папке",
            "удали все документы за планирование в этой папке",
            "удали все документы за планировать работы в этой папке",
            "удали все документы за предложение в этой папке",
            "удали все документы за продажу в этой папке",
            "удали все документы за публичное предложение в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Реализация",
            "собери все документы в папку Реализация по Гримме",
            "удали документ 214",
            "удали все документы по делу Реализация имущества",
        ):
            self.assertFalse(looks_like_realization_scoped_document_request(text), text)
            self.assertFalse(realization_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за реализацию",
            "по реализации",
            "на реализации",
            "о реализации",
            "за реализации",
            "за реализацией",
            "за реализаций",
            "по реализациям",
            "о реализациях",
            "за реализациями",
            "за реализацию плана",
            "по плану реализации",
            "по проекту реализации",
            "за программу реализации",
            "в процессе реализации",
            "за счет реализации",
            "в ходе реализации",
            "в рамках реализации",
            "за полную реализацию",
            "за поэтапную реализацию",
            "за текущую реализацию",
            "за открытую реализацию",
            "до реализации",
            "за первую реализацию",
            "за мою реализацию",
            "за нашу реализацию",
            "по твоей реализации",
            "за вашу реализацию",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_realization_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("realization_blocks_bulk_document_mutation", source)
        self.assertIn("mask_realization_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("realization_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_realization_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_realization_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("realization_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
