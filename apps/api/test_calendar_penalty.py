"""«Штраф» / «неустойка» / «пеня» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го штрафа» as document id 1. The calendar-period parser does
not recognize these phrases. «Пена» (foam) and bare «санкции» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_penalty import (
    mask_penalty_ordinals,
    penalty_blocks_bulk_document_mutation,
    looks_like_penalty_scoped_document_request,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_penalty_ordinals(raw)
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


class PenaltyScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за штраф в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(penalty_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за штрафы в этой папке",
            "удали все документы по штрафу в этой папке",
            "удали все документы со штрафом в этой папке",
            "удали все документы о штрафе в этой папке",
            "удали все документы об штрафе в этой папке",
            "удали все документы из штрафа в этой папке",
            "удали все документы за административный штраф в этой папке",
            "удали все документы за штрафные санкции в этой папке",
            "удали все документы за неустойку в этой папке",
            "удали все документы за неустойки в этой папке",
            "удали все документы по неустойке в этой папке",
            "удали все документы с неустойкой в этой папке",
            "удали все документы о неустойке в этой папке",
            "удали все документы за договорную неустойку в этой папке",
            "удали все документы за законную неустойку в этой папке",
            "удали все документы за пеню в этой папке",
            "удали все документы за пени в этой папке",
            "удали все документы по пене в этой папке",
            "удали все документы с пеней в этой папке",
            "удали все документы о пенях в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(penalty_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за текущий штраф",
            "удали все документы за открытую неустойку",
            "удали все документы за открытую пеню",
        ):
            low = text.lower()
            self.assertIn("все документ", low)
            self.assertTrue("текущ" in low or "открыт" in low)
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertIsNone(parse_calendar_period_ru(text))
            self.assertTrue(penalty_blocks_bulk_document_mutation(text), text)

    def test_case_number_scope_would_wipe_that_case(self) -> None:
        text = "удали все документы за штраф дела А53-13969/2026"
        self.assertIn("все документ", text.lower())
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertTrue(penalty_blocks_bulk_document_mutation(text))
        self.assertTrue(
            penalty_blocks_bulk_document_mutation(
                "удали все документы за неустойку дела А40-12345/2025"
            )
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation(
                "удали все документы по неустойке дела А53-13969/2026"
            )
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation("удали все документы за пеню дела А40-12345/2025")
        )

    def test_ordinal_wrong_id_trigger(self) -> None:
        """Pre-fix: the leading ordinal digit was document id 1 and that file was hard-deleted."""
        samples = (
            "удали документы 1-го штрафа",
            "удали документы 1-й штраф",
            "удали документы 1-му штрафу",
            "удали документы 1-й неустойки",
            "удали документы 1-ю неустойку",
            "удали документы 1-й пени",
            "удали документы 1-ю пеню",
            "удали документы 1-е пени",
            "удали документы 2-го штрафа",
            "удали документы 2-й договорной неустойки",
        )
        for text in samples:
            expected = [2] if text.startswith("удали документы 2-") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(penalty_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за штраф в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(penalty_blocks_bulk_document_mutation(text))
        self.assertTrue(
            penalty_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за неустойку в папку Архив"
            )
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за пеню в папку Архив"
            )
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation(
                "перенеси все документы за штрафные санкции в папку Архив"
            )
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation("перенеси документ 1-го штрафа в дело Архив")
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation("перенеси документ 1-й неустойки в дело Архив")
        )
        self.assertTrue(
            penalty_blocks_bulk_document_mutation("перенеси документ 1-й пени в дело Архив")
        )

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text, noun in (
            ("перенеси документ 1-го штрафа в дело Архив", "штрафа"),
            ("перенеси документ 1-й неустойки в дело Архив", "неустойки"),
            ("перенеси документ 1-й пени в дело Архив", "пени"),
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_penalty_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], noun)
            self.assertEqual(post, [], noun)
        kept = "перенеси документ 214 за штраф в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_penalty_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            penalty_blocks_bulk_document_mutation(
                "удали документ 254 за штраф",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за штраф"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за неустойку"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за пеню"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за штраф"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за штраф в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за неустойку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за пеню"), [214])
        self.assertIn("214", mask_penalty_ordinals("удали документ 214 за штраф"))
        self.assertIn("12345", mask_penalty_ordinals(text))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без штрафа",
            "удали все документы в этой папке без неустойки",
            "удали все документы в этой папке без пени",
            "удали все документы в папке Штраф",
            "перенеси все документы в папку Неустойка",
            "удали все документы из папки Пеня",
            "удали все документы в папку Штраф",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за гарантию в этой папке",
            "удали все документы за письмо в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за ответ в этой папке",
            "удали все документы за полис в этой папке",
            "удали все документы за санкции в этой папке",
            "удали все документы за пену в этой папке",
            "удали все документы за пение в этой папке",
            "штрафовать удаление всех документов в этой папке",
            "оштрафовать за удаление всех документов в этой папке",
            "пенять на удаление всех документов в этой папке",
            "удали документы 1-го ответа",
            "удали документы 1-й гарантии",
            "удали документы 1-го договора",
        ):
            self.assertFalse(looks_like_penalty_scoped_document_request(text), text)
            self.assertFalse(penalty_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все штрафные документы в этой папке",
            "удали все документы штрафные в этой папке",
            "удали все документы за штрафные санкции в этой папке",
            "удали все документы во время штрафа в этой папке",
            "удали все документы во время неустойки в этой папке",
            "удали все документы за первый штраф в этой папке",
            "удали все документы за вторую неустойку в этой папке",
            "удали все документы за первую пеню в этой папке",
            "удали документы штрафа в этой папке",
            "удали документы неустойки в этой папке",
            "удали документы пени в этой папке",
        ):
            self.assertTrue(penalty_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("penalty_blocks_bulk_document_mutation", source)
        self.assertIn("mask_penalty_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("penalty_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_penalty_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_penalty_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("penalty_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
