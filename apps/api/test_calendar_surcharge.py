"""Surcharge chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-я доплата» as document id 1.
A folder titled «Доплата» is not this guard. «премия», «вознаграждение»,
«зарплата», «алименты», and «оплата труда» are not this guard. «надбавка»,
«гонорар», «пособие», «пенсия», and «недоплата» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_surcharge import (
    looks_like_surcharge_scoped_document_request,
    mask_surcharge_ordinals,
    surcharge_blocks_bulk_document_mutation,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_surcharge_ordinals(raw)
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


class SurchargeFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за доплату в этой папке",
            "удали все документы по доплате в этой папке",
            "удали все документы о доплате в этой папке",
            "удали все документы за взыскание доплаты в этой папке",
            "удали все документы за невыплату доплаты в этой папке",
            "удали все документы по выплате доплаты в этой папке",
            "удали все документы за задолженность по доплате в этой папке",
            "удали все документы по размеру доплаты в этой папке",
            "удали все документы за задержку доплаты в этой папке",
            "удали все документы за начисление доплаты в этой папке",
            "удали все документы за индексацию доплаты в этой папке",
            "удали все документы за снижение доплаты в этой папке",
            "удали все документы за установление доплаты в этой папке",
            "удали все документы за ночную доплату в этой папке",
            "удали все документы за сверхурочную доплату в этой папке",
            "удали все документы за районную доплату в этой папке",
            "удали все документы за праздничную доплату в этой папке",
            "удали все документы за компенсационную доплату в этой папке",
            "удали все документы за годовую доплату в этой папке",
            "удали все документы за текущую доплату",
            "удали все документы за открытую доплату",
            "удали все документы за счёт доплаты в этой папке",
            "удали все файлы за доплату в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(surcharge_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за доплату"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(surcharge_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я доплата", [1]),
            ("удали документы 1 доплата", [1]),
            ("удали документы 2-ю доплату", [2]),
            ("удали документы 1-й доплаты", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(surcharge_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 доплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 доплат"), [])
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
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 надбавок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 надбавок"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% доплаты"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% доплаты"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% доплаты"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% доплаты"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я доплата"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я доплата"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х доплат"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х доплат"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за доплату"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за доплату"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я премия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я надбавка"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й гонорар"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я пенсия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я недоплата"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за доплату в папку Архив",
            "перенеси все документы дела А40-12345/2025 по доплате в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание доплаты в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ночную доплату в папку Архив",
            "перенеси документ 1-я доплата в дело Архив",
            "перемести документ 100 доплат в дело Архив",
        )
        for text in phrases:
            self.assertTrue(surcharge_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за доплату в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_surcharge_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 доплат в папку Архив"
        masked = mask_surcharge_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        bonus = mask_surcharge_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 премий в папку Архив"
        )
        self.assertIn("100", bonus)
        allowance = mask_surcharge_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 надбавок в папку Архив"
        )
        self.assertIn("100", allowance)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            surcharge_blocks_bulk_document_mutation(
                "удали документ 214 за доплату",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за доплату"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по доплате"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за доплату"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за доплату"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Доплата",
            "удали все документы в папке «Доплата»",
            "удали все документы по делу Доплата",
            "удали все документы по делу «Доплата»",
            "удали все документы без доплаты в этой папке",
            "удали все документы за премию в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за заработную плату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за оплату труда в этой папке",
            "удали все документы за оплату в этой папке",
            "удали все документы за плату в этой папке",
            "удали все документы за выплату в этой папке",
            "удали все документы за вознаграждение в этой папке",
            "удали все документы за надбавку в этой папке",
            "удали все документы за гонорар в этой папке",
            "удали все документы за пособие в этой папке",
            "удали все документы за пенсию в этой папке",
            "удали все документы за недоплату в этой папке",
            "удали все документы за доплатить в этой папке",
            "удали все документы за доплачивать в этой папке",
            "удали все документы за доплаченный в этой папке",
            "удали все документы за доплатный в этой папке",
            "удали все документы за страхование в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Доплата",
            "собери все документы в папку Доплата по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_surcharge_scoped_document_request(text), text)
            self.assertFalse(surcharge_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за доплату",
            "по доплате",
            "о доплате",
            "об доплате",
            "на доплату",
            "с доплаты",
            "за «доплату»",
            "за Доплату",
            "за взыскание доплаты",
            "по взысканию доплаты",
            "за невыплату доплаты",
            "по выплате доплаты",
            "за задержку доплаты",
            "по размеру доплаты",
            "за начисление доплаты",
            "по задолженности по доплате",
            "за платеж доплаты",
            "за индексацию доплаты",
            "за снижение доплаты",
            "за установление доплаты",
            "по проценту доплаты",
            "за период доплаты",
            "в ходе доплаты",
            "за счет доплаты",
            "за счёт доплаты",
            "при доплате",
            "за полную доплату",
            "за текущую доплату",
            "за открытую доплату",
            "за ночную доплату",
            "за сверхурочную доплату",
            "за районную доплату",
            "за праздничную доплату",
            "за компенсационную доплату",
            "за годовую доплату",
            "до доплаты",
            "за первую доплату",
            "за мою доплату",
            "за моё доплату",
            "за нашу доплату",
            "по твоей доплате",
            "за ваши доплаты",
            "во время доплаты",
            "во время начисления доплаты",
            "за не доплату",
            "с доплатой",
            "из доплат",
            "о доплатах",
            "доплатами",
            "доплатам",
            "доплатою",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_surcharge_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("surcharge_blocks_bulk_document_mutation", source)
        self.assertIn("mask_surcharge_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("surcharge_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_surcharge_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_surcharge_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("surcharge_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
