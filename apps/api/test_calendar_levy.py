"""Levy-scoped chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го вреда» as document id 1. The calendar-period parser does not
recognize these phrases. «Вредить», «заложить», «индексировать», and «взыскать»
are not this guard. «Убытки» remains a separate guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_levy import (
    looks_like_levy_scoped_document_request,
    levy_blocks_bulk_document_mutation,
    mask_levy_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_levy_ordinals(raw)
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


class LevyScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за вред в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(levy_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за вред в этой папке",
            "удали все документы за моральный вред в этой папке",
            "удали все документы за возмещение вреда в этой папке",
            "удали все документы по вреду в этой папке",
            "удали все документы с вредом в этой папке",
            "удали все документы о вреде в этой папке",
            "удали все документы за пошлину в этой папке",
            "удали все документы за пошлины в этой папке",
            "удали все документы за госпошлину в этой папке",
            "удали все документы за уплату госпошлины в этой папке",
            "удали все документы за государственную пошлину в этой папке",
            "удали все документы по пошлине в этой папке",
            "удали все документы за залог в этой папке",
            "удали все документы под залог в этой папке",
            "удали все документы по залогу в этой папке",
            "удали все документы за индексацию в этой папке",
            "удали все документы по индексации в этой папке",
            "удали все документы за проценты в этой папке",
            "удали все документы по процентам в этой папке",
            "удали все документы за сумму процентов в этой папке",
            "удали все документы за начисление процентов в этой папке",
            "удали все документы за 5 процентов в этой папке",
            "удали все документы за 100 процентов в этой папке",
            "удали все документы за 12,5 процента в этой папке",
            "удали все документы за весь вред в этой папке",
            "удали все документы за все проценты в этой папке",
            "удали все документы за размер вреда в этой папке",
            "удали все документы за взыскание в этой папке",
            "удали все документы по взысканию в этой папке",
            "удали все документы за обращение взыскания в этой папке",
            "удали все документы со взысканием в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(levy_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за вред в текущей папке",
            "удали все документы за пошлину в открытой папке",
            "удали все документы по залогу из этой папки",
            "удали каждый документ за индексацию в этой папке",
            "удали все файлы за проценты в этой папке",
            "удали всех документов за взыскание в этой папке",
        ):
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertTrue(levy_blocks_bulk_document_mutation(text), text)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го вреда",
            "удали документы 1-го возмещения вреда",
            "удали документы 1-й пошлины",
            "удали документы 1-ю пошлину",
            "удали документы 1-й госпошлины",
            "удали документы 1-го залога",
            "удали документы 1-й индексации",
            "удали документы 1-го процента",
            "удали документы 1-х процентов",
            "удали документы 1-го взыскания",
            "удали документ 1 вред",
            "удали документы 2-го процента",
            "удали документы 2-го обращения взыскания",
        )
        for text in samples:
            expected = [2] if "2-" in text or text.startswith("удали документы 2") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(levy_blocks_bulk_document_mutation(text), text)
        # «100 процентов» / «12,5 процента» are amounts. Pre-fix the digits are document ids.
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 процентов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 процентов"), [])
        self.assertTrue(levy_blocks_bulk_document_mutation("удали документы 100 процентов"))
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 процента"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 процента"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 процентов"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за вред в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(levy_blocks_bulk_document_mutation(text))
        for phrase in (
            "перенеси все документы дела А40-12345/2025 за пошлину в папку Архив",
            "перенеси все документы дела А40-12345/2025 за госпошлину в папку Архив",
            "перенеси все документы дела А40-12345/2025 за залог в папку Архив",
            "перенеси все документы дела А40-12345/2025 за индексацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за проценты в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание в папку Архив",
            "перенеси документ 1-го вреда в дело Архив",
            "перенеси документ 1-го процента в дело Архив",
        ):
            self.assertTrue(levy_blocks_bulk_document_mutation(phrase), phrase)

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text in (
            "перенеси документ 1-го вреда в дело Архив",
            "перенеси документ 1-й пошлины в дело Архив",
            "перенеси документ 1-го залога в дело Архив",
            "перенеси документ 1-го процента в дело Архив",
            "перенеси документ 1-го взыскания в дело Архив",
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_levy_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], text)
            self.assertEqual(post, [], text)
        kept = "перенеси документ 214 за вред в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_levy_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            levy_blocks_bulk_document_mutation(
                "удали документ 254 за вред",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за вред"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за пошлину"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за залог"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за проценты"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за взыскание"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за вред"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за вред в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за проценты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за проценты"), [214])
        self.assertIn("214", mask_levy_ordinals("удали документ 214 за вред"))
        self.assertIn("12345", mask_levy_ordinals(text))
        self.assertIn("2025", mask_levy_ordinals(text))
        amount = "перенеси все документы дела А40-12345/2025 за 100 процентов в папку Архив"
        masked_amount = mask_levy_ordinals(amount)
        self.assertIn("12345", masked_amount)
        self.assertIn("2025", masked_amount)
        self.assertNotIn("100", masked_amount)
        self.assertEqual(_parse_ids_like_main(amount), [])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без вреда",
            "удали все документы в этой папке без пошлины",
            "удали все документы в этой папке без госпошлины",
            "удали все документы в этой папке без залога",
            "удали все документы в этой папке без индексации",
            "удали все документы в этой папке без процентов",
            "удали все документы в этой папке без взыскания",
            "удали все документы в папке Вред",
            "перенеси все документы в папку Пошлина",
            "удали все документы из папки Залог",
            "удали все документы в папку Индексация",
            "удали все документы в папке Проценты",
            "удали все документы в папке Взыскание",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за убытки в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за арест в этой папке",
            "удали все документы за штраф в этой папке",
            "удали все документы за полис в этой папке",
            "удали все документы за гарантию в этой папке",
            "удали все документы за вредить в этой папке",
            "удали все документы за навредить в этой папке",
            "удали все документы за вредный в этой папке",
            "удали все документы за заложить в этой папке",
            "удали все документы за залогодателя в этой папке",
            "удали все документы за индексировать в этой папке",
            "удали все документы за индекс в этой папке",
            "удали все документы за взыскать в этой папке",
            "удали все документы за взыскателя в этой папке",
            "удали документы 1-го убытка",
            "удали документы 1-го полиса",
            "удали документы 1-го штрафа",
        ):
            self.assertFalse(looks_like_levy_scoped_document_request(text), text)
            self.assertFalse(levy_blocks_bulk_document_mutation(text), text)

    def test_adjective_and_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все вредные документы в этой папке",
            "удали все документы вредные в этой папке",
            "удали все пошлинные документы в этой папке",
            "удали все залоговые документы в этой папке",
            "удали все индексационные документы в этой папке",
            "удали все процентные документы в этой папке",
            "удали все документы во время взыскания в этой папке",
            "удали все документы за первый вред в этой папке",
            "удали все документы за второй залог в этой папке",
            "удали документы вреда в этой папке",
            "удали документы пошлины в этой папке",
            "удали документы залога в этой папке",
            "удали документы индексации в этой папке",
            "удали документы процентов в этой папке",
            "удали документы взыскания в этой папке",
            "удали эти проценты в этой папке",
            "удали все документы за моральный вред в этой папке",
            "удали все документы за обеспечительный залог в этой папке",
        ):
            self.assertTrue(levy_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("levy_blocks_bulk_document_mutation", source)
        self.assertIn("mask_levy_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("levy_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_levy_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_levy_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("levy_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
