"""Inheritance chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
«по принятию наследства» as a PDF-text hint.
parse_document_ids_for_delete_command read «1-е наследство» as document id 1.

A folder titled «Наследство» is not this guard. «без наследства» is not
this guard. «наследственный», «наследник», «наследование», «претензия»,
«упущенная прибыль», «упущенная выгода», «неосновательное обогащение»,
and «ущерб» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_inheritance import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    inheritance_blocks_bulk_document_mutation,
    looks_like_inheritance_scoped_document_request,
    mask_inheritance_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_inheritance_ordinals(raw)
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


def _pre_fix_pdf_hint(text: str) -> str | None:
    """Tail of «по <phrase>» that handle_delete_documents_chat searches across PDFs."""
    m2 = re.search(
        r"(?<![а-яё])по\s+(?!делу\b)([А-Яа-яЁё][А-Яа-яЁё'\-]*(?:\s+[А-Яа-яЁё][А-Яа-яЁё'\-]*){1,6})"
        r"(?:\s*[!?.…]*)?(?:\s*$|\n)",
        text or "",
        flags=re.IGNORECASE,
    )
    if not m2:
        return None
    return m2.group(1).strip()


class InheritanceFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за наследство в этой папке",
            "удали все документы по наследству в этой папке",
            "удали все документы о наследстве в этой папке",
            "удали все документы об наследстве в этой папке",
            "удали все документы за принятие наследства в этой папке",
            "удали все документы за вступление в наследство в этой папке",
            "удали все документы за отказ от наследства в этой папке",
            "удали все документы за раздел наследства в этой папке",
            "удали все документы за открытие наследства в этой папке",
            "удали все документы за оформление наследства в этой папке",
            "удали все документы за получение наследства в этой папке",
            "удали все документы за долю наследства в этой папке",
            "удали все документы за долю в наследстве в этой папке",
            "удали все документы за состав наследства в этой папке",
            "удали все документы за размер наследства в этой папке",
            "удали все документы за оценку наследства в этой папке",
            "удали все документы за расчет наследства в этой папке",
            "удали все документы за расчёт наследства в этой папке",
            "удали все документы за очередь наследства в этой папке",
            "удали все документы за массу наследства в этой папке",
            "удали все документы за выдел наследства в этой папке",
            "удали все документы за выделение наследства в этой папке",
            "удали все документы за переход наследства в этой папке",
            "удали все документы за текущее наследство",
            "удали все документы за открытое наследство",
            "удали все документы за текущее принятое наследство",
            "удали все файлы за наследство в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(inheritance_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за наследство"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(inheritance_blocks_bulk_document_mutation(numbered), numbered)
        acceptance = "удали все документы дела А40-12345/2025 за принятие наследства"
        self.assertTrue(inheritance_blocks_bulk_document_mutation(acceptance), acceptance)

        hint = "удали документы по принятию наследства"
        self.assertEqual(_pre_fix_pdf_hint(hint), "принятию наследства")
        self.assertTrue(inheritance_blocks_bulk_document_mutation(hint), hint)
        hinted_all = "удали все документы по принятию наследства"
        self.assertEqual(_pre_fix_pdf_hint(hinted_all), "принятию наследства")
        self.assertTrue(inheritance_blocks_bulk_document_mutation(hinted_all), hinted_all)
        single = "удали документы по наследству"
        self.assertIsNone(_pre_fix_pdf_hint(single))
        self.assertTrue(inheritance_blocks_bulk_document_mutation(single), single)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е наследство", [1]),
            ("удали документы 1 наследство", [1]),
            ("удали документы 1-ое наследство", [1]),
            ("удали документы 2-е наследства", [2]),
            ("удали документы 1-м наследством", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(inheritance_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 наследств"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 наследств"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12,5% наследства"),
            [5, 12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% наследства"), [])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12.5% наследства"),
            [12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% наследства"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е наследство"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-ое наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-ое наследство"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(
            _parse_ids_like_main("удали документы 214 287 за наследство"),
            [214, 287],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ущерб"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я претензия"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за наследство в папку Архив",
            "перенеси все документы дела А40-12345/2025 за принятие наследства в папку Архив",
            "перенеси все документы дела А40-12345/2025 за раздел наследства в папку Архив",
            "перенеси все документы дела А40-12345/2025 по наследству в папку Архив",
            "перенеси документ 1-е наследство в дело Архив",
            "перемести документ 100 наследств в дело Архив",
        )
        for text in phrases:
            self.assertTrue(inheritance_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за наследство в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_inheritance_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 наследств в папку Архив"
        masked = mask_inheritance_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_inheritance_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            inheritance_blocks_bulk_document_mutation(
                "удали документ 214 за наследство",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по наследству"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за наследство"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за наследство"), [214])
        self.assertIn("наследств", DELETE_REFUSED_REPLY)
        self.assertIn("наследств", MOVE_REFUSED_REPLY)
        self.assertNotIn("претенз", DELETE_REFUSED_REPLY)
        self.assertNotIn("упущен", DELETE_REFUSED_REPLY)
        self.assertNotIn("ущерб", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Наследство",
            "удали все документы в папке «Наследство»",
            "удали все документы в папке «НАСЛЕДСТВО»",
            "удали все документы по делу Наследство",
            "удали все документы по делу «Наследство»",
            "удали все документы по делу «Принятие наследства»",
            "удали все документы в папке «Раздел наследства»",
            "удали все документы без наследства в этой папке",
            "удали все документы за наследственный спор в этой папке",
            "удали все документы за наследника в этой папке",
            "удали все документы за наследование в этой папке",
            "удали все документы за претензию в этой папке",
            "удали все документы за упущенную прибыль в этой папке",
            "удали все документы за упущенную выгоду в этой папке",
            "удали все документы за неосновательное обогащение в этой папке",
            "удали все документы за ущерб в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за расходы в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Наследство",
            "собери все документы в папку Наследство",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_inheritance_scoped_document_request(text), text)
            self.assertFalse(inheritance_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за наследство",
            "за наследства",
            "по наследству",
            "о наследстве",
            "об наследстве",
            "с наследством",
            "из наследств",
            "за «наследство»",
            "за Наследство",
            "за НАСЛЕДСТВО",
            "за принятие наследства",
            "по принятию наследства",
            "за вступление в наследство",
            "за отказ от наследства",
            "за раздел наследства",
            "за открытие наследства",
            "за оформление наследства",
            "за получение наследства",
            "за долю наследства",
            "за долю в наследстве",
            "за состав наследства",
            "за размер наследства",
            "за оценку наследства",
            "за расчет наследства",
            "за расчёт наследства",
            "за очередь наследства",
            "за массу наследства",
            "за выдел наследства",
            "за выделение наследства",
            "за переход наследства",
            "за текущее наследство",
            "за открытое наследство",
            "за моё наследство",
            "за мое наследство",
            "за первое наследство",
            "за все наследства",
            "за не наследство",
            "во время наследства",
            "во время принятия наследства",
            "на наследство",
            "документы наследство",
            "файлы наследства",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_inheritance_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            '"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"',
            source,
        )
        self.assertIn("inheritance_blocks_bulk_document_mutation", source)
        self.assertIn("mask_inheritance_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("inheritance_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        self.assertLess(
            delete_fn.index("inheritance_blocks_bulk_document_mutation"),
            delete_fn.index("_extract_delete_target_phrases"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertLess(
            parse_fn.index("mask_inheritance_ordinals"),
            parse_fn.index("re.search"),
        )
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_inheritance_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("inheritance_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
