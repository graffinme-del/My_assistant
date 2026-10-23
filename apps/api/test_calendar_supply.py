"""Supply, work-contract, and sale chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й поставки» as document id 1. The calendar period parser does not recognize
these phrases.

A folder titled «Поставка» or «Купля-продажа» is not this guard.
The adverb «подряд» («все документы подряд») is not this guard.
Bare «банкротство», «продажа», and «купля» are not this guard.
«постановление» and «поставлять» are not «поставка».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_supply import (
    looks_like_supply_contract_scoped_document_request,
    mask_supply_contract_ordinals,
    supply_contract_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_supply_contract_ordinals(raw)
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


class SupplyContractScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за поставку в этой папке",
            "удали все документы по поставке в этой папке",
            "удали все документы о поставке в этой папке",
            "удали все документы за договор поставки в этой папке",
            "удали все документы за недопоставку в этой папке",
            "удали все документы за поставщика в этой папке",
            "удали все документы за поставщицу в этой папке",
            "удали все документы за подряд в этой папке",
            "удали все документы по подряду в этой папке",
            "удали все документы за подрядчика в этой папке",
            "удали все документы за субподряд в этой папке",
            "удали все документы за генподряд в этой папке",
            "удали все документы за субподрядчика в этой папке",
            "удали все документы за подрядные работы в этой папке",
            "удали все документы за работы подрядчика в этой папке",
            "удали все документы за куплю-продажу в этой папке",
            "удали все документы за договор купли-продажи в этой папке",
            "удали все документы за куплю продажи в этой папке",
            "удали все документы за партию поставки в этой папке",
            "удали все документы за строительство подряда в этой папке",
            "удали все документы за предмет поставки в этой папке",
            "удали все документы за выполнение подряда в этой папке",
            "удали все документы за исполнение договора поставки в этой папке",
            "удали все документы за неисполнение поставки в этой папке",
            "удали все документы за товар поставщика в этой папке",
            "удали все документы за услуги поставщика в этой папке",
            "удали все документы за текущую поставку",
            "удали все документы за открытый подряд",
            "удали все документы за открытую куплю-продажу",
            "удали каждый документ за поставку в этой папке",
            "удали все файлы за поставки в этой папке",
            "удали все документы дела А40-12345/2025 за поставку",
            "удали все документы дела А40-12345/2025 за подряд",
            "удали все документы дела А40-12345/2025 за куплю-продажу",
            "удали все документы за Поставку в этой папке",
            "удали все документы во время поставки в этой папке",
            "удали все документы во время подряда в этой папке",
            "удали все документы за «поставку» в этой папке",
            "удали все документы за «договор поставки» в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(supply_contract_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за поставку в этой папке",
            "удали все документы за подряд в этой папке",
            "удали все документы за куплю-продажу в этой папке",
            "удали все документы за текущую поставку",
            "удали все документы за открытый подряд в этой папке",
            "удали все документы за открытую куплю-продажу",
            "удали все документы подряд в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й поставки",
            "удали документы 1-го поставщика",
            "удали документы 1-й поставщицы",
            "удали документы 1-го подряда",
            "удали документы 1-го подрядчика",
            "удали документы 1-го субподряда",
            "удали документы 1-й купли-продажи",
            "удали документы 2-й поставки",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(supply_contract_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 поставки"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 поставки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 поставок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 поставок"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 подряда"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 подряда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% поставки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% поставки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% подряда"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% подряда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% купли-продажи"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% купли-продажи"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го поставщика"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го поставщика"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й поставки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й поставки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го подряда"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го подряда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 подряд"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 подряд"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 поставки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за поставку"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го полиса"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й франшизы"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за поставку в папку Архив",
            "перенеси все документы дела А40-12345/2025 за подряд в папку Архив",
            "перенеси все документы дела А40-12345/2025 за подрядчика в папку Архив",
            "перенеси все документы дела А40-12345/2025 за куплю-продажу в папку Архив",
            "перенеси все документы дела А40-12345/2025 за договор купли-продажи в папку Архив",
            "перенеси все документы дела А40-12345/2025 за поставщика в папку Архив",
            "перенеси документ 1-й поставки в дело Архив",
            "перемести документ 1-го подряда в дело Архив",
        )
        for text in phrases:
            self.assertTrue(supply_contract_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за поставку в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_supply_contract_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 поставки в папку Архив"
        masked = mask_supply_contract_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            supply_contract_blocks_bulk_document_mutation(
                "удали документ 214 за поставку",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за поставку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за подряд"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за куплю-продажу"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за поставку"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за поставку"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Поставка",
            "удали все документы в папке Подряд",
            "удали все документы в папке Купля-продажа",
            "удали все документы в папке «Поставка»",
            "удали все документы в папке «Договор поставки»",
            "удали все документы подряд в этой папке",
            "удали все документы подряд",
            "удали все файлы три дня подряд",
            "удали все документы без поставки в этой папке",
            "удали все документы без подряда в этой папке",
            "удали все документы без купли-продажи в этой папке",
            "удали все документы за строительство в этой папке",
            "удали все документы за предмет в этой папке",
            "удали все документы за выполнение в этой папке",
            "удали все документы за исполнение в этой папке",
            "удали все документы за продажу в этой папке",
            "удали все документы за куплю в этой папке",
            "удали все документы за постановление в этой папке",
            "удали все документы за поставляемый товар в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы подряд в папку Архив",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_supply_contract_scoped_document_request(text), text)
            self.assertFalse(supply_contract_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за поставку",
            "за поставки",
            "по поставке",
            "о поставке",
            "за поставкой",
            "за поставок",
            "за недопоставку",
            "за недопоставки",
            "за поставщика",
            "за поставщику",
            "за поставщиком",
            "о поставщике",
            "за поставщики",
            "за поставщиков",
            "за поставщицу",
            "за поставщицы",
            "за подряд",
            "по подряду",
            "за подрядом",
            "о подряде",
            "за подряды",
            "за подрядчика",
            "за подрядчику",
            "за подрядчиком",
            "о подрядчике",
            "за подрядчики",
            "за подрядчиков",
            "за субподряд",
            "за субподряда",
            "за генподряд",
            "за генподряда",
            "за субподрядчика",
            "за генподрядчика",
            "за подрядный договор",
            "за подрядные работы",
            "за подрядного договора",
            "за куплю-продажу",
            "за купли-продажи",
            "по купле-продаже",
            "за куплей-продажей",
            "за договор купли-продажи",
            "за договор поставки",
            "за работы подрядчика",
            "за партию поставки",
            "за товар поставщика",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_supply_contract_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("supply_contract_blocks_bulk_document_mutation", source)
        self.assertIn("mask_supply_contract_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("supply_contract_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_supply_contract_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_supply_contract_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("supply_contract_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
