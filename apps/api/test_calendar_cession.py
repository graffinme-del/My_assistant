"""Bailiff / enforcement-fee / accord / cession chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number) as wipe-the-folder and parsed «1-го судебного пристава»
as document id 1. The calendar period parser does not recognize these phrases.

«исполнительный лист», «исполнительное производство», and «судебный приказ»
belong to other guards. A folder titled «Цессия» is not this guard.
Bare «банкротство» is not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_cession import (
    cession_blocks_bulk_document_mutation,
    looks_like_cession_scoped_document_request,
    mask_cession_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_cession_ordinals(raw)
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


class CessionScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за судебного пристава в этой папке",
            "удали все документы по судебному приставу в этой папке",
            "удали все документы за судебного пристава-исполнителя в этой папке",
            "удали все документы за пристава-исполнителя в этой папке",
            "удали все документы за ФССП в этой папке",
            "удали все документы за службу судебных приставов в этой папке",
            "удали все документы за постановление судебного пристава в этой папке",
            "удали все документы за действия судебного пристава в этой папке",
            "удали все документы за текущего судебного пристава в этой папке",
            "удали все документы за открытого судебного пристава в этой папке",
            "удали все документы за исполнительский сбор в этой папке",
            "удали все документы по исполнительскому сбору в этой папке",
            "удали все документы за уплату исполнительского сбора в этой папке",
            "удали все документы за взыскание исполнительского сбора в этой папке",
            "удали все документы за отмену исполнительского сбора в этой папке",
            "удали все документы за расчет исполнительского сбора в этой папке",
            "удали все документы во время исполнительского сбора в этой папке",
            "удали все документы за отступное в этой папке",
            "удали все документы об отступном в этой папке",
            "удали все документы за соглашение об отступном в этой папке",
            "удали все документы за предоставление отступного в этой папке",
            "удали все документы за уступку права в этой папке",
            "удали все документы за уступку права требования в этой папке",
            "удали все документы за договор уступки права в этой папке",
            "удали все документы по уступке права в этой папке",
            "удали все документы за цессию в этой папке",
            "удали все документы по цессии в этой папке",
            "удали все документы за договор цессии в этой папке",
            "удали все документы за уведомление о цессии в этой папке",
            "удали все документы за цессионария в этой папке",
            "удали все документы за цедента в этой папке",
            "удали все документы за цессионный договор в этой папке",
            "удали каждый документ за цессию в этой папке",
            "удали все файлы за отступное в этой папке",
            "удали все документы дела А40-12345/2025 за судебного пристава",
            "удали все документы дела А40-12345/2025 за исполнительский сбор",
            "удали все документы дела А40-12345/2025 за отступное",
            "удали все документы дела А40-12345/2025 за уступку права",
            "удали все документы дела А40-12345/2025 за цессию",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(cession_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за судебного пристава в этой папке",
            "удали все документы за исполнительский сбор в этой папке",
            "удали все документы за отступное в этой папке",
            "удали все документы за цессию в этой папке",
            "удали все документы за текущего судебного пристава в этой папке",
            "удали все документы за открытого судебного пристава в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го судебного пристава",
            "удали документы 1-й судебный пристав",
            "удали документы 1-му судебному приставу",
            "удали документы 1-го исполнительского сбора",
            "удали документы 1-й цессии",
            "удали документы 1-го отступного",
            "удали документы 1-й уступки права",
            "удали документы 2-го судебного пристава",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(cession_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 судебного пристава"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 судебного пристава"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 исполнительского сбора"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 исполнительского сбора"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 отступного"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 отступного"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 цессии"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 цессии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 отступного"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 отступного"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 цессии"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 цессии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го судебного пристава"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го судебного пристава"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 цессии"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за судебного пристава в папку Архив",
            "перенеси все документы дела А40-12345/2025 за исполнительский сбор в папку Архив",
            "перенеси все документы дела А40-12345/2025 за отступное в папку Архив",
            "перенеси все документы дела А40-12345/2025 за уступку права в папку Архив",
            "перенеси все документы дела А40-12345/2025 за цессию в папку Архив",
            "перенеси документ 1-го судебного пристава в дело Архив",
            "перемести документ 1-го исполнительского сбора в дело Архив",
            "перемести документ 1-й цессии в дело Архив",
        )
        for text in phrases:
            self.assertTrue(cession_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за цессию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_cession_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 цессии в папку Архив"
        masked = mask_cession_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            cession_blocks_bulk_document_mutation(
                "удали документ 214 за цессию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за судебного пристава"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за исполнительский сбор"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за отступное"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за уступку права"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за цессию"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за цессию"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без судебного пристава",
            "удали все документы в этой папке без исполнительского сбора",
            "удали все документы в этой папке без отступного",
            "удали все документы в этой папке без уступки права",
            "удали все документы в этой папке без цессии",
            "удали все документы в папке «Судебный пристав»",
            "удали все документы в папке Судебный пристав",
            "удали все документы в папке Исполнительский сбор",
            "удали все документы в папке Отступное",
            "удали все документы в папке Цессия",
            "удали все документы в папке Уступка права",
            "удали все документы из папки Цессия",
            "перенеси все документы в папку Цессия",
            "перенеси все документы в папку Судебный пристав",
            "удали все документы по делу Цессия",
            "удали все документы по делу Судебный пристав",
            "удали все документы по делу Отступное",
            "удали все документы по делу Уступка права",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за исполнительный лист в этой папке",
            "удали все документы за исполнительное производство в этой папке",
            "удали все документы за судебный приказ в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за сбор в этой папке",
            "удали все документы за сбор доказательств в этой папке",
            "удали все документы за сборник в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за требование в этой папке",
            "удали все документы за жалобу в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за права в этой папке",
            "удали все документы по делу Исполнительский сбор",
            "удали все документы из папки Приставы",
            "перенеси все документы в папку Приставы",
            "перенеси все документы в папку Архив",
            "удали все документы за отступление в этой папке",
            "удали все документы за процесс в этой папке",
            "удали все документы за приставку в этой папке",
            "удали все документы за конкурсного управляющего в этой папке",
            "удали документы 1-го приказа",
            "удали документы 1-го листа",
            "удали документы 1-го производства",
            "удали документы 1-го сборника",
        ):
            self.assertFalse(looks_like_cession_scoped_document_request(text), text)
            self.assertFalse(cession_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы судебного пристава в этой папке",
            "удали документы исполнительского сбора в этой папке",
            "удали документы отступного в этой папке",
            "удали документы уступки права в этой папке",
            "удали документы цессии в этой папке",
            "удали документы цессионария в этой папке",
            "удали все документы за первого судебного пристава в этой папке",
            "удали эти цессии в этой папке",
            "удали все документы за это отступное в этой папке",
        ):
            self.assertTrue(cession_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за судебного пристава",
            "за судебному приставу",
            "за судебным приставом",
            "за судебных приставов",
            "за судебными приставами",
            "по судебному приставу",
            "за исполнительский сбор",
            "за исполнительского сбора",
            "за исполнительскому сбору",
            "за исполнительским сбором",
            "за исполнительских сборов",
            "за отступное",
            "за отступного",
            "за отступному",
            "за отступным",
            "об отступном",
            "за отступные",
            "за уступку права",
            "за уступки права",
            "за уступке права",
            "по уступке права требования",
            "за цессию",
            "за цессии",
            "за цессией",
            "по цессии",
            "за цедента",
            "за цессионария",
            "за цессионное соглашение",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_cession_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("cession_blocks_bulk_document_mutation", source)
        self.assertIn("mask_cession_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("cession_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_cession_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_cession_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("cession_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
