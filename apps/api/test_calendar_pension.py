"""Pension chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-я пенсия» as document id 1.
A folder titled «Пенсия» is not this guard. «пособие», «гонорар»,
«надбавка», «доплата», «премия», «вознаграждение», «зарплата», «алименты»,
and «оплата труда» are not this guard. «пенсионер» and «пенсионный» are not
this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_pension import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    looks_like_pension_scoped_document_request,
    mask_pension_ordinals,
    pension_blocks_bulk_document_mutation,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_pension_ordinals(raw)
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


class PensionFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за пенсию в этой папке",
            "удали все документы по пенсии в этой папке",
            "удали все документы о пенсии в этой папке",
            "удали все документы за взыскание пенсии в этой папке",
            "удали все документы за невыплату пенсии в этой папке",
            "удали все документы по выплате пенсии в этой папке",
            "удали все документы за задолженность по пенсии в этой папке",
            "удали все документы по размеру пенсии в этой папке",
            "удали все документы за задержку пенсии в этой папке",
            "удали все документы за начисление пенсии в этой папке",
            "удали все документы за индексацию пенсии в этой папке",
            "удали все документы за назначение пенсии в этой папке",
            "удали все документы за получение пенсии в этой папке",
            "удали все документы за трудовую пенсию в этой папке",
            "удали все документы за страховую пенсию в этой папке",
            "удали все документы за социальную пенсию в этой папке",
            "удали все документы за накопительную пенсию в этой папке",
            "удали все документы за государственную пенсию в этой папке",
            "удали все документы за досрочную пенсию в этой папке",
            "удали все документы за пенсию по старости в этой папке",
            "удали все документы за пенсию по инвалидности в этой папке",
            "удали все документы за пенсию по потере кормильца в этой папке",
            "удали все документы за пенсию по выслуге лет в этой папке",
            "удали все документы за перерасчёт пенсии в этой папке",
            "удали все документы за удержание пенсии в этой папке",
            "удали все документы за приостановление пенсии в этой папке",
            "удали все документы за восстановление пенсии в этой папке",
            "удали все документы за оформление пенсии в этой папке",
            "удали все документы за текущую пенсию",
            "удали все документы за открытую пенсию",
            "удали все документы за счёт пенсии в этой папке",
            "удали все файлы за пенсию в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(pension_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за пенсию"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(pension_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я пенсия", [1]),
            ("удали документы 1 пенсия", [1]),
            ("удали документы 2-й пенсии", [2]),
            ("удали документы 1-ю пенсию", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(pension_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пенсий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пенсий"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пособий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пособий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 гонораров"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 гонораров"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 надбавок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 надбавок"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% пенсии"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% пенсии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% пенсии"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% пенсии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я пенсия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я пенсия"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х пенсий"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х пенсий"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за пенсию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за пенсию"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й гонорар"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за пенсию в папку Архив",
            "перенеси все документы дела А40-12345/2025 по пенсии в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание пенсии в папку Архив",
            "перенеси все документы дела А40-12345/2025 за трудовую пенсию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за пенсию по старости в папку Архив",
            "перенеси документ 1-я пенсия в дело Архив",
            "перемести документ 100 пенсий в дело Архив",
        )
        for text in phrases:
            self.assertTrue(pension_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за пенсию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_pension_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 пенсий в папку Архив"
        masked = mask_pension_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        benefit = mask_pension_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 пособий в папку Архив"
        )
        self.assertIn("100", benefit)
        honorarium = mask_pension_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 гонораров в папку Архив"
        )
        self.assertIn("100", honorarium)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            pension_blocks_bulk_document_mutation(
                "удали документ 214 за пенсию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за пенсию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по пенсии"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за пенсию"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за пенсию"), [214])
        self.assertIn("пенсия", DELETE_REFUSED_REPLY)
        self.assertIn("пенсия", MOVE_REFUSED_REPLY)
        self.assertNotIn("пособи", DELETE_REFUSED_REPLY)
        self.assertNotIn("гонорар", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Пенсия",
            "удали все документы в папке «Пенсия»",
            "удали все документы в папке «Пенсия по старости»",
            "удали все документы в папке «Трудовая пенсия»",
            "удали все документы по делу Пенсия",
            "удали все документы по делу «Пенсия»",
            "удали все документы по делу «Трудовая пенсия»",
            "удали все документы без пенсии в этой папке",
            "удали все документы за пособие в этой папке",
            "удали все документы за пенсионное пособие в этой папке",
            "удали все документы за гонорар в этой папке",
            "удали все документы за надбавку в этой папке",
            "удали все документы за доплату в этой папке",
            "удали все документы за премию в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за оплату труда в этой папке",
            "удали все документы за вознаграждение в этой папке",
            "удали все документы за пенсионера в этой папке",
            "удали все документы за пенсионерку в этой папке",
            "удали все документы за пенсионный фонд в этой папке",
            "удали все документы за пенсионное обеспечение в этой папке",
            "удали все документы за страхование в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Пенсия",
            "собери все документы в папку Пенсия по старости",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_pension_scoped_document_request(text), text)
            self.assertFalse(pension_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за пенсию",
            "по пенсии",
            "о пенсии",
            "об пенсии",
            "на пенсию",
            "с пенсии",
            "за «пенсию»",
            "за Пенсию",
            "за взыскание пенсии",
            "по взысканию пенсии",
            "за невыплату пенсии",
            "по выплате пенсии",
            "за задержку пенсии",
            "по размеру пенсии",
            "за начисление пенсии",
            "по задолженности по пенсии",
            "за платеж пенсии",
            "за индексацию пенсии",
            "за назначение пенсии",
            "за получение пенсии",
            "за лишение пенсии",
            "по проценту пенсии",
            "за период пенсии",
            "в ходе пенсии",
            "за счет пенсии",
            "за счёт пенсии",
            "при пенсии",
            "за полную пенсию",
            "за текущую пенсию",
            "за открытую пенсию",
            "за трудовую пенсию",
            "за страховую пенсию",
            "за социальную пенсию",
            "за накопительную пенсию",
            "за государственную пенсию",
            "за досрочную пенсию",
            "за пенсию по старости",
            "за пенсию по инвалидности",
            "за пенсию по случаю потери кормильца",
            "за пенсию по выслуге лет",
            "за перерасчет пенсии",
            "за перерасчёт пенсии",
            "за удержание пенсии",
            "за приостановку пенсии",
            "за приостановление пенсии",
            "за восстановление пенсии",
            "за оформление пенсии",
            "за подтверждение пенсии",
            "за расчет пенсии",
            "за расчёт пенсии",
            "за доплату пенсии",
            "за недоплату пенсии",
            "до пенсии",
            "за первую пенсию",
            "за мою пенсию",
            "за моё пенсию",
            "за нашу сумму пенсии",
            "по твоей пенсии",
            "за ваши пенсии",
            "во время пенсии",
            "во время начисления пенсии",
            "за не пенсию",
            "с пенсией",
            "из пенсий",
            "о пенсиях",
            "пенсиями",
            "пенсиям",
            "пенсий",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_pension_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("pension_blocks_bulk_document_mutation", source)
        self.assertIn("mask_pension_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("pension_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_pension_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_pension_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("pension_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
