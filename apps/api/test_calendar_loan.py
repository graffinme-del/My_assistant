"""Bill / escrow / leasing / loan chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-го векселя» as document id 1. The calendar period parser does not recognize
these phrases.

«кредит», «кредитор», and «аккредитив» belong to other guards or stay unmatched.
A folder titled «Вексель» is not this guard. Bare «банкротство» is not this guard.
«замена» and «взамен» are not «заем».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_loan import (
    loan_blocks_bulk_document_mutation,
    looks_like_loan_scoped_document_request,
    mask_loan_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_loan_ordinals(raw)
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


class LoanScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за вексель в этой папке",
            "удали все документы по векселю в этой папке",
            "удали все документы об векселе в этой папке",
            "удали все документы за простой вексель в этой папке",
            "удали все документы за переводной вексель в этой папке",
            "удали все документы за соло-вексель в этой папке",
            "удали все документы за протест векселя в этой папке",
            "удали все документы за индоссамент векселя в этой папке",
            "удали все документы за аваль векселя в этой папке",
            "удали все документы за аваль в этой папке",
            "удали все документы за авалиста в этой папке",
            "удали все документы за тратту в этой папке",
            "удали все документы за индоссамент в этой папке",
            "удали все документы за индоссамента в этой папке",
            "удали все документы за индоссанта в этой папке",
            "удали все документы за учет векселя в этой папке",
            "удали все документы за дисконт векселя в этой папке",
            "удали все документы за векселедателя в этой папке",
            "удали все документы за векселедержателя в этой папке",
            "удали все документы за текущий вексель в этой папке",
            "удали все документы во время векселя в этой папке",
            "удали все документы за эскроу в этой папке",
            "удали все документы по эскроу в этой папке",
            "удали все документы за счет эскроу в этой папке",
            "удали все документы за эскроу-счет в этой папке",
            "удали все документы за счет-эскроу в этой папке",
            "удали все документы за договор эскроу в этой папке",
            "удали все документы за открытие эскроу в этой папке",
            "удали все документы за лизинг в этой папке",
            "удали все документы по лизингу в этой папке",
            "удали все документы за договор лизинга в этой папке",
            "удали все документы за финансовый лизинг в этой папке",
            "удали все документы за возвратный лизинг в этой папке",
            "удали все документы за операционный лизинг в этой папке",
            "удали все документы за лизинговый платеж в этой папке",
            "удали все документы за график лизинговых платежей в этой папке",
            "удали все документы за выкуп лизинга в этой папке",
            "удали все документы за лизингодателя в этой папке",
            "удали все документы за лизингополучателя в этой папке",
            "удали все документы за открытый лизинг в этой папке",
            "удали все документы за заем в этой папке",
            "удали все документы за заём в этой папке",
            "удали все документы за займ в этой папке",
            "удали все документы по займу в этой папке",
            "удали все документы за договор займа в этой папке",
            "удали все документы за возврат займа в этой папке",
            "удали все документы за выдачу займа в этой папке",
            "удали все документы за проценты по займу в этой папке",
            "удали все документы за график погашения займа в этой папке",
            "удали все документы за тело займа в этой папке",
            "удали все документы за новацию займа в этой папке",
            "удали все документы за замену займа в этой папке",
            "удали все документы за 12,5% займа в этой папке",
            "удали все документы за 12,5 % займа в этой папке",
            "удали все документы за заемные средства в этой папке",
            "удали все документы за заёмные средства в этой папке",
            "удали все документы за микрозайм в этой папке",
            "удали все документы за микрозаём в этой папке",
            "удали все документы за микрозаем в этой папке",
            "удали все документы за заемщика в этой папке",
            "удали все документы за займодавца в этой папке",
            "удали все документы за заимодавца в этой папке",
            "удали все документы взятые взаймы в этой папке",
            "удали все документы за тем займом в этой папке",
            "удали все документы о том векселе в этой папке",
            "удали все документы за того заемщика в этой папке",
            "удали все документы за ту тратту в этой папке",
            "удали все документы за текущий заем в этой папке",
            "удали все документы за текущий займ",
            "удали все документы за открытый лизинг",
            "удали каждый документ за вексель в этой папке",
            "удали все файлы за эскроу в этой папке",
            "удали все документы дела А40-12345/2025 за вексель",
            "удали все документы дела А40-12345/2025 за эскроу",
            "удали все документы дела А40-12345/2025 за лизинг",
            "удали все документы дела А40-12345/2025 за займ",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(loan_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за вексель в этой папке",
            "удали все документы за эскроу в этой папке",
            "удали все документы за лизинг в этой папке",
            "удали все документы за займ в этой папке",
            "удали все документы за заём в этой папке",
            "удали все документы за текущий займ",
            "удали все документы за открытый лизинг",
            "удали все документы за открытие эскроу в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го векселя",
            "удали документы 1-й вексель",
            "удали документы 1-му векселю",
            "удали документы 1-го эскроу",
            "удали документы 1-го лизинга",
            "удали документы 1-й займ",
            "удали документы 1-го займа",
            "удали документы 2-го векселя",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(loan_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 векселя"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 векселя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 лизинга"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 лизинга"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 займа"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 займа"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 эскроу"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 эскроу"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 займа"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 займа"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% займа"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% займа"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 векселя"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 векселя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го векселя"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го векселя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го микрозайма"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го микрозайма"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го векселедателя"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го векселедателя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го заемщика"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го заемщика"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 векселя"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го кредита"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го кредита"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го кредитора"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го аккредитива"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за вексель в папку Архив",
            "перенеси все документы дела А40-12345/2025 за эскроу в папку Архив",
            "перенеси все документы дела А40-12345/2025 за лизинг в папку Архив",
            "перенеси все документы дела А40-12345/2025 за займ в папку Архив",
            "перенеси документ 1-го векселя в дело Архив",
            "перемести документ 1-го займа в дело Архив",
            "перемести документ 1-го лизинга в дело Архив",
        )
        for text in phrases:
            self.assertTrue(loan_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за вексель в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_loan_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 займа в папку Архив"
        masked = mask_loan_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            loan_blocks_bulk_document_mutation(
                "удали документ 214 за вексель",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за вексель"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за эскроу"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за лизинг"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за займ"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за заём"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за вексель"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без векселя",
            "удали все документы в этой папке без эскроу",
            "удали все документы в этой папке без лизинга",
            "удали все документы в этой папке без займа",
            "удали все документы в папке «Вексель»",
            "удали все документы в папке Вексель",
            "удали все документы в папке Эскроу",
            "удали все документы в папке Лизинг",
            "удали все документы в папке Заем",
            "удали все документы в папке Заём",
            "удали все документы в папке Займ",
            "удали все документы из папки Вексель",
            "перенеси все документы в папку Вексель",
            "перенеси все документы в папку Займ",
            "перенеси все документы в папку Эскроу",
            "удали все документы по делу Вексель",
            "удали все документы по делу Эскроу",
            "удали все документы по делу Лизинг",
            "удали все документы по делу Займ",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за банкротство в этой папке",
            "удали все документы за платеж в этой папке",
            "удали все документы за кредит в этой папке",
            "удали все документы за собрание кредиторов в этой папке",
            "удали все документы за комитет кредиторов в этой папке",
            "удали все документы за аккредитив в этой папке",
            "удали все документы за аванс в этой папке",
            "удали все документы за депозит в этой папке",
            "удали все документы за факторинг в этой папке",
            "удали все документы за замену в этой папке",
            "удали все документы за новацию в этой папке",
            "удали все документы за инновацию в этой папке",
            "удали все документы за тело в этой папке",
            "удали все документы за телефон в этой папке",
            "удали все документы о том в этой папке",
            "удали все документы за тем в этой папке",
            "удали все документы в папке Аваль",
            "удали все документы в папке Тратта",
            "удали все документы в папке Индоссамент",
            "удали все документы взамен в этой папке",
            "удали все документы за незаемные средства в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы за учет в этой папке",
            "удали документы 1-го приказа",
            "удали документы 1-го кредита",
            "удали документы 1-го аккредитива",
            "перенеси все документы в папку Архив",
        ):
            self.assertFalse(looks_like_loan_scoped_document_request(text), text)
            self.assertFalse(loan_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы векселя в этой папке",
            "удали документы эскроу в этой папке",
            "удали документы лизинга в этой папке",
            "удали документы займа в этой папке",
            "удали все документы за первый вексель в этой папке",
            "удали все документы за первый займ в этой папке",
            "удали эти векселя в этой папке",
            "удали все документы за эту лизинговую сделку в этой папке",
        ):
            self.assertTrue(loan_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за вексель",
            "за векселя",
            "за векселю",
            "за векселем",
            "по векселю",
            "о векселе",
            "за вексели",
            "за векселей",
            "за вексельный долг",
            "за эскроу",
            "по эскроу",
            "за лизинг",
            "за лизинга",
            "за лизингом",
            "по лизингу",
            "о лизинге",
            "за лизинговый платеж",
            "за заем",
            "за заём",
            "за займа",
            "за займу",
            "за займом",
            "по займу",
            "о займе",
            "за займы",
            "за займов",
            "за займ",
            "за микрозайм",
            "за микрозайма",
            "за заемные средства",
            "за заемщика",
            "за заемщиком",
            "за займодавца",
            "за заимодавца",
            "за векселедателя",
            "за векселедержателя",
            "за лизингодателя",
            "за лизингополучателя",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_loan_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("loan_blocks_bulk_document_mutation", source)
        self.assertIn("mask_loan_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("loan_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_loan_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_loan_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("loan_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
