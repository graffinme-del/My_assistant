"""Installment/liability/title chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-й рассрочки» as document id 1. The calendar-period parser does not
recognize these phrases. «Рассрочить», «отсрочить», «солидарность», and bare
«полис» are not this guard. «Вред» / «пошлина» remain a separate guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_installment import (
    installment_blocks_bulk_document_mutation,
    looks_like_installment_scoped_document_request,
    mask_installment_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_installment_ordinals(raw)
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


def _open_folder_wipe_phrase(text: str) -> bool:
    """Same wants_all + open-folder checks as handle_delete_documents_chat."""
    low = (text or "").lower()
    wants_all = any(
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
    open_folder = any(p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"))
    return wants_all and open_folder


class InstallmentScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за рассрочку в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(installment_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за рассрочку в этой папке",
            "удали все документы за рассрочки в этой папке",
            "удали все документы по рассрочке в этой папке",
            "удали все документы с рассрочкой в этой папке",
            "удали все документы о рассрочке в этой папке",
            "удали все документы за предоставление рассрочки в этой папке",
            "удали все документы за судебную рассрочку в этой папке",
            "удали все документы за график рассрочки в этой папке",
            "удали все документы в рассрочку в этой папке",
            "удали все документы за отсрочку в этой папке",
            "удали все документы за отсрочки в этой папке",
            "удали все документы по отсрочке в этой папке",
            "удали все документы за отсрочку исполнения в этой папке",
            "удали все документы за предоставление отсрочки в этой папке",
            "удали все документы за реструктуризацию в этой папке",
            "удали все документы по реструктуризации в этой папке",
            "удали все документы за план реструктуризации в этой папке",
            "удали все документы за субсидиарную ответственность в этой папке",
            "удали все документы по субсидиарной ответственности в этой папке",
            "удали все документы к субсидиарной ответственности в этой папке",
            "удали все документы за субсидиарку в этой папке",
            "удали все документы за субсидиарный иск в этой папке",
            "удали все документы за солидарную ответственность в этой папке",
            "удали все документы по солидарным должникам в этой папке",
            "удали все документы за ОСАГО в этой папке",
            "удали все документы по ОСАГО в этой папке",
            "удали все документы за полис ОСАГО в этой папке",
            "удали все документы за страховой полис ОСАГО в этой папке",
            "удали все документы об ОСАГО в этой папке",
            "удали все документы за OSAGO в этой папке",
            "удали все документы за ПТС в этой папке",
            "удали все документы по ПТС в этой папке",
            "удали все документы с ПТС в этой папке",
            "удали все документы за паспорт ПТС в этой папке",
            "удали все документы за всю рассрочку в этой папке",
            "удали все документы за все отсрочки в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(installment_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за рассрочку в текущей папке",
            "удали все документы за отсрочку в открытой папке",
            "удали все документы по реструктуризации из этой папки",
            "удали каждый документ за субсидиарную ответственность в этой папке",
            "удали все файлы за ОСАГО в этой папке",
            "удали всех документов за ПТС в этой папке",
        ):
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertTrue(installment_blocks_bulk_document_mutation(text), text)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й рассрочки",
            "удали документы 1-ю рассрочку",
            "удали документы 1-й отсрочки",
            "удали документы 1-го предоставления отсрочки",
            "удали документы 1-й реструктуризации",
            "удали документы 1-й субсидиарной ответственности",
            "удали документы 1-й субсидиарки",
            "удали документы 1-й солидарной ответственности",
            "удали документы 1-го ОСАГО",
            "удали документы 1 ОСАГО",
            "удали документы 1-го ПТС",
            "удали документы 1 ПТС",
            "удали документ 1 рассрочка",
            "удали документы 2-й рассрочки",
            "удали документы 2-й отсрочки",
        )
        for text in samples:
            expected = [2] if "2-" in text or text.startswith("удали документы 2") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(installment_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 ПТС"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 ПТС"), [])
        self.assertTrue(installment_blocks_bulk_document_mutation("удали документы 100 ПТС"))
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 ОСАГО"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 ОСАГО"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 рассрочки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 рассрочки"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 ПТС"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за рассрочку в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(installment_blocks_bulk_document_mutation(text))
        for phrase in (
            "перенеси все документы дела А40-12345/2025 за отсрочку в папку Архив",
            "перенеси все документы дела А40-12345/2025 за реструктуризацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за субсидиарную ответственность в папку Архив",
            "перенеси все документы дела А40-12345/2025 за солидарную ответственность в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ОСАГО в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ПТС в папку Архив",
            "перенеси документ 1-й рассрочки в дело Архив",
            "перенеси документ 1-го ОСАГО в дело Архив",
            "перенеси документ 1 ПТС в дело Архив",
        ):
            self.assertTrue(installment_blocks_bulk_document_mutation(phrase), phrase)

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text in (
            "перенеси документ 1-й рассрочки в дело Архив",
            "перенеси документ 1-й отсрочки в дело Архив",
            "перенеси документ 1-й субсидиарки в дело Архив",
            "перенеси документ 1-го ОСАГО в дело Архив",
            "перенеси документ 1 ПТС в дело Архив",
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_installment_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], text)
            self.assertEqual(post, [], text)
        kept = "перенеси документ 214 за рассрочку в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_installment_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            installment_blocks_bulk_document_mutation(
                "удали документ 254 за рассрочку",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за рассрочку"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за отсрочку"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за ОСАГО"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за ПТС"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за субсидиарную ответственность"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за рассрочку"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за рассрочку в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за ОСАГО"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ОСАГО"), [214])
        self.assertIn("214", mask_installment_ordinals("удали документ 214 за рассрочку"))
        self.assertIn("12345", mask_installment_ordinals(text))
        self.assertIn("2025", mask_installment_ordinals(text))
        amount = "перенеси все документы дела А40-12345/2025 за 100 ПТС в папку Архив"
        masked_amount = mask_installment_ordinals(amount)
        self.assertIn("12345", masked_amount)
        self.assertIn("2025", masked_amount)
        self.assertNotIn("100", masked_amount)
        self.assertEqual(_parse_ids_like_main(amount), [])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без рассрочки",
            "удали все документы в этой папке без отсрочки",
            "удали все документы в этой папке без реструктуризации",
            "удали все документы в этой папке без субсидиарки",
            "удали все документы в этой папке без ОСАГО",
            "удали все документы в этой папке без ПТС",
            "удали все документы в папке Рассрочка",
            "перенеси все документы в папку Отсрочка",
            "удали все документы из папки Реструктуризация",
            "удали все документы в папке ОСАГО",
            "удали все документы в папке ПТС",
            "удали все документы дела А53-13969/2026",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за вред в этой папке",
            "удали все документы за пошлину в этой папке",
            "удали все документы за проценты в этой папке",
            "удали все документы за полис в этой папке",
            "удали все документы за паспорт в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы за план в этой папке",
            "удали все документы за рассрочить в этой папке",
            "удали все документы за отсрочить в этой папке",
            "удали все документы за реструктуризировать в этой папке",
            "удали все документы за солидарность в этой папке",
            "удали все документы за субсидиарно в этой папке",
            "удали документы 1-го вреда",
            "удали документы 1-го полиса",
            "удали документы 1-й пошлины",
        ):
            self.assertFalse(looks_like_installment_scoped_document_request(text), text)
            self.assertFalse(installment_blocks_bulk_document_mutation(text), text)

    def test_adjective_and_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все рассроченные документы в этой папке",
            "удали все документы отсроченные в этой папке",
            "удали все реструктуризационные документы в этой папке",
            "удали все субсидиарные документы в этой папке",
            "удали все солидарные документы в этой папке",
            "удали все документы во время рассрочки в этой папке",
            "удали все документы за первую рассрочку в этой папке",
            "удали все документы за вторую отсрочку в этой папке",
            "удали документы рассрочки в этой папке",
            "удали документы отсрочки в этой папке",
            "удали документы реструктуризации в этой папке",
            "удали документы субсидиарки в этой папке",
            "удали документы ОСАГО в этой папке",
            "удали документы ПТС в этой папке",
            "удали эти рассрочки в этой папке",
            "удали это ОСАГО в этой папке",
            "удали этот ПТС в этой папке",
        ):
            self.assertTrue(installment_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("installment_blocks_bulk_document_mutation", source)
        self.assertIn("mask_installment_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("installment_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_installment_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_installment_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("installment_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
