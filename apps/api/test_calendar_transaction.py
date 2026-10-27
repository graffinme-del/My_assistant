"""Transaction and gift chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й сделки» as document id 1. The calendar period parser does not recognize
these phrases.

A folder titled «Сделка» or «Дарение» is not this guard. «без сделки» is not
this guard. Bare «банкротство» is not this guard. «сделать» and «сдельный» are
not «сделка». «ударение» is not «дарение». «дарить» is not «даритель».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_transaction import (
    looks_like_transaction_scoped_document_request,
    mask_transaction_ordinals,
    transaction_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_transaction_ordinals(raw)
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


class TransactionScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за сделку в этой папке",
            "удали все документы по сделке в этой папке",
            "удали все документы о сделке в этой папке",
            "удали все документы за сделки в этой папке",
            "удали все документы за сделочный договор в этой папке",
            "удали все документы за мнимую сделку в этой папке",
            "удали все документы за притворную сделку в этой папке",
            "удали все документы за оспаривание сделки в этой папке",
            "удали все документы за дарение в этой папке",
            "удали все документы по дарению в этой папке",
            "удали все документы о дарении в этой папке",
            "удали все документы за договор дарения в этой папке",
            "удали все документы за дарственную в этой папке",
            "удали все документы за дарителя в этой папке",
            "удали все документы за одаряемого в этой папке",
            "удали все документы за срок сделки в этой папке",
            "удали все документы в ходе дарения в этой папке",
            "удали все документы в процессе сделки в этой папке",
            "удали все документы на стадии дарения в этой папке",
            "удали все документы при сделке в этой папке",
            "удали все документы за текущую сделку",
            "удали все документы за текущее дарение",
            "удали все документы за открытую сделку",
            "удали все документы за открытое дарение",
            "удали каждый документ за сделку в этой папке",
            "удали все файлы за дарение в этой папке",
            "удали все документы дела А40-12345/2025 за сделку",
            "удали все документы дела А40-12345/2025 за дарение",
            "удали все документы дела А40-12345/2025 по сделке",
            "удали все документы за Сделку в этой папке",
            "удали все документы во время сделки в этой папке",
            "удали все документы во время дарения в этой папке",
            "удали все документы за «сделку» в этой папке",
            "удали все документы за «договор дарения» в этой папке",
            "удали все документы за совершение сделки в этой папке",
            "удали все документы за отчуждение дарения в этой папке",
            "удали все документы за несделку в этой папке",
            "удали все документы за недарение в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(transaction_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за сделку в этой папке",
            "удали все документы по сделке в этой папке",
            "удали все документы за дарение в этой папке",
            "удали все документы за текущую сделку",
            "удали все документы за текущее дарение",
            "удали все документы за открытую сделку",
            "удали все документы за открытое дарение",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й сделки",
            "удали документы 1-го сделки",
            "удали документы 1-й сделке",
            "удали документы 1-й дарения",
            "удали документы 1-го дарения",
            "удали документы 1-го дарителя",
            "удали документы 2-й сделки",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(transaction_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 сделок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 сделок"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 дарений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 дарений"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% сделки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% сделки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% дарения"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% дарения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% дарения"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% дарения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го сделки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го сделки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й дарения"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й дарения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го дарителя"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го дарителя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 сделки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 сделки"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 сделок"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за сделку"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й поставки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й приостановления"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й налога"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-е отложения"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за сделку в папку Архив",
            "перенеси все документы дела А40-12345/2025 по сделке в папку Архив",
            "перенеси все документы дела А40-12345/2025 за дарение в папку Архив",
            "перенеси все документы дела А40-12345/2025 за дарителя в папку Архив",
            "перенеси все документы дела А40-12345/2025 за договор дарения в папку Архив",
            "перенеси документ 1-й сделки в дело Архив",
            "перемести документ 1-й дарения в дело Архив",
        )
        for text in phrases:
            self.assertTrue(transaction_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за сделку в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_transaction_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 сделок в папку Архив"
        masked = mask_transaction_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            transaction_blocks_bulk_document_mutation(
                "удали документ 214 за сделку",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за сделку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за дарение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по сделке"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за сделку"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за дарение"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Сделка",
            "удали все документы в папке Дарение",
            "удали все документы в папке «Сделка»",
            "удали все документы в папке «Дарение»",
            "удали все документы без сделки в этой папке",
            "удали все документы без дарения в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за приостановление в этой папке",
            "удали все документы за налог в этой папке",
            "удали все документы за остановку в этой папке",
            "удали все документы за срок в этой папке",
            "удали все документы в ходе проверки в этой папке",
            "удали все документы за ходатайство в этой папке",
            "удали все документы чтобы сделать копию в этой папке",
            "удали все документы за сдельную оплату в этой папке",
            "удали все документы за сдельщика в этой папке",
            "удали все документы за сделкоспособность в этой папке",
            "удали все документы за ударение в этой папке",
            "удали все документы за дарить в этой папке",
            "удали все документы за подарить в этой папке",
            "удали все документы за удар в этой папке",
            "удали все документы за дар в этой папке",
            "удали все документы за третейский суд в этой папке",
            "удали все документы за перевозку в этой папке",
            "удали все документы за оценщика в этой папке",
            "удали все документы за отложение в этой папке",
            "удали все документы за НДФЛ в этой папке",
            "удали все документы за ФНС в этой папке",
            "удали все документы за УСН в этой папке",
            "удали все документы за недоимку в этой папке",
            "удали все документы за доначисление в этой папке",
            "удали все документы за производство в папке Сделка",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Сделка",
            "перенеси все документы в папку Дарение",
            "собери все документы в папку Сделка по Гримме",
            "удали документ 214",
            "удали все документы по делу Сделка",
            "удали все документы по делу Дарение",
        ):
            self.assertFalse(looks_like_transaction_scoped_document_request(text), text)
            self.assertFalse(transaction_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за сделку",
            "за сделки",
            "по сделке",
            "о сделке",
            "за сделкой",
            "за сделками",
            "за сделок",
            "за сделочный договор",
            "за сделочную схему",
            "за мнимую сделку",
            "за притворную сделку",
            "за оспаривание сделки",
            "за совершение сделки",
            "за отчуждение по сделке",
            "за дарение",
            "по дарению",
            "о дарении",
            "за дарением",
            "за дарений",
            "за договор дарения",
            "за дарственную",
            "за дарственного",
            "за дарителя",
            "за дарителю",
            "за дарителем",
            "за дарителей",
            "за дарительский взнос",
            "за одаряемого",
            "за одаряемому",
            "за срок сделки",
            "в ходе дарения",
            "в процессе сделки",
            "на стадии дарения",
            "во время сделки",
            "при сделке",
            "за несделку",
            "за недарение",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_transaction_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("transaction_blocks_bulk_document_mutation", source)
        self.assertIn("mask_transaction_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("transaction_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_transaction_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_transaction_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("transaction_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
