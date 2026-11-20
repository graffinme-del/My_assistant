"""Court-cost chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-е расходы» as document id 1.
A folder titled «Расходы» or «Издержки» is not this guard. «компенсация
расходов», «госпошлина», «убытки», «вред», and «проценты» are not this guard.
«расходный» and «расходование» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_expenses import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    expenses_blocks_bulk_document_mutation,
    looks_like_expenses_scoped_document_request,
    mask_expenses_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_expenses_ordinals(raw)
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


class ExpensesFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за расходы в этой папке",
            "удали все документы по расходам в этой папке",
            "удали все документы о расходах в этой папке",
            "удали все документы за судебные расходы в этой папке",
            "удали все документы за издержки в этой папке",
            "удали все документы по издержкам в этой папке",
            "удали все документы о судебных издержках в этой папке",
            "удали все документы за судебные издержки в этой папке",
            "удали все документы за взыскание судебных расходов в этой папке",
            "удали все документы за возмещение судебных расходов в этой папке",
            "удали все документы за возмещение издержек в этой папке",
            "удали все документы за распределение судебных расходов в этой папке",
            "удали все документы за размер судебных расходов в этой папке",
            "удали все документы за сумму издержек в этой папке",
            "удали все документы за оплату судебных расходов в этой папке",
            "удали все документы за представительские расходы в этой папке",
            "удали все документы за транспортные расходы в этой папке",
            "удали все документы за почтовые расходы в этой папке",
            "удали все документы за командировочные расходы в этой папке",
            "удали все документы за статью судебных расходов в этой папке",
            "удали все документы за счет судебных расходов в этой папке",
            "удали все документы за счёт судебных расходов в этой папке",
            "удали все документы за текущие расходы",
            "удали все документы за открытые расходы",
            "удали все документы за текущие судебные издержки",
            "удали все документы за открытые судебные издержки",
            "удали все файлы за издержки в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(expenses_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за судебные расходы"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(expenses_blocks_bulk_document_mutation(numbered), numbered)
        costs = "удали все документы дела А40-12345/2025 за издержки"
        self.assertTrue(expenses_blocks_bulk_document_mutation(costs), costs)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е расходы", [1]),
            ("удали документы 1 расходы", [1]),
            ("удали документы 2-й расход", [2]),
            ("удали документы 1-ю издержку", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(expenses_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 расходов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 расходов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 издержек"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 издержек"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 компенсаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 компенсаций"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% расходов"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% расходов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% издержек"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% издержек"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е расходы"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е расходы"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х издержек"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х издержек"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за расходы"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за издержки"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я компенсация"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за судебные расходы в папку Архив",
            "перенеси все документы дела А40-12345/2025 за издержки в папку Архив",
            "перенеси все документы дела А40-12345/2025 за возмещение судебных расходов в папку Архив",
            "перенеси все документы дела А40-12345/2025 по издержкам в папку Архив",
            "перенеси документ 1-е расходы в дело Архив",
            "перемести документ 100 издержек в дело Архив",
        )
        for text in phrases:
            self.assertTrue(expenses_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за расходы в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_expenses_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 расходов в папку Архив"
        masked = mask_expenses_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_expenses_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 компенсаций в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            expenses_blocks_bulk_document_mutation(
                "удали документ 214 за расходы",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за расходы"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по издержкам"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за судебные расходы"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за издержки"), [214])
        self.assertIn("расходы", DELETE_REFUSED_REPLY)
        self.assertIn("издержки", DELETE_REFUSED_REPLY)
        self.assertIn("расходы", MOVE_REFUSED_REPLY)
        self.assertNotIn("компенсац", DELETE_REFUSED_REPLY)
        self.assertNotIn("госпошлин", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Расходы",
            "удали все документы в папке «Расходы»",
            "удали все документы в папке «Судебные расходы»",
            "удали все документы в папке «Издержки»",
            "удали все документы в папке «Судебные издержки»",
            "удали все документы по делу Расходы",
            "удали все документы по делу «Расходы»",
            "удали все документы по делу «Судебные расходы»",
            "удали все документы по делу Издержки",
            "удали все документы по делу «Издержки»",
            "удали все документы без расходов в этой папке",
            "удали все документы без издержек в этой папке",
            "удали все документы без судебных расходов в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за компенсацию расходов в этой папке",
            "удали все документы за госпошлину в этой папке",
            "удали все документы за убытки в этой папке",
            "удали все документы за вред в этой папке",
            "удали все документы за проценты в этой папке",
            "удали все документы за пенсию в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за расходные материалы в этой папке",
            "удали все документы за расходование средств в этой папке",
            "удали все документы за израсходование средств в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Расходы",
            "собери все документы в папку Судебные расходы",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_expenses_scoped_document_request(text), text)
            self.assertFalse(expenses_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за расход",
            "за расхода",
            "за расходу",
            "за расходом",
            "за расходе",
            "за расходы",
            "по расходам",
            "о расходах",
            "с расходами",
            "из расходов",
            "за издержку",
            "за издержки",
            "за издержек",
            "по издержке",
            "с издержкой",
            "с издержками",
            "об издержках",
            "за «расходы»",
            "за Расходы",
            "за судебные расходы",
            "по судебным расходам",
            "о судебных издержках",
            "за взыскание судебных расходов",
            "по взысканию издержек",
            "за возмещение судебных расходов",
            "за возмещение издержек",
            "за распределение судебных расходов",
            "за статью судебных расходов",
            "по статье издержек",
            "за счет судебных расходов",
            "за счёт судебных расходов",
            "за текущие расходы",
            "за открытые расходы",
            "за мои расходы",
            "за моё расходы",
            "за первую издержку",
            "за все расходы",
            "за не расходы",
            "во время судебных расходов",
            "во время издержек",
            "за представительские расходы",
            "за транспортные расходы",
            "за почтовые расходы",
            "за командировочные расходы",
            "документы расходы",
            "файлы издержек",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_expenses_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("expenses_blocks_bulk_document_mutation", source)
        self.assertIn("mask_expenses_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("expenses_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_expenses_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_expenses_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("expenses_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
