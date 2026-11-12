"""Remuneration chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-е вознаграждение» as document id 1.
A folder titled «Вознаграждение» is not this guard. «зарплата», «алименты»,
and «оплата труда» are not this guard. «премия», «доплата», «надбавка»,
«гонорар», «пособие», and «пенсия» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_remuneration import (
    remuneration_blocks_bulk_document_mutation,
    looks_like_remuneration_scoped_document_request,
    mask_remuneration_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_remuneration_ordinals(raw)
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


class RemunerationFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за вознаграждение в этой папке",
            "удали все документы по вознаграждению в этой папке",
            "удали все документы о вознаграждении в этой папке",
            "удали все документы за взыскание вознаграждения в этой папке",
            "удали все документы за неуплату вознаграждения в этой папке",
            "удали все документы по выплате вознаграждения в этой папке",
            "удали все документы за задолженность по вознаграждению в этой папке",
            "удали все документы по размеру вознаграждения в этой папке",
            "удали все документы за задержку вознаграждения в этой папке",
            "удали все документы за начисление вознаграждения в этой папке",
            "удали все документы за индексацию вознаграждения в этой папке",
            "удали все документы за фонд вознаграждения в этой папке",
            "удали все документы за систему вознаграждения в этой папке",
            "удали все документы за компенсацию вознаграждения в этой папке",
            "удали все документы за утверждение вознаграждения в этой папке",
            "удали все документы за установление вознаграждения в этой папке",
            "удали все документы за снижение вознаграждения в этой папке",
            "удали все документы за процент вознаграждения в этой папке",
            "удали все документы за текущее вознаграждение",
            "удали все документы за открытое вознаграждение",
            "удали все документы за счёт вознаграждения в этой папке",
            "удали все файлы за вознаграждение в этой папке",
            "удали все документы за вознаграждение арбитражного управляющего в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(remuneration_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за вознаграждение"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(remuneration_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е вознаграждение", [1]),
            ("удали документы 1 вознаграждение", [1]),
            ("удали документы 2-е вознаграждение", [2]),
            ("удали документы 1-го вознаграждения", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(remuneration_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 вознаграждений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 вознаграждений"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 зарплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 зарплат"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 алиментов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 алиментов"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оплат труда"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оплат труда"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% вознаграждения"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% вознаграждения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% вознаграждения"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% вознаграждения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е вознаграждение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е вознаграждение"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х вознаграждений"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х вознаграждений"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за вознаграждение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за вознаграждение"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я зарплата"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я оплата труда"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за вознаграждение в папку Архив",
            "перенеси все документы дела А40-12345/2025 по вознаграждению в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание вознаграждения в папку Архив",
            "перенеси все документы дела А40-12345/2025 за выплату вознаграждения в папку Архив",
            "перенеси документ 1-е вознаграждение в дело Архив",
            "перемести документ 100 вознаграждений в дело Архив",
        )
        for text in phrases:
            self.assertTrue(remuneration_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за вознаграждение в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_remuneration_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 вознаграждений в папку Архив"
        masked = mask_remuneration_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_remuneration_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 зарплат в папку Архив"
        )
        self.assertIn("100", other)
        alimony = mask_remuneration_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 алиментов в папку Архив"
        )
        self.assertIn("100", alimony)
        labor = mask_remuneration_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 оплат труда в папку Архив"
        )
        self.assertIn("100", labor)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            remuneration_blocks_bulk_document_mutation(
                "удали документ 214 за вознаграждение",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за вознаграждение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по вознаграждению"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за вознаграждение"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за вознаграждение"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Вознаграждение",
            "удали все документы в папке «Вознаграждение»",
            "удали все документы по делу Вознаграждение",
            "удали все документы по делу «Вознаграждение»",
            "удали все документы без вознаграждения в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за заработную плату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за оплату труда в этой папке",
            "удали все документы за оплату в этой папке",
            "удали все документы за премию в этой папке",
            "удали все документы за доплату в этой папке",
            "удали все документы за надбавку в этой папке",
            "удали все документы за гонорар в этой папке",
            "удали все документы за пособие в этой папке",
            "удали все документы за пенсию в этой папке",
            "удали все документы за вознаградить в этой папке",
            "удали все документы за вознагражденный в этой папке",
            "удали все документы за вознаграждать в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Вознаграждение",
            "собери все документы в папку Вознаграждение по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_remuneration_scoped_document_request(text), text)
            self.assertFalse(remuneration_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за вознаграждение",
            "по вознаграждению",
            "о вознаграждении",
            "об вознаграждении",
            "на вознаграждение",
            "с вознаграждения",
            "за «вознаграждение»",
            "за взыскание вознаграждения",
            "по взысканию вознаграждения",
            "за неуплату вознаграждения",
            "по выплате вознаграждения",
            "за задержку вознаграждения",
            "по размеру вознаграждения",
            "за начисление вознаграждения",
            "по задолженности по вознаграждению",
            "за платеж вознаграждения",
            "за индексацию вознаграждения",
            "по фонду вознаграждения",
            "за систему вознаграждения",
            "за компенсацию вознаграждения",
            "за утверждение вознаграждения",
            "за установление вознаграждения",
            "за снижение вознаграждения",
            "по проценту вознаграждения",
            "за период вознаграждения",
            "в ходе вознаграждения",
            "за счет вознаграждения",
            "за счёт вознаграждения",
            "при вознаграждении",
            "за полное вознаграждение",
            "за текущее вознаграждение",
            "за открытое вознаграждение",
            "за фиксированное вознаграждение",
            "за процентное вознаграждение",
            "до вознаграждения",
            "за первое вознаграждение",
            "за мое вознаграждение",
            "за моё вознаграждение",
            "за наше вознаграждение",
            "по твоему вознаграждению",
            "за ваши вознаграждения",
            "во время вознаграждения",
            "во время начисления вознаграждения",
            "за не вознаграждение",
            "с вознаграждением",
            "из вознаграждений",
            "о вознаграждениях",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_remuneration_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("remuneration_blocks_bulk_document_mutation", source)
        self.assertIn("mask_remuneration_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("remuneration_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_remuneration_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_remuneration_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("remuneration_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
