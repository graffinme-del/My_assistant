"""Labor-pay chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-я оплата труда» as document id 1.
A folder titled «Оплата труда» is not this guard. «зарплата» and «алименты»
are not this guard. Bare «оплата» and bare «труд» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_labor_pay import (
    labor_pay_blocks_bulk_document_mutation,
    looks_like_labor_pay_scoped_document_request,
    mask_labor_pay_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_labor_pay_ordinals(raw)
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


class LaborPayFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за оплату труда в этой папке",
            "удали все документы по оплате труда в этой папке",
            "удали все документы об оплате труда в этой папке",
            "удали все документы за взыскание оплаты труда в этой папке",
            "удали все документы за неуплату оплаты труда в этой папке",
            "удали все документы по выплате оплаты труда в этой папке",
            "удали все документы за задолженность по оплате труда в этой папке",
            "удали все документы по размеру оплаты труда в этой папке",
            "удали все документы за задержку оплаты труда в этой папке",
            "удали все документы за начисление оплаты труда в этой папке",
            "удали все документы за индексацию оплаты труда в этой папке",
            "удали все документы за фонд оплаты труда в этой папке",
            "удали все документы за систему оплаты труда в этой папке",
            "удали все документы за компенсацию оплаты труда в этой папке",
            "удали все документы за текущую оплату труда",
            "удали все документы за открытую оплату труда",
            "удали все документы за счёт оплаты труда в этой папке",
            "удали все файлы за оплату труда в этой папке",
            "удали все документы за оплату труда работников в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(labor_pay_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за оплату труда"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(labor_pay_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я оплата труда", [1]),
            ("удали документы 1 оплата труда", [1]),
            ("удали документы 2-й оплаты труда", [2]),
            ("удали документы 1-ю оплату труда", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(labor_pay_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оплат труда"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оплат труда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 зарплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 зарплат"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 алиментов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 алиментов"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% оплаты труда"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% оплаты труда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% оплаты труда"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% оплаты труда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я оплата труда"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я оплата труда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х оплат труда"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х оплат труда"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за оплату труда"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за оплату труда"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я зарплата"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за оплату труда в папку Архив",
            "перенеси все документы дела А40-12345/2025 по оплате труда в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание оплаты труда в папку Архив",
            "перенеси все документы дела А40-12345/2025 за задержку оплаты труда в папку Архив",
            "перенеси документ 1-я оплата труда в дело Архив",
            "перемести документ 100 оплат труда в дело Архив",
        )
        for text in phrases:
            self.assertTrue(labor_pay_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за оплату труда в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_labor_pay_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 оплат труда в папку Архив"
        masked = mask_labor_pay_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_labor_pay_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 зарплат в папку Архив"
        )
        self.assertIn("100", other)
        alimony = mask_labor_pay_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 алиментов в папку Архив"
        )
        self.assertIn("100", alimony)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            labor_pay_blocks_bulk_document_mutation(
                "удали документ 214 за оплату труда",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за оплату труда"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по оплате труда"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за оплату труда"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за оплату труда"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Оплата труда",
            "удали все документы в папке «Оплата труда»",
            "удали все документы по делу Оплата труда",
            "удали все документы по делу «Оплата труда»",
            "удали все документы без оплаты труда в этой папке",
            "удали все документы за оплату в этой папке",
            "удали все документы за оплату услуг в этой папке",
            "удали все документы за труд в этой папке",
            "удали все документы за труднее в этой папке",
            "удали все документы за трудовой договор в этой папке",
            "удали все документы за оплату трудовой деятельности в этой папке",
            "удали все документы за оплатить труд в этой папке",
            "удали все документы за оплаченный труд в этой папке",
            "удали все документы за предоплату в этой папке",
            "удали все документы за доплату в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за заработную плату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за содержание в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Оплата труда",
            "собери все документы в папку Оплата труда по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_labor_pay_scoped_document_request(text), text)
            self.assertFalse(labor_pay_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за оплату труда",
            "по оплате труда",
            "об оплате труда",
            "о оплате труда",
            "на оплату труда",
            "с оплаты труда",
            "за «оплату труда»",
            "за взыскание оплаты труда",
            "по взысканию оплаты труда",
            "за неуплату оплаты труда",
            "по выплате оплаты труда",
            "за задержку оплаты труда",
            "по размеру оплаты труда",
            "за начисление оплаты труда",
            "по задолженности по оплате труда",
            "за платеж оплаты труда",
            "за индексацию оплаты труда",
            "по фонду оплаты труда",
            "за систему оплаты труда",
            "за компенсацию оплаты труда",
            "за период оплаты труда",
            "в ходе оплаты труда",
            "за счет оплаты труда",
            "за счёт оплаты труда",
            "при оплате труда",
            "за полную оплату труда",
            "за текущую оплату труда",
            "за открытую оплату труда",
            "за минимальную оплату труда",
            "до оплаты труда",
            "за первую оплату труда",
            "за мою оплату труда",
            "за нашу оплату труда",
            "по твоей оплате труда",
            "за ваши оплаты труда",
            "во время оплаты труда",
            "во время индексации оплаты труда",
            "за неоплату труда",
            "за не оплату труда",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_labor_pay_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("labor_pay_blocks_bulk_document_mutation", source)
        self.assertIn("mask_labor_pay_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("labor_pay_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_labor_pay_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_labor_pay_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("labor_pay_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
