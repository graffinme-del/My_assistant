"""Debt-restructuring chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-я реструктуризация», «12,5% реструктуризации», and «214-я реструктуризация»
as document ids. The calendar period parser does not recognize these phrases.

«наблюдение» / «конкурсное производство» / «внешнее управление» /
«финансовое оздоровление» are the procedure guard. «реализация имущества»
is the trustee guard. A folder titled «Реструктуризация» is not this guard.
«без реструктуризации» is not this guard. «реструктурированный»,
«реструктурировать», and «реструктуризационный» are not this stem.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_restructuring import (
    looks_like_restructuring_scoped_document_request,
    mask_restructuring_ordinals,
    restructuring_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_restructuring_ordinals(raw)
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


class RestructuringScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за реструктуризацию в этой папке",
            "удали все документы за реструктуризацию долгов в этой папке",
            "удали все документы по реструктуризации в этой папке",
            "удали все документы по реструктуризации долгов в этой папке",
            "удали все документы по плану реструктуризации в этой папке",
            "удали все документы по графику реструктуризации в этой папке",
            "удали все документы за план реструктуризации в этой папке",
            "удали все документы за график реструктуризации долгов в этой папке",
            "удали все документы за процедуру реструктуризации в этой папке",
            "удали все документы на реструктуризации в этой папке",
            "удали все документы о реструктуризации в этой папке",
            "удали все документы в процессе реструктуризации в этой папке",
            "удали все документы в ходе реструктуризации в этой папке",
            "удали все документы в рамках реструктуризации в этой папке",
            "удали все документы за счет реструктуризации в этой папке",
            "удали все документы за счёт реструктуризации долгов в этой папке",
            "удали все документы за не реструктуризацию в этой папке",
            "удали все документы за не полную реструктуризацию в этой папке",
            "удали все документы за неполную реструктуризацию в этой папке",
            "удали все документы за полную реструктуризацию в этой папке",
            "удали все документы за текущую реструктуризацию",
            "удали все документы за открытую реструктуризацию",
            "удали все документы за нереструктуризацию долгов в этой папке",
            "удали все документы до реструктуризации в этой папке",
            "удали все документы после реструктуризации в этой папке",
            "удали все документы во время реструктуризации в этой папке",
            "удали все документы за «реструктуризацию» в этой папке",
            "удали все документы за «реструктуризацию долгов» в этой папке",
            "удали каждый документ за реструктуризацию в этой папке",
            "удали все файлы за реструктуризацию в этой папке",
            "удали все документы дела А40-12345/2025 за реструктуризацию",
            "удали все документы дела А40-12345/2025 за реструктуризацию долгов",
            "удали все документы за первую реструктуризацию в этой папке",
            "удали все документы за мою реструктуризацию в этой папке",
            "удали все документы за нашу реструктуризацию в этой папке",
            "удали все документы по твоей реструктуризации в этой папке",
            "удали все документы с реструктуризации в этой папке",
            "удали все документы об реструктуризации в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(restructuring_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за реструктуризацию в этой папке",
            "удали все документы за реструктуризацию долгов в этой папке",
            "удали все документы за текущую реструктуризацию",
            "удали все документы за открытую реструктуризацию",
            "удали все документы по плану реструктуризации в этой папке",
            "удали все документы по графику реструктуризации в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я реструктуризация", [1]),
            ("удали документы 1 реструктуризация", [1]),
            ("удали документы 2-й реструктуризации", [2]),
            ("удали документы 1-ю реструктуризацию", [1]),
            ("удали документы 1-й реструктуризации долгов", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(restructuring_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 реструктуризаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 реструктуризаций"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 реализаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 реализаций"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% реструктуризации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% реструктуризации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% реструктуризации"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% реструктуризации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я реструктуризация"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я реструктуризация"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й реструктуризации долгов"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й реструктуризации долгов"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реструктуризацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реструктуризацию долгов"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за реструктуризацию"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я реализация"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й продажи"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за реструктуризацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за реструктуризацию долгов в папку Архив",
            "перенеси все документы дела А40-12345/2025 по плану реструктуризации в папку Архив",
            "перенеси все документы дела А40-12345/2025 по графику реструктуризации в папку Архив",
            "перенеси документ 1-я реструктуризация в дело Архив",
            "перемести документ 1-ю реструктуризацию долгов в дело Архив",
        )
        for text in phrases:
            self.assertTrue(restructuring_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за реструктуризацию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_restructuring_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 реструктуризаций в папку Архив"
        masked = mask_restructuring_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        realization = mask_restructuring_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 реализаций в папку Архив"
        )
        self.assertIn("100", realization)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            restructuring_blocks_bulk_document_mutation(
                "удали документ 214 за реструктуризацию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реструктуризацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реструктуризацию долгов"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по реструктуризации"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за реструктуризацию"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за реструктуризацию"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Реструктуризация",
            "удали все документы в папке «Реструктуризация»",
            "удали все документы по делу Реструктуризация",
            "удали все документы по делу Реструктуризация долгов",
            "удали все документы без реструктуризации в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за наблюдение в этой папке",
            "удали все документы за конкурсное производство в этой папке",
            "удали все документы за внешнее управление в этой папке",
            "удали все документы за финансовое оздоровление в этой папке",
            "удали все документы за реализацию в этой папке",
            "удали все документы за реализацию имущества в этой папке",
            "удали все документы за реструктурированный план в этой папке",
            "удали все документы за реструктурировать долг в этой папке",
            "удали все документы за реструктуризационную схему в этой папке",
            "удали все документы за план в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы за продажу в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Реструктуризация",
            "собери все документы в папку Реструктуризация по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_restructuring_scoped_document_request(text), text)
            self.assertFalse(restructuring_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за реструктуризацию",
            "по реструктуризации",
            "на реструктуризации",
            "о реструктуризации",
            "за реструктуризации",
            "за реструктуризацией",
            "за реструктуризаций",
            "по реструктуризациям",
            "о реструктуризациях",
            "за реструктуризациями",
            "за реструктуризацию долгов",
            "по плану реструктуризации",
            "по графику реструктуризации",
            "за процедуру реструктуризации",
            "в процессе реструктуризации",
            "за счет реструктуризации",
            "в ходе реструктуризации",
            "в рамках реструктуризации",
            "за полную реструктуризацию",
            "за текущую реструктуризацию",
            "за открытую реструктуризацию",
            "до реструктуризации",
            "за первую реструктуризацию",
            "за мою реструктуризацию",
            "за нашу реструктуризацию",
            "по твоей реструктуризации",
            "за вашу реструктуризацию",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_restructuring_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("restructuring_blocks_bulk_document_mutation", source)
        self.assertIn("mask_restructuring_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("restructuring_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_restructuring_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_restructuring_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("restructuring_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
