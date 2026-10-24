"""Challenge, restitution, and inventory chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й оспаривания» as document id 1. The calendar period parser does not recognize
these phrases.

A folder titled «Оспаривание», «Реституция», or «Инвентаризация» is not this guard.
«без оспаривания» is not this guard. Bare «банкротство» is not this guard.
«оспорить», «оспаривать», and «инвентарь» are not «оспаривание» / «инвентаризация».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_challenge import (
    challenge_blocks_bulk_document_mutation,
    looks_like_challenge_scoped_document_request,
    mask_challenge_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_challenge_ordinals(raw)
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


class ChallengeScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за оспаривание в этой папке",
            "удали все документы по оспариванию в этой папке",
            "удали все документы об оспаривании в этой папке",
            "удали все документы за оспаривание сделки в этой папке",
            "удали все документы за заявление об оспаривании в этой папке",
            "удали все документы за оспариваемую сделку в этой папке",
            "удали все документы за оспоренную сделку в этой папке",
            "удали все документы за неоспоренную сделку в этой папке",
            "удали все документы за оспоримую сделку в этой папке",
            "удали все документы за оспоримость сделки в этой папке",
            "удали все документы за реституцию в этой папке",
            "удали все документы о реституции в этой папке",
            "удали все документы за применение реституции в этой папке",
            "удали все документы за последствия реституции в этой папке",
            "удали все документы за реституционное требование в этой папке",
            "удали все документы за инвентаризацию в этой папке",
            "удали все документы по инвентаризации в этой папке",
            "удали все документы за результаты инвентаризации в этой папке",
            "удали все документы за переинвентаризацию в этой папке",
            "удали все документы за инвентаризатора в этой папке",
            "удали все документы за инвентаризационную опись в этой папке",
            "удали все документы за текущее оспаривание",
            "удали все документы за текущую инвентаризацию",
            "удали все документы за открытую реституцию",
            "удали все документы за открытое оспаривание",
            "удали каждый документ за оспаривание в этой папке",
            "удали все файлы за реституцию в этой папке",
            "удали все документы дела А40-12345/2025 за оспаривание",
            "удали все документы дела А40-12345/2025 за реституцию",
            "удали все документы дела А40-12345/2025 за инвентаризацию",
            "удали все документы за Оспаривание в этой папке",
            "удали все документы во время оспаривания в этой папке",
            "удали все документы во время реституции в этой папке",
            "удали все документы за «оспаривание» в этой папке",
            "удали все документы за «договор оспаривания» в этой папке",
            "удали все документы за признание оспаривания в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(challenge_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за оспаривание в этой папке",
            "удали все документы за реституцию в этой папке",
            "удали все документы за инвентаризацию в этой папке",
            "удали все документы за текущее оспаривание",
            "удали все документы за текущую инвентаризацию",
            "удали все документы за открытую реституцию в этой папке",
            "удали все документы за открытое оспаривание",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й оспаривания",
            "удали документы 1-го оспаривания",
            "удали документы 1-й реституции",
            "удали документы 1-й инвентаризации",
            "удали документы 1-го инвентаризатора",
            "удали документы 2-й реституции",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(challenge_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оспаривания"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оспаривания"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оспариваний"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оспариваний"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 реституции"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 реституции"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 инвентаризации"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 инвентаризации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% оспаривания"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% оспаривания"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% реституции"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% реституции"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% инвентаризации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% инвентаризации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го оспаривания"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го оспаривания"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й реституции"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й реституции"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го инвентаризатора"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го инвентаризатора"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 оспаривания"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 оспаривания"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 оспаривания"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за оспаривание"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й поставки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го дарения"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за оспаривание в папку Архив",
            "перенеси все документы дела А40-12345/2025 за реституцию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за инвентаризацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за инвентаризатора в папку Архив",
            "перенеси все документы дела А40-12345/2025 за применение реституции в папку Архив",
            "перенеси документ 1-й оспаривания в дело Архив",
            "перемести документ 1-й инвентаризации в дело Архив",
        )
        for text in phrases:
            self.assertTrue(challenge_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за оспаривание в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_challenge_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 оспаривания в папку Архив"
        masked = mask_challenge_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            challenge_blocks_bulk_document_mutation(
                "удали документ 214 за оспаривание",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за оспаривание"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за реституцию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за инвентаризацию"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за оспаривание"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за оспаривание"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Оспаривание",
            "удали все документы в папке Реституция",
            "удали все документы в папке Инвентаризация",
            "удали все документы в папке «Оспаривание»",
            "удали все документы в папке «Инвентаризация имущества»",
            "удали все документы без оспаривания в этой папке",
            "удали все документы без реституции в этой папке",
            "удали все документы без инвентаризации в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за инвентарь в этой папке",
            "удали все документы в этой папке чтобы оспорить сделку",
            "удали все документы в этой папке, мы оспариваем сделку",
            "удали все документы, чтобы оспаривать сделку в этой папке",
            "перенеси все документы в папку Архив",
            "удали документ 214",
            "удали все документы за поставку в этой папке",
            "удали все документы за дарение в этой папке",
            "удали все документы за налог в этой папке",
        ):
            self.assertFalse(looks_like_challenge_scoped_document_request(text), text)
            self.assertFalse(challenge_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за оспаривание",
            "за оспаривания",
            "по оспариванию",
            "об оспаривании",
            "за оспариванием",
            "за оспариваний",
            "за оспариваемую сделку",
            "за оспариваемого должника",
            "за оспоренную сделку",
            "за оспоренный договор",
            "за неоспоренную сделку",
            "за оспоримую сделку",
            "за оспоримость",
            "за реституцию",
            "за реституции",
            "о реституции",
            "за реституцией",
            "за реституцию",
            "за реституционное требование",
            "за применение реституции",
            "за последствия реституции",
            "за инвентаризацию",
            "за инвентаризации",
            "по инвентаризации",
            "за инвентаризацией",
            "за инвентаризаций",
            "за инвентаризатора",
            "за инвентаризатору",
            "за инвентаризатором",
            "об инвентаризаторе",
            "за инвентаризаторы",
            "за инвентаризаторов",
            "за инвентаризационную опись",
            "за переинвентаризацию",
            "за результаты инвентаризации",
            "за сделку оспаривания",
            "за признание реституции",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_challenge_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("challenge_blocks_bulk_document_mutation", source)
        self.assertIn("mask_challenge_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("challenge_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_challenge_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_challenge_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("challenge_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
