"""Overdraft / annuity / ссуда chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-го овердрафта» as document id 1. The calendar period parser does not recognize
these phrases.

«аренда» is not «рента». «рентабельность» and «рентген» are not this guard.
A folder titled «Овердрафт» is not this guard. Bare «банкротство» is not this guard.
«кредит» / «заем» / «аккредитив» stay with their own guards.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_overdraft import (
    looks_like_overdraft_scoped_document_request,
    mask_overdraft_ordinals,
    overdraft_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_overdraft_ordinals(raw)
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


class OverdraftScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за овердрафт в этой папке",
            "удали все документы по овердрафту в этой папке",
            "удали все документы об овердрафте в этой папке",
            "удали все документы за договор овердрафта в этой папке",
            "удали все документы за лимит овердрафта в этой папке",
            "удали все документы за технический овердрафт в этой папке",
            "удали все документы за разрешенный овердрафт в этой папке",
            "удали все документы за неразрешенный овердрафт в этой папке",
            "удали все документы за карту овердрафта в этой папке",
            "удали все документы за овердрафтный лимит в этой папке",
            "удали все документы за погашение овердрафта в этой папке",
            "удали все документы за проценты по овердрафту в этой папке",
            "удали все документы за 12,5% овердрафта в этой папке",
            "удали все документы за текущий овердрафт в этой папке",
            "удали все документы за открытый овердрафт в этой папке",
            "удали все документы во время овердрафта в этой папке",
            "удали все документы за ренту в этой папке",
            "удали все документы по ренте в этой папке",
            "удали все документы за договор ренты в этой папке",
            "удали все документы за пожизненную ренту в этой папке",
            "удали все документы за постоянную ренту в этой папке",
            "удали все документы за рентный платеж в этой папке",
            "удали все документы за рентополучателя в этой папке",
            "удали все документы за рентодателя в этой папке",
            "удали все документы за ссуду в этой папке",
            "удали все документы по ссуде в этой папке",
            "удали все документы за договор ссуды в этой папке",
            "удали все документы за беспроцентную ссуду в этой папке",
            "удали все документы за ссудный счет в этой папке",
            "удали все документы за выдачу ссуды в этой папке",
            "удали все документы за ссудодателя в этой папке",
            "удали все документы за ссудополучателя в этой папке",
            "удали все документы за текущую ренту",
            "удали все документы за текущий овердрафт",
            "удали все документы за открытую ссуду",
            "удали каждый документ за овердрафт в этой папке",
            "удали все файлы за ренту в этой папке",
            "удали все документы каждого овердрафта в этой папке",
            "удали все документы по всем рентам в этой папке",
            "удали все документы дела А40-12345/2025 за овердрафт",
            "удали все документы дела А40-12345/2025 за ренту",
            "удали все документы дела А40-12345/2025 за ссуду",
            "удали все документы за Овердрафт в этой папке",
            "удали все документы за Ренту в этой папке",
            "удали все документы за Ссуду в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(overdraft_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за овердрафт в этой папке",
            "удали все документы за ренту в этой папке",
            "удали все документы за ссуду в этой папке",
            "удали все документы за текущий овердрафт",
            "удали все документы за открытую ссуду",
            "удали все документы за открытый овердрафт в этой папке",
            "удали все документы за текущую ренту",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го овердрафта",
            "удали документы 1-й овердрафт",
            "удали документы 1-му овердрафту",
            "удали документы 1-й ренты",
            "удали документы 1-ю ренту",
            "удали документы 1-й ссуды",
            "удали документы 1-ю ссуду",
            "удали документы 2-го овердрафта",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(overdraft_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 овердрафта"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 овердрафта"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 ренты"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 ренты"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 ссуды"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 ссуды"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 ренты"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 ренты"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% ссуды"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% ссуды"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% овердрафта"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% овердрафта"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го овердрафта"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го овердрафта"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го рентополучателя"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го рентополучателя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й ссуды"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ссуды"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го ссудодателя"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го ссудодателя"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 ренты"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го кредита"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го кредита"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й аренды"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го займа"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й рентабельности"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за овердрафт в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ренту в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ссуду в папку Архив",
            "перенеси документ 1-го овердрафта в дело Архив",
            "перемести документ 1-й ренты в дело Архив",
            "перемести документ 1-й ссуды в дело Архив",
        )
        for text in phrases:
            self.assertTrue(overdraft_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за овердрафт в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_overdraft_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 ренты в папку Архив"
        masked = mask_overdraft_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            overdraft_blocks_bulk_document_mutation(
                "удали документ 214 за овердрафт",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за овердрафт"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за ренту"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за ссуду"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за ренту"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за ссуду"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без овердрафта",
            "удали все документы в этой папке без ренты",
            "удали все документы в этой папке без ссуды",
            "удали все документы в папке «Овердрафт»",
            "удали все документы в папке Овердрафт",
            "удали все документы в папке Рента",
            "удали все документы в папке Ссуда",
            "удали все документы из папки Овердрафт",
            "перенеси все документы в папку Овердрафт",
            "перенеси все документы в папку Рента",
            "перенеси все документы в папку Ссуда",
            "удали все документы по делу Овердрафт",
            "удали все документы по делу Рента",
            "удали все документы по делу Ссуда",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за банкротство в этой папке",
            "удали все документы за платеж в этой папке",
            "удали все документы за кредит в этой папке",
            "удали все документы за аренду в этой папке",
            "удали все документы за заем в этой папке",
            "удали все документы за займ в этой папке",
            "удали все документы за аккредитив в этой папке",
            "удали все документы за ипотеку в этой папке",
            "удали все документы за лизинг в этой папке",
            "удали все документы за рентабельность в этой папке",
            "удали все документы за рентабельный проект в этой папке",
            "удали все документы за рентген в этой папке",
            "удали все документы за подсудность в этой папке",
            "удали все документы за рассуждение в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы о том в этой папке",
            "удали все документы за тем в этой папке",
            "удали все документы после открытия",
            "удали все документы по текущей задолженности",
            "удали документы 1-го приказа",
            "удали документы 1-го кредита",
            "удали документы 1-й аренды",
            "удали документы 1-й рентабельности",
            "перенеси все документы в папку Архив",
        ):
            self.assertFalse(looks_like_overdraft_scoped_document_request(text), text)
            self.assertFalse(overdraft_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы овердрафта в этой папке",
            "удали документы ренты в этой папке",
            "удали документы ссуды в этой папке",
            "удали документы рентополучателя в этой папке",
            "удали все документы за первый овердрафт в этой папке",
            "удали все документы за первую ренту в этой папке",
            "удали все документы за первую ссуду в этой папке",
            "удали все документы за эту ренту в этой папке",
            "удали все документы за тот овердрафт в этой папке",
            "удали все документы о той ссуде в этой папке",
        ):
            self.assertTrue(overdraft_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за овердрафт",
            "за овердрафта",
            "за овердрафту",
            "за овердрафтом",
            "по овердрафту",
            "об овердрафте",
            "за овердрафты",
            "за овердрафтов",
            "за овердрафтам",
            "за овердрафтами",
            "за овердрафтах",
            "за овердрафтный лимит",
            "за овердрафтная карта",
            "за овердрафтное обслуживание",
            "за ренту",
            "за ренты",
            "по ренте",
            "о ренте",
            "за рентой",
            "за рентою",
            "за рентам",
            "за рентами",
            "за рентах",
            "за рентный платеж",
            "за рентного плательщика",
            "за рентополучателя",
            "за рентополучателем",
            "за рентодателя",
            "за рентодателем",
            "за пожизненную ренту",
            "за постоянную ренту",
            "за ссуду",
            "за ссуды",
            "по ссуде",
            "о ссуде",
            "за ссудой",
            "за ссудою",
            "за ссудам",
            "за ссудами",
            "за ссудах",
            "за ссуд",
            "за ссудный счет",
            "за ссудного должника",
            "за ссудодателя",
            "за ссудодателем",
            "за ссудополучателя",
            "за ссудополучателем",
            "за беспроцентную ссуду",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_overdraft_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("overdraft_blocks_bulk_document_mutation", source)
        self.assertIn("mask_overdraft_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("overdraft_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_overdraft_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_overdraft_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("overdraft_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
