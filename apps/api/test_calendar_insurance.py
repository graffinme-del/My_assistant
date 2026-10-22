"""Insurance chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й страховки» as document id 1. The calendar period parser does not recognize
these phrases.

«полис», «ОСАГО», and «франшиза» are not this guard. A folder titled
«Страхование» or «КАСКО» is not this guard. Bare «банкротство» is not this guard.
«каска» and «каскад» are not «КАСКО». Bare «страх», «премия», and «возмещение»
are not «страхование».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_insurance import (
    insurance_blocks_bulk_document_mutation,
    looks_like_insurance_scoped_document_request,
    mask_insurance_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_insurance_ordinals(raw)
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


class InsuranceScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за страхование в этой папке",
            "удали все документы по страхованию в этой папке",
            "удали все документы о страховании в этой папке",
            "удали все документы за договор страхования в этой папке",
            "удали все документы за перестрахование в этой папке",
            "удали все документы за сострахование в этой папке",
            "удали все документы за страховку в этой папке",
            "удали все документы за выплату страховки в этой папке",
            "удали все документы за страховой случай в этой папке",
            "удали все документы за страховое возмещение в этой папке",
            "удали все документы за страховую выплату в этой папке",
            "удали все документы за страховую премию в этой папке",
            "удали все документы за страховщика в этой папке",
            "удали все документы за страхователя в этой папке",
            "удали все документы за застрахованного в этой папке",
            "удали все документы за КАСКО в этой папке",
            "удали все документы за каско в этой папке",
            "удали все документы за KASKO в этой папке",
            "удали все документы за касковый полис в этой папке",
            "удали все документы за ДМС в этой папке",
            "удали все документы за ОМС в этой папке",
            "удали все документы за полис ДМС в этой папке",
            "удали все документы за текущее страхование",
            "удали все документы за открытую страховку",
            "удали все документы за текущий страховой случай",
            "удали каждый документ за страхование в этой папке",
            "удали все файлы за страховки в этой папке",
            "удали все документы дела А40-12345/2025 за страхование",
            "удали все документы дела А40-12345/2025 за КАСКО",
            "удали все документы дела А40-12345/2025 за ДМС",
            "удали все документы за Страхование в этой папке",
            "удали все документы во время страхования в этой папке",
            "удали все документы во время КАСКО в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(insurance_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за страхование в этой папке",
            "удали все документы за страховку в этой папке",
            "удали все документы за КАСКО в этой папке",
            "удали все документы за ДМС в этой папке",
            "удали все документы за текущее страхование",
            "удали все документы за открытую страховку в этой папке",
            "удали все документы за открытый страховой случай",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го страхования",
            "удали документы 1-й страховки",
            "удали документы 1-го страховщика",
            "удали документы 1-го страхователя",
            "удали документы 1-го застрахованного",
            "удали документы 1-го каско",
            "удали документы 1-го ДМС",
            "удали документы 2-й страховки",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(insurance_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 страхования"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 страхования"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 страховки"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 страховки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% страхования"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% страхования"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% каско"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% каско"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го страховщика"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го страховщика"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й страховки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й страховки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го ДМС"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го ДМС"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 страхования"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за страхование"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го полиса"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го ОСАГО"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й франшизы"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й каски"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за страхование в папку Архив",
            "перенеси все документы дела А40-12345/2025 за страховку в папку Архив",
            "перенеси все документы дела А40-12345/2025 за КАСКО в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ДМС в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ОМС в папку Архив",
            "перенеси все документы дела А40-12345/2025 за страховое возмещение в папку Архив",
            "перенеси документ 1-й страховки в дело Архив",
            "перемести документ 1-го страхования в дело Архив",
        )
        for text in phrases:
            self.assertTrue(insurance_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за страхование в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_insurance_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 страхования в папку Архив"
        masked = mask_insurance_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            insurance_blocks_bulk_document_mutation(
                "удали документ 214 за страхование",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за страхование"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за КАСКО"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за ДМС"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за страховку"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за страхование"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Страхование",
            "удали все документы в папке КАСКО",
            "удали все документы в папке ДМС",
            "удали все документы без страхования в этой папке",
            "удали все документы без КАСКО в этой папке",
            "удали все документы за полис в этой папке",
            "удали все документы за ОСАГО в этой папке",
            "удали все документы за франшизу в этой папке",
            "удали все документы за страх в этой папке",
            "удали все документы за премию в этой папке",
            "удали все документы за возмещение в этой папке",
            "удали все документы за каску в этой папке",
            "удали все документы за каскад в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_insurance_scoped_document_request(text), text)
            self.assertFalse(insurance_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за страхование",
            "за страхования",
            "по страхованию",
            "о страховании",
            "за страхованием",
            "за перестрахование",
            "за сострахование",
            "за страховку",
            "за страховки",
            "за страховке",
            "за страховкой",
            "за страховок",
            "за страховой случай",
            "за страхового случая",
            "за страховому случаю",
            "за страховым случаем",
            "о страховом случае",
            "за страховое возмещение",
            "за страхового возмещения",
            "за страховую выплату",
            "за страховую премию",
            "за страховщика",
            "за страховщику",
            "за страховщиком",
            "о страховщике",
            "за страховщики",
            "за страховщиков",
            "за страхователя",
            "за страхователю",
            "за страхователем",
            "о страхователе",
            "за страхователи",
            "за страхователей",
            "за застрахованного",
            "за застрахованному",
            "за застрахованным",
            "за застрахованная",
            "за каско",
            "за КАСКО",
            "за KASKO",
            "за касковый полис",
            "за каскового полиса",
            "за ДМС",
            "за дмс",
            "за ОМС",
            "за омс",
            "за полис ДМС",
            "за получение страхового возмещения",
            "за выплату страховки",
            "за договор страхования",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_insurance_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("insurance_blocks_bulk_document_mutation", source)
        self.assertIn("mask_insurance_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("insurance_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_insurance_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_insurance_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("insurance_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
