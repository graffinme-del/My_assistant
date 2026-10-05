"""«Гарантия» / «поручительство» / «акцепт» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-й гарантии» as document id 1. The calendar-period parser does
not recognize these phrases, and the reply / letter guards do not match
«гарантия», «поручительство», or «акцепт». «Поручение» is not «поручительство».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_guarantee import (
    guarantee_blocks_bulk_document_mutation,
    looks_like_guarantee_scoped_document_request,
    mask_guarantee_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_guarantee_ordinals(raw)
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


class GuaranteeScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за гарантию в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(guarantee_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за гарантии в этой папке",
            "удали все документы по гарантии в этой папке",
            "удали все документы с гарантией в этой папке",
            "удали все документы с гарантиями в этой папке",
            "удали все документы о гарантии в этой папке",
            "удали все документы об гарантии в этой папке",
            "удали все документы из гарантии в этой папке",
            "удали все документы на гарантию в этой папке",
            "удали все документы за банковскую гарантию в этой папке",
            "удали все документы за независимую гарантию в этой папке",
            "удали все документы за гарантийное письмо в этой папке",
            "удали все документы за гарантийную записку в этой папке",
            "удали все документы за поручительство в этой папке",
            "удали все документы за поручительства в этой папке",
            "удали все документы по поручительству в этой папке",
            "удали все документы с поручительством в этой папке",
            "удали все документы о поручительстве в этой папке",
            "удали все документы за нотариальное поручительство в этой папке",
            "удали все документы за акцепт в этой папке",
            "удали все документы за акцепты в этой папке",
            "удали все документы по акцепту в этой папке",
            "удали все документы с акцептом в этой папке",
            "удали все документы об акцепте в этой папке",
            "удали все документы за безусловный акцепт в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(guarantee_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за текущую гарантию",
            "удали все документы за открытое поручительство",
            "удали все документы за открытый акцепт",
        ):
            low = text.lower()
            self.assertIn("все документ", low)
            self.assertTrue("текущ" in low or "открыт" in low)
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertIsNone(parse_calendar_period_ru(text))
            self.assertTrue(guarantee_blocks_bulk_document_mutation(text), text)

    def test_case_number_scope_would_wipe_that_case(self) -> None:
        text = "удали все документы за гарантию дела А53-13969/2026"
        self.assertIn("все документ", text.lower())
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertTrue(guarantee_blocks_bulk_document_mutation(text))
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "удали все документы за поручительство дела А40-12345/2025"
            )
        )
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "удали все документы за акцепт дела А40-12345/2025"
            )
        )

    def test_ordinal_wrong_id_trigger(self) -> None:
        """Pre-fix: the leading ordinal digit was document id 1 and that file was hard-deleted."""
        samples = (
            "удали документы 1-й гарантии",
            "удали документы 1-го гарантии",
            "удали документы 1-ю гарантию",
            "удали документы 1-го поручительства",
            "удали документы 1-е поручительство",
            "удали документы 1-го акцепта",
            "удали документы 1-й акцепт",
            "удали документы 1-го гарантийного письма",
            "удали документы 2-й гарантии",
            "удали документы 2-го банковского акцепта",
        )
        for text in samples:
            expected = [2] if text.startswith("удали документы 2-") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(guarantee_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за гарантию в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(guarantee_blocks_bulk_document_mutation(text))
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за поручительство в папку Архив"
            )
        )
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за акцепт в папку Архив"
            )
        )
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "перенеси все документы за гарантийное письмо в папку Архив"
            )
        )
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "перенеси документ 1-й гарантии в дело Архив"
            )
        )
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "перенеси документ 1-го поручительства в дело Архив"
            )
        )
        self.assertTrue(
            guarantee_blocks_bulk_document_mutation(
                "перенеси документ 1-го акцепта в дело Архив"
            )
        )

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text, noun in (
            ("перенеси документ 1-й гарантии в дело Архив", "гарантии"),
            ("перенеси документ 1-го поручительства в дело Архив", "поручительства"),
            ("перенеси документ 1-го акцепта в дело Архив", "акцепта"),
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_guarantee_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], noun)
            self.assertEqual(post, [], noun)
        kept = "перенеси документ 214 за гарантию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_guarantee_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            guarantee_blocks_bulk_document_mutation(
                "удали документ 254 за гарантию",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за гарантию"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за поручительство"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за акцепт"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за гарантию"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за гарантию в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за поручительство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за акцепт"), [214])
        self.assertIn("214", mask_guarantee_ordinals("удали документ 214 за гарантию"))
        self.assertIn("12345", mask_guarantee_ordinals(text))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без гарантии",
            "удали все документы в этой папке без поручительства",
            "удали все документы в этой папке без акцепта",
            "удали все документы в папке Гарантия",
            "перенеси все документы в папку Поручительство",
            "удали все документы из папки Акцепт",
            "удали все документы в папку Гарантия",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за ответ в этой папке",
            "удали все документы за письмо в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за запрос в этой папке",
            "удали все документы по поручению директора в этой папке",
            "удали все документы за поручение в этой папке",
            "гарантировать удаление всех документов в этой папке",
            "акцептовать удаление всех документов в этой папке",
            "удали документы 1-го ответа",
            "удали документы 1-го письма",
            "удали документы 1-го договора",
            "удали документы 1-го поручения",
        ):
            self.assertFalse(looks_like_guarantee_scoped_document_request(text), text)
            self.assertFalse(guarantee_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все гарантийные документы в этой папке",
            "удали все документы гарантийные в этой папке",
            "удали все поручительские документы в этой папке",
            "удали все акцептные документы в этой папке",
            "удали все документы за гарантийное письмо в этой папке",
            "удали все документы во время гарантии в этой папке",
            "удали все документы во время акцепта в этой папке",
            "удали все документы за первую гарантию в этой папке",
            "удали все документы за второе поручительство в этой папке",
            "удали документы гарантии в этой папке",
            "удали документы поручительства в этой папке",
            "удали документы акцепта в этой папке",
        ):
            self.assertTrue(guarantee_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("guarantee_blocks_bulk_document_mutation", source)
        self.assertIn("mask_guarantee_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("guarantee_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_guarantee_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_guarantee_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("guarantee_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
