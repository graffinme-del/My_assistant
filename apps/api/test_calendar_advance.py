"""Advance / cash-deposit / letter-of-credit / factoring chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-го аванса» as document id 1. The calendar period parser does not recognize
these phrases.

«задаток», «обеспечительный платеж», and «новация» belong to another guard.
A folder titled «Аванс» is not this guard. Bare «банкротство» is not this guard.
«авансцена», «депозитарий», and bare «фактор» are not these nouns.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_advance import (
    advance_blocks_bulk_document_mutation,
    looks_like_advance_scoped_document_request,
    mask_advance_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_advance_ordinals(raw)
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


class AdvanceScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за аванс в этой папке",
            "удали все документы по авансу в этой папке",
            "удали все документы об авансе в этой папке",
            "удали все документы за возврат аванса в этой папке",
            "удали все документы за невозврат аванса в этой папке",
            "удали все документы за выдачу аванса в этой папке",
            "удали все документы за получение аванса в этой папке",
            "удали все документы за уплату аванса в этой папке",
            "удали все документы за сумму аванса в этой папке",
            "удали все документы за часть аванса в этой папке",
            "удали все документы за транш аванса в этой папке",
            "удали все документы за авансовый платеж в этой папке",
            "удали все документы за авансовый платёж в этой папке",
            "удали все документы за авансовый отчет в этой папке",
            "удали все документы за авансовый отчёт в этой папке",
            "удали все документы за текущий аванс в этой папке",
            "удали все документы за открытый аванс в этой папке",
            "удали все документы во время аванса в этой папке",
            "удали все документы за авансирование в этой папке",
            "удали все документы за депозит в этой папке",
            "удали все документы по депозиту в этой папке",
            "удали все документы за возврат депозита в этой папке",
            "удали все документы за внесение депозита в этой папке",
            "удали все документы за перевод депозита в этой папке",
            "удали все документы за зачисление депозита в этой папке",
            "удали все документы за депозитный счет в этой папке",
            "удали все документы за депозитный счёт в этой папке",
            "удали все документы во время депозита в этой папке",
            "удали все документы за аккредитив в этой папке",
            "удали все документы об аккредитиве в этой папке",
            "удали все документы за открытие аккредитива в этой папке",
            "удали все документы за покрытие аккредитива в этой папке",
            "удали все документы за непокрытый аккредитив в этой папке",
            "удали все документы за документарный аккредитив в этой папке",
            "удали все документы за отзывный аккредитив в этой папке",
            "удали все документы за безотзывный аккредитив в этой папке",
            "удали все документы за факторинг в этой папке",
            "удали все документы по факторингу в этой папке",
            "удали все документы за договор факторинга в этой папке",
            "удали все документы за соглашение о факторинге в этой папке",
            "удали все документы за факторинговое обслуживание в этой папке",
            "удали каждый документ за аванс в этой папке",
            "удали все файлы за депозит в этой папке",
            "удали все документы дела А40-12345/2025 за аванс",
            "удали все документы дела А40-12345/2025 за депозит",
            "удали все документы дела А40-12345/2025 за аккредитив",
            "удали все документы дела А40-12345/2025 за факторинг",
            "удали все документы за текущий аванс",
            "удали все документы за открытый аккредитив",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(advance_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за аванс в этой папке",
            "удали все документы за депозит в этой папке",
            "удали все документы за аккредитив в этой папке",
            "удали все документы за факторинг в этой папке",
            "удали все документы за текущий аванс",
            "удали все документы за открытый аккредитив",
            "удали все документы за открытие аккредитива в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го аванса",
            "удали документы 1-й аванс",
            "удали документы 1-му авансу",
            "удали документы 1-го депозита",
            "удали документы 1-го аккредитива",
            "удали документы 1-й факторинг",
            "удали документы 2-го аванса",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(advance_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 аванса"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 аванса"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 депозита"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 депозита"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 аккредитива"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 аккредитива"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 факторинга"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 факторинга"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 аванса"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 аванса"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 аккредитива"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 аккредитива"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го факторинга"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го факторинга"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го депозита"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го депозита"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 аванса"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за аванс в папку Архив",
            "перенеси все документы дела А40-12345/2025 за депозит в папку Архив",
            "перенеси все документы дела А40-12345/2025 за аккредитив в папку Архив",
            "перенеси все документы дела А40-12345/2025 за факторинг в папку Архив",
            "перенеси документ 1-го аванса в дело Архив",
            "перемести документ 1-го депозита в дело Архив",
            "перемести документ 1-го аккредитива в дело Архив",
        )
        for text in phrases:
            self.assertTrue(advance_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за аванс в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_advance_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 аванса в папку Архив"
        masked = mask_advance_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            advance_blocks_bulk_document_mutation(
                "удали документ 214 за аванс",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за аванс"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за депозит"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за аккредитив"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за факторинг"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за аванс"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без аванса",
            "удали все документы в этой папке без депозита",
            "удали все документы в этой папке без аккредитива",
            "удали все документы в этой папке без факторинга",
            "удали все документы в папке «Аванс»",
            "удали все документы в папке Аванс",
            "удали все документы в папке Депозит",
            "удали все документы в папке Аккредитив",
            "удали все документы в папке Факторинг",
            "удали все документы из папки Аванс",
            "перенеси все документы в папку Аванс",
            "перенеси все документы в папку Факторинг",
            "удали все документы по делу Аванс",
            "удали все документы по делу Депозит",
            "удали все документы по делу Аккредитив",
            "удали все документы по делу Факторинг",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за банкротство в этой папке",
            "удали все документы за платеж в этой папке",
            "удали все документы за задаток в этой папке",
            "удали все документы за обеспечительный платеж в этой папке",
            "удали все документы за новацию в этой папке",
            "удали все документы за суброгацию в этой папке",
            "удали все документы за цессию в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за требование в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за авансцену в этой папке",
            "удали все документы за авангард в этой папке",
            "удали все документы за депозитарий в этой папке",
            "удали все документы за депозитария в этой папке",
            "удали все документы за фактор в этой папке",
            "удали все документы за открытие в этой папке",
            "удали документы 1-го приказа",
            "удали документы 1-го задатка",
            "удали документы 1-й новации",
            "перенеси все документы в папку Архив",
        ):
            self.assertFalse(looks_like_advance_scoped_document_request(text), text)
            self.assertFalse(advance_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы аванса в этой папке",
            "удали документы депозита в этой папке",
            "удали документы аккредитива в этой папке",
            "удали документы факторинга в этой папке",
            "удали все документы за первый аванс в этой папке",
            "удали эти авансы в этой папке",
            "удали все документы за эту факторинговую сделку в этой папке",
        ):
            self.assertTrue(advance_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за аванс",
            "за аванса",
            "за авансу",
            "за авансом",
            "по авансу",
            "об авансе",
            "за авансы",
            "за авансов",
            "за авансовый платеж",
            "за авансирование",
            "за депозит",
            "за депозита",
            "за депозитом",
            "по депозиту",
            "о депозите",
            "за депозитный счет",
            "за аккредитив",
            "за аккредитива",
            "за аккредитивом",
            "об аккредитиве",
            "за аккредитивы",
            "за факторинг",
            "за факторинга",
            "за факторингом",
            "по факторингу",
            "за факторинговое обслуживание",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_advance_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("advance_blocks_bulk_document_mutation", source)
        self.assertIn("mask_advance_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("advance_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_advance_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_advance_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("advance_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
