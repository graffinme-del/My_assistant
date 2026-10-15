"""Deposit / security-payment / novation / subrogation chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-го задатка» as document id 1. The calendar period parser does not recognize
these phrases.

«обеспечительные меры», «цессия», and «исполнительский сбор» belong to other
guards. A folder titled «Задаток» is not this guard. Bare «банкротство» is not
this guard. «инновация» is not «новация».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_deposit import (
    deposit_blocks_bulk_document_mutation,
    looks_like_deposit_scoped_document_request,
    mask_deposit_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_deposit_ordinals(raw)
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


class DepositScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за задаток в этой папке",
            "удали все документы по задатку в этой папке",
            "удали все документы о задатке в этой папке",
            "удали все документы за возврат задатка в этой папке",
            "удали все документы за невозврат задатка в этой папке",
            "удали все документы за внесение задатка в этой папке",
            "удали все документы за невнесение задатка в этой папке",
            "удали все документы за уплату задатка в этой папке",
            "удали все документы за сумму задатка в этой папке",
            "удали все документы за двойной задаток в этой папке",
            "удали все документы за задаточный платеж в этой папке",
            "удали все документы за текущий задаток в этой папке",
            "удали все документы за открытый задаток в этой папке",
            "удали все документы во время задатка в этой папке",
            "удали все документы за обеспечительный платеж в этой папке",
            "удали все документы за обеспечительный платёж в этой папке",
            "удали все документы по обеспечительному платежу в этой папке",
            "удали все документы за уплату обеспечительного платежа в этой папке",
            "удали все документы за возврат обеспечительного платежа в этой папке",
            "удали все документы за внесение обеспечительного платежа в этой папке",
            "удали все документы за обеспечительный страховой платеж в этой папке",
            "удали все документы за обеспечительный взнос в этой папке",
            "удали все документы во время обеспечительного платежа в этой папке",
            "удали все документы за новацию в этой папке",
            "удали все документы о новации в этой папке",
            "удали все документы по новации в этой папке",
            "удали все документы за соглашение о новации в этой папке",
            "удали все документы за договор новации в этой папке",
            "удали все документы за новационное соглашение в этой папке",
            "удали все документы за суброгацию в этой папке",
            "удали все документы о суброгации в этой папке",
            "удали все документы по суброгации в этой папке",
            "удали все документы за право суброгации в этой папке",
            "удали все документы за суброгационное требование в этой папке",
            "удали все документы за суброганта в этой папке",
            "удали каждый документ за задаток в этой папке",
            "удали все файлы за новацию в этой папке",
            "удали все документы дела А40-12345/2025 за задаток",
            "удали все документы дела А40-12345/2025 за обеспечительный платеж",
            "удали все документы дела А40-12345/2025 за новацию",
            "удали все документы дела А40-12345/2025 за суброгацию",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(deposit_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за задаток в этой папке",
            "удали все документы за обеспечительный платеж в этой папке",
            "удали все документы за новацию в этой папке",
            "удали все документы за суброгацию в этой папке",
            "удали все документы за текущий задаток в этой папке",
            "удали все документы за открытый задаток в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го задатка",
            "удали документы 1-й задаток",
            "удали документы 1-му задатку",
            "удали документы 1-го обеспечительного платежа",
            "удали документы 1-й новации",
            "удали документы 1-й суброгации",
            "удали документы 2-го задатка",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(deposit_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 задатка"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 задатка"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 обеспечительного платежа"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 обеспечительного платежа"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 новации"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 новации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 суброгации"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 суброгации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 задатка"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 задатка"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 новации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 новации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го задатка"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го задатка"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 задатка"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за задаток в папку Архив",
            "перенеси все документы дела А40-12345/2025 за обеспечительный платеж в папку Архив",
            "перенеси все документы дела А40-12345/2025 за новацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за суброгацию в папку Архив",
            "перенеси документ 1-го задатка в дело Архив",
            "перемести документ 1-го обеспечительного платежа в дело Архив",
            "перемести документ 1-й новации в дело Архив",
        )
        for text in phrases:
            self.assertTrue(deposit_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за задаток в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_deposit_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 задатка в папку Архив"
        masked = mask_deposit_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            deposit_blocks_bulk_document_mutation(
                "удали документ 214 за задаток",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за задаток"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за обеспечительный платеж"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за новацию"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за суброгацию"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за задаток"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без задатка",
            "удали все документы в этой папке без обеспечительного платежа",
            "удали все документы в этой папке без новации",
            "удали все документы в этой папке без суброгации",
            "удали все документы в папке «Задаток»",
            "удали все документы в папке Задаток",
            "удали все документы в папке Обеспечительный платеж",
            "удали все документы в папке Новация",
            "удали все документы в папке Суброгация",
            "удали все документы из папки Задаток",
            "перенеси все документы в папку Задаток",
            "перенеси все документы в папку Новация",
            "удали все документы по делу Задаток",
            "удали все документы по делу Новация",
            "удали все документы по делу Суброгация",
            "удали все документы по делу Обеспечительный платеж",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за банкротство в этой папке",
            "удали все документы за платеж в этой папке",
            "удали все документы за платежное поручение в этой папке",
            "удали все документы за обеспечительные меры в этой папке",
            "удали все документы за инновацию в этой папке",
            "удали все документы за реновацию в этой папке",
            "удали все документы за цессию в этой папке",
            "удали все документы за судебного пристава в этой папке",
            "удали все документы за исполнительский сбор в этой папке",
            "удали все документы за отступное в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за требование в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за задачу в этой папке",
            "удали все документы за задачник в этой папке",
            "удали документы 1-го приказа",
            "удали документы 1-го листа",
            "удали документы 1-й инновации",
            "перенеси все документы в папку Архив",
        ):
            self.assertFalse(looks_like_deposit_scoped_document_request(text), text)
            self.assertFalse(deposit_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы задатка в этой папке",
            "удали документы обеспечительного платежа в этой папке",
            "удали документы новации в этой папке",
            "удали документы суброгации в этой папке",
            "удали документы суброганта в этой папке",
            "удали все документы за первый задаток в этой папке",
            "удали эти задатки в этой папке",
            "удали все документы за эту новацию в этой папке",
        ):
            self.assertTrue(deposit_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за задаток",
            "за задатка",
            "за задатку",
            "за задатком",
            "по задатку",
            "о задатке",
            "за задатки",
            "за задатков",
            "за задаточный платеж",
            "за обеспечительный платеж",
            "за обеспечительного платежа",
            "за обеспечительному платежу",
            "за обеспечительным платежом",
            "по обеспечительному платежу",
            "за обеспечительные платежи",
            "за обеспечительных платежей",
            "за новацию",
            "за новации",
            "за новацией",
            "о новации",
            "по новации",
            "за новационное соглашение",
            "за суброгацию",
            "за суброгации",
            "за суброгацией",
            "о суброгации",
            "по суброгации",
            "за суброганта",
            "за суброгационное требование",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_deposit_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("deposit_blocks_bulk_document_mutation", source)
        self.assertIn("mask_deposit_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("deposit_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_deposit_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_deposit_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("deposit_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
