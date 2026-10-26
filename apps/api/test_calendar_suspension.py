"""Suspension, termination, and mediation chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й приостановления» as document id 1. The calendar period parser does not
recognize these phrases.

A folder titled «Приостановление», «Прекращение», or «Медиация» is not this guard.
«без приостановления» is not this guard. Bare «банкротство» is not this guard.
«остановка» is not «приостановка». «прекрасно» and «прекратить» are not
«прекращение». «приостановить» is not «приостановление». «медиа» is not «медиация».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_suspension import (
    looks_like_suspension_scoped_document_request,
    mask_suspension_ordinals,
    suspension_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_suspension_ordinals(raw)
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


class SuspensionScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за приостановление в этой папке",
            "удали все документы по приостановлению в этой папке",
            "удали все документы о приостановлении в этой папке",
            "удали все документы за приостановку в этой папке",
            "удали все документы за приостановленное производство в этой папке",
            "удали все документы за приостановочные меры в этой папке",
            "удали все документы за прекращение в этой папке",
            "удали все документы о прекращении в этой папке",
            "удали все документы за прекращенное производство в этой папке",
            "удали все документы за медиацию в этой папке",
            "удали все документы по медиации в этой папке",
            "удали все документы об медиации в этой папке",
            "удали все документы за медиационное соглашение в этой папке",
            "удали все документы за медиативную процедуру в этой папке",
            "удали все документы за медиатора в этой папке",
            "удали все документы за срок приостановления в этой папке",
            "удали все документы в ходе прекращения в этой папке",
            "удали все документы в процессе медиации в этой папке",
            "удали все документы за меры приостановления в этой папке",
            "удали все документы на стадии медиации в этой папке",
            "удали все документы за производство прекращения в этой папке",
            "удали все документы при приостановлении в этой папке",
            "удали все документы за текущее приостановление",
            "удали все документы за текущее прекращение",
            "удали все документы за открытую медиацию",
            "удали все документы за открытое прекращение",
            "удали каждый документ за приостановление в этой папке",
            "удали все файлы за медиацию в этой папке",
            "удали все документы дела А40-12345/2025 за приостановление",
            "удали все документы дела А40-12345/2025 за прекращение",
            "удали все документы дела А40-12345/2025 за медиацию",
            "удали все документы за Приостановление в этой папке",
            "удали все документы во время приостановления в этой папке",
            "удали все документы во время медиации в этой папке",
            "удали все документы за «медиацию» в этой папке",
            "удали все документы за «договор медиации» в этой папке",
            "удали все документы за процедуру медиации в этой папке",
            "удали все документы за непрекращение в этой папке",
            "удали все документы за неприостановление в этой папке",
            "удали все документы за неприостановку в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(suspension_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за приостановление в этой папке",
            "удали все документы за прекращение в этой папке",
            "удали все документы за медиацию в этой папке",
            "удали все документы за текущее приостановление",
            "удали все документы за текущее прекращение",
            "удали все документы за открытую медиацию",
            "удали все документы за открытое прекращение",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й приостановления",
            "удали документы 1-го приостановления",
            "удали документы 1-й приостановки",
            "удали документы 1-й прекращения",
            "удали документы 1-й медиации",
            "удали документы 1-го медиатора",
            "удали документы 2-й медиации",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(suspension_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 приостановления"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 приостановления"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 прекращений"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 прекращений"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 медиации"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 медиации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% приостановления"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% приостановления"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% прекращения"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% прекращения"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% медиации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% медиации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го приостановления"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го приостановления"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й медиации"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й медиации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го медиатора"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го медиатора"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 приостановления"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 приостановления"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 приостановления"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за прекращение"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й поставки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го дарения"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й налога"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за приостановление в папку Архив",
            "перенеси все документы дела А40-12345/2025 за прекращение в папку Архив",
            "перенеси все документы дела А40-12345/2025 за медиацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за медиатора в папку Архив",
            "перенеси все документы дела А40-12345/2025 за приостановку в папку Архив",
            "перенеси документ 1-й приостановления в дело Архив",
            "перемести документ 1-й медиации в дело Архив",
        )
        for text in phrases:
            self.assertTrue(suspension_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за приостановление в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_suspension_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 приостановления в папку Архив"
        masked = mask_suspension_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            suspension_blocks_bulk_document_mutation(
                "удали документ 214 за приостановление",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за приостановление"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за прекращение"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за медиацию"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за приостановление"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за медиацию"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Приостановление",
            "удали все документы в папке Прекращение",
            "удали все документы в папке Медиация",
            "удали все документы в папке «Приостановление»",
            "удали все документы в папке «Медиация»",
            "удали все документы без приостановления в этой папке",
            "удали все документы без прекращения в этой папке",
            "удали все документы без медиации в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за сделку в этой папке",
            "удали все документы за налог в этой папке",
            "удали все документы за дарение в этой папке",
            "удали все документы за остановку в этой папке",
            "удали все документы при остановке в этой папке",
            "удали все документы за срок в этой папке",
            "удали все документы в ходе проверки в этой папке",
            "удали все документы за ходатайство в этой папке",
            "удали все документы за мероприятие в этой папке",
            "удали все документы за прекрасно составленный акт в этой папке",
            "удали все документы за прекратить производство в этой папке",
            "удали все документы за приостановить производство в этой папке",
            "удали все документы за приостанавливать производство в этой папке",
            "удали все документы за медиа в этой папке",
            "удали все документы за медиафайл в этой папке",
            "удали все документы за третейский суд в этой папке",
            "удали все документы за перевозку в этой папке",
            "удали все документы за оценщика в этой папке",
            "удали все документы за НДФЛ в этой папке",
            "удали все документы за производство в папке Приостановление",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Приостановление",
            "перенеси все документы в папку Медиация",
            "собери все документы в папку Прекращение",
            "удали документ 214",
            "удали все документы по делу Приостановление",
            "удали все документы по делу Медиация",
            "удали все документы по делу Прекращение",
        ):
            self.assertFalse(looks_like_suspension_scoped_document_request(text), text)
            self.assertFalse(suspension_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за приостановление",
            "за приостановления",
            "по приостановлению",
            "о приостановлении",
            "за приостановлением",
            "за приостановлениями",
            "за приостановку",
            "за приостановки",
            "по приостановке",
            "за приостановкой",
            "за приостановок",
            "за приостановленное производство",
            "за приостановленный договор",
            "за приостановочные меры",
            "за приостановочную меру",
            "за прекращение",
            "о прекращении",
            "по прекращению",
            "за прекращением",
            "за прекращений",
            "за прекращенное производство",
            "за прекращенный договор",
            "за медиацию",
            "по медиации",
            "о медиации",
            "за медиацией",
            "за медиаций",
            "за медиационное соглашение",
            "за медиационный сбор",
            "за медиативную процедуру",
            "за медиатора",
            "за медиатору",
            "за медиатором",
            "за медиаторов",
            "за медиаторский сбор",
            "за срок приостановления",
            "в ходе прекращения",
            "в процессе медиации",
            "на стадии медиации",
            "за меры приостановления",
            "за производство прекращения",
            "во время приостановления",
            "при приостановлении",
            "за непрекращение",
            "за неприостановление",
            "за неприостановку",
            "за непрекращенное производство",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_suspension_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("suspension_blocks_bulk_document_mutation", source)
        self.assertIn("mask_suspension_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("suspension_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_suspension_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_suspension_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("suspension_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
