"""Benefit chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-е пособие» as document id 1.
A folder titled «Пособие» is not this guard. «пенсия», «гонорар»,
«надбавка», «доплата», «премия», «вознаграждение», «зарплата», «алименты»,
and «оплата труда» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_benefit import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    benefit_blocks_bulk_document_mutation,
    looks_like_benefit_scoped_document_request,
    mask_benefit_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_benefit_ordinals(raw)
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


class BenefitFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за пособие в этой папке",
            "удали все документы по пособию в этой папке",
            "удали все документы о пособии в этой папке",
            "удали все документы за взыскание пособия в этой папке",
            "удали все документы за невыплату пособия в этой папке",
            "удали все документы по выплате пособия в этой папке",
            "удали все документы за задолженность по пособию в этой папке",
            "удали все документы по размеру пособия в этой папке",
            "удали все документы за задержку пособия в этой папке",
            "удали все документы за начисление пособия в этой папке",
            "удали все документы за индексацию пособия в этой папке",
            "удали все документы за назначение пособия в этой папке",
            "удали все документы за получение пособия в этой папке",
            "удали все документы за детское пособие в этой папке",
            "удали все документы за социальное пособие в этой папке",
            "удали все документы за выходное пособие в этой папке",
            "удали все документы за ежемесячное пособие в этой папке",
            "удали все документы за единовременное пособие в этой папке",
            "удали все документы за государственное пособие в этой папке",
            "удали все документы за страховое пособие в этой папке",
            "удали все документы за пенсионное пособие в этой папке",
            "удали все документы за пособие по безработице в этой папке",
            "удали все документы за пособие по беременности в этой папке",
            "удали все документы за пособие по уходу за ребенком в этой папке",
            "удали все документы за пособие по временной нетрудоспособности в этой папке",
            "удали все документы за пособие на погребение в этой папке",
            "удали все документы за текущее пособие",
            "удали все документы за открытое пособие",
            "удали все документы за счёт пособия в этой папке",
            "удали все файлы за пособие в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(benefit_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за пособие"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(benefit_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е пособие", [1]),
            ("удали документы 1 пособие", [1]),
            ("удали документы 2-го пособия", [2]),
            ("удали документы 1-му пособию", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(benefit_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пособий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пособий"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пенсий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пенсий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 гонораров"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 гонораров"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 надбавок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 надбавок"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 зарплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 зарплат"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 алиментов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 алиментов"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оплат труда"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оплат труда"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 вознаграждений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 вознаграждений"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% пособия"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% пособия"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% пособия"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% пособия"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е пособие"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х пособий"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х пособий"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за пособие"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я пенсия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й гонорар"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за пособие в папку Архив",
            "перенеси все документы дела А40-12345/2025 по пособию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание пособия в папку Архив",
            "перенеси все документы дела А40-12345/2025 за выходное пособие в папку Архив",
            "перенеси все документы дела А40-12345/2025 за детское пособие в папку Архив",
            "перенеси документ 1-е пособие в дело Архив",
            "перемести документ 100 пособий в дело Архив",
        )
        for text in phrases:
            self.assertTrue(benefit_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за пособие в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_benefit_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 пособий в папку Архив"
        masked = mask_benefit_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        pension = mask_benefit_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 пенсий в папку Архив"
        )
        self.assertIn("100", pension)
        honorarium = mask_benefit_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 гонораров в папку Архив"
        )
        self.assertIn("100", honorarium)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            benefit_blocks_bulk_document_mutation(
                "удали документ 214 за пособие",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по пособию"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за пособие"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за пособие"), [214])
        self.assertIn("пособие", DELETE_REFUSED_REPLY)
        self.assertIn("пособие", MOVE_REFUSED_REPLY)
        self.assertNotIn("пенси", DELETE_REFUSED_REPLY)
        self.assertNotIn("гонорар", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Пособие",
            "удали все документы в папке «Пособие»",
            "удали все документы в папке «Пособие по безработице»",
            "удали все документы по делу Пособие",
            "удали все документы по делу «Пособие»",
            "удали все документы по делу «Детское пособие»",
            "удали все документы без пособия в этой папке",
            "удали все документы за пенсию в этой папке",
            "удали все документы за гонорар в этой папке",
            "удали все документы за надбавку в этой папке",
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
            "удали все документы за пособника в этой папке",
            "удали все документы за пособничество в этой папке",
            "удали все документы за пособийный договор в этой папке",
            "удали все документы за страхование в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Пособие",
            "собери все документы в папку Пособие по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_benefit_scoped_document_request(text), text)
            self.assertFalse(benefit_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за пособие",
            "по пособию",
            "о пособии",
            "об пособии",
            "на пособие",
            "с пособия",
            "за «пособие»",
            "за Пособие",
            "за взыскание пособия",
            "по взысканию пособия",
            "за невыплату пособия",
            "по выплате пособия",
            "за задержку пособия",
            "по размеру пособия",
            "за начисление пособия",
            "по задолженности по пособию",
            "за платеж пособия",
            "за индексацию пособия",
            "за назначение пособия",
            "за получение пособия",
            "за лишение пособия",
            "по проценту пособия",
            "за период пособия",
            "в ходе пособия",
            "за счет пособия",
            "за счёт пособия",
            "при пособии",
            "за полное пособие",
            "за текущее пособие",
            "за открытое пособие",
            "за детское пособие",
            "за социальное пособие",
            "за выходное пособие",
            "за ежемесячное пособие",
            "за единовременное пособие",
            "за государственное пособие",
            "за страховое пособие",
            "за пенсионное пособие",
            "за пособие по безработице",
            "за пособие по беременности",
            "за пособие по уходу",
            "за пособие по временной нетрудоспособности",
            "за пособие на погребение",
            "до пособия",
            "за первое пособие",
            "за моё пособие",
            "за нашу сумму пособия",
            "по твоему пособию",
            "за ваши пособия",
            "во время пособия",
            "во время начисления пособия",
            "за не пособие",
            "с пособием",
            "из пособий",
            "о пособиях",
            "пособиями",
            "пособиям",
            "пособий",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_benefit_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("benefit_blocks_bulk_document_mutation", source)
        self.assertIn("mask_benefit_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("benefit_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_benefit_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_benefit_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("benefit_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
