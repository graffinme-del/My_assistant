"""Allowance chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-я надбавка» as document id 1.
A folder titled «Надбавка» is not this guard. «доплата», «премия»,
«вознаграждение», «зарплата», «алименты», and «оплата труда» are not this
guard. «гонорар», «пособие», and «пенсия» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_allowance import (
    allowance_blocks_bulk_document_mutation,
    looks_like_allowance_scoped_document_request,
    mask_allowance_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_allowance_ordinals(raw)
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


class AllowanceFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за надбавку в этой папке",
            "удали все документы по надбавке в этой папке",
            "удали все документы о надбавке в этой папке",
            "удали все документы за взыскание надбавки в этой папке",
            "удали все документы за невыплату надбавки в этой папке",
            "удали все документы по выплате надбавки в этой папке",
            "удали все документы за задолженность по надбавке в этой папке",
            "удали все документы по размеру надбавки в этой папке",
            "удали все документы за задержку надбавки в этой папке",
            "удали все документы за начисление надбавки в этой папке",
            "удали все документы за индексацию надбавки в этой папке",
            "удали все документы за снижение надбавки в этой папке",
            "удали все документы за установление надбавки в этой папке",
            "удали все документы за лишение надбавки в этой папке",
            "удали все документы за ночную надбавку в этой папке",
            "удали все документы за сверхурочную надбавку в этой папке",
            "удали все документы за районную надбавку в этой папке",
            "удали все документы за северную надбавку в этой папке",
            "удали все документы за процентную надбавку в этой папке",
            "удали все документы за стимулирующую надбавку в этой папке",
            "удали все документы за персональную надбавку в этой папке",
            "удали все документы за компенсационную надбавку в этой папке",
            "удали все документы за годовую надбавку в этой папке",
            "удали все документы за текущую надбавку",
            "удали все документы за открытую надбавку",
            "удали все документы за счёт надбавки в этой папке",
            "удали все файлы за надбавку в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(allowance_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за надбавку"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(allowance_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я надбавка", [1]),
            ("удали документы 1 надбавка", [1]),
            ("удали документы 2-ю надбавку", [2]),
            ("удали документы 1-й надбавки", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(allowance_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 надбавок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 надбавок"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 доплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 доплат"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 премий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 премий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 зарплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 зарплат"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 алиментов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 алиментов"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оплат труда"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оплат труда"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 вознаграждений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 вознаграждений"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 гонораров"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 гонораров"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пособий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пособий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пенсий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пенсий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% надбавки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% надбавки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% надбавки"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% надбавки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я надбавка"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я надбавка"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х надбавок"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х надбавок"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за надбавку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за надбавку"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я доплата"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я премия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й гонорар"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я пенсия"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за надбавку в папку Архив",
            "перенеси все документы дела А40-12345/2025 по надбавке в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание надбавки в папку Архив",
            "перенеси все документы дела А40-12345/2025 за северную надбавку в папку Архив",
            "перенеси все документы дела А40-12345/2025 за районную надбавку в папку Архив",
            "перенеси документ 1-я надбавка в дело Архив",
            "перемести документ 100 надбавок в дело Архив",
        )
        for text in phrases:
            self.assertTrue(allowance_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за надбавку в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_allowance_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 надбавок в папку Архив"
        masked = mask_allowance_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        surcharge = mask_allowance_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 доплат в папку Архив"
        )
        self.assertIn("100", surcharge)
        fee = mask_allowance_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 гонораров в папку Архив"
        )
        self.assertIn("100", fee)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            allowance_blocks_bulk_document_mutation(
                "удали документ 214 за надбавку",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за надбавку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по надбавке"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за надбавку"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за надбавку"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Надбавка",
            "удали все документы в папке «Надбавка»",
            "удали все документы по делу Надбавка",
            "удали все документы по делу «Надбавка»",
            "удали все документы без надбавки в этой папке",
            "удали все документы за доплату в этой папке",
            "удали все документы за премию в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за заработную плату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за оплату труда в этой папке",
            "удали все документы за оплату в этой папке",
            "удали все документы за плату в этой папке",
            "удали все документы за выплату в этой папке",
            "удали все документы за вознаграждение в этой папке",
            "удали все документы за гонорар в этой папке",
            "удали все документы за пособие в этой папке",
            "удали все документы за пенсию в этой папке",
            "удали все документы за недоплату в этой папке",
            "удали все документы за надбавочный коэффициент в этой папке",
            "удали все документы за надбавить в этой папке",
            "удали все документы за страхование в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Надбавка",
            "собери все документы в папку Надбавка по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_allowance_scoped_document_request(text), text)
            self.assertFalse(allowance_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за надбавку",
            "по надбавке",
            "о надбавке",
            "об надбавке",
            "на надбавку",
            "с надбавки",
            "за «надбавку»",
            "за Надбавку",
            "за взыскание надбавки",
            "по взысканию надбавки",
            "за невыплату надбавки",
            "по выплате надбавки",
            "за задержку надбавки",
            "по размеру надбавки",
            "за начисление надбавки",
            "по задолженности по надбавке",
            "за платеж надбавки",
            "за индексацию надбавки",
            "за снижение надбавки",
            "за установление надбавки",
            "за лишение надбавки",
            "по проценту надбавки",
            "за период надбавки",
            "в ходе надбавки",
            "за счет надбавки",
            "за счёт надбавки",
            "при надбавке",
            "за полную надбавку",
            "за текущую надбавку",
            "за открытую надбавку",
            "за ночную надбавку",
            "за сверхурочную надбавку",
            "за районную надбавку",
            "за северную надбавку",
            "за процентную надбавку",
            "за стимулирующую надбавку",
            "за персональную надбавку",
            "за квалификационную надбавку",
            "за компенсационную надбавку",
            "за годовую надбавку",
            "до надбавки",
            "за первую надбавку",
            "за мою надбавку",
            "за моё надбавку",
            "за нашу надбавку",
            "по твоей надбавке",
            "за ваши надбавки",
            "во время надбавки",
            "во время начисления надбавки",
            "за не надбавку",
            "с надбавкой",
            "из надбавок",
            "о надбавках",
            "надбавками",
            "надбавкам",
            "надбавкою",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_allowance_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("allowance_blocks_bulk_document_mutation", source)
        self.assertIn("mask_allowance_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("allowance_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_allowance_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_allowance_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("allowance_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
