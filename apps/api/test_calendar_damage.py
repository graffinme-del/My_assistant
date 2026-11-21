"""Damage chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-й ущерб» as document id 1.
A folder titled «Ущерб» is not this guard. «убытки», «вред», «расходы»,
«компенсация», «госпошлина», and «проценты» are not this guard.
«ущербный» and «ущербность» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_damage import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    damage_blocks_bulk_document_mutation,
    looks_like_damage_scoped_document_request,
    mask_damage_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_damage_ordinals(raw)
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


class DamageFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за ущерб в этой папке",
            "удали все документы по ущербу в этой папке",
            "удали все документы об ущербе в этой папке",
            "удали все документы за реальный ущерб в этой папке",
            "удали все документы за имущественный ущерб в этой папке",
            "удали все документы за материальный ущерб в этой папке",
            "удали все документы за прямой ущерб в этой папке",
            "удали все документы за моральный ущерб в этой папке",
            "удали все документы за возмещение ущерба в этой папке",
            "удали все документы за взыскание ущерба в этой папке",
            "удали все документы за причинение ущерба в этой папке",
            "удали все документы за размер ущерба в этой папке",
            "удали все документы за сумму ущерба в этой папке",
            "удали все документы за оценку ущерба в этой папке",
            "удали все документы за расчет ущерба в этой папке",
            "удали все документы за текущий ущерб",
            "удали все документы за открытый ущерб",
            "удали все документы за текущий реальный ущерб",
            "удали все файлы за ущерб в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(damage_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за ущерб"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(damage_blocks_bulk_document_mutation(numbered), numbered)
        real = "удали все документы дела А40-12345/2025 за реальный ущерб"
        self.assertTrue(damage_blocks_bulk_document_mutation(real), real)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-й ущерб", [1]),
            ("удали документы 1 ущерб", [1]),
            ("удали документы 2-го ущерба", [2]),
            ("удали документы 1-му ущербу", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(damage_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 ущербов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 ущербов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% ущерба"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% ущерба"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% ущерба"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% ущерба"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й ущерб"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ущерб"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го ущерба"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го ущерба"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ущерб"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за ущерб"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е расходы"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за ущерб в папку Архив",
            "перенеси все документы дела А40-12345/2025 за реальный ущерб в папку Архив",
            "перенеси все документы дела А40-12345/2025 за возмещение ущерба в папку Архив",
            "перенеси все документы дела А40-12345/2025 по ущербу в папку Архив",
            "перенеси документ 1-й ущерб в дело Архив",
            "перемести документ 100 ущербов в дело Архив",
        )
        for text in phrases:
            self.assertTrue(damage_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за ущерб в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_damage_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 ущербов в папку Архив"
        masked = mask_damage_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_damage_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            damage_blocks_bulk_document_mutation(
                "удали документ 214 за ущерб",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ущерб"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по ущербу"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за ущерб"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за ущерб"), [214])
        self.assertIn("ущерб", DELETE_REFUSED_REPLY)
        self.assertIn("ущерб", MOVE_REFUSED_REPLY)
        self.assertNotIn("убыт", DELETE_REFUSED_REPLY)
        self.assertNotIn("госпошлин", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Ущерб",
            "удали все документы в папке «Ущерб»",
            "удали все документы в папке «Реальный ущерб»",
            "удали все документы по делу Ущерб",
            "удали все документы по делу «Ущерб»",
            "удали все документы по делу «Имущественный ущерб»",
            "удали все документы без ущерба в этой папке",
            "удали все документы за убытки в этой папке",
            "удали все документы за вред в этой папке",
            "удали все документы за расходы в этой папке",
            "удали все документы за издержки в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за компенсацию ущерба в этой папке",
            "удали все документы за госпошлину в этой папке",
            "удали все документы за проценты в этой папке",
            "удали все документы за ущербный товар в этой папке",
            "удали все документы за ущербность в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Ущерб",
            "собери все документы в папку Ущерб",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_damage_scoped_document_request(text), text)
            self.assertFalse(damage_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за ущерб",
            "за ущерба",
            "за ущербу",
            "за ущербом",
            "за ущербе",
            "за ущербы",
            "по ущербам",
            "об ущербах",
            "с ущербами",
            "из ущербов",
            "за «ущерб»",
            "за Ущерб",
            "за реальный ущерб",
            "по реальному ущербу",
            "о имущественном ущербе",
            "за материальный ущерб",
            "за прямой ущерб",
            "за моральный ущерб",
            "за возмещение ущерба",
            "по возмещению ущерба",
            "за взыскание ущерба",
            "за причинение ущерба",
            "за оценку ущерба",
            "за расчет ущерба",
            "за счёт ущерба",
            "за текущий ущерб",
            "за открытый ущерб",
            "за мой ущерб",
            "за моё ущерб",
            "за первый ущерб",
            "за все ущербы",
            "за не ущерб",
            "во время ущерба",
            "во время причинения ущерба",
            "документы ущерб",
            "файлы ущерба",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_damage_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("damage_blocks_bulk_document_mutation", source)
        self.assertIn("mask_damage_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("damage_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_damage_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_damage_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("damage_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
